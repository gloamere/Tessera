"""Inspect Codex Skills, lint eval contracts, and run evidence-bound native evals."""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterable


MIN_PYTHON = (3, 10)
PRODUCER_ID = "gloamere-skill-eval"
EVENT_ADAPTER_ID = "codex-exec-jsonl"
EVENT_ADAPTER_SCHEMA_VERSION = 1
REPORT_SCHEMA_VERSION = 4
SUITE_SCHEMA_VERSION = 2
SUPPORTED_SUITE_SCHEMA_VERSIONS = {1, 2}
TARGET_LOCK_SCHEMA_VERSION = 2
JOURNAL_SCHEMA_VERSION = 1
# 根因：native CLI 省略 --mode 时默认 exhaustive；修复要点：默认 release，完整覆盖保持显式 opt-in。
DEFAULT_NATIVE_MODE = "release"
RISK_POLICY_V2: dict[str, Any] = {
    "id": "risk-tiered-v2",
    "version": 2,
    "modes": {
        "pr": {
            "repeat": 1,
            "independent_batches": 1,
            "default_max_calls": 12,
            "selection": "up-to-4-sentinels-per-focus",
        },
        "release": {
            "repeat": 1,
            "independent_batches": 1,
            "default_max_calls": 40,
            "selection": {
                "fixed_positive_or_high_risk": 6,
                "rotating_adjacent_boundary": 6,
                "multi_intent": 4,
                "targeted_per_focus": 6,
                "maximum_cases": 34,
            },
        },
        "exhaustive": {
            "repeat": "suite",
            "independent_batches": "suite",
            "initial_calls": "planned",
            "default_max_calls": "planned+adaptive",
            "selection": "all-selected-cases",
        },
    },
    "retry": {
        "unexpected_attempts": 3,
        "confirmed_failure_count": 2,
        "infrastructure_retry_count": 1,
        "single_failure_outcome": "pending",
        "budget_exhausted_outcome": "pending",
    },
}

SKILL_ROOT = Path(__file__).resolve().parents[1]
REFERENCES = SKILL_ROOT / "references"
SCHEMAS = REFERENCES / "schemas"
NATIVE_OUTPUT_SCHEMA = SCHEMAS / "native-invocation-output.schema.json"

KNOWN_EVENT_TYPES = {
    "thread.started",
    "turn.started",
    "turn.completed",
    "turn.failed",
    "item.started",
    "item.updated",
    "item.completed",
    "error",
}
KNOWN_ITEM_TYPES = {
    "agent_message",
    "reasoning",
    "command_execution",
    "file_change",
    "mcp_tool_call",
    "web_search",
    "plan_update",
    "todo_list",
}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class HostResult:
    payload: dict[str, Any] | None
    event_stream: str
    duration_ms: int
    error: str | None = None
    codex_version: str | None = None
    failure_kind: str | None = None


@dataclass(frozen=True)
class EventEvidence:
    observed_target_ids: tuple[str, ...]
    unbound_skill_names: tuple[str, ...]
    complete: bool
    malformed_lines: int
    unknown_event_types: tuple[str, ...]
    unknown_item_types: tuple[str, ...]
    terminal_event: str | None
    usage: dict[str, int] | None
    event_count: int
    rejected_target_references: tuple[str, ...]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_object(value: Any) -> str:
    return sha256_text(canonical_json(value))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_or_print(value: Any, output: Path | None) -> None:
    rendered = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if output is not None:
        destination = output.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)


def parse_iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def repository_commit() -> str:
    override = os.environ.get("GLOAMERE_EVAL_COMMIT")
    if override:
        return override
    repository_root = next(
        (
            candidate
            for candidate in (SKILL_ROOT, *SKILL_ROOT.parents)
            if (candidate / ".git").exists()
        ),
        SKILL_ROOT,
    )
    try:
        completed = subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={repository_root.as_posix()}",
                "rev-parse",
                "HEAD",
            ],
            cwd=repository_root,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    value = completed.stdout.strip()
    return value if re.fullmatch(r"[0-9a-fA-F]{40,64}", value) else "unavailable"


def append_journal_record(path: Path, record: dict[str, Any]) -> None:
    destination = path.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = (canonical_json(record) + "\n").encode("utf-8")
    descriptor = os.open(
        destination,
        os.O_APPEND | os.O_CREAT | os.O_WRONLY,
        0o600,
    )
    try:
        # 根因：只在整轮结束后写报告时，中断会丢失数小时结果；每次调用只追加
        # 一条完整 JSONL 并 fsync，使 resume 最多重跑正在执行的那一个单元。
        written = os.write(descriptor, encoded)
        if written != len(encoded):
            raise OSError("journal append was incomplete")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path}: missing YAML frontmatter")
    result: dict[str, str] = {}
    closed = False
    for line in lines[1:]:
        if line.strip() == "---":
            closed = True
            break
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        key = key.strip()
        if key in {"name", "description"}:
            result[key] = raw.strip().strip("\"'")
    if not closed:
        raise ValueError(f"{path}: unterminated YAML frontmatter")
    if not result.get("name"):
        raise ValueError(f"{path}: frontmatter is missing name")
    if not result.get("description"):
        raise ValueError(f"{path}: frontmatter is missing description")
    return result


def plugin_manifest(plugin_root: Path) -> tuple[Path, dict[str, Any]]:
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    if not manifest_path.is_file():
        raise ValueError(f"{plugin_root}: missing .codex-plugin/plugin.json")
    manifest = read_json(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError(f"{manifest_path}: manifest must be an object")
    if not isinstance(manifest.get("name"), str) or not manifest["name"]:
        raise ValueError(f"{manifest_path}: manifest is missing name")
    if not isinstance(manifest.get("version"), str) or not manifest["version"]:
        raise ValueError(f"{manifest_path}: manifest is missing version")
    return manifest_path, manifest


def catalog_entries(catalog: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(catalog, dict):
        return []
    installed = catalog.get("installed")
    if not isinstance(installed, list):
        return []
    return [item for item in installed if isinstance(item, dict)]


def catalog_source_path(entry: dict[str, Any]) -> Path | None:
    source = entry.get("source")
    if not isinstance(source, dict) or not isinstance(source.get("path"), str):
        return None
    try:
        return Path(source["path"]).resolve()
    except OSError:
        return None


def catalog_binding(
    root: Path,
    plugin_id: str,
    plugin_version: str,
    catalog: dict[str, Any] | None,
) -> tuple[bool | None, bool | None, str | None, list[dict[str, Any]]]:
    if catalog is None:
        return None, None, None, []
    entries = catalog_entries(catalog)
    named = [
        item
        for item in entries
        if item.get("name") == plugin_id
        or str(item.get("pluginId", "")).split("@", 1)[0] == plugin_id
    ]
    exact = [item for item in entries if catalog_source_path(item) == root]
    conflicts: list[dict[str, Any]] = []
    if len(named) > 1:
        identities = {
            (
                str(item.get("pluginId")),
                str(item.get("version")),
                str(catalog_source_path(item)),
            )
            for item in named
        }
        if len(identities) > 1:
            conflicts.append(
                {
                    "kind": "multiple-installed-identities",
                    "plugin_id": plugin_id,
                    "installed_identities": [
                        {
                            "plugin_selector": selector,
                            "plugin_version": version,
                            "plugin_root": path,
                        }
                        for selector, version, path in sorted(identities)
                    ],
                }
            )
    if len(exact) != 1:
        if named:
            conflicts.append(
                {
                    "kind": "installation-path-mismatch",
                    "plugin_id": plugin_id,
                    "requested_root": str(root),
                    "installed_roots": sorted(
                        str(path)
                        for item in named
                        if (path := catalog_source_path(item)) is not None
                    ),
                }
            )
        return False, False, None, conflicts

    match = exact[0]
    selector = (
        match.get("pluginId")
        if isinstance(match.get("pluginId"), str)
        else None
    )
    if (
        match.get("name") != plugin_id
        or match.get("version") != plugin_version
    ):
        conflicts.append(
            {
                "kind": "installation-identity-mismatch",
                "plugin_id": plugin_id,
                "requested_version": plugin_version,
                "installed_plugin_id": match.get("name"),
                "installed_version": match.get("version"),
                "plugin_root": str(root),
            }
        )
    installed = match.get("installed")
    enabled = match.get("enabled")
    return (
        installed if isinstance(installed, bool) else None,
        enabled if isinstance(enabled, bool) else None,
        selector,
        conflicts,
    )


def build_conflicts(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    by_name: dict[str, list[dict[str, Any]]] = {}
    by_id: dict[str, list[dict[str, Any]]] = {}
    for target in targets:
        if not all(
            isinstance(target.get(field), str) and target[field]
            for field in ("skill_name", "target_id", "plugin_id", "skill_path")
        ):
            continue
        by_name.setdefault(target["skill_name"], []).append(target)
        by_id.setdefault(target["target_id"], []).append(target)
    for skill_name, matches in sorted(by_name.items()):
        unique_plugins = {item["plugin_id"] for item in matches}
        unique_paths = {item["skill_path"] for item in matches}
        if len(unique_plugins) > 1 or len(unique_paths) > 1:
            conflicts.append(
                {
                    "kind": "duplicate-skill-name",
                    "skill_name": skill_name,
                    "target_ids": sorted(item["target_id"] for item in matches),
                    "plugin_ids": sorted(unique_plugins),
                }
            )
    for target_id, matches in sorted(by_id.items()):
        if len({item["skill_path"] for item in matches}) > 1:
            conflicts.append(
                {
                    "kind": "duplicate-target-id",
                    "target_id": target_id,
                    "paths": sorted(item["skill_path"] for item in matches),
                }
            )
    return conflicts


def inspect_plugins(
    plugin_roots: Iterable[Path],
    marketplace: str | None = None,
    catalog: dict[str, Any] | None = None,
    catalog_source: str = "unavailable",
    catalog_error: str | None = None,
    catalog_codex_version: str | None = None,
) -> dict[str, Any]:
    targets: list[dict[str, Any]] = []
    errors: list[str] = []
    installation_conflicts: list[dict[str, Any]] = []
    seen_roots: set[Path] = set()
    for requested_root in plugin_roots:
        root = requested_root.resolve()
        if root in seen_roots:
            continue
        seen_roots.add(root)
        try:
            manifest_path, manifest = plugin_manifest(root)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(str(exc))
            continue
        plugin_id = manifest["name"]
        plugin_version = manifest["version"]
        manifest_sha256 = sha256_file(manifest_path)
        installed, enabled, discovered_selector, root_conflicts = catalog_binding(
            root,
            plugin_id,
            plugin_version,
            catalog,
        )
        requested_selector = (
            f"{plugin_id}@{marketplace}" if marketplace else discovered_selector
        )
        if (
            marketplace
            and discovered_selector is not None
            and requested_selector != discovered_selector
        ):
            root_conflicts.append(
                {
                    "kind": "plugin-selector-mismatch",
                    "plugin_id": plugin_id,
                    "requested_selector": requested_selector,
                    "installed_selector": discovered_selector,
                }
            )
        skill_paths = sorted((root / "skills").glob("*/SKILL.md"))
        if not skill_paths:
            errors.append(f"{root}: no skills/*/SKILL.md files found")
            continue
        for skill_path in skill_paths:
            try:
                frontmatter = parse_frontmatter(skill_path)
                relative_path = skill_path.relative_to(root).as_posix()
                agent_config_path = skill_path.parent / "agents" / "openai.yaml"
                if not agent_config_path.is_file():
                    raise ValueError(
                        f"{agent_config_path}: missing routing policy metadata"
                    )
                agent_config_relative_path = agent_config_path.relative_to(
                    root
                ).as_posix()
                skill_name = frontmatter["name"]
                targets.append(
                    {
                        "target_id": f"{plugin_id}:{skill_name}",
                        "plugin_id": plugin_id,
                        "plugin_selector": requested_selector,
                        "plugin_version": plugin_version,
                        "installed": installed,
                        "enabled": enabled,
                        "plugin_root": str(root),
                        "plugin_manifest_path": str(manifest_path.resolve()),
                        "plugin_manifest_sha256": manifest_sha256,
                        "skill_name": skill_name,
                        "skill_path": str(skill_path.resolve()),
                        "relative_path": relative_path,
                        "sha256": sha256_file(skill_path),
                        "agent_config_path": str(agent_config_path.resolve()),
                        "agent_config_relative_path": agent_config_relative_path,
                        "agent_config_sha256": sha256_file(agent_config_path),
                    }
                )
            except (OSError, ValueError) as exc:
                errors.append(str(exc))
        target_ids = [
            item["target_id"]
            for item in targets
            if item["plugin_root"] == str(root)
        ]
        for conflict in root_conflicts:
            installation_conflicts.append(
                {
                    **conflict,
                    "target_ids": sorted(target_ids),
                }
            )
    targets.sort(key=lambda item: (item["target_id"], item["skill_path"]))
    conflicts = [
        *build_conflicts(targets),
        *sorted(
            installation_conflicts,
            key=lambda item: (str(item.get("kind")), str(item.get("plugin_id"))),
        ),
    ]
    return {
        "schema_version": TARGET_LOCK_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "catalog": {
            "observable": catalog is not None,
            "source": catalog_source,
            "codex_version": catalog_codex_version,
            "error": catalog_error,
        },
        "targets": targets,
        "conflicts": conflicts,
        "errors": errors,
    }


def validate_suite(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["eval suite must be an object"]
    if value.get("schema_version") not in SUPPORTED_SUITE_SCHEMA_VERSIONS:
        errors.append(
            "eval suite schema_version must be one of "
            + ", ".join(str(item) for item in sorted(SUPPORTED_SUITE_SCHEMA_VERSIONS))
        )
    if not isinstance(value.get("suite_id"), str) or not value["suite_id"]:
        errors.append("eval suite is missing suite_id")
    if not isinstance(value.get("description"), str) or not value["description"]:
        errors.append("eval suite is missing description")
    plugin_id = value.get("plugin_id")
    if not isinstance(plugin_id, str) or not plugin_id:
        errors.append("eval suite is missing plugin_id")
    execution_policy = value.get("execution_policy")
    if not isinstance(execution_policy, dict):
        errors.append("eval suite is missing execution_policy")
    else:
        if (
            value.get("schema_version") == 2
            and execution_policy.get("policy_id") != RISK_POLICY_V2["id"]
        ):
            errors.append(
                f"eval suite execution_policy.policy_id must be "
                f"{RISK_POLICY_V2['id']}"
            )
        for field in ("repeat", "independent_batches"):
            amount = execution_policy.get(field)
            if (
                not isinstance(amount, int)
                or isinstance(amount, bool)
                or not 1 <= amount <= 10
            ):
                errors.append(
                    f"eval suite execution_policy.{field} must be from 1 to 10"
                )
    cases = value.get("cases")
    if not isinstance(cases, list) or not cases:
        errors.append("eval suite cases must be a non-empty array")
        cases = []
    case_ids: set[str] = set()
    for index, case in enumerate(cases):
        prefix = f"eval suite cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{prefix} must be an object")
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id:
            errors.append(f"{prefix} is missing id")
        elif case_id in case_ids:
            errors.append(f"eval suite case id is duplicated: {case_id}")
        else:
            case_ids.add(case_id)
        case_plugin_id = case.get("plugin_id")
        if not isinstance(case_plugin_id, str) or not case_plugin_id:
            errors.append(f"{prefix} is missing plugin_id")
        elif isinstance(plugin_id, str) and case_plugin_id != plugin_id:
            errors.append(f"{prefix}.plugin_id does not match suite plugin_id")
        if not isinstance(case.get("prompt"), str) or not case["prompt"].strip():
            errors.append(f"{prefix} is missing prompt")
        if not isinstance(case.get("language"), str) or not case["language"]:
            errors.append(f"{prefix} is missing language")
        tags = case.get("tags")
        if (
            not isinstance(tags, list)
            or not tags
            or any(not isinstance(item, str) or not item for item in tags)
            or len(tags) != len(set(tags))
        ):
            errors.append(f"{prefix}.tags must be a non-empty unique string array")
        for field in ("expected_skills", "forbidden_skills"):
            if field not in case:
                errors.append(f"{prefix} is missing {field}")
                continue
            selected = case.get(field)
            if not isinstance(selected, list) or any(
                not isinstance(item, str) for item in selected
            ):
                errors.append(f"{prefix}.{field} must be a string array")
                continue
            if len(selected) != len(set(selected)):
                errors.append(f"{prefix}.{field} contains duplicate Skills")
            invalid = sorted(
                item
                for item in selected
                if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", item)
            )
            if invalid:
                errors.append(
                    f"{prefix}.{field} contains invalid Skill IDs: {', '.join(invalid)}"
                )
        expected = case.get("expected_skills", [])
        excluded = case.get("forbidden_skills", [])
        if not isinstance(expected, list) or any(
            not isinstance(item, str) for item in expected
        ):
            expected = []
        if not isinstance(excluded, list) or any(
            not isinstance(item, str) for item in excluded
        ):
            excluded = []
        if not expected and not excluded:
            errors.append(
                f"{prefix} must declare at least one expected or forbidden Skill"
            )
        overlap = sorted(set(expected).intersection(excluded))
        if overlap:
            errors.append(
                f"{prefix} expects and forbids the same Skills: {', '.join(overlap)}"
            )
    return errors


def validate_target_lock(value: Any, verify_files: bool = True) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["target lock must be an object"]
    if value.get("schema_version") != TARGET_LOCK_SCHEMA_VERSION:
        errors.append(
            f"target lock schema_version must be {TARGET_LOCK_SCHEMA_VERSION}"
        )
    catalog = value.get("catalog")
    if not isinstance(catalog, dict) or not isinstance(
        catalog.get("observable"), bool
    ):
        errors.append("target lock catalog observation is missing")
    targets = value.get("targets")
    if not isinstance(targets, list) or not targets:
        errors.append("target lock targets must be a non-empty array")
        targets = []
    for index, target in enumerate(targets):
        prefix = f"target lock targets[{index}]"
        if not isinstance(target, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in (
            "target_id",
            "plugin_id",
            "plugin_version",
            "plugin_root",
            "plugin_manifest_path",
            "plugin_manifest_sha256",
            "skill_name",
            "skill_path",
            "relative_path",
            "sha256",
            "agent_config_path",
            "agent_config_relative_path",
            "agent_config_sha256",
        ):
            if not isinstance(target.get(field), str) or not target[field]:
                errors.append(f"{prefix} is missing {field}")
        for digest_field in (
            "plugin_manifest_sha256",
            "sha256",
            "agent_config_sha256",
        ):
            digest = target.get(digest_field)
            if isinstance(digest, str) and not SHA256_PATTERN.fullmatch(digest):
                errors.append(
                    f"{prefix}.{digest_field} must be a lowercase SHA-256 digest"
                )
        target_id = target.get("target_id")
        plugin_id = target.get("plugin_id")
        skill_name = target.get("skill_name")
        if (
            isinstance(target_id, str)
            and isinstance(plugin_id, str)
            and isinstance(skill_name, str)
            and target_id != f"{plugin_id}:{skill_name}"
        ):
            errors.append(
                f"{prefix}.target_id must equal <plugin_id>:<skill_name>"
            )
        selector = target.get("plugin_selector")
        if selector is not None and not isinstance(selector, str):
            errors.append(f"{prefix}.plugin_selector must be a string or null")
        if (
            isinstance(selector, str)
            and isinstance(plugin_id, str)
            and not selector.startswith(f"{plugin_id}@")
        ):
            errors.append(f"{prefix}.plugin_selector does not match plugin_id")
        for field in ("installed", "enabled"):
            if target.get(field) is not None and not isinstance(
                target.get(field), bool
            ):
                errors.append(f"{prefix}.{field} must be boolean or null")
        if not verify_files:
            continue
        try:
            skill_path = Path(target["skill_path"]).resolve()
            plugin_root = Path(target["plugin_root"]).resolve()
            manifest_path = Path(target["plugin_manifest_path"]).resolve()
            agent_config_path = Path(target["agent_config_path"]).resolve()
            if not skill_path.is_file():
                errors.append(f"{prefix} skill_path does not exist: {skill_path}")
                continue
            if not manifest_path.is_file():
                errors.append(
                    f"{prefix} plugin_manifest_path does not exist: {manifest_path}"
                )
                continue
            if not agent_config_path.is_file():
                errors.append(
                    f"{prefix} agent_config_path does not exist: "
                    f"{agent_config_path}"
                )
                continue
            if plugin_root not in skill_path.parents:
                errors.append(f"{prefix} skill_path is outside plugin_root")
            if plugin_root not in agent_config_path.parents:
                errors.append(f"{prefix} agent_config_path is outside plugin_root")
            expected_manifest = (
                plugin_root / ".codex-plugin" / "plugin.json"
            ).resolve()
            if manifest_path != expected_manifest:
                errors.append(
                    f"{prefix} plugin_manifest_path does not match plugin_root"
                )
            expected_relative = skill_path.relative_to(plugin_root).as_posix()
            if expected_relative != target.get("relative_path"):
                errors.append(f"{prefix} relative_path does not match skill_path")
            expected_agent_config = (
                skill_path.parent / "agents" / "openai.yaml"
            ).resolve()
            if agent_config_path != expected_agent_config:
                errors.append(
                    f"{prefix} agent_config_path does not match skill_path"
                )
            expected_agent_relative = agent_config_path.relative_to(
                plugin_root
            ).as_posix()
            if expected_agent_relative != target.get("agent_config_relative_path"):
                errors.append(
                    f"{prefix} agent_config_relative_path does not match "
                    "agent_config_path"
                )
            actual_digest = sha256_file(skill_path)
            if actual_digest != target.get("sha256"):
                errors.append(f"{prefix} SHA-256 does not match skill contents")
            manifest_digest = sha256_file(manifest_path)
            if manifest_digest != target.get("plugin_manifest_sha256"):
                errors.append(
                    f"{prefix} plugin manifest SHA-256 does not match contents"
                )
            agent_config_digest = sha256_file(agent_config_path)
            if agent_config_digest != target.get("agent_config_sha256"):
                errors.append(
                    f"{prefix} agent config SHA-256 does not match contents"
                )
            frontmatter = parse_frontmatter(skill_path)
            if frontmatter["name"] != target.get("skill_name"):
                errors.append(f"{prefix} skill_name does not match frontmatter")
            manifest = read_json(manifest_path)
            if manifest.get("name") != target.get("plugin_id"):
                errors.append(f"{prefix} plugin_id does not match manifest")
            if manifest.get("version") != target.get("plugin_version"):
                errors.append(f"{prefix} plugin_version does not match manifest")
        except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{prefix} cannot be verified: {exc}")
    conflicts = build_conflicts(
        [target for target in targets if isinstance(target, dict)]
    )
    declared_conflicts = value.get("conflicts", [])
    if not isinstance(declared_conflicts, list):
        errors.append("target lock conflicts must be an array")
        declared_conflicts = []
    declared_duplicate_conflicts = [
        item
        for item in declared_conflicts
        if isinstance(item, dict)
        and item.get("kind") in {"duplicate-skill-name", "duplicate-target-id"}
    ]
    if declared_duplicate_conflicts != conflicts:
        errors.append("target lock conflicts do not match the locked targets")
    lock_errors = value.get("errors", [])
    if lock_errors:
        errors.append("target lock contains inspection errors")
    return errors


def validate_suite_binding(
    suite: dict[str, Any],
    target_lock: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    locked_targets = target_lock.get("targets", [])
    if not isinstance(locked_targets, list):
        locked_targets = []
    locked = {
        item["target_id"]: item
        for item in locked_targets
        if isinstance(item, dict) and isinstance(item.get("target_id"), str)
    }
    suite_names: set[str] = set()
    scoped_target_ids: set[str] = set()
    cases = suite.get("cases", [])
    if not isinstance(cases, list):
        cases = []
    for case in cases:
        if not isinstance(case, dict):
            continue
        plugin_id = case.get("plugin_id")
        if not isinstance(plugin_id, str):
            continue
        for field in ("expected_skills", "forbidden_skills"):
            references = case.get(field, [])
            if not isinstance(references, list):
                continue
            for skill_name in references:
                if not isinstance(skill_name, str):
                    continue
                suite_names.add(skill_name)
                target_id = f"{plugin_id}:{skill_name}"
                scoped_target_ids.add(target_id)
                match = locked.get(target_id)
                if match is None:
                    errors.append(
                        f"suite Skill is missing from target lock: {target_id}"
                    )
                elif (
                    match.get("plugin_id") != plugin_id
                    or match.get("skill_name") != skill_name
                ):
                    errors.append(
                        f"suite Skill identity does not match target lock: {target_id}"
                    )
    conflicts = target_lock.get("conflicts", [])
    if not isinstance(conflicts, list):
        conflicts = []
    for conflict in conflicts:
        if not isinstance(conflict, dict):
            continue
        if (
            conflict.get("kind") == "duplicate-skill-name"
            and conflict.get("skill_name") in suite_names
        ):
            errors.append(
                f"same-name target conflict is in evaluation scope: "
                f"{conflict.get('skill_name')}"
            )
        conflict_target_ids = conflict.get("target_ids", [])
        if (
            isinstance(conflict_target_ids, list)
            and scoped_target_ids.intersection(
                item for item in conflict_target_ids if isinstance(item, str)
            )
            and conflict.get("kind") != "duplicate-skill-name"
        ):
            errors.append(
                f"target installation identity conflict is in evaluation scope: "
                f"{conflict.get('kind')}"
            )
    return errors


def suite_target_ids(suite: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for case in suite.get("cases", []):
        if not isinstance(case, dict) or not isinstance(
            case.get("plugin_id"), str
        ):
            continue
        for field in ("expected_skills", "forbidden_skills"):
            for skill_name in case.get(field, []):
                if isinstance(skill_name, str):
                    result.add(f"{case['plugin_id']}:{skill_name}")
    return result


def assess_native_preflight(
    suite: dict[str, Any],
    target_lock: dict[str, Any],
    catalog: dict[str, Any] | None,
) -> tuple[str, list[str]]:
    identity_errors = [
        *validate_target_lock(target_lock, verify_files=True),
        *validate_suite_binding(suite, target_lock),
    ]
    for target in target_lock.get("targets", []):
        if not isinstance(target, dict):
            continue
        for field in (
            "plugin_root",
            "plugin_manifest_path",
            "skill_path",
            "agent_config_path",
        ):
            path_value = target.get(field)
            if not isinstance(path_value, str):
                continue
            identity_errors = [
                item.replace(path_value, f"<redacted-{field}>")
                for item in identity_errors
            ]
    if identity_errors:
        return "identity_conflict", sorted(set(identity_errors))
    if catalog is None:
        return "unavailable", ["Codex plugin catalog is unavailable"]

    scoped_ids = suite_target_ids(suite)
    unavailable: list[str] = []
    for target in target_lock.get("targets", []):
        if (
            not isinstance(target, dict)
            or target.get("target_id") not in scoped_ids
        ):
            continue
        root = Path(target["plugin_root"]).resolve()
        installed, enabled, selector, conflicts = catalog_binding(
            root,
            target["plugin_id"],
            target["plugin_version"],
            catalog,
        )
        if conflicts:
            identity_errors.extend(
                f"{target['target_id']}: {item.get('kind')}" for item in conflicts
            )
        if installed != target.get("installed"):
            identity_errors.append(
                f"{target['target_id']}: installed state differs from target lock"
            )
        if enabled != target.get("enabled"):
            identity_errors.append(
                f"{target['target_id']}: enabled state differs from target lock"
            )
        locked_selector = target.get("plugin_selector")
        if selector != locked_selector:
            identity_errors.append(
                f"{target['target_id']}: plugin selector differs from target lock"
            )
        if installed is not True:
            unavailable.append(f"{target['target_id']}: plugin is not installed")
        elif enabled is not True:
            unavailable.append(f"{target['target_id']}: plugin is not enabled")
    if identity_errors:
        return "identity_conflict", sorted(set(identity_errors))
    if unavailable:
        return "unavailable", sorted(set(unavailable))
    return "verified", []


def normalize_path(value: str) -> str:
    normalized = value.replace("\\\\", "\\").replace("\\", "/")
    return normalized.casefold() if os.name == "nt" else normalized


READ_COMMAND_PATTERN = re.compile(
    r"""
    ^\s*(?:&\s*)?
    (?:
        (?:\$\w+\s*=\s*)?(?:get-content|gc|cat|type)\b
        | cmd(?:\.exe)?\s+/[ck]\s+type\b
        | (?:powershell|pwsh)(?:\.exe)?\b.*\bget-content\b
        | (?:bash|sh|zsh)\b.*\bcat\b
        | /(?:usr/)?bin/cat\b
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def path_reference_index(command: str, path: str) -> int | None:
    normalized_command = normalize_path(command)
    normalized_path = normalize_path(path)
    pattern = re.compile(
        rf"(?<![a-z0-9_.:/-]){re.escape(normalized_path)}"
        r"(?![a-z0-9_.:/-])",
        re.IGNORECASE if os.name == "nt" else 0,
    )
    match = pattern.search(normalized_command)
    return match.start() if match else None


def command_reads_path(command: str, path: str) -> bool:
    normalized_command = normalize_path(command)
    reference_index = path_reference_index(command, path)
    if reference_index is None:
        return False
    separators = list(
        re.finditer(r"(?:&&|\|\||[;\r\n])", normalized_command[:reference_index])
    )
    segment_start = separators[-1].end() if separators else 0
    segment = normalized_command[segment_start:reference_index]
    return READ_COMMAND_PATTERN.search(segment) is not None


def normalized_output(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def command_output(item: dict[str, Any]) -> str | None:
    for field in ("aggregated_output", "output"):
        value = item.get(field)
        if isinstance(value, str):
            return value
    return None


def output_proves_target(item: dict[str, Any], target: dict[str, Any]) -> bool:
    output = command_output(item)
    if output is None:
        return False
    try:
        expected = Path(target["skill_path"]).read_text(encoding="utf-8")
    except (KeyError, OSError, UnicodeError):
        return False
    expected_normalized = normalized_output(expected).rstrip("\n")
    return bool(expected_normalized) and expected_normalized in normalized_output(output)


def targets_from_command(
    command: str,
    targets: list[dict[str, Any]],
    suite_skill_names: set[str],
) -> tuple[set[str], set[str]]:
    observed: set[str] = set()
    for target in targets:
        target_path = str(Path(target["skill_path"]).resolve())
        if path_reference_index(command, target_path) is not None:
            observed.add(target["target_id"])
    unbound: set[str] = set()
    normalized_command = normalize_path(command)
    for skill_name in suite_skill_names:
        skill_marker = normalize_path(f"/skills/{skill_name}/SKILL.md")
        if skill_marker not in normalized_command:
            continue
        matched_ids = {
            target["target_id"]
            for target in targets
            if target["skill_name"] == skill_name
            and normalize_path(str(Path(target["skill_path"]).resolve()))
            in normalized_command
        }
        if not matched_ids:
            unbound.add(skill_name)
    return observed, unbound


def parse_codex_events(
    text: str,
    target_lock: dict[str, Any],
    suite: dict[str, Any],
) -> EventEvidence:
    targets = [
        item for item in target_lock.get("targets", []) if isinstance(item, dict)
    ]
    suite_skill_names = {
        skill_name
        for case in suite.get("cases", [])
        if isinstance(case, dict)
        for field in ("expected_skills", "forbidden_skills")
        for skill_name in case.get(field, [])
        if isinstance(skill_name, str)
    }
    observed: set[str] = set()
    unbound: set[str] = set()
    malformed = 0
    unknown_events: set[str] = set()
    unknown_items: set[str] = set()
    event_types: list[str] = []
    usage: dict[str, int] | None = None
    thread_started_count = 0
    turn_started_count = 0
    terminal_event: str | None = None
    terminal_index: int | None = None
    terminal_count = 0
    event_count = 0
    item_states: dict[str, dict[str, Any]] = {}

    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            malformed += 1
            continue
        event_count += 1
        event_type = event["type"]
        event_types.append(event_type)
        if event_type not in KNOWN_EVENT_TYPES:
            unknown_events.add(event_type)
            continue
        if event_type == "thread.started":
            thread_started_count += 1
        elif event_type == "turn.started":
            turn_started_count += 1
        elif event_type in {"turn.completed", "turn.failed", "error"}:
            terminal_event = event_type
            terminal_index = len(event_types) - 1
            terminal_count += 1
            if event_type == "turn.completed" and isinstance(
                event.get("usage"), dict
            ):
                usage = {
                    key: int(value)
                    for key, value in event["usage"].items()
                    if isinstance(value, int)
                }
        if not event_type.startswith("item."):
            continue
        item = event.get("item")
        if not isinstance(item, dict):
            malformed += 1
            continue
        item_type = item.get("type")
        if not isinstance(item_type, str):
            malformed += 1
            continue
        if item_type not in KNOWN_ITEM_TYPES:
            unknown_items.add(item_type)
        item_id = item.get("id")
        state_key = (
            item_id
            if isinstance(item_id, str) and item_id
            else f"anonymous-item-{event_count}"
        )
        state = item_states.setdefault(
            state_key,
            {
                "item": {},
                "commands": [],
                "event_type": event_type,
            },
        )
        state["item"].update(item)
        state["event_type"] = event_type
        if isinstance(item.get("command"), str):
            state["commands"].append(item["command"])

    rejected_target_references: set[str] = set()
    for state in item_states.values():
        merged_item = state["item"]
        commands = state["commands"]
        if not commands:
            continue
        referenced_ids: set[str] = set()
        referenced_unbound: set[str] = set()
        for command in commands:
            matched, unmatched = targets_from_command(
                command, targets, suite_skill_names
            )
            referenced_ids.update(matched)
            referenced_unbound.update(unmatched)
        if not referenced_ids and not referenced_unbound:
            continue
        final_command = merged_item.get("command")
        successful_completion = (
            state["event_type"] == "item.completed"
            and merged_item.get("type") == "command_execution"
            and merged_item.get("status") == "completed"
            and merged_item.get("exit_code") == 0
            and isinstance(final_command, str)
        )
        if not successful_completion:
            rejected_target_references.update(referenced_ids)
            rejected_target_references.update(referenced_unbound)
            continue
        output = command_output(merged_item)
        for target in targets:
            target_id = target.get("target_id")
            if target_id not in referenced_ids:
                continue
            target_path = str(Path(target["skill_path"]).resolve())
            if command_reads_path(final_command, target_path) and output_proves_target(
                merged_item, target
            ):
                observed.add(target_id)
            else:
                rejected_target_references.add(target_id)
        normalized_command = normalize_path(final_command)
        for skill_name in referenced_unbound:
            marker = normalize_path(f"/skills/{skill_name}/SKILL.md")
            if (
                marker in normalized_command
                and READ_COMMAND_PATTERN.search(normalized_command) is not None
                and isinstance(output, str)
                and bool(output.strip())
            ):
                unbound.add(skill_name)
            else:
                rejected_target_references.add(skill_name)

    terminal_is_last = (
        terminal_index is not None and terminal_index == len(event_types) - 1
    )
    complete = (
        event_count > 0
        and thread_started_count == 1
        and turn_started_count == 1
        and event_types[0] == "thread.started"
        and len(event_types) > 1
        and event_types[1] == "turn.started"
        and terminal_count == 1
        and terminal_event == "turn.completed"
        and terminal_is_last
        and malformed == 0
        and not unknown_events
        and not unknown_items
        and not rejected_target_references
    )
    return EventEvidence(
        observed_target_ids=tuple(sorted(observed)),
        unbound_skill_names=tuple(sorted(unbound)),
        complete=complete,
        malformed_lines=malformed,
        unknown_event_types=tuple(sorted(unknown_events)),
        unknown_item_types=tuple(sorted(unknown_items)),
        terminal_event=terminal_event,
        usage=usage,
        event_count=event_count,
        rejected_target_references=tuple(sorted(rejected_target_references)),
    )


def find_codex() -> str | None:
    for name in ("codex", "codex.cmd", "codex.exe"):
        found = shutil.which(name)
        if found:
            return found
    return None


def codex_version(executable: str) -> str | None:
    try:
        completed = subprocess.run(
            [executable, "--version"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or completed.stderr.strip() or None


def load_plugin_catalog(
    fixture: Path | None = None,
) -> tuple[dict[str, Any] | None, str, str | None, str | None]:
    if fixture is not None:
        try:
            value = read_json(fixture)
            if not isinstance(value, dict) or not isinstance(
                value.get("installed"), list
            ):
                raise ValueError("catalog fixture must contain installed[]")
            return value, "fixture", None, "fixture-adapter"
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return None, "fixture", f"cannot read plugin catalog: {exc}", None
    executable = find_codex()
    if executable is None:
        return None, "codex", "Codex CLI unavailable", None
    version = codex_version(executable)
    try:
        completed = subprocess.run(
            [executable, "plugin", "list", "--json"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            return (
                None,
                "codex",
                f"codex plugin list exited {completed.returncode}: {detail[-1000:]}",
                version,
            )
        value = json.loads(completed.stdout)
        if not isinstance(value, dict) or not isinstance(
            value.get("installed"), list
        ):
            raise ValueError("codex plugin list did not return installed[]")
        return value, "codex", None, version
    except (
        OSError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        return None, "codex", str(exc), version


def terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def build_native_prompt(prompt: str) -> str:
    return f"""<user_request>
{prompt}
</user_request>

Host observation protocol (not part of the user request): apply the normal Skill
trigger rules only to the text inside <user_request>. Load any necessary Skill
instructions, then stop before performing the requested work. Do not modify files,
install dependencies, or call tools with external side effects. Return only the
structured response. `selected_skills` must list the frontmatter names of Skills that
were actually loaded. Do not infer or invent an expected answer.
"""


def run_codex(
    prompt: str,
    timeout: int,
    workspace: Path,
    model: str | None,
) -> HostResult:
    executable = find_codex()
    if executable is None:
        return HostResult(
            None,
            "",
            0,
            "Codex CLI unavailable",
            failure_kind="unavailable",
        )
    version = codex_version(executable)
    with tempfile.TemporaryDirectory(prefix="gloamere-skill-eval-") as temp:
        last_message = Path(temp) / "last-message.json"
        command = [
            executable,
            "exec",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--json",
            "--output-schema",
            str(NATIVE_OUTPUT_SCHEMA),
            "--output-last-message",
            str(last_message),
            "--cd",
            str(workspace),
        ]
        if model:
            command.extend(["--model", model])
        command.append("-")
        process_options: dict[str, Any] = {}
        if os.name == "nt":
            process_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            process_options["start_new_session"] = True
        started = time.perf_counter()
        try:
            process = subprocess.Popen(
                command,
                cwd=workspace,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                **process_options,
            )
            timed_out = False
            try:
                stdout, stderr = process.communicate(input=prompt, timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                terminate_process_tree(process)
                try:
                    stdout, stderr = process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate()
            duration = round((time.perf_counter() - started) * 1000)
            if timed_out:
                return HostResult(
                    None,
                    stdout,
                    duration,
                    f"Codex observation timed out after {timeout}s",
                    version,
                    "execution_error",
                )
            if process.returncode != 0:
                detail = "\n".join(
                    part for part in (stdout.strip(), stderr.strip()) if part
                )
                return HostResult(
                    None,
                    stdout,
                    duration,
                    f"Codex exited {process.returncode}: {detail[-2000:]}",
                    version,
                    "execution_error",
                )
            if not last_message.is_file():
                return HostResult(
                    None,
                    stdout,
                    duration,
                    "Codex did not write the last-message file",
                    version,
                    "execution_error",
                )
            payload = read_json(last_message)
            if not isinstance(payload, dict):
                raise ValueError("Codex last message must be a JSON object")
            return HostResult(payload, stdout, duration, codex_version=version)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            duration = round((time.perf_counter() - started) * 1000)
            return HostResult(
                None,
                "",
                duration,
                str(exc),
                version,
                "execution_error",
            )


def run_adapter(
    executable: str,
    arguments: list[str],
    prompt: str,
    timeout: int,
    workspace: Path,
) -> HostResult:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [executable, *arguments],
            input=prompt,
            cwd=workspace,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=False,
        )
        duration = round((time.perf_counter() - started) * 1000)
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            return HostResult(
                None,
                "",
                duration,
                f"adapter exited {completed.returncode}: {detail[-2000:]}",
                "fixture-adapter",
                "execution_error",
            )
        envelope = json.loads(completed.stdout)
        if not isinstance(envelope, dict):
            raise ValueError("adapter output must be a JSON object")
        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("adapter output is missing payload")
        if isinstance(envelope.get("event_stream"), str):
            event_stream = envelope["event_stream"]
        elif isinstance(envelope.get("events"), list):
            event_stream = "\n".join(
                canonical_json(item) if not isinstance(item, str) else item
                for item in envelope["events"]
            )
        else:
            raise ValueError("adapter output is missing event_stream or events")
        return HostResult(
            payload,
            event_stream,
            duration,
            codex_version="fixture-adapter",
        )
    except (
        OSError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        duration = round((time.perf_counter() - started) * 1000)
        return HostResult(
            None,
            "",
            duration,
            str(exc),
            "fixture-adapter",
            "execution_error",
        )


def declared_target_ids(
    payload: dict[str, Any],
    suite: dict[str, Any],
) -> tuple[set[str], list[str], list[str], bool]:
    selected = payload.get("selected_skills")
    if (
        not isinstance(selected, list)
        or any(not isinstance(item, str) or not item for item in selected)
        or len(selected) != len(set(selected))
    ):
        return set(), [], [], False
    selected_names = sorted(
        {item for item in selected if isinstance(item, str)}
    )
    by_name = {
        skill_name: f"{case['plugin_id']}:{skill_name}"
        for case in suite.get("cases", [])
        if isinstance(case, dict) and isinstance(case.get("plugin_id"), str)
        for field in ("expected_skills", "forbidden_skills")
        for skill_name in case.get(field, [])
        if isinstance(skill_name, str)
    }
    return (
        {by_name[name] for name in selected_names if name in by_name},
        selected_names,
        sorted(name for name in selected_names if name not in by_name),
        True,
    )


def resolve_skill_references(
    references: Iterable[str],
    plugin_id: str,
) -> set[str]:
    return {f"{plugin_id}:{reference}" for reference in references}


def skill_names_for_target_ids(
    target_ids: Iterable[str],
    target_lock: dict[str, Any],
) -> list[str]:
    requested = set(target_ids)
    return sorted(
        target["skill_name"]
        for target in target_lock.get("targets", [])
        if isinstance(target, dict)
        and target.get("target_id") in requested
        and isinstance(target.get("skill_name"), str)
    )


def event_diagnostics(evidence: EventEvidence) -> dict[str, Any]:
    return {
        "complete": evidence.complete,
        "event_count": evidence.event_count,
        "malformed_lines": evidence.malformed_lines,
        "unknown_event_types": list(evidence.unknown_event_types),
        "unknown_item_types": list(evidence.unknown_item_types),
        "terminal_event": evidence.terminal_event,
        "rejected_target_references": list(
            evidence.rejected_target_references
        ),
    }


def classify_native_attempt(
    case: dict[str, Any],
    suite: dict[str, Any],
    target_lock: dict[str, Any],
    result: HostResult,
    attempt: int,
    include_prompt: bool = False,
    batch: int = 1,
) -> dict[str, Any]:
    evidence = parse_codex_events(result.event_stream, target_lock, suite)
    payload = result.payload or {}
    (
        declared_ids,
        declared_names,
        unbound_declared_names,
        declaration_valid,
    ) = declared_target_ids(payload, suite)
    observed = set(evidence.observed_target_ids)
    case_plugin_id = str(case.get("plugin_id", suite.get("plugin_id", "")))
    expected = resolve_skill_references(
        case.get("expected_skills", []), case_plugin_id
    )
    excluded = resolve_skill_references(
        case.get("forbidden_skills", []), case_plugin_id
    )

    if result.error:
        evidence_status = result.failure_kind or "execution_error"
        verdict = None
        reason = (
            "Codex host is unavailable"
            if evidence_status == "unavailable"
            else "Codex or adapter execution failed"
        )
    elif not evidence.complete:
        evidence_status = "unobservable"
        verdict = None
        reason = "Codex event stream was not complete and fully recognized"
    elif evidence.unbound_skill_names:
        evidence_status = "identity_conflict"
        verdict = None
        reason = "A same-name Skill was observed from a path outside the target lock"
    elif not declaration_valid:
        evidence_status = "identity_conflict"
        verdict = None
        reason = "Model declaration does not satisfy the native output contract"
    elif unbound_declared_names:
        evidence_status = "identity_conflict"
        verdict = None
        reason = "Model declaration contains a Skill outside the evaluation target set"
    elif declared_ids != observed:
        evidence_status = "identity_conflict"
        verdict = None
        reason = "Model declaration conflicts with path-bound host evidence"
    else:
        evidence_status = "verified"
        passed = observed == expected and not observed.intersection(excluded)
        verdict = "pass" if passed else "fail"
        reason = "Host path evidence and model declaration agree"

    item: dict[str, Any] = {
        "batch_id": batch,
        "attempt": attempt,
        "prompt_sha256": sha256_text(case["prompt"]),
        "expected_skills": sorted(case.get("expected_skills", [])),
        "forbidden_skills": sorted(case.get("forbidden_skills", [])),
        "expected_target_ids": sorted(expected),
        "forbidden_target_ids": sorted(excluded),
        "declared_skills": declared_names,
        "declared_target_ids": sorted(declared_ids),
        "unbound_declared_skills": unbound_declared_names,
        "observed_skills": skill_names_for_target_ids(observed, target_lock),
        "observed_target_ids": sorted(observed),
        "unbound_skill_names": list(evidence.unbound_skill_names),
        "evidence_status": evidence_status,
        "verdict": verdict,
        "reason": reason,
        "duration_ms": result.duration_ms,
        "event_diagnostics": event_diagnostics(evidence),
        "usage": evidence.usage,
    }
    if include_prompt:
        item["prompt"] = case["prompt"]
    return item


def preflight_attempt(
    case: dict[str, Any],
    status: str,
    reasons: list[str],
    attempt: int,
    include_prompt: bool = False,
    batch: int = 1,
) -> dict[str, Any]:
    plugin_id = case["plugin_id"]
    expected = sorted(
        f"{plugin_id}:{skill_name}"
        for skill_name in case.get("expected_skills", [])
    )
    forbidden = sorted(
        f"{plugin_id}:{skill_name}"
        for skill_name in case.get("forbidden_skills", [])
    )
    item: dict[str, Any] = {
        "batch_id": batch,
        "attempt": attempt,
        "prompt_sha256": sha256_text(case["prompt"]),
        "expected_skills": sorted(case.get("expected_skills", [])),
        "forbidden_skills": sorted(case.get("forbidden_skills", [])),
        "expected_target_ids": expected,
        "forbidden_target_ids": forbidden,
        "declared_skills": [],
        "declared_target_ids": [],
        "unbound_declared_skills": [],
        "observed_skills": [],
        "observed_target_ids": [],
        "unbound_skill_names": [],
        "evidence_status": status,
        "verdict": None,
        "reason": "; ".join(reasons),
        "duration_ms": 0,
        "event_diagnostics": {
            "complete": False,
            "event_count": 0,
            "malformed_lines": 0,
            "unknown_event_types": [],
            "unknown_item_types": [],
            "terminal_event": None,
            "rejected_target_references": [],
        },
        "usage": None,
    }
    if include_prompt:
        item["prompt"] = case["prompt"]
    return item


def retry_policy_settings(policy: dict[str, Any]) -> dict[str, Any]:
    configured = policy.get("retry")
    defaults = RISK_POLICY_V2["retry"]
    if not isinstance(configured, dict):
        configured = {}
    result = {
        field: configured.get(field, default)
        for field, default in defaults.items()
    }
    for field in (
        "unexpected_attempts",
        "confirmed_failure_count",
        "infrastructure_retry_count",
    ):
        amount = result[field]
        if (
            not isinstance(amount, int)
            or isinstance(amount, bool)
            or amount < (0 if field == "infrastructure_retry_count" else 1)
        ):
            raise ValueError(f"evaluation policy retry.{field} is invalid")
    if result["confirmed_failure_count"] > result["unexpected_attempts"]:
        raise ValueError(
            "evaluation policy retry.confirmed_failure_count exceeds "
            "unexpected_attempts"
        )
    for field in ("single_failure_outcome", "budget_exhausted_outcome"):
        if result[field] not in {"pass", "fail", "pending"}:
            raise ValueError(f"evaluation policy retry.{field} is invalid")
    return result


INFRASTRUCTURE_EVIDENCE_STATUSES = {
    "unobservable",
    "unavailable",
    "execution_error",
}


def desired_adaptive_attempts(
    attempts: list[dict[str, Any]],
    retry_policy: dict[str, Any],
    enabled: bool,
) -> int:
    if not enabled or not attempts:
        return 1
    if any(
        attempt.get("evidence_status") == "verified"
        and attempt.get("verdict") == "fail"
        or attempt.get("evidence_status") == "identity_conflict"
        for attempt in attempts
    ):
        return retry_policy["unexpected_attempts"]
    if any(
        attempt.get("evidence_status") in INFRASTRUCTURE_EVIDENCE_STATUSES
        for attempt in attempts
    ):
        return 1 + retry_policy["infrastructure_retry_count"]
    return 1


def adaptive_failure_signature(attempt: dict[str, Any]) -> str:
    return sha256_object(
        {
            "evidence_status": attempt.get("evidence_status"),
            "verdict": attempt.get("verdict"),
            "observed_target_ids": attempt.get("observed_target_ids", []),
            "declared_target_ids": attempt.get("declared_target_ids", []),
            "unbound_declared_skills": attempt.get(
                "unbound_declared_skills",
                [],
            ),
            "unbound_skill_names": attempt.get("unbound_skill_names", []),
        }
    )


def adaptive_case_evaluation(
    attempts: list[dict[str, Any]],
    expected_attempts: int,
    retry_policy: dict[str, Any],
    budget_exhausted: bool,
    enabled: bool,
) -> dict[str, Any]:
    verified_passes = sum(
        attempt.get("evidence_status") == "verified"
        and attempt.get("verdict") == "pass"
        for attempt in attempts
    )
    verified_failures = [
        attempt
        for attempt in attempts
        if attempt.get("evidence_status") == "verified"
        and attempt.get("verdict") == "fail"
    ]
    infrastructure_failures = sum(
        attempt.get("evidence_status") in INFRASTRUCTURE_EVIDENCE_STATUSES
        for attempt in attempts
    )
    identity_conflicts = sum(
        attempt.get("evidence_status") == "identity_conflict"
        for attempt in attempts
    )
    signatures = Counter(
        adaptive_failure_signature(attempt) for attempt in verified_failures
    )
    confirmed_failures = max(signatures.values(), default=0)
    retry_complete = len(attempts) >= expected_attempts
    initial_anomaly = bool(
        attempts
        and not (
            attempts[0].get("evidence_status") == "verified"
            and attempts[0].get("verdict") == "pass"
        )
    )

    if not attempts:
        outcome = "pending"
        reason = "no-attempt-evidence"
    elif budget_exhausted and not retry_complete:
        outcome = retry_policy["budget_exhausted_outcome"]
        reason = "retry-budget-exhausted"
    elif not retry_complete:
        outcome = "pending"
        reason = "adaptive-retry-incomplete"
    elif confirmed_failures >= retry_policy["confirmed_failure_count"]:
        outcome = "fail"
        reason = "confirmed-same-routing-failure"
    elif verified_failures:
        outcome = retry_policy["single_failure_outcome"]
        reason = "single-or-inconsistent-routing-failure"
    elif identity_conflicts:
        outcome = "pending"
        reason = "identity-conflict-not-confirmed-as-routing-result"
    elif infrastructure_failures:
        if verified_passes and infrastructure_failures < len(attempts):
            outcome = "pass"
            reason = "transient-infrastructure-anomaly-recovered"
        else:
            outcome = "pending"
            reason = "persistent-infrastructure-anomaly"
    elif verified_passes == len(attempts):
        outcome = "pass"
        reason = "verified-routing-pass"
    else:
        outcome = "pending"
        reason = "unclassified-adaptive-result"
    return {
        "enabled": enabled,
        "outcome": outcome,
        "reason": reason,
        "initial_anomaly": initial_anomaly,
        "retry_complete": retry_complete,
        "expected_attempts": expected_attempts,
        "verified_passes": verified_passes,
        "verified_failures": len(verified_failures),
        "confirmed_same_failures": confirmed_failures,
        "infrastructure_failures": infrastructure_failures,
        "identity_conflicts": identity_conflicts,
    }


def case_metrics(
    attempts: list[dict[str, Any]],
    repeat: int,
    independent_batches: int,
    expected_attempts_override: int | None = None,
) -> dict[str, Any]:
    if expected_attempts_override is None:
        expected_pairs = {
            (batch, attempt)
            for batch in range(1, independent_batches + 1)
            for attempt in range(1, repeat + 1)
        }
    else:
        expected_pairs = {
            (1, attempt)
            for attempt in range(1, expected_attempts_override + 1)
        }
    actual_pairs = [
        (attempt.get("batch_id"), attempt.get("attempt")) for attempt in attempts
    ]
    signatures = [
        (
            attempt.get("evidence_status"),
            attempt.get("verdict"),
            tuple(attempt.get("expected_target_ids", [])),
            tuple(attempt.get("forbidden_target_ids", [])),
            tuple(attempt.get("observed_target_ids", [])),
            tuple(attempt.get("declared_target_ids", [])),
            tuple(attempt.get("declared_skills", [])),
            tuple(attempt.get("unbound_declared_skills", [])),
            tuple(attempt.get("unbound_skill_names", [])),
        )
        for attempt in attempts
    ]
    all_completed = (
        len(attempts) == len(expected_pairs)
        and len(actual_pairs) == len(set(actual_pairs))
        and set(actual_pairs) == expected_pairs
        and all(
            attempt.get("evidence_status") == "verified"
            and attempt.get("verdict") in {"pass", "fail"}
            for attempt in attempts
        )
    )
    passed = sum(
        attempt.get("evidence_status") == "verified"
        and attempt.get("verdict") == "pass"
        for attempt in attempts
    )
    scored = sum(
        attempt.get("evidence_status") == "verified"
        and attempt.get("verdict") in {"pass", "fail"}
        for attempt in attempts
    )
    expected_attempts = (
        repeat * independent_batches
        if expected_attempts_override is None
        else expected_attempts_override
    )
    verdicts = Counter(
        (
            str(item.get("verdict"))
            if item.get("verdict") is not None
            else "null"
        )
        for item in attempts
    )
    return {
        "attempt_count": len(attempts),
        "expected_attempts": expected_attempts,
        "scored_attempts": scored,
        "unscored_attempts": len(attempts) - scored,
        "passed_attempts": passed,
        "failed_attempts": sum(
            attempt.get("evidence_status") == "verified"
            and attempt.get("verdict") == "fail"
            for attempt in attempts
        ),
        "evidence_coverage": round(scored / expected_attempts, 4),
        "conditional_accuracy": (
            round(passed / scored, 4) if scored else None
        ),
        "stable": all_completed and len(set(signatures)) == 1,
        "evidence_statuses": dict(
            Counter(item.get("evidence_status") for item in attempts)
        ),
        "verdicts": dict(verdicts),
    }


def aggregate_case(
    case: dict[str, Any],
    attempts: list[dict[str, Any]],
    repeat: int,
    independent_batches: int = 1,
    adaptive_evaluation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item = {
        "id": case["id"],
        "plugin_id": case["plugin_id"],
        "language": case["language"],
        "tags": sorted(case["tags"]),
        "prompt_sha256": sha256_text(case["prompt"]),
        "expected_skills": sorted(case.get("expected_skills", [])),
        "forbidden_skills": sorted(case.get("forbidden_skills", [])),
        **case_metrics(
            attempts,
            repeat,
            independent_batches,
            (
                adaptive_evaluation.get("expected_attempts")
                if adaptive_evaluation is not None
                else None
            ),
        ),
        "attempts": attempts,
    }
    if adaptive_evaluation is not None:
        item["adaptive_evaluation"] = adaptive_evaluation
    return item


def summarize_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    attempts = [
        attempt for case in cases for attempt in case.get("attempts", [])
    ]
    total = len(attempts)
    scored = sum(
        item["evidence_status"] == "verified"
        and item["verdict"] in {"pass", "fail"}
        for item in attempts
    )
    scored_passed = sum(
        item["evidence_status"] == "verified" and item["verdict"] == "pass"
        for item in attempts
    )
    return {
        "case_count": len(cases),
        "attempt_count": total,
        "scored_attempts": scored,
        "unscored_attempts": total - scored,
        "passed_attempts": scored_passed,
        "failed_attempts": sum(
            item["evidence_status"] == "verified"
            and item["verdict"] == "fail"
            for item in attempts
        ),
        "unobservable_attempts": sum(
            item["evidence_status"] == "unobservable" for item in attempts
        ),
        "unavailable_attempts": sum(
            item["evidence_status"] == "unavailable" for item in attempts
        ),
        "identity_conflicts": sum(
            item["evidence_status"] == "identity_conflict" for item in attempts
        ),
        "execution_errors": sum(
            item["evidence_status"] == "execution_error" for item in attempts
        ),
        "evidence_coverage": round(scored / total, 4) if total else 0.0,
        "conditional_accuracy": (
            round(scored_passed / scored, 4) if scored else None
        ),
        "evidence_statuses": dict(
            Counter(item["evidence_status"] for item in attempts)
        ),
        "stable_cases": sum(bool(case.get("stable")) for case in cases),
    }


def producer_metadata() -> dict[str, Any]:
    plugin_root = SKILL_ROOT.parents[1]
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    plugin_id = "gloamere-eval"
    plugin_version = "unknown"
    try:
        manifest = read_json(manifest_path)
        if isinstance(manifest.get("name"), str):
            plugin_id = manifest["name"]
        if isinstance(manifest.get("version"), str):
            plugin_version = manifest["version"]
    except (OSError, json.JSONDecodeError, AttributeError):
        pass
    return {
        "id": PRODUCER_ID,
        "plugin_id": plugin_id,
        "plugin_version": plugin_version,
    }


def report_targets(target_lock: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "target_id": item["target_id"],
            "plugin_id": item["plugin_id"],
            "plugin_selector": item.get("plugin_selector"),
            "plugin_version": item["plugin_version"],
            "installed": item.get("installed"),
            "enabled": item.get("enabled"),
            "plugin_manifest_relative_path": ".codex-plugin/plugin.json",
            "plugin_manifest_sha256": item["plugin_manifest_sha256"],
            "skill_name": item["skill_name"],
            "relative_path": item["relative_path"],
            "sha256": item["sha256"],
            "agent_config_relative_path": item[
                "agent_config_relative_path"
            ],
            "agent_config_sha256": item["agent_config_sha256"],
        }
        for item in target_lock.get("targets", [])
        if isinstance(item, dict)
        and all(
            field in item
            for field in (
                "target_id",
                "plugin_id",
                "plugin_version",
                "plugin_manifest_sha256",
                "skill_name",
                "relative_path",
                "sha256",
                "agent_config_relative_path",
                "agent_config_sha256",
            )
        )
    ]


def build_report(
    suite: dict[str, Any],
    target_lock: dict[str, Any],
    cases: list[dict[str, Any]],
    repeat: int,
    timeout: int,
    model: str | None,
    codex_version_value: str | None,
    include_prompts: bool,
    preflight_status: str = "verified",
    preflight_reasons: list[str] | None = None,
    execution_provenance: str = "codex_cli",
    *,
    mode: str = DEFAULT_NATIVE_MODE,
    selection_reason: str = "release mode selected by default",
    selection_roles: dict[str, str] | None = None,
    rotation_key: str | None = None,
    max_calls: int | None = None,
    routing_max_calls: int | None = None,
    quality_reserved_calls: int = 0,
    actual_calls: int | None = None,
    resumed_calls: int = 0,
    new_calls: int | None = None,
    shard: tuple[int, int] | None = None,
    complete: bool = True,
    independent_batches: int | None = None,
    policy: dict[str, Any] | None = None,
    policy_sha256: str | None = None,
    policy_source: str = "builtin:risk-tiered-v2",
    changed_skills: list[str] | None = None,
    commit: str | None = None,
    suite_sha256: str | None = None,
    execution_strategy: str | None = None,
    initial_phase_complete: bool | None = None,
    initial_actual_calls: int | None = None,
) -> dict[str, Any]:
    generated_at = utc_now()
    summary = summarize_cases(cases)
    effective_batches = (
        suite["execution_policy"]["independent_batches"]
        if independent_batches is None
        else independent_batches
    )
    initial_planned_calls = len(cases) * repeat * effective_batches
    planned_calls = sum(
        (
            case.get("adaptive_evaluation", {}).get(
                "expected_attempts",
                repeat * effective_batches,
            )
            if isinstance(case.get("adaptive_evaluation"), dict)
            else repeat * effective_batches
        )
        for case in cases
    )
    effective_actual_calls = (
        summary["attempt_count"] if actual_calls is None else actual_calls
    )
    effective_max_calls = planned_calls if max_calls is None else max_calls
    effective_routing_max_calls = (
        effective_max_calls
        if routing_max_calls is None
        else routing_max_calls
    )
    effective_initial_actual_calls = (
        min(effective_actual_calls, initial_planned_calls)
        if initial_actual_calls is None
        else initial_actual_calls
    )
    effective_retry_actual_calls = (
        effective_actual_calls - effective_initial_actual_calls
    )
    effective_initial_phase_complete = (
        all(
            case.get("attempt_count", 0)
            >= repeat * effective_batches
            for case in cases
        )
        if initial_phase_complete is None
        else initial_phase_complete
    )
    effective_execution_strategy = execution_strategy or (
        "adaptive-retry"
        if any(
            isinstance(case.get("adaptive_evaluation"), dict)
            for case in cases
        )
        else "fixed-grid"
    )
    effective_new_calls = (
        max(0, effective_actual_calls - resumed_calls)
        if new_calls is None
        else new_calls
    )
    effective_policy = policy or RISK_POLICY_V2
    effective_policy_id = effective_policy.get(
        "id",
        effective_policy.get("policy_id"),
    )
    policy_sha = policy_sha256 or sha256_object(effective_policy)
    suite_sha = suite_sha256 or sha256_object(suite)
    target_lock_sha = sha256_object(target_lock)
    target_hashes = {
        item["target_id"]: item["sha256"]
        for item in report_targets(target_lock)
    }
    selected_case_ids = [case["id"] for case in cases]
    selected_roles = selection_roles or {
        case_id: mode for case_id in selected_case_ids
    }
    case_outcomes: dict[str, str] = {}
    for case in cases:
        adaptive = case.get("adaptive_evaluation")
        if isinstance(adaptive, dict) and adaptive.get("outcome") in {
            "pass",
            "fail",
            "pending",
        }:
            outcome = adaptive["outcome"]
        elif case.get("unscored_attempts"):
            outcome = "pending"
        elif case.get("failed_attempts"):
            outcome = "fail"
        else:
            outcome = "pass"
        case_outcomes[case["id"]] = outcome
    outcome_counts = dict(Counter(case_outcomes.values()))
    pending_case_ids = sorted(
        case_id
        for case_id, outcome in case_outcomes.items()
        if outcome == "pending"
    )
    failed_case_ids = sorted(
        case_id
        for case_id, outcome in case_outcomes.items()
        if outcome == "fail"
    )
    evidence_complete = (
        complete
        and preflight_status == "verified"
        and not pending_case_ids
    )
    release_eligible = (
        execution_provenance == "codex_cli"
        and mode in {"release", "exhaustive"}
        and evidence_complete
    )
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "producer": producer_metadata(),
        "command": "native",
        "event_adapter": {
            "id": EVENT_ADAPTER_ID,
            "schema_version": EVENT_ADAPTER_SCHEMA_VERSION,
        },
        "execution_provenance": execution_provenance,
        "release_evidence_eligible": release_eligible,
        "evaluation": {
            "policy_id": effective_policy_id,
            "policy": effective_policy,
            "policy_source": policy_source,
            "mode": mode,
            "selection_reason": selection_reason,
            "selection": selected_roles,
            "selected_case_ids": selected_case_ids,
            "changed_skills": sorted(set(changed_skills or [])),
            "rotation_key": rotation_key,
            "execution_strategy": effective_execution_strategy,
            "max_calls": effective_max_calls,
            "routing_max_calls": effective_routing_max_calls,
            "quality_reserved_calls": quality_reserved_calls,
            "projected_total_calls": (
                effective_actual_calls + quality_reserved_calls
            ),
            "initial_planned_calls": initial_planned_calls,
            "retry_planned_calls": planned_calls - initial_planned_calls,
            "planned_calls": planned_calls,
            "actual_calls": effective_actual_calls,
            "initial_actual_calls": effective_initial_actual_calls,
            "retry_actual_calls": effective_retry_actual_calls,
            "initial_phase_complete": effective_initial_phase_complete,
            "resumed_calls": resumed_calls,
            "new_calls": effective_new_calls,
            "shard": (
                {"index": shard[0], "total": shard[1]}
                if shard is not None
                else None
            ),
            "complete": complete,
            "case_outcomes": case_outcomes,
            "outcomes": outcome_counts,
            "pending_case_ids": pending_case_ids,
            "failed_case_ids": failed_case_ids,
        },
        "provenance": {
            "commit": commit or repository_commit(),
            "policy_sha256": policy_sha,
            "suite_sha256": suite_sha,
            "target_lock_sha256": target_lock_sha,
            "target_sha256": target_hashes,
            "codex_cli": codex_version_value,
            "model": model,
            "generated_at": generated_at,
        },
        "preflight": {
            "evidence_status": preflight_status,
            "reasons": preflight_reasons or [],
        },
        "suite": {
            "suite_id": suite["suite_id"],
            "plugin_id": suite["plugin_id"],
            "execution_policy": {
                "repeat": repeat,
                "independent_batches": effective_batches,
            },
            "sha256": suite_sha,
        },
        "target_lock": {
            "sha256": target_lock_sha,
            "targets": report_targets(target_lock),
        },
        "environment": {
            "codex_version": codex_version_value,
            "model": model,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        },
        "privacy": {
            "prompts_included": include_prompts,
            "absolute_paths_included": False,
        },
        "repeat": repeat,
        "independent_batches": effective_batches,
        "timeout_seconds": timeout,
        "summary": summary,
        "cases": cases,
    }


WINDOWS_ABSOLUTE_PATH_PATTERN = re.compile(
    r"""(?ix)
    (?:^|[\s"'(<\[])
    (?:
        [a-z]:[\\/]
        | \\\\[^\\/\s]+[\\/][^\\/\s]+
    )
    """
)
POSIX_ABSOLUTE_PATH_PATTERN = re.compile(
    r"""(?x)
    (?:^|[\s"'(<\[])
    /(?!/)[^\s"'<>]+
    """
)


def absolute_path_locations(
    value: Any,
    location: str = "$",
) -> list[str]:
    if isinstance(value, str):
        if WINDOWS_ABSOLUTE_PATH_PATTERN.search(
            value
        ) or POSIX_ABSOLUTE_PATH_PATTERN.search(value):
            return [location]
        return []
    if isinstance(value, list):
        return [
            item
            for index, child in enumerate(value)
            for item in absolute_path_locations(child, f"{location}[{index}]")
        ]
    if isinstance(value, dict):
        return [
            item
            for key, child in value.items()
            for item in absolute_path_locations(child, f"{location}.{key}")
        ]
    return []


def _validate_native_report(
    value: Any,
    expected_schema_version: int,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["report must be an object"]

    def valid_string_array(candidate: Any) -> bool:
        return (
            isinstance(candidate, list)
            and all(isinstance(item, str) for item in candidate)
            and len(candidate) == len(set(candidate))
        )

    if value.get("schema_version") != expected_schema_version:
        errors.append(
            f"report schema_version must be {expected_schema_version}"
        )
    if parse_iso_datetime(value.get("generated_at")) is None:
        errors.append("report generated_at must be an ISO 8601 timestamp")
    is_v4 = expected_schema_version == REPORT_SCHEMA_VERSION
    evaluation = value.get("evaluation") if is_v4 else None
    provenance = value.get("provenance") if is_v4 else None
    report_complete = True
    if is_v4:
        if not isinstance(evaluation, dict):
            errors.append("report evaluation contract is missing")
            evaluation = {}
        mode = evaluation.get("mode")
        evaluation_policy = evaluation.get("policy")
        if evaluation.get("policy_id") != RISK_POLICY_V2["id"]:
            errors.append("report evaluation.policy_id is invalid")
        if (
            not isinstance(evaluation_policy, dict)
            or evaluation_policy.get(
                "id",
                evaluation_policy.get("policy_id"),
            )
            != evaluation.get("policy_id")
        ):
            errors.append("report evaluation.policy is invalid")
        if not isinstance(evaluation.get("policy_source"), str) or not (
            evaluation.get("policy_source")
        ):
            errors.append("report evaluation.policy_source is missing")
        if mode not in {"pr", "release", "exhaustive"}:
            errors.append("report evaluation.mode is invalid")
        selected_case_ids = evaluation.get("selected_case_ids")
        selection = evaluation.get("selection")
        if not valid_string_array(selected_case_ids):
            errors.append("report evaluation.selected_case_ids is invalid")
            selected_case_ids = []
        if not valid_string_array(evaluation.get("changed_skills")):
            errors.append("report evaluation.changed_skills is invalid")
        if (
            not isinstance(selection, dict)
            or any(
                not isinstance(key, str)
                or not isinstance(role, str)
                or not role
                for key, role in selection.items()
            )
            or set(selection) != set(selected_case_ids)
        ):
            errors.append("report evaluation.selection is invalid")
        if not isinstance(evaluation.get("selection_reason"), str) or not (
            evaluation.get("selection_reason")
        ):
            errors.append("report evaluation.selection_reason is missing")
        rotation_key = evaluation.get("rotation_key")
        if rotation_key is not None and not isinstance(rotation_key, str):
            errors.append("report evaluation.rotation_key is invalid")
        execution_strategy = evaluation.get("execution_strategy")
        if execution_strategy is not None and execution_strategy not in {
            "fixed-grid",
            "adaptive-retry",
            "initial-coverage-then-adaptive-retry",
        }:
            errors.append("report evaluation.execution_strategy is invalid")
        for field in (
            "max_calls",
            "routing_max_calls",
            "quality_reserved_calls",
            "projected_total_calls",
            "initial_planned_calls",
            "retry_planned_calls",
            "planned_calls",
            "actual_calls",
            "resumed_calls",
            "new_calls",
        ):
            amount = evaluation.get(field)
            if (
                not isinstance(amount, int)
                or isinstance(amount, bool)
                or amount < 0
            ):
                errors.append(f"report evaluation.{field} is invalid")
        for field in ("initial_actual_calls", "retry_actual_calls"):
            amount = evaluation.get(field)
            if amount is not None and (
                not isinstance(amount, int)
                or isinstance(amount, bool)
                or amount < 0
            ):
                errors.append(f"report evaluation.{field} is invalid")
        if (
            evaluation.get("initial_phase_complete") is not None
            and not isinstance(
                evaluation.get("initial_phase_complete"),
                bool,
            )
        ):
            errors.append(
                "report evaluation.initial_phase_complete must be boolean"
            )
        if (
            isinstance(evaluation.get("initial_actual_calls"), int)
            and isinstance(evaluation.get("retry_actual_calls"), int)
            and isinstance(evaluation.get("actual_calls"), int)
            and evaluation["initial_actual_calls"]
            + evaluation["retry_actual_calls"]
            != evaluation["actual_calls"]
        ):
            errors.append(
                "report actual_calls does not equal initial + retry calls"
            )
        if (
            execution_strategy
            == "initial-coverage-then-adaptive-retry"
            and isinstance(evaluation.get("retry_actual_calls"), int)
            and evaluation["retry_actual_calls"] > 0
            and evaluation.get("initial_phase_complete") is not True
        ):
            errors.append(
                "report records exhaustive retries before initial coverage"
            )
        if (
            isinstance(evaluation.get("initial_planned_calls"), int)
            and isinstance(evaluation.get("retry_planned_calls"), int)
            and isinstance(evaluation.get("planned_calls"), int)
            and evaluation["initial_planned_calls"]
            + evaluation["retry_planned_calls"]
            != evaluation["planned_calls"]
        ):
            errors.append(
                "report planned_calls does not equal initial + retry calls"
            )
        case_outcomes = evaluation.get("case_outcomes")
        if not isinstance(case_outcomes, dict) or any(
            not isinstance(case_id, str)
            or outcome not in {"pass", "fail", "pending"}
            for case_id, outcome in (
                case_outcomes.items()
                if isinstance(case_outcomes, dict)
                else ()
            )
        ):
            errors.append("report evaluation.case_outcomes is invalid")
        outcomes = evaluation.get("outcomes")
        if not isinstance(outcomes, dict) or any(
            outcome not in {"pass", "fail", "pending"}
            or not isinstance(amount, int)
            or isinstance(amount, bool)
            or amount < 0
            for outcome, amount in (
                outcomes.items() if isinstance(outcomes, dict) else ()
            )
        ):
            errors.append("report evaluation.outcomes is invalid")
        for field in ("pending_case_ids", "failed_case_ids"):
            if not valid_string_array(evaluation.get(field)):
                errors.append(f"report evaluation.{field} is invalid")
        if isinstance(evaluation.get("actual_calls"), int) and isinstance(
            evaluation.get("routing_max_calls"),
            int,
        ) and evaluation["actual_calls"] > evaluation["routing_max_calls"]:
            errors.append("report actual_calls exceeds routing_max_calls")
        if (
            isinstance(evaluation.get("actual_calls"), int)
            and isinstance(evaluation.get("quality_reserved_calls"), int)
            and isinstance(evaluation.get("projected_total_calls"), int)
            and evaluation["projected_total_calls"]
            != evaluation["actual_calls"]
            + evaluation["quality_reserved_calls"]
        ):
            errors.append(
                "report projected_total_calls does not match routing + quality"
            )
        if (
            isinstance(evaluation.get("projected_total_calls"), int)
            and isinstance(evaluation.get("max_calls"), int)
            and evaluation["projected_total_calls"] > evaluation["max_calls"]
        ):
            errors.append("report projected_total_calls exceeds max_calls")
        if (
            isinstance(evaluation.get("actual_calls"), int)
            and isinstance(evaluation.get("resumed_calls"), int)
            and isinstance(evaluation.get("new_calls"), int)
            and evaluation["actual_calls"]
            != evaluation["resumed_calls"] + evaluation["new_calls"]
        ):
            errors.append(
                "report actual_calls does not equal resumed_calls + new_calls"
            )
        report_complete = evaluation.get("complete") is True
        if not isinstance(evaluation.get("complete"), bool):
            errors.append("report evaluation.complete must be boolean")
        shard = evaluation.get("shard")
        if shard is not None and (
            not isinstance(shard, dict)
            or not isinstance(shard.get("index"), int)
            or isinstance(shard.get("index"), bool)
            or not isinstance(shard.get("total"), int)
            or isinstance(shard.get("total"), bool)
            or shard.get("index", 1) < 1
            or shard.get("index", 1) > shard.get("total", 0)
        ):
            errors.append("report evaluation.shard is invalid")
        if not isinstance(provenance, dict):
            errors.append("report provenance contract is missing")
            provenance = {}
        commit = provenance.get("commit")
        if commit != "unavailable" and not re.fullmatch(
            r"[0-9a-fA-F]{40,64}",
            str(commit),
        ):
            errors.append("report provenance.commit is invalid")
        for field in (
            "policy_sha256",
            "suite_sha256",
            "target_lock_sha256",
        ):
            if not SHA256_PATTERN.fullmatch(str(provenance.get(field, ""))):
                errors.append(f"report provenance.{field} is invalid")
        if parse_iso_datetime(provenance.get("generated_at")) is None:
            errors.append("report provenance.generated_at is invalid")
        if provenance.get("generated_at") != value.get("generated_at"):
            errors.append(
                "report provenance.generated_at does not match generated_at"
            )
        if provenance.get("codex_cli") is not None and not isinstance(
            provenance.get("codex_cli"), str
        ):
            errors.append("report provenance.codex_cli is invalid")
        if provenance.get("model") is not None and not isinstance(
            provenance.get("model"), str
        ):
            errors.append("report provenance.model is invalid")
        target_hashes = provenance.get("target_sha256")
        if not isinstance(target_hashes, dict) or any(
            not isinstance(target_id, str)
            or not SHA256_PATTERN.fullmatch(str(digest))
            for target_id, digest in (
                target_hashes.items()
                if isinstance(target_hashes, dict)
                else ()
            )
        ):
            errors.append("report provenance.target_sha256 is invalid")
    producer = value.get("producer")
    if not isinstance(producer, dict) or producer.get("id") != PRODUCER_ID:
        errors.append(f"report producer.id must be {PRODUCER_ID}")
    elif not all(
        isinstance(producer.get(field), str) and producer[field]
        for field in ("plugin_id", "plugin_version")
    ):
        errors.append("report producer plugin identity is incomplete")
    if value.get("command") != "native":
        errors.append("report command must be native")
    event_adapter = value.get("event_adapter")
    if (
        not isinstance(event_adapter, dict)
        or event_adapter.get("id") != EVENT_ADAPTER_ID
        or event_adapter.get("schema_version") != EVENT_ADAPTER_SCHEMA_VERSION
    ):
        errors.append(
            f"report event_adapter must be {EVENT_ADAPTER_ID} "
            f"schema v{EVENT_ADAPTER_SCHEMA_VERSION}"
        )
    execution_provenance = value.get("execution_provenance")
    if execution_provenance not in {"codex_cli", "fixture_adapter"}:
        errors.append("report execution_provenance is invalid")
    if is_v4:
        no_pending_cases = evaluation.get("pending_case_ids") == []
        preflight_value = value.get("preflight")
        expected_release_eligibility = (
            execution_provenance == "codex_cli"
            and evaluation.get("mode") in {"release", "exhaustive"}
            and report_complete
            and no_pending_cases
            and isinstance(preflight_value, dict)
            and preflight_value.get("evidence_status") == "verified"
        )
    else:
        expected_release_eligibility = execution_provenance == "codex_cli"
    if (
        value.get("release_evidence_eligible")
        is not expected_release_eligibility
    ):
        errors.append(
            "report release_evidence_eligible does not match "
            "execution_provenance"
        )
    evidence_statuses = {
        "verified",
        "unobservable",
        "unavailable",
        "identity_conflict",
        "execution_error",
    }
    preflight = value.get("preflight")
    if (
        not isinstance(preflight, dict)
        or preflight.get("evidence_status") not in evidence_statuses
        or not valid_string_array(preflight.get("reasons"))
    ):
        errors.append("report preflight contract is invalid")
    suite = value.get("suite")
    if not isinstance(suite, dict) or not SHA256_PATTERN.fullmatch(
        str(suite.get("sha256", ""))
    ):
        errors.append("report suite.sha256 is invalid")
    elif not isinstance(suite.get("suite_id"), str) or not suite["suite_id"]:
        errors.append("report suite.suite_id is missing")
    elif not isinstance(suite.get("plugin_id"), str) or not suite["plugin_id"]:
        errors.append("report suite.plugin_id is missing")
    target_lock = value.get("target_lock")
    if not isinstance(target_lock, dict) or not SHA256_PATTERN.fullmatch(
        str(target_lock.get("sha256", ""))
    ):
        errors.append("report target_lock.sha256 is invalid")
        report_targets_value: list[Any] = []
    else:
        report_targets_value = target_lock.get("targets", [])
        if not isinstance(report_targets_value, list):
            errors.append("report target_lock.targets must be an array")
            report_targets_value = []
    forbidden_target_fields = {
        "plugin_root",
        "plugin_manifest_path",
        "skill_path",
        "agent_config_path",
    }
    report_targets_by_id: dict[str, dict[str, Any]] = {}
    for index, target in enumerate(report_targets_value):
        if not isinstance(target, dict):
            errors.append(f"report target_lock.targets[{index}] must be an object")
            continue
        if forbidden_target_fields.intersection(target):
            errors.append(
                f"report target_lock.targets[{index}] contains absolute path fields"
            )
        for field in (
            "target_id",
            "plugin_id",
            "plugin_version",
            "skill_name",
        ):
            if not isinstance(target.get(field), str) or not target[field]:
                errors.append(
                    f"report target_lock.targets[{index}].{field} is invalid"
                )
        selector = target.get("plugin_selector")
        if selector is not None and not isinstance(selector, str):
            errors.append(
                f"report target_lock.targets[{index}].plugin_selector is invalid"
            )
        if target.get("plugin_manifest_relative_path") != (
            ".codex-plugin/plugin.json"
        ):
            errors.append(
                f"report target_lock.targets[{index}] manifest path is invalid"
            )
        relative_path = target.get("relative_path")
        if not isinstance(relative_path, str) or not re.fullmatch(
            r"skills/[^/]+/SKILL\.md", relative_path
        ):
            errors.append(
                f"report target_lock.targets[{index}] relative_path is invalid"
            )
        agent_relative_path = target.get("agent_config_relative_path")
        if not isinstance(agent_relative_path, str) or not re.fullmatch(
            r"skills/[^/]+/agents/openai\.yaml", agent_relative_path
        ):
            errors.append(
                f"report target_lock.targets[{index}] agent config path is invalid"
            )
        for digest_field in (
            "plugin_manifest_sha256",
            "sha256",
            "agent_config_sha256",
        ):
            if not SHA256_PATTERN.fullmatch(
                str(target.get(digest_field, ""))
            ):
                errors.append(
                    f"report target_lock.targets[{index}].{digest_field} "
                    "is invalid"
                )
        for field in ("installed", "enabled"):
            if target.get(field) is not None and not isinstance(
                target.get(field), bool
            ):
                errors.append(
                    f"report target_lock.targets[{index}].{field} is invalid"
                )
        target_id = target.get("target_id")
        expected_target_id = (
            f"{target.get('plugin_id')}:{target.get('skill_name')}"
        )
        if target_id != expected_target_id:
            errors.append(
                f"report target_lock.targets[{index}].target_id is invalid"
            )
        elif target_id in report_targets_by_id:
            errors.append(
                f"report target_lock target_id is duplicated: {target_id}"
            )
        else:
            report_targets_by_id[target_id] = target
    if is_v4 and isinstance(provenance, dict):
        if isinstance(suite, dict) and provenance.get("suite_sha256") != (
            suite.get("sha256")
        ):
            errors.append(
                "report provenance.suite_sha256 does not match suite.sha256"
            )
        if isinstance(target_lock, dict) and provenance.get(
            "target_lock_sha256"
        ) != target_lock.get("sha256"):
            errors.append(
                "report provenance.target_lock_sha256 does not match "
                "target_lock.sha256"
            )
        expected_target_hashes = {
            target_id: target.get("sha256")
            for target_id, target in report_targets_by_id.items()
        }
        if provenance.get("target_sha256") != expected_target_hashes:
            errors.append(
                "report provenance.target_sha256 does not match target lock"
            )
    privacy = value.get("privacy")
    if not isinstance(privacy, dict):
        errors.append("report privacy contract is missing")
        prompts_included = False
    else:
        prompts_included = privacy.get("prompts_included")
        if not isinstance(prompts_included, bool):
            errors.append("report privacy.prompts_included must be boolean")
            prompts_included = False
        if privacy.get("absolute_paths_included") is not False:
            errors.append("report privacy.absolute_paths_included must be false")
        else:
            path_locations = absolute_path_locations(value)
            if path_locations:
                errors.append(
                    "report declares absolute_paths_included=false but contains "
                    "absolute paths at: "
                    + ", ".join(path_locations[:10])
                )
    if is_v4 and isinstance(provenance, dict):
        environment = value.get("environment")
        if not isinstance(environment, dict):
            errors.append("report environment contract is missing")
        else:
            if provenance.get("codex_cli") != environment.get(
                "codex_version"
            ):
                errors.append(
                    "report provenance.codex_cli does not match environment"
                )
            if provenance.get("model") != environment.get("model"):
                errors.append(
                    "report provenance.model does not match environment"
                )
    repeat = value.get("repeat")
    if not isinstance(repeat, int) or isinstance(repeat, bool) or not 1 <= repeat <= 10:
        errors.append("report repeat must be an integer from 1 to 10")
        effective_repeat = 1
    else:
        effective_repeat = repeat
    independent_batches = value.get("independent_batches")
    if (
        not isinstance(independent_batches, int)
        or isinstance(independent_batches, bool)
        or not 1 <= independent_batches <= 10
    ):
        errors.append(
            "report independent_batches must be an integer from 1 to 10"
        )
        effective_batches = 1
    else:
        effective_batches = independent_batches
    if isinstance(suite, dict):
        execution_policy = suite.get("execution_policy")
        if (
            not isinstance(execution_policy, dict)
            or execution_policy.get("independent_batches")
            != effective_batches
        ):
            errors.append(
                "report independent_batches does not match suite policy"
            )
        if isinstance(execution_policy, dict) and execution_policy.get(
            "repeat"
        ) != effective_repeat:
            errors.append("report repeat does not match suite policy")
    timeout = value.get("timeout_seconds")
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout < 1:
        errors.append("report timeout_seconds must be a positive integer")
    cases = value.get("cases")
    if not isinstance(cases, list):
        errors.append("report cases must be an array")
        cases = []
    case_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            errors.append("report case must be an object")
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id:
            errors.append("report case id is invalid")
        elif case_id in case_ids:
            errors.append(f"report case id is duplicated: {case_id}")
        else:
            case_ids.add(case_id)
        if case.get("plugin_id") != (
            suite.get("plugin_id") if isinstance(suite, dict) else None
        ):
            errors.append(f"report case {case_id} plugin_id is invalid")
        if not isinstance(case.get("language"), str) or not valid_string_array(
            case.get("tags")
        ):
            errors.append(f"report case {case_id} metadata is invalid")
        for field in ("expected_skills", "forbidden_skills"):
            if not valid_string_array(case.get(field)):
                errors.append(f"report case {case_id}.{field} is invalid")
        case_plugin_id = case.get("plugin_id")
        case_expected_skills = case.get("expected_skills", [])
        case_forbidden_skills = case.get("forbidden_skills", [])
        if not isinstance(case_expected_skills, list):
            case_expected_skills = []
        if not isinstance(case_forbidden_skills, list):
            case_forbidden_skills = []
        expected_target_ids = sorted(
            f"{case_plugin_id}:{skill_name}"
            for skill_name in case_expected_skills
            if isinstance(skill_name, str)
        )
        forbidden_target_ids = sorted(
            f"{case_plugin_id}:{skill_name}"
            for skill_name in case_forbidden_skills
            if isinstance(skill_name, str)
        )
        for target_id in (*expected_target_ids, *forbidden_target_ids):
            if target_id not in report_targets_by_id:
                errors.append(
                    f"report case {case_id} target is missing from target lock: "
                    f"{target_id}"
                )
        if not SHA256_PATTERN.fullmatch(str(case.get("prompt_sha256", ""))):
            errors.append(f"report case {case_id} prompt_sha256 is invalid")
        attempts = case.get("attempts")
        if not isinstance(attempts, list):
            errors.append(f"report case {case_id} attempts must be an array")
            continue
        if case.get("attempt_count") != len(attempts):
            errors.append(
                f"report case {case_id} attempt_count does not match attempts"
            )
        adaptive = case.get("adaptive_evaluation")
        adaptive_expected_attempts: int | None = None
        if is_v4 and adaptive is not None:
            if not isinstance(adaptive, dict):
                errors.append(
                    f"report case {case_id} adaptive_evaluation is invalid"
                )
                adaptive = {}
            adaptive_expected_attempts = adaptive.get("expected_attempts")
            if (
                not isinstance(adaptive_expected_attempts, int)
                or isinstance(adaptive_expected_attempts, bool)
                or adaptive_expected_attempts < 1
            ):
                errors.append(
                    f"report case {case_id} adaptive expected_attempts is invalid"
                )
                adaptive_expected_attempts = 1
            if adaptive.get("outcome") not in {"pass", "fail", "pending"}:
                errors.append(
                    f"report case {case_id} adaptive outcome is invalid"
                )
            if not isinstance(adaptive.get("reason"), str) or not adaptive.get(
                "reason"
            ):
                errors.append(
                    f"report case {case_id} adaptive reason is invalid"
                )
            for field in ("enabled", "initial_anomaly", "retry_complete"):
                if not isinstance(adaptive.get(field), bool):
                    errors.append(
                        f"report case {case_id} adaptive {field} is invalid"
                    )
            for field in (
                "verified_passes",
                "verified_failures",
                "confirmed_same_failures",
                "infrastructure_failures",
                "identity_conflicts",
            ):
                amount = adaptive.get(field)
                if (
                    not isinstance(amount, int)
                    or isinstance(amount, bool)
                    or amount < 0
                ):
                    errors.append(
                        f"report case {case_id} adaptive {field} is invalid"
                    )
        attempt_pairs: list[tuple[int, int]] = []
        for attempt in attempts:
            if not isinstance(attempt, dict):
                errors.append(f"report case {case_id} attempt must be an object")
                continue
            batch_id = attempt.get("batch_id")
            attempt_id = attempt.get("attempt")
            if (
                not isinstance(batch_id, int)
                or isinstance(batch_id, bool)
                or not 1 <= batch_id <= effective_batches
                or not isinstance(attempt_id, int)
                or isinstance(attempt_id, bool)
                or not 1
                <= attempt_id
                <= (
                    adaptive_expected_attempts
                    if adaptive_expected_attempts is not None
                    else effective_repeat
                )
            ):
                errors.append(
                    f"report case {case_id} attempt batch/id is invalid"
                )
            else:
                attempt_pairs.append((batch_id, attempt_id))
            if attempt.get("evidence_status") not in evidence_statuses:
                errors.append(
                    f"report case {case_id} has invalid evidence_status"
                )
            if attempt.get("verdict") not in {"pass", "fail", None}:
                errors.append(f"report case {case_id} has invalid verdict")
            status = attempt.get("evidence_status")
            verdict = attempt.get("verdict")
            if (
                status == "verified"
                and verdict not in {"pass", "fail"}
                or status in evidence_statuses.difference({"verified"})
                and verdict is not None
            ):
                errors.append(
                    f"report case {case_id} evidence_status and verdict conflict"
                )
            for field in (
                "expected_skills",
                "forbidden_skills",
                "expected_target_ids",
                "forbidden_target_ids",
                "declared_skills",
                "declared_target_ids",
                "unbound_declared_skills",
                "observed_skills",
                "observed_target_ids",
                "unbound_skill_names",
            ):
                if not valid_string_array(attempt.get(field)):
                    errors.append(
                        f"report case {case_id} attempt.{field} is invalid"
                    )
            for field in ("expected_skills", "forbidden_skills"):
                if attempt.get(field) != case.get(field):
                    errors.append(
                        f"report case {case_id} attempt.{field} "
                        "does not match case"
                    )
            if attempt.get("expected_target_ids") != expected_target_ids:
                errors.append(
                    f"report case {case_id} attempt.expected_target_ids "
                    "does not match case identity"
                )
            if attempt.get("forbidden_target_ids") != forbidden_target_ids:
                errors.append(
                    f"report case {case_id} attempt.forbidden_target_ids "
                    "does not match case identity"
                )
            has_prompt = isinstance(attempt.get("prompt"), str)
            if prompts_included != has_prompt:
                errors.append(
                    f"report case {case_id} prompt privacy flag is inconsistent"
                )
            if attempt.get("prompt_sha256") != case.get("prompt_sha256"):
                errors.append(
                    f"report case {case_id} attempt prompt hash does not match"
                )
            if has_prompt and sha256_text(attempt["prompt"]) != attempt.get(
                "prompt_sha256"
            ):
                errors.append(
                    f"report case {case_id} attempt prompt content does not "
                    "match its hash"
                )
            if (
                not isinstance(attempt.get("duration_ms"), int)
                or isinstance(attempt.get("duration_ms"), bool)
                or attempt["duration_ms"] < 0
            ):
                errors.append(
                    f"report case {case_id} attempt duration_ms is invalid"
                )
            if attempt.get("reason") is not None and not isinstance(
                attempt.get("reason"), str
            ):
                errors.append(
                    f"report case {case_id} attempt reason is invalid"
                )
            diagnostics = attempt.get("event_diagnostics")
            if not isinstance(diagnostics, dict):
                errors.append(
                    f"report case {case_id} event_diagnostics is invalid"
                )
            else:
                if not isinstance(diagnostics.get("complete"), bool):
                    errors.append(
                        f"report case {case_id} diagnostics.complete is invalid"
                    )
                for field in (
                    "unknown_event_types",
                    "unknown_item_types",
                    "rejected_target_references",
                ):
                    if not valid_string_array(diagnostics.get(field)):
                        errors.append(
                            f"report case {case_id} diagnostics.{field} "
                            "is invalid"
                        )
                for field in ("event_count", "malformed_lines"):
                    if (
                        not isinstance(diagnostics.get(field), int)
                        or isinstance(diagnostics.get(field), bool)
                        or diagnostics[field] < 0
                    ):
                        errors.append(
                            f"report case {case_id} diagnostics.{field} "
                            "is invalid"
                        )
                terminal = diagnostics.get("terminal_event")
                if terminal is not None and not isinstance(terminal, str):
                    errors.append(
                        f"report case {case_id} terminal_event is invalid"
                    )
            observed_skills = attempt.get("observed_skills")
            observed_target_ids = attempt.get("observed_target_ids")
            declared_skills = attempt.get("declared_skills")
            declared_target_ids = attempt.get("declared_target_ids")
            resolved_observed_ids = (
                sorted(
                    f"{case_plugin_id}:{skill_name}"
                    for skill_name in observed_skills
                )
                if valid_string_array(observed_skills)
                else []
            )
            resolved_declared_ids = (
                sorted(
                    f"{case_plugin_id}:{skill_name}"
                    for skill_name in declared_skills
                )
                if valid_string_array(declared_skills)
                else []
            )
            if observed_target_ids != resolved_observed_ids:
                errors.append(
                    f"report case {case_id} observed Skill names and target "
                    "IDs disagree"
                )
            if declared_target_ids != resolved_declared_ids:
                errors.append(
                    f"report case {case_id} declared Skill names and target "
                    "IDs disagree"
                )
            if any(
                target_id not in report_targets_by_id
                for target_id in resolved_observed_ids
            ):
                errors.append(
                    f"report case {case_id} observed target is missing from "
                    "target lock"
                )
            if status == "verified":
                # 根因：只按上报 verdict 汇总时可同步伪造 attempt 与聚合值；
                # 修复：从路径绑定的 observed 证据重算 verdict 与声明一致性。
                observed_set = (
                    set(observed_target_ids)
                    if valid_string_array(observed_target_ids)
                    else set()
                )
                expected_set = set(expected_target_ids)
                forbidden_set = set(forbidden_target_ids)
                expected_verdict = (
                    "pass"
                    if observed_set == expected_set
                    and not observed_set.intersection(forbidden_set)
                    else "fail"
                )
                if verdict != expected_verdict:
                    errors.append(
                        f"report case {case_id} verdict does not match "
                        "observed evidence"
                    )
                if declared_skills != observed_skills or (
                    declared_target_ids != observed_target_ids
                ):
                    errors.append(
                        f"report case {case_id} verified declaration and "
                        "observation disagree"
                    )
                if attempt.get("unbound_declared_skills") or attempt.get(
                    "unbound_skill_names"
                ):
                    errors.append(
                        f"report case {case_id} verified evidence contains "
                        "unbound Skills"
                    )
                if isinstance(diagnostics, dict) and (
                    diagnostics.get("complete") is not True
                    or not isinstance(diagnostics.get("event_count"), int)
                    or isinstance(diagnostics.get("event_count"), bool)
                    or diagnostics.get("event_count") < 3
                    or diagnostics.get("terminal_event") != "turn.completed"
                    or diagnostics.get("malformed_lines") != 0
                    or diagnostics.get("unknown_event_types") != []
                    or diagnostics.get("unknown_item_types") != []
                    or diagnostics.get("rejected_target_references") != []
                ):
                    errors.append(
                        f"report case {case_id} verified event diagnostics "
                        "are inconsistent"
                    )
            usage = attempt.get("usage")
            if usage is not None and (
                not isinstance(usage, dict)
                or any(
                    not isinstance(amount, int)
                    or isinstance(amount, bool)
                    or amount < 0
                    for amount in usage.values()
                )
            ):
                errors.append(f"report case {case_id} usage is invalid")
        expected_pairs = (
            {
                (1, attempt_id)
                for attempt_id in range(1, adaptive_expected_attempts + 1)
            }
            if adaptive_expected_attempts is not None
            else {
                (batch_id, attempt_id)
                for batch_id in range(1, effective_batches + 1)
                for attempt_id in range(1, effective_repeat + 1)
            }
        )
        invalid_grid = len(attempt_pairs) != len(set(attempt_pairs))
        if report_complete:
            invalid_grid = invalid_grid or set(attempt_pairs) != expected_pairs
        else:
            invalid_grid = invalid_grid or not set(attempt_pairs).issubset(
                expected_pairs
            )
        if invalid_grid:
            errors.append(
                f"report case {case_id} does not contain a valid "
                "batch/repeat attempt grid"
            )
        try:
            expected_metrics = case_metrics(
                attempts,
                effective_repeat,
                effective_batches,
                adaptive_expected_attempts,
            )
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            expected_metrics = None
        if expected_metrics is None:
            errors.append(f"report case {case_id} metrics cannot be recomputed")
        else:
            for field, expected_value in expected_metrics.items():
                if case.get(field) != expected_value:
                    errors.append(
                        f"report case {case_id}.{field} does not match attempts"
                    )
        if is_v4 and isinstance(adaptive, dict) and isinstance(
            evaluation,
            dict,
        ):
            evaluation_policy = evaluation.get("policy")
            try:
                retry_policy = retry_policy_settings(
                    evaluation_policy
                    if isinstance(evaluation_policy, dict)
                    else {}
                )
                recomputed_adaptive = adaptive_case_evaluation(
                    attempts,
                    adaptive_expected_attempts or 1,
                    retry_policy,
                    bool(
                        len(attempts) < (adaptive_expected_attempts or 1)
                        and evaluation.get("actual_calls")
                        >= evaluation.get("routing_max_calls")
                    ),
                    bool(adaptive.get("enabled")),
                )
            except (TypeError, ValueError):
                recomputed_adaptive = None
            if recomputed_adaptive is None:
                errors.append(
                    f"report case {case_id} adaptive evaluation cannot "
                    "be recomputed"
                )
            elif adaptive != recomputed_adaptive:
                errors.append(
                    f"report case {case_id} adaptive evaluation does not "
                    "match attempts"
                )
    if is_v4 and isinstance(evaluation, dict):
        selected_ids = evaluation.get("selected_case_ids")
        if isinstance(selected_ids, list) and selected_ids != [
            case.get("id") for case in cases if isinstance(case, dict)
        ]:
            errors.append(
                "report evaluation.selected_case_ids does not match cases"
            )
        initial_planned_calls = (
            len(cases) * effective_repeat * effective_batches
        )
        planned_calls = sum(
            (
                case.get("adaptive_evaluation", {}).get(
                    "expected_attempts",
                    effective_repeat * effective_batches,
                )
                if isinstance(case.get("adaptive_evaluation"), dict)
                else effective_repeat * effective_batches
            )
            for case in cases
            if isinstance(case, dict)
        )
        if evaluation.get("initial_planned_calls") != initial_planned_calls:
            errors.append(
                "report evaluation.initial_planned_calls does not match cases"
            )
        if evaluation.get("retry_planned_calls") != (
            planned_calls - initial_planned_calls
        ):
            errors.append(
                "report evaluation.retry_planned_calls does not match cases"
            )
        if evaluation.get("planned_calls") != planned_calls:
            errors.append("report evaluation.planned_calls does not match cases")
        expected_case_outcomes = {
            case["id"]: (
                case["adaptive_evaluation"]["outcome"]
                if isinstance(case.get("adaptive_evaluation"), dict)
                else (
                    "pending"
                    if case.get("unscored_attempts")
                    else "fail" if case.get("failed_attempts") else "pass"
                )
            )
            for case in cases
            if isinstance(case, dict) and isinstance(case.get("id"), str)
        }
        if evaluation.get("case_outcomes") != expected_case_outcomes:
            errors.append(
                "report evaluation.case_outcomes does not match cases"
            )
        if evaluation.get("outcomes") != dict(
            Counter(expected_case_outcomes.values())
        ):
            errors.append("report evaluation.outcomes does not match cases")
        if evaluation.get("pending_case_ids") != sorted(
            case_id
            for case_id, outcome in expected_case_outcomes.items()
            if outcome == "pending"
        ):
            errors.append(
                "report evaluation.pending_case_ids does not match cases"
            )
        if evaluation.get("failed_case_ids") != sorted(
            case_id
            for case_id, outcome in expected_case_outcomes.items()
            if outcome == "fail"
        ):
            errors.append(
                "report evaluation.failed_case_ids does not match cases"
            )
        actual_calls = evaluation.get("actual_calls")
        attempt_count = sum(
            len(case.get("attempts", []))
            for case in cases
            if isinstance(case, dict) and isinstance(case.get("attempts"), list)
        )
        if isinstance(actual_calls, int) and actual_calls > attempt_count:
            errors.append(
                "report evaluation.actual_calls exceeds recorded attempts"
            )
        if report_complete and attempt_count != planned_calls:
            errors.append(
                "report evaluation.complete conflicts with attempt coverage"
            )
    summary = value.get("summary")
    if not isinstance(summary, dict):
        errors.append("report summary must be an object")
    else:
        try:
            expected_summary = summarize_cases(cases)
        except (KeyError, TypeError):
            expected_summary = None
        if expected_summary is not None and summary != expected_summary:
            errors.append("report summary does not match case attempts")
    return errors


def validate_report_v4(value: Any) -> list[str]:
    return _validate_native_report(value, REPORT_SCHEMA_VERSION)


def validate_report_v3(value: Any) -> list[str]:
    """Validate the read-only historical v3 contract."""
    return _validate_native_report(value, 3)


def normalize_legacy_identifier(value: Any) -> Any:
    if isinstance(value, str):
        mappings = {
            "tessera-eval": PRODUCER_ID,
            "tessera-core@tessera": "gloamere-eval@gloamere",
        }
        return mappings.get(value, value)
    if isinstance(value, list):
        return [normalize_legacy_identifier(item) for item in value]
    if isinstance(value, dict):
        return {
            key: normalize_legacy_identifier(item)
            for key, item in value.items()
        }
    return value


def validate_legacy_report_v2(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["legacy report must be an object"]
    errors: list[str] = []
    if value.get("schema_version") != 2:
        errors.append("legacy report schema_version must be 2")
    for field in ("generated_at", "host", "mode", "adapter"):
        if not isinstance(value.get(field), str) or not value[field]:
            errors.append(f"legacy report is missing {field}")
    repeat = value.get("repeat")
    if (
        not isinstance(repeat, int)
        or isinstance(repeat, bool)
        or repeat < 1
    ):
        errors.append("legacy report repeat must be a positive integer")
    if value.get("model") is not None and not isinstance(
        value.get("model"), str
    ):
        errors.append("legacy report model must be a string or null")
    if not isinstance(value.get("summary"), dict):
        errors.append("legacy report summary must be an object")
    for field in ("cases", "results", "tuning_candidates"):
        if not isinstance(value.get(field), list):
            errors.append(f"legacy report {field} must be an array")
    return errors


def load_report_compat(path: Path) -> tuple[dict[str, Any], bool]:
    value = read_json(path)
    if not isinstance(value, dict):
        raise ValueError("report must be an object")
    version = value.get("schema_version")
    if version == REPORT_SCHEMA_VERSION:
        return value, False
    if version == 3:
        legacy_errors = validate_report_v3(value)
        if legacy_errors:
            raise ValueError(
                "invalid legacy schema v3 report: " + "; ".join(legacy_errors)
            )
        normalized_v3 = deepcopy(value)
        normalized_v3["release_evidence_eligible"] = False
        normalized_v3["_compatibility"] = {
            "source_schema_version": 3,
            "normalized_for": PRODUCER_ID,
            "raw_report_sha256": sha256_file(path),
            "execution_provenance": value.get("execution_provenance"),
            "release_evidence_eligible": False,
        }
        return normalized_v3, True
    if version != 2:
        raise ValueError(f"unsupported report schema_version: {version}")
    legacy_errors = validate_legacy_report_v2(value)
    if legacy_errors:
        raise ValueError(
            "invalid legacy schema v2 report: " + "; ".join(legacy_errors)
        )
    normalized = normalize_legacy_identifier(deepcopy(value))
    normalized["_compatibility"] = {
        "source_schema_version": 2,
        "normalized_for": PRODUCER_ID,
        "raw_report_sha256": sha256_file(path),
        "execution_provenance": "legacy_v2",
        "release_evidence_eligible": False,
    }
    return normalized, True


def selected_cases(
    suite: dict[str, Any],
    case_ids: list[str] | None,
) -> list[dict[str, Any]]:
    cases = suite["cases"]
    if not case_ids:
        return cases
    requested = set(case_ids)
    selected = [case for case in cases if case["id"] in requested]
    missing = sorted(requested.difference(case["id"] for case in selected))
    if missing:
        raise ValueError(f"unknown case ids: {', '.join(missing)}")
    return selected


def stable_case_order(
    cases: Iterable[dict[str, Any]],
    seed: str,
) -> list[dict[str, Any]]:
    by_language: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        by_language.setdefault(str(case.get("language", "")), []).append(case)
    for language_cases in by_language.values():
        language_cases.sort(
            key=lambda case: (
                sha256_text(f"{seed}\0{case.get('id', '')}"),
                str(case.get("id", "")),
            )
        )
    ordered: list[dict[str, Any]] = []
    languages = sorted(by_language)
    offset = 0
    while True:
        added = False
        for language in languages:
            language_cases = by_language[language]
            if offset < len(language_cases):
                ordered.append(language_cases[offset])
                added = True
        if not added:
            break
        offset += 1
    return ordered


def case_focuses(case: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        sorted(
            tag.removeprefix("focus:")
            for tag in case.get("tags", [])
            if isinstance(tag, str) and tag.startswith("focus:")
        )
    )


def load_eval_policy(
    suite: dict[str, Any],
    suite_path: Path,
    explicit_path: Path | None,
    mode: str,
) -> tuple[dict[str, Any], str, str]:
    configured = suite.get("execution_policy", {}).get("policy_path")
    policy_path = explicit_path
    if policy_path is None and isinstance(configured, str) and configured:
        policy_path = Path(configured)
        if not policy_path.is_absolute():
            policy_path = suite_path.resolve().parent / policy_path
    if policy_path is None:
        configured_id = suite.get("execution_policy", {}).get("policy_id")
        if isinstance(configured_id, str) and configured_id:
            sibling = suite_path.resolve().parent / f"{configured_id}.json"
            if sibling.is_file():
                policy_path = sibling
    if policy_path is None:
        if mode != "exhaustive":
            raise ValueError(
                "--policy is required for pr/release mode unless "
                "suite.execution_policy.policy_path is set"
            )
        return (
            deepcopy(RISK_POLICY_V2),
            sha256_object(RISK_POLICY_V2),
            "builtin:risk-tiered-v2",
        )
    resolved = policy_path.resolve()
    try:
        value = read_json(resolved)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read evaluation policy: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("evaluation policy must be a JSON object")
    policy_id = value.get("id", value.get("policy_id"))
    if policy_id != RISK_POLICY_V2["id"]:
        raise ValueError(
            f"evaluation policy id must be {RISK_POLICY_V2['id']}"
        )
    if value.get("suite_id") not in {None, suite.get("suite_id")}:
        raise ValueError("evaluation policy suite_id does not match eval suite")
    modes = value.get("modes")
    if not isinstance(modes, dict) or not isinstance(modes.get(mode), dict):
        raise ValueError(f"evaluation policy does not define mode {mode}")
    try:
        source = resolved.relative_to(suite_path.resolve().parent).as_posix()
    except ValueError:
        source = resolved.name
    return value, sha256_file(resolved), source


def policy_case_ids(
    cases: list[dict[str, Any]],
    requested: Any,
    label: str,
) -> list[dict[str, Any]]:
    if requested is None:
        return []
    if not isinstance(requested, list) or any(
        not isinstance(case_id, str) or not case_id for case_id in requested
    ):
        raise ValueError(f"evaluation policy {label} must be a string array")
    by_id = {case["id"]: case for case in cases}
    unknown = [case_id for case_id in requested if case_id not in by_id]
    if unknown:
        raise ValueError(
            f"evaluation policy {label} has unknown cases: "
            + ", ".join(sorted(set(unknown)))
        )
    if len(requested) != len(set(requested)):
        raise ValueError(f"evaluation policy {label} contains duplicates")
    return [by_id[case_id] for case_id in requested]


def risk_selected_cases(
    suite: dict[str, Any],
    mode: str,
    case_ids: list[str] | None,
    rotation_key: str,
    policy: dict[str, Any],
    changed_skills: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, str], str]:
    explicit = selected_cases(suite, case_ids)
    if case_ids or mode == "exhaustive":
        role = "explicit" if case_ids else "exhaustive"
        reason = (
            "explicit --case selection"
            if case_ids
            else "all suite cases selected for exhaustive coverage"
        )
        return explicit, {case["id"]: role for case in explicit}, reason

    suite_sha = sha256_object(suite)
    cases = list(suite["cases"])
    selected: list[dict[str, Any]] = []
    roles: dict[str, str] = {}
    mode_policy = policy.get("modes", {}).get(mode, {})
    exact_case_ids = mode_policy.get("case_ids")
    if exact_case_ids is not None:
        exact = policy_case_ids(cases, exact_case_ids, f"modes.{mode}.case_ids")
        return (
            exact,
            {case["id"]: "policy-explicit" for case in exact},
            f"{policy.get('id', policy.get('policy_id'))} "
            f"{mode} policy-explicit case set",
        )

    def add(pool: Iterable[dict[str, Any]], amount: int, role: str, seed: str) -> None:
        for case in stable_case_order(pool, f"{suite_sha}:{seed}")[:amount]:
            case_id = case["id"]
            if case_id in roles:
                continue
            selected.append(case)
            roles[case_id] = role

    focuses = sorted({focus for case in cases for focus in case_focuses(case)})
    unknown_changed = sorted(set(changed_skills or []).difference(focuses))
    if unknown_changed:
        raise ValueError(
            "unknown --changed-skill values: " + ", ".join(unknown_changed)
        )
    if mode == "pr":
        sentinel_ids = mode_policy.get("sentinel_case_ids")
        if sentinel_ids is not None:
            sentinels = policy_case_ids(
                cases,
                sentinel_ids,
                "modes.pr.sentinel_case_ids",
            )
            return (
                sentinels,
                {case["id"]: "sentinel" for case in sentinels},
                f"{policy.get('id', policy.get('policy_id'))} "
                "PR policy sentinels",
            )
        configured_per_focus = mode_policy.get(
            "per_focus_case_ids",
            mode_policy.get("per_changed_case_ids"),
        )
        if configured_per_focus is not None:
            if not isinstance(configured_per_focus, dict):
                raise ValueError(
                    "evaluation policy PR per-focus cases must be an object"
                )
            active_focuses = changed_skills or focuses
            for focus in active_focuses:
                configured_cases = policy_case_ids(
                    cases,
                    configured_per_focus.get(focus),
                    f"modes.pr.per_focus_case_ids.{focus}",
                )
                for case in configured_cases[:4]:
                    if case["id"] not in roles:
                        selected.append(case)
                        roles[case["id"]] = f"sentinel:{focus}"
                    if len(selected) >= 12:
                        break
                if len(selected) >= 12:
                    break
            return (
                selected,
                roles,
                f"{policy.get('id', policy.get('policy_id'))} PR sentinels "
                f"for {len(active_focuses)} changed focus group(s)",
            )
        per_focus = {
            focus: stable_case_order(
                (case for case in cases if focus in case_focuses(case)),
                f"{suite_sha}:pr:{focus}",
            )[:4]
            for focus in focuses
        }
        for offset in range(4):
            for focus in focuses:
                focus_cases = per_focus[focus]
                if offset < len(focus_cases):
                    add(
                        [focus_cases[offset]],
                        1,
                        f"sentinel:{focus}",
                        f"pr:{focus}:{offset}",
                    )
                    if len(selected) >= 12:
                        break
            if len(selected) >= 12:
                break
        if not selected:
            add(cases, 12, "sentinel", "pr:fallback")
        return (
            selected,
            roles,
            "risk-tiered PR sentinels (up to four per focus, hard cap 12)",
        )

    configured_fixed = policy_case_ids(
        cases,
        mode_policy.get("fixed_case_ids"),
        "modes.release.fixed_case_ids",
    )
    fixed_pool = configured_fixed or [
        case
        for case in cases
        if "kind:positive" in case.get("tags", [])
        or "risk:high" in case.get("tags", [])
    ]
    rotating_value = mode_policy.get("rotating_case_ids")
    if isinstance(rotating_value, dict):
        rotating_value = rotating_value.get(
            rotation_key,
            rotating_value.get("default"),
        )
    configured_boundary = policy_case_ids(
        cases,
        rotating_value,
        "modes.release.rotating_case_ids",
    )
    boundary_pool = configured_boundary or [
        case
        for case in cases
        if "kind:adjacent-negative" in case.get("tags", [])
        and "risk:high" not in case.get("tags", [])
    ]
    configured_multi = policy_case_ids(
        cases,
        mode_policy.get("multi_intent_case_ids"),
        "modes.release.multi_intent_case_ids",
    )
    multi_pool = configured_multi or [
        case for case in cases if "kind:multi-intent" in case.get("tags", [])
    ]
    fixed_count = int(mode_policy.get("fixed_count", 6))
    rotating_count = int(mode_policy.get("rotating_count", 6))
    multi_count = int(mode_policy.get("multi_intent_count", 4))
    per_focus_count = int(mode_policy.get("per_focus_count", 4))
    maximum_cases = int(mode_policy.get("maximum_cases", 34))
    add(
        fixed_pool,
        fixed_count,
        "fixed-positive-or-high-risk",
        "release:fixed",
    )
    add(
        boundary_pool,
        rotating_count,
        "rotating-adjacent-boundary",
        f"release:boundary:{rotation_key}",
    )
    add(
        multi_pool,
        multi_count,
        "cross-skill-multi-intent",
        "release:multi",
    )
    configured_per_focus = mode_policy.get(
        "per_focus_case_ids",
        mode_policy.get("per_changed_case_ids"),
    )
    if configured_per_focus is not None and not isinstance(
        configured_per_focus,
        dict,
    ):
        raise ValueError(
            "evaluation policy release per-focus cases must be an object"
        )
    active_release_focuses = changed_skills or []
    for focus in active_release_focuses:
        configured_focus_cases = (
            policy_case_ids(
                cases,
                configured_per_focus.get(focus),
                f"modes.release.per_focus_case_ids.{focus}",
            )
            if isinstance(configured_per_focus, dict)
            else []
        )
        remaining = configured_focus_cases or [
            case
            for case in cases
            if focus in case_focuses(case) and case["id"] not in roles
        ]
        add(
            remaining,
            per_focus_count,
            f"targeted:{focus}",
            f"release:targeted:{focus}",
        )
    if not selected:
        add(
            cases,
            maximum_cases,
            "release-fallback",
            "release:fallback",
        )
    selected = selected[:maximum_cases]
    roles = {case["id"]: roles[case["id"]] for case in selected}
    return (
        selected,
        roles,
        f"{policy.get('id', policy.get('policy_id'))} release sample: "
        f"{fixed_count} fixed, "
        f"{rotating_count} rotating boundary, {multi_count} multi-intent, "
        f"then up to {per_focus_count} per focus "
        f"for {len(active_release_focuses)} changed focus group(s) "
        f"(hard cap {maximum_cases})",
    )


def parse_shard(value: str | None) -> tuple[int, int] | None:
    if value is None:
        return None
    match = re.fullmatch(r"([1-9][0-9]*)/([1-9][0-9]*)", value)
    if match is None:
        raise ValueError("--shard must use the 1-based INDEX/TOTAL form")
    index, total = (int(match.group(1)), int(match.group(2)))
    if index > total:
        raise ValueError("--shard INDEX cannot be greater than TOTAL")
    return index, total


def apply_shard(
    cases: list[dict[str, Any]],
    shard: tuple[int, int] | None,
) -> list[dict[str, Any]]:
    if shard is None:
        return cases
    index, total = shard
    return [
        case
        for offset, case in enumerate(cases)
        if offset % total == index - 1
    ]


def default_journal_path(
    args: argparse.Namespace,
    suite_sha: str,
    target_lock_sha: str,
) -> Path:
    if args.journal is not None:
        return args.journal
    if args.output is not None:
        return Path(f"{args.output}.journal.jsonl")
    unique = f"{os.getpid()}-{time.time_ns()}"
    return (
        Path(tempfile.gettempdir())
        / (
            f"gloamere-eval-{suite_sha[:10]}-{target_lock_sha[:10]}-"
            f"{args.mode}-{unique}.journal.jsonl"
        )
    )


def journal_identity(
    suite_sha: str,
    target_lock_sha: str,
    policy_sha: str,
    mode: str,
    rotation_key: str,
    selection_sha: str,
    execution_provenance: str,
    model: str | None,
    adapter_signature: str | None,
    commit: str,
) -> dict[str, Any]:
    return {
        "suite_sha256": suite_sha,
        "target_lock_sha256": target_lock_sha,
        "policy_sha256": policy_sha,
        "mode": mode,
        "rotation_key": rotation_key,
        "selection_sha256": selection_sha,
        "execution_provenance": execution_provenance,
        "model": model,
        "adapter_signature": adapter_signature,
        "commit": commit,
        "runner_sha256": sha256_file(Path(__file__)),
    }


def load_journal(
    path: Path,
    identity: dict[str, Any],
) -> tuple[
    dict[tuple[str, int, int], dict[str, Any]],
    set[tuple[str, int, int]],
    str | None,
]:
    attempts: dict[tuple[str, int, int], dict[str, Any]] = {}
    consumed_call_keys: set[tuple[str, int, int]] = set()
    codex_version_value: str | None = None
    observed_versions: set[str] = set()
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"journal line {line_number} is not valid JSON: {exc}"
            ) from exc
        if not isinstance(record, dict) or record.get("journal_version") != (
            JOURNAL_SCHEMA_VERSION
        ):
            raise ValueError(f"journal line {line_number} has an invalid version")
        if record.get("identity") != identity:
            raise ValueError(
                f"journal line {line_number} does not match current inputs/policy"
            )
        case_id = record.get("case_id")
        batch = record.get("batch_id")
        attempt_id = record.get("attempt")
        attempt = record.get("attempt_data")
        if (
            not isinstance(case_id, str)
            or not isinstance(batch, int)
            or isinstance(batch, bool)
            or not isinstance(attempt_id, int)
            or isinstance(attempt_id, bool)
            or not isinstance(attempt, dict)
        ):
            raise ValueError(f"journal line {line_number} is malformed")
        key = (case_id, batch, attempt_id)
        previous = attempts.get(key)
        supersedes = record.get("supersedes") is True
        if previous is not None and previous != attempt and not supersedes:
            raise ValueError(
                f"journal contains conflicting records for {case_id} "
                f"batch={batch} attempt={attempt_id}"
            )
        if record.get("call_consumed") is True:
            consumed_call_keys.add(key)
        attempts[key] = attempt
        version = record.get("codex_version")
        if isinstance(version, str) and version:
            codex_version_value = version
            observed_versions.add(version)
    if len(observed_versions) > 1:
        raise ValueError(
            "journal mixes incompatible Codex CLI/adapter versions"
        )
    return attempts, consumed_call_keys, codex_version_value


def append_attempt_journal(
    path: Path,
    identity: dict[str, Any],
    case_id: str,
    attempt: dict[str, Any],
    call_consumed: bool,
    codex_version_value: str | None,
    supersedes: bool = False,
) -> None:
    append_journal_record(
        path,
        {
            "journal_version": JOURNAL_SCHEMA_VERSION,
            "recorded_at": utc_now(),
            "identity": identity,
            "case_id": case_id,
            "batch_id": attempt["batch_id"],
            "attempt": attempt["attempt"],
            "call_consumed": call_consumed,
            "supersedes": supersedes,
            "codex_version": codex_version_value,
            "attempt_data": attempt,
        },
    )


def command_inspect(args: argparse.Namespace) -> int:
    catalog, source, catalog_error, version = load_plugin_catalog(args.catalog)
    lock = inspect_plugins(
        args.plugin_root,
        args.marketplace,
        catalog,
        source,
        catalog_error,
        version,
    )
    write_or_print(lock, args.output)
    return 1 if lock["errors"] or lock["conflicts"] else 0


def command_lint(args: argparse.Namespace) -> int:
    errors: list[str] = []
    warnings: list[str] = []
    legacy_report = False
    release_evidence_eligible: bool | None = None
    suite: dict[str, Any] | None = None
    target_lock: dict[str, Any] | None = None
    if args.suite:
        try:
            raw_suite = read_json(args.suite)
            if isinstance(raw_suite, dict):
                suite = raw_suite
            errors.extend(validate_suite(raw_suite))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"cannot read eval suite: {exc}")
    if args.target_lock:
        try:
            raw_lock = read_json(args.target_lock)
            if isinstance(raw_lock, dict):
                target_lock = raw_lock
            errors.extend(validate_target_lock(raw_lock, verify_files=True))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"cannot read target lock: {exc}")
    if suite is not None and target_lock is not None:
        errors.extend(validate_suite_binding(suite, target_lock))
    if args.report:
        try:
            report, legacy_report = load_report_compat(args.report)
            if legacy_report:
                warnings.append(
                    "legacy schema v2/v3 report was read through the "
                    "compatibility mapper and is never release evidence"
                )
                release_evidence_eligible = False
            else:
                errors.extend(validate_report_v4(report))
                release_evidence_eligible = bool(
                    report.get("release_evidence_eligible")
                )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"cannot read report: {exc}")
    if not any((args.suite, args.target_lock, args.report)):
        errors.append("lint requires --suite, --target-lock, or --report")
    result = {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "legacy_report": legacy_report,
        "release_evidence_eligible": release_evidence_eligible,
    }
    write_or_print(result, args.output)
    return 0 if not errors else 1


def command_native(args: argparse.Namespace) -> int:
    try:
        suite = read_json(args.suite)
        target_lock = read_json(args.target_lock)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot load eval inputs: {exc}", file=sys.stderr)
        return 2
    if not isinstance(suite, dict) or not isinstance(target_lock, dict):
        print("eval inputs must be JSON objects", file=sys.stderr)
        return 2
    suite_errors = validate_suite(suite)
    if suite_errors:
        print("eval suite validation failed:", file=sys.stderr)
        for error in suite_errors:
            print(f"- {error}", file=sys.stderr)
        return 2
    try:
        policy, policy_sha, policy_source = load_eval_policy(
            suite,
            args.suite,
            args.policy,
            args.mode,
        )
        retry_policy = retry_policy_settings(policy)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.mode != "exhaustive" and args.repeat not in {None, 1}:
        print("--repeat is fixed at 1 in pr/release mode", file=sys.stderr)
        return 2
    repeat_per_batch = (
        (
            args.repeat
            if args.repeat is not None
            else suite["execution_policy"]["repeat"]
        )
        if args.mode == "exhaustive"
        else 1
    )
    if repeat_per_batch < 1 or repeat_per_batch > 10:
        print("--repeat must be between 1 and 10", file=sys.stderr)
        return 2
    independent_batches = (
        suite["execution_policy"]["independent_batches"]
        if args.mode == "exhaustive"
        else 1
    )
    if args.timeout < 1:
        print("--timeout must be greater than 0", file=sys.stderr)
        return 2
    try:
        shard = parse_shard(args.shard)
        unsharded_cases, selection_roles, selection_reason = (
            risk_selected_cases(
                suite,
                args.mode,
                args.case_ids,
                args.rotation_key,
                policy,
                args.changed_skills,
            )
        )
        cases = apply_shard(unsharded_cases, shard)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not cases:
        print("the selected shard contains no cases", file=sys.stderr)
        return 2
    selection_roles = {
        case["id"]: selection_roles[case["id"]] for case in cases
    }

    if args.workspace is not None and independent_batches > 1:
        print(
            "--workspace cannot be reused across independent batches; "
            "use the default isolated workspaces or a suite with one batch",
            file=sys.stderr,
        )
        return 2

    planned_calls = len(cases) * repeat_per_batch * independent_batches
    unsharded_initial_calls = (
        len(unsharded_cases) * repeat_per_batch * independent_batches
    )
    mode_policy = policy.get("modes", {}).get(args.mode, {})
    configured_initial_calls = mode_policy.get("initial_calls")
    if configured_initial_calls == "planned":
        configured_initial_calls = unsharded_initial_calls
    if configured_initial_calls is not None and (
        not isinstance(configured_initial_calls, int)
        or isinstance(configured_initial_calls, bool)
        or configured_initial_calls < 1
    ):
        print(
            f"evaluation policy {args.mode}.initial_calls is invalid",
            file=sys.stderr,
        )
        return 2
    if (
        args.mode == "exhaustive"
        and args.case_ids is None
        and configured_initial_calls is not None
        and configured_initial_calls != unsharded_initial_calls
    ):
        print(
            "evaluation policy exhaustive.initial_calls does not match "
            f"the {unsharded_initial_calls}-case initial execution grid",
            file=sys.stderr,
        )
        return 2
    initial_call_requirement = (
        configured_initial_calls
        if isinstance(configured_initial_calls, int)
        and args.case_ids is None
        else unsharded_initial_calls
    )
    adaptive_retry_enabled = args.mode in {"pr", "release"} or (
        args.mode == "exhaustive"
        and repeat_per_batch == 1
        and independent_batches == 1
    )
    maximum_adaptive_attempts = (
        max(
            retry_policy["unexpected_attempts"],
            1 + retry_policy["infrastructure_retry_count"],
        )
        if adaptive_retry_enabled
        else repeat_per_batch
    )
    execution_strategy = (
        "initial-coverage-then-adaptive-retry"
        if args.mode == "exhaustive" and adaptive_retry_enabled
        else "adaptive-retry"
        if adaptive_retry_enabled
        else "fixed-grid"
    )
    configured_budget = mode_policy.get(
        "max_calls",
        mode_policy.get("default_max_calls"),
    )
    if (
        args.mode == "exhaustive"
        and isinstance(configured_budget, int)
        and not isinstance(configured_budget, bool)
        and configured_budget < initial_call_requirement
    ):
        print(
            "evaluation policy exhaustive.max_calls is below "
            "exhaustive.initial_calls",
            file=sys.stderr,
        )
        return 2
    if args.max_calls is not None:
        max_calls = args.max_calls
    elif isinstance(configured_budget, int) and not isinstance(
        configured_budget,
        bool,
    ):
        max_calls = configured_budget
    elif (
        args.mode == "exhaustive"
        and configured_budget == "planned+adaptive"
    ):
        max_calls = unsharded_initial_calls + min(
            18 if adaptive_retry_enabled else 0,
            unsharded_initial_calls * 2,
        )
    else:
        max_calls = (
            12
            if args.mode == "pr"
            else 40 if args.mode == "release" else planned_calls
        )
    if max_calls < 1:
        print("--max-calls must be greater than 0", file=sys.stderr)
        return 2
    quality_policy = policy.get("quality")
    quality_per_changed_skill = (
        quality_policy.get("release_cases_per_changed_skill", 0)
        if isinstance(quality_policy, dict)
        else 0
    )
    if (
        not isinstance(quality_per_changed_skill, int)
        or isinstance(quality_per_changed_skill, bool)
        or quality_per_changed_skill < 0
    ):
        print(
            "evaluation policy quality.release_cases_per_changed_skill "
            "is invalid",
            file=sys.stderr,
        )
        return 2
    quality_reserved_calls = (
        quality_per_changed_skill * len(set(args.changed_skills or []))
        if args.mode == "release"
        else 0
    )
    routing_max_calls = max_calls - quality_reserved_calls
    if routing_max_calls < 1:
        print(
            "quality call reservation leaves no routing budget",
            file=sys.stderr,
        )
        return 2
    retry_call_capacity = max(
        0,
        routing_max_calls - initial_call_requirement,
    )
    if execution_strategy == "initial-coverage-then-adaptive-retry":
        selection_reason += (
            f"; complete all {initial_call_requirement} initial calls "
            f"before adaptive retries (capacity {retry_call_capacity})"
        )
    if quality_reserved_calls:
        selection_reason += (
            f"; reserving {quality_reserved_calls} of {max_calls} calls "
            "for output-quality evaluation"
        )

    execution_provenance = (
        "fixture_adapter"
        if args.adapter_executable or args.catalog is not None
        else "codex_cli"
    )
    adapter_signature = (
        sha256_object(
            {
                "adapter_executable": args.adapter_executable,
                "adapter_args": args.adapter_arg,
                "catalog_sha256": (
                    sha256_file(args.catalog)
                    if args.catalog is not None and args.catalog.is_file()
                    else None
                ),
            }
        )
        if execution_provenance == "fixture_adapter"
        else None
    )
    commit_value = repository_commit()
    suite_sha = sha256_file(args.suite)
    target_lock_sha = sha256_object(target_lock)
    selection_sha = sha256_object(
        {
            "case_ids": [case["id"] for case in unsharded_cases],
            "repeat": repeat_per_batch,
            "independent_batches": independent_batches,
        }
    )
    identity = journal_identity(
        suite_sha,
        target_lock_sha,
        policy_sha,
        args.mode,
        args.rotation_key,
        selection_sha,
        execution_provenance,
        args.model,
        adapter_signature,
        commit_value,
    )
    journal_path = default_journal_path(
        args,
        suite_sha,
        target_lock_sha,
    )
    if args.finalize and args.dry_run:
        print("--finalize and --dry-run cannot be combined", file=sys.stderr)
        return 2
    resume_requested = args.resume or args.finalize
    if resume_requested and not journal_path.is_file():
        print(f"journal does not exist: {journal_path}", file=sys.stderr)
        return 2
    if (
        not resume_requested
        and not args.dry_run
        and journal_path.exists()
    ):
        print(
            f"journal already exists; use --resume or another --journal: "
            f"{journal_path}",
            file=sys.stderr,
        )
        return 2

    resumed_attempts: dict[tuple[str, int, int], dict[str, Any]] = {}
    consumed_call_keys: set[tuple[str, int, int]] = set()
    resumed_calls = 0
    resumed_codex_version: str | None = None
    if resume_requested:
        try:
            (
                resumed_attempts,
                consumed_call_keys,
                resumed_codex_version,
            ) = load_journal(journal_path, identity)
        except (OSError, ValueError) as exc:
            print(f"cannot resume journal: {exc}", file=sys.stderr)
            return 2
    expected_keys = {
        (case["id"], batch, attempt)
        for case in cases
        for batch in range(1, independent_batches + 1)
        for attempt in range(1, repeat_per_batch + 1)
    }
    selected_universe_keys = {
        (case["id"], batch, attempt)
        for case in cases
        for batch in range(1, independent_batches + 1)
        for attempt in range(
            1,
            (
                maximum_adaptive_attempts
                if adaptive_retry_enabled
                else repeat_per_batch
            )
            + 1,
        )
    }
    unsharded_keys = {
        (case["id"], batch, attempt)
        for case in unsharded_cases
        for batch in range(1, independent_batches + 1)
        for attempt in range(
            1,
            (
                maximum_adaptive_attempts
                if adaptive_retry_enabled
                else repeat_per_batch
            )
            + 1,
        )
    }
    selected_initial_keys = {
        (case["id"], batch, attempt)
        for case in cases
        for batch in range(1, independent_batches + 1)
        for attempt in range(1, repeat_per_batch + 1)
    }
    unsharded_initial_keys = {
        (case["id"], batch, attempt)
        for case in unsharded_cases
        for batch in range(1, independent_batches + 1)
        for attempt in range(1, repeat_per_batch + 1)
    }
    unknown_journal_keys = sorted(
        set(resumed_attempts).difference(unsharded_keys)
    )
    if unknown_journal_keys:
        print(
            "journal contains attempts outside the selected execution grid",
            file=sys.stderr,
        )
        return 2
    resumed_calls = len(
        consumed_call_keys.intersection(selected_universe_keys)
    )
    journal_total_calls = len(consumed_call_keys)
    if journal_total_calls > routing_max_calls:
        print(
            "journal call count already exceeds the routing budget",
            file=sys.stderr,
        )
        return 2
    replaceable_keys: set[tuple[str, int, int]] = set()
    if resume_requested and not args.finalize:
        replaceable_keys = {
            key
            for key, attempt in resumed_attempts.items()
            if key in selected_universe_keys
            and key not in consumed_call_keys
            and attempt.get("evidence_status")
            in {"unavailable", "identity_conflict"}
        }
        for key in replaceable_keys:
            resumed_attempts.pop(key, None)

    if args.dry_run:
        plan = {
            "schema_version": 1,
            "command": "native-plan",
            "mode": args.mode,
            "policy_id": policy.get("id", policy.get("policy_id")),
            "policy_sha256": policy_sha,
            "policy_source": policy_source,
            "suite_sha256": suite_sha,
            "target_lock_sha256": target_lock_sha,
            "selection_reason": selection_reason,
            "selected_case_ids": [case["id"] for case in cases],
            "selection": selection_roles,
            "changed_skills": sorted(set(args.changed_skills or [])),
            "rotation_key": args.rotation_key,
            "shard": (
                {"index": shard[0], "total": shard[1]}
                if shard is not None
                else None
            ),
            "repeat": repeat_per_batch,
            "independent_batches": independent_batches,
            "planned_calls": planned_calls,
            "initial_planned_calls": initial_call_requirement,
            "execution_strategy": execution_strategy,
            "max_calls": max_calls,
            "hard_max_calls": max_calls,
            "routing_max_calls": routing_max_calls,
            "quality_reserved_calls": quality_reserved_calls,
            "retry_call_capacity": retry_call_capacity,
            "adaptive_retry_limit": maximum_adaptive_attempts,
            "resumable_attempts": len(
                set(resumed_attempts).intersection(selected_universe_keys)
            ),
            "resumed_calls": resumed_calls,
            "model_calls": 0,
        }
        write_or_print(plan, args.output)
        return 0

    print(f"journal: {journal_path.resolve()}", file=sys.stderr, flush=True)
    attempts_by_case: dict[str, list[dict[str, Any]]] = {
        case["id"]: [] for case in cases
    }
    for key, attempt_data in sorted(resumed_attempts.items()):
        case_id, _, _ = key
        if key in selected_universe_keys:
            attempts_by_case[case_id].append(attempt_data)
    preflight_results: list[tuple[int, str, list[str], str]] = []
    codex_version_value: str | None = resumed_codex_version
    actual_calls = resumed_calls
    total_calls = journal_total_calls
    new_calls = 0
    budget_exhausted = False

    if args.finalize:
        print(
            f"finalizing "
            f"{len(set(resumed_attempts).intersection(expected_keys))}/"
            f"{len(expected_keys)} "
            "journaled attempts without model calls",
            file=sys.stderr,
        )

    execution_phases = (
        ("initial", "retry")
        if execution_strategy
        == "initial-coverage-then-adaptive-retry"
        else ("adaptive",)
        if adaptive_retry_enabled
        else ("fixed",)
    )

    def pending_attempt_numbers(
        case_id: str,
        batch: int,
        phase: str,
    ) -> list[int]:
        existing = sorted(
            (
                attempt
                for (existing_case_id, batch_id, _), attempt in (
                    resumed_attempts.items()
                )
                if existing_case_id == case_id and batch_id == batch
            ),
            key=lambda item: item["attempt"],
        )
        if phase == "initial" or phase == "fixed":
            desired_numbers = range(1, repeat_per_batch + 1)
        else:
            desired = desired_adaptive_attempts(
                existing,
                retry_policy,
                adaptive_retry_enabled,
            )
            desired_numbers = range(1, desired + 1)
        return [
            attempt_number
            for attempt_number in desired_numbers
            if (case_id, batch, attempt_number) not in resumed_attempts
            and not (
                phase == "retry"
                and attempt_number <= repeat_per_batch
            )
        ]

    for execution_phase in execution_phases:
        if args.finalize or budget_exhausted:
            break
        if (
            execution_phase == "retry"
            and not unsharded_initial_keys.issubset(resumed_attempts)
        ):
            # exhaustive 的复验必须等待完整初始覆盖；分片运行也不能提前消费
            # 其他分片尚未完成的 102 例初始预算。
            break
        for batch in range(1, independent_batches + 1):
            pending_by_case = {
                case["id"]: pending_attempt_numbers(
                    case["id"],
                    batch,
                    execution_phase,
                )
                for case in cases
            }
            if not any(pending_by_case.values()):
                continue
            catalog, _, _, catalog_version_value = load_plugin_catalog(
                args.catalog
            )
            codex_version_value = (
                catalog_version_value or codex_version_value
            )
            preflight_status, preflight_reasons = assess_native_preflight(
                suite,
                target_lock,
                catalog,
            )
            preflight_results.append(
                (
                    batch,
                    preflight_status,
                    preflight_reasons,
                    f"{execution_phase}-preflight",
                )
            )
            if preflight_status != "verified":
                for case in cases:
                    for attempt_number in pending_by_case[case["id"]]:
                        key = (case["id"], batch, attempt_number)
                        attempt_data = preflight_attempt(
                            case,
                            preflight_status,
                            preflight_reasons,
                            attempt_number,
                            args.include_prompts,
                            batch,
                        )
                        attempts_by_case[case["id"]].append(attempt_data)
                        resumed_attempts[key] = attempt_data
                        append_attempt_journal(
                            journal_path,
                            identity,
                            case["id"],
                            attempt_data,
                            False,
                            codex_version_value,
                            supersedes=key in replaceable_keys,
                        )
                continue

            temporary_workspace: tempfile.TemporaryDirectory[str] | None = None
            if args.workspace is None:
                temporary_workspace = tempfile.TemporaryDirectory(
                    prefix=(
                        "gloamere-skill-eval-"
                        f"{execution_phase}-batch-{batch}-"
                    )
                )
                workspace = Path(temporary_workspace.name)
            else:
                workspace = args.workspace.resolve()
            batch_new_keys: list[tuple[str, int, int]] = []
            try:
                for case_index, case in enumerate(cases, start=1):
                    while True:
                        pending_numbers = pending_attempt_numbers(
                            case["id"],
                            batch,
                            execution_phase,
                        )
                        if not pending_numbers:
                            break
                        attempt_number = pending_numbers[0]
                        key = (case["id"], batch, attempt_number)
                        if total_calls >= routing_max_calls:
                            budget_exhausted = True
                            break
                        print(
                            f"[{execution_phase}] "
                            f"[batch {batch}/{independent_batches}] "
                            f"[{case_index}/{len(cases)}] {case['id']} "
                            f"attempt={attempt_number}",
                            file=sys.stderr,
                            flush=True,
                        )
                        prompt = build_native_prompt(case["prompt"])
                        if args.adapter_executable:
                            host_result = run_adapter(
                                args.adapter_executable,
                                args.adapter_arg,
                                prompt,
                                args.timeout,
                                workspace,
                            )
                        else:
                            host_result = run_codex(
                                prompt,
                                args.timeout,
                                workspace,
                                args.model,
                            )
                        codex_version_value = (
                            host_result.codex_version
                            or codex_version_value
                        )
                        attempt_data = classify_native_attempt(
                            case,
                            suite,
                            target_lock,
                            host_result,
                            attempt_number,
                            args.include_prompts,
                            batch,
                        )
                        attempts_by_case[case["id"]].append(attempt_data)
                        resumed_attempts[key] = attempt_data
                        batch_new_keys.append(key)
                        actual_calls += 1
                        total_calls += 1
                        new_calls += 1
                        consumed_call_keys.add(key)
                        append_attempt_journal(
                            journal_path,
                            identity,
                            case["id"],
                            attempt_data,
                            True,
                            codex_version_value,
                            supersedes=key in replaceable_keys,
                        )
                    if budget_exhausted:
                        break
            finally:
                if temporary_workspace is not None:
                    temporary_workspace.cleanup()

            if not batch_new_keys:
                if budget_exhausted:
                    break
                continue
            post_catalog, _, _, post_catalog_version = load_plugin_catalog(
                args.catalog
            )
            codex_version_value = (
                post_catalog_version or codex_version_value
            )
            postflight_status, postflight_reasons = assess_native_preflight(
                suite,
                target_lock,
                post_catalog,
            )
            preflight_results.append(
                (
                    batch,
                    postflight_status,
                    postflight_reasons,
                    f"{execution_phase}-postflight",
                )
            )
            if postflight_status != "verified":
                # 根因：批次运行期间身份可能漂移；修复：把已落 journal 的该批
                # 记录追加一条 supersedes 冲突记录，既保留调用历史又不伪造 verified。
                for case_id, batch_id, attempt_number in batch_new_keys:
                    case = next(
                        item for item in cases if item["id"] == case_id
                    )
                    invalidated = preflight_attempt(
                        case,
                        postflight_status,
                        postflight_reasons,
                        attempt_number,
                        args.include_prompts,
                        batch_id,
                    )
                    resumed_attempts[
                        (case_id, batch_id, attempt_number)
                    ] = invalidated
                    attempts_by_case[case_id] = [
                        invalidated
                        if (
                            item.get("batch_id"),
                            item.get("attempt"),
                        )
                        == (batch_id, attempt_number)
                        else item
                        for item in attempts_by_case[case_id]
                    ]
                    append_attempt_journal(
                        journal_path,
                        identity,
                        case_id,
                        invalidated,
                        False,
                        codex_version_value,
                        supersedes=True,
                    )
            if budget_exhausted:
                break

    priority = {"verified": 0, "unavailable": 1, "identity_conflict": 2}
    preflight_status = max(
        (status for _, status, _, _ in preflight_results),
        key=lambda status: priority.get(status, 3),
        default="unavailable",
    )
    preflight_reasons = sorted(
        {
            f"batch {batch} {phase}: {reason}"
            for batch, status, reasons, phase in preflight_results
            if status != "verified"
            for reason in reasons
        }
    )
    if not preflight_results:
        recorded_statuses = {
            attempt.get("evidence_status")
            for key, attempt in resumed_attempts.items()
            if key in selected_universe_keys
            if isinstance(attempt.get("evidence_status"), str)
        }
        preflight_status = max(
            recorded_statuses,
            key=lambda status: priority.get(status, 3),
            default="verified",
        )
        preflight_reasons = sorted(
            {
                str(attempt.get("reason"))
                for key, attempt in resumed_attempts.items()
                if key in selected_universe_keys
                if attempt.get("evidence_status") != "verified"
                and attempt.get("reason")
            }
        )
    for case_id in attempts_by_case:
        attempts_by_case[case_id].sort(
            key=lambda item: (item["batch_id"], item["attempt"])
        )
    adaptive_by_case: dict[str, dict[str, Any]] = {}
    required_keys = set(expected_keys)
    if adaptive_retry_enabled:
        for case in cases:
            case_attempts = attempts_by_case[case["id"]]
            expected_attempt_count = desired_adaptive_attempts(
                case_attempts,
                retry_policy,
                True,
            )
            case_budget_exhausted = (
                len(case_attempts) < expected_attempt_count
                and total_calls >= routing_max_calls
            )
            adaptive_by_case[case["id"]] = adaptive_case_evaluation(
                case_attempts,
                expected_attempt_count,
                retry_policy,
                case_budget_exhausted,
                True,
            )
            required_keys.update(
                (case["id"], 1, attempt_number)
                for attempt_number in range(1, expected_attempt_count + 1)
            )
    initial_phase_complete = unsharded_initial_keys.issubset(
        resumed_attempts
    )
    complete = required_keys.issubset(resumed_attempts) and (
        execution_strategy
        != "initial-coverage-then-adaptive-retry"
        or initial_phase_complete
    )
    aggregates = [
        aggregate_case(
            case,
            attempts_by_case[case["id"]],
            repeat_per_batch,
            independent_batches,
            adaptive_by_case.get(case["id"]),
        )
        for case in cases
    ]
    report = build_report(
        suite,
        target_lock,
        aggregates,
        repeat_per_batch,
        args.timeout,
        args.model,
        codex_version_value,
        args.include_prompts,
        preflight_status,
        preflight_reasons,
        execution_provenance,
        mode=args.mode,
        selection_reason=selection_reason,
        selection_roles=selection_roles,
        rotation_key=args.rotation_key,
        max_calls=max_calls,
        routing_max_calls=routing_max_calls,
        quality_reserved_calls=quality_reserved_calls,
        actual_calls=actual_calls,
        resumed_calls=resumed_calls,
        new_calls=new_calls,
        shard=shard,
        complete=complete,
        independent_batches=independent_batches,
        policy=policy,
        policy_sha256=policy_sha,
        policy_source=policy_source,
        changed_skills=args.changed_skills,
        commit=commit_value,
        suite_sha256=suite_sha,
        execution_strategy=execution_strategy,
        initial_phase_complete=initial_phase_complete,
        initial_actual_calls=len(
            consumed_call_keys.intersection(selected_initial_keys)
        ),
    )
    report_errors = validate_report_v4(report)
    if report_errors:
        print("internal report validation failed:", file=sys.stderr)
        for error in report_errors:
            print(f"- {error}", file=sys.stderr)
        return 2
    write_or_print(report, args.output)
    summary = report["summary"]
    if not complete:
        return 1
    if adaptive_retry_enabled:
        outcomes = report["evaluation"]["case_outcomes"].values()
        return 0 if all(outcome == "pass" for outcome in outcomes) else 1
    if summary["execution_errors"] or summary["unavailable_attempts"]:
        return 2
    if summary["scored_attempts"] != summary["attempt_count"]:
        return 1
    if summary["passed_attempts"] != summary["scored_attempts"]:
        return 1
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    subcommands = result.add_subparsers(dest="command", required=True)

    inspect_parser = subcommands.add_parser(
        "inspect",
        help="Create a path/SHA/plugin-bound target lock from Codex plugins.",
    )
    inspect_parser.add_argument(
        "--plugin-root",
        action="append",
        type=Path,
        required=True,
        help="Plugin root containing .codex-plugin/plugin.json; repeatable.",
    )
    inspect_parser.add_argument("--marketplace")
    inspect_parser.add_argument(
        "--catalog",
        type=Path,
        help="Test-only codex plugin list --json fixture.",
    )
    inspect_parser.add_argument("--output", type=Path)
    inspect_parser.set_defaults(handler=command_inspect)

    lint_parser = subcommands.add_parser(
        "lint",
        help="Validate eval-suite, target-lock, and report contracts.",
    )
    lint_parser.add_argument("--suite", type=Path)
    lint_parser.add_argument("--target-lock", type=Path)
    lint_parser.add_argument("--report", type=Path)
    lint_parser.add_argument("--output", type=Path)
    lint_parser.set_defaults(handler=command_lint)

    native_parser = subcommands.add_parser(
        "native",
        help="Run native Codex Skill activation evals.",
    )
    native_parser.add_argument("--suite", type=Path, required=True)
    native_parser.add_argument("--target-lock", type=Path, required=True)
    native_parser.add_argument(
        "--case", action="append", dest="case_ids"
    )
    native_parser.add_argument(
        "--changed-skill",
        action="append",
        dest="changed_skills",
        help="Changed focus Skill; repeatable for risk-tiered selection.",
    )
    native_parser.add_argument(
        "--mode",
        choices=("pr", "release", "exhaustive"),
        default=DEFAULT_NATIVE_MODE,
        help=(
            "Evaluation mode (default: release; exhaustive must be selected "
            "explicitly)."
        ),
    )
    native_parser.add_argument(
        "--policy",
        type=Path,
        help="risk-tiered-v2 policy JSON (required for pr/release).",
    )
    native_parser.add_argument("--max-calls", type=int)
    native_parser.add_argument(
        "--rotation-key",
        default=datetime.now(timezone.utc).strftime("%Y-%m"),
        help="Stable key used for rotating release boundary cases.",
    )
    native_parser.add_argument(
        "--journal",
        type=Path,
        help="Append-only JSONL attempt journal.",
    )
    native_parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume and deduplicate attempts from --journal.",
    )
    native_parser.add_argument(
        "--shard",
        help="Run a deterministic 1-based INDEX/TOTAL case shard.",
    )
    native_parser.add_argument(
        "--finalize",
        action="store_true",
        help="Build a report from --journal without making model calls.",
    )
    native_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the selection/budget plan without model calls.",
    )
    native_parser.add_argument("--repeat", type=int)
    native_parser.add_argument("--timeout", type=int, default=45)
    native_parser.add_argument("--model")
    native_parser.add_argument("--workspace", type=Path)
    native_parser.add_argument("--output", type=Path)
    native_parser.add_argument("--include-prompts", action="store_true")
    native_parser.add_argument("--adapter-executable")
    native_parser.add_argument(
        "--catalog",
        type=Path,
        help="Test-only codex plugin list --json fixture.",
    )
    native_parser.add_argument(
        "--adapter-arg", action="append", default=[]
    )
    native_parser.set_defaults(handler=command_native)
    return result


def main(argv: list[str] | None = None) -> int:
    # 根因：Windows 管道可能沿用本地代码页；修复：CLI JSON 与诊断统一为 UTF-8。
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")
    if sys.version_info < MIN_PYTHON:
        required = ".".join(str(item) for item in MIN_PYTHON)
        print(
            f"{PRODUCER_ID} requires Python {required} or newer",
            file=sys.stderr,
        )
        return 127
    args = parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
