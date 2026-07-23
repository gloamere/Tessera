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
REPORT_SCHEMA_VERSION = 3
SUITE_SCHEMA_VERSION = 1
TARGET_LOCK_SCHEMA_VERSION = 2

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
    if value.get("schema_version") != SUITE_SCHEMA_VERSION:
        errors.append(f"eval suite schema_version must be {SUITE_SCHEMA_VERSION}")
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


def case_metrics(
    attempts: list[dict[str, Any]],
    repeat: int,
    independent_batches: int,
) -> dict[str, Any]:
    expected_pairs = {
        (batch, attempt)
        for batch in range(1, independent_batches + 1)
        for attempt in range(1, repeat + 1)
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
    expected_attempts = repeat * independent_batches
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
) -> dict[str, Any]:
    return {
        "id": case["id"],
        "plugin_id": case["plugin_id"],
        "language": case["language"],
        "tags": sorted(case["tags"]),
        "prompt_sha256": sha256_text(case["prompt"]),
        "expected_skills": sorted(case.get("expected_skills", [])),
        "forbidden_skills": sorted(case.get("forbidden_skills", [])),
        **case_metrics(attempts, repeat, independent_batches),
        "attempts": attempts,
    }


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
) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "producer": producer_metadata(),
        "command": "native",
        "event_adapter": {
            "id": EVENT_ADAPTER_ID,
            "schema_version": EVENT_ADAPTER_SCHEMA_VERSION,
        },
        "execution_provenance": execution_provenance,
        "release_evidence_eligible": execution_provenance == "codex_cli",
        "preflight": {
            "evidence_status": preflight_status,
            "reasons": preflight_reasons or [],
        },
        "suite": {
            "suite_id": suite["suite_id"],
            "plugin_id": suite["plugin_id"],
            "execution_policy": suite["execution_policy"],
            "sha256": sha256_object(suite),
        },
        "target_lock": {
            "sha256": sha256_object(target_lock),
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
        "independent_batches": suite["execution_policy"][
            "independent_batches"
        ],
        "timeout_seconds": timeout,
        "summary": summarize_cases(cases),
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


def validate_report_v3(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["report must be an object"]

    def valid_string_array(candidate: Any) -> bool:
        return (
            isinstance(candidate, list)
            and all(isinstance(item, str) for item in candidate)
            and len(candidate) == len(set(candidate))
        )

    if value.get("schema_version") != REPORT_SCHEMA_VERSION:
        errors.append(f"report schema_version must be {REPORT_SCHEMA_VERSION}")
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
                or not 1 <= attempt_id <= effective_repeat
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
        expected_pairs = {
            (batch_id, attempt_id)
            for batch_id in range(1, effective_batches + 1)
            for attempt_id in range(1, effective_repeat + 1)
        }
        if (
            len(attempt_pairs) != len(set(attempt_pairs))
            or set(attempt_pairs) != expected_pairs
        ):
            errors.append(
                f"report case {case_id} does not contain one attempt for "
                "each batch/repeat pair"
            )
        try:
            expected_metrics = case_metrics(
                attempts,
                effective_repeat,
                effective_batches,
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
                    "legacy schema v2 report was read through the "
                    "compatibility mapper and is never release evidence"
                )
                release_evidence_eligible = False
            else:
                errors.extend(validate_report_v3(report))
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
    repeat_per_batch = (
        args.repeat
        if args.repeat is not None
        else suite["execution_policy"]["repeat"]
    )
    if repeat_per_batch < 1 or repeat_per_batch > 10:
        print("--repeat must be between 1 and 10", file=sys.stderr)
        return 2
    independent_batches = suite["execution_policy"]["independent_batches"]
    if args.timeout < 1:
        print("--timeout must be greater than 0", file=sys.stderr)
        return 2
    try:
        cases = selected_cases(suite, args.case_ids)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.workspace is not None and independent_batches > 1:
        print(
            "--workspace cannot be reused across independent batches; "
            "use the default isolated workspaces or a suite with one batch",
            file=sys.stderr,
        )
        return 2

    execution_provenance = (
        "fixture_adapter"
        if args.adapter_executable or args.catalog is not None
        else "codex_cli"
    )
    attempts_by_case: dict[str, list[dict[str, Any]]] = {
        case["id"]: [] for case in cases
    }
    preflight_results: list[tuple[int, str, list[str], str]] = []
    codex_version_value: str | None = None

    for batch in range(1, independent_batches + 1):
        catalog, _, _, catalog_version_value = load_plugin_catalog(args.catalog)
        codex_version_value = catalog_version_value or codex_version_value
        preflight_status, preflight_reasons = assess_native_preflight(
            suite,
            target_lock,
            catalog,
        )
        preflight_results.append(
            (batch, preflight_status, preflight_reasons, "preflight")
        )
        if preflight_status != "verified":
            for case in cases:
                attempts_by_case[case["id"]].extend(
                    preflight_attempt(
                        case,
                        preflight_status,
                        preflight_reasons,
                        attempt,
                        args.include_prompts,
                        batch,
                    )
                    for attempt in range(1, repeat_per_batch + 1)
                )
            continue

        temporary_workspace: tempfile.TemporaryDirectory[str] | None = None
        if args.workspace is None:
            temporary_workspace = tempfile.TemporaryDirectory(
                prefix=f"gloamere-skill-eval-batch-{batch}-"
            )
            workspace = Path(temporary_workspace.name)
        else:
            workspace = args.workspace.resolve()
        batch_attempts: dict[str, list[dict[str, Any]]] = {
            case["id"]: [] for case in cases
        }
        try:
            for case_index, case in enumerate(cases, start=1):
                for attempt in range(1, repeat_per_batch + 1):
                    print(
                        f"[batch {batch}/{independent_batches}] "
                        f"[{case_index}/{len(cases)}] {case['id']} "
                        f"attempt={attempt}",
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
                        host_result.codex_version or codex_version_value
                    )
                    batch_attempts[case["id"]].append(
                        classify_native_attempt(
                            case,
                            suite,
                            target_lock,
                            host_result,
                            attempt,
                            args.include_prompts,
                            batch,
                        )
                    )
        finally:
            if temporary_workspace is not None:
                temporary_workspace.cleanup()

        post_catalog, _, _, post_catalog_version = load_plugin_catalog(
            args.catalog
        )
        codex_version_value = post_catalog_version or codex_version_value
        postflight_status, postflight_reasons = assess_native_preflight(
            suite,
            target_lock,
            post_catalog,
        )
        preflight_results.append(
            (batch, postflight_status, postflight_reasons, "postflight")
        )
        if postflight_status != "verified":
            # 根因：批次运行期间身份可能漂移；修复：整批降级为未评分冲突，
            # 避免把旧 SHA 预检与新文件读取拼成伪 verified 证据。
            for case in cases:
                batch_attempts[case["id"]] = [
                    preflight_attempt(
                        case,
                        postflight_status,
                        postflight_reasons,
                        attempt,
                        args.include_prompts,
                        batch,
                    )
                    for attempt in range(1, repeat_per_batch + 1)
                ]
        for case in cases:
            attempts_by_case[case["id"]].extend(
                batch_attempts[case["id"]]
            )

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
    aggregates = [
        aggregate_case(
            case,
            attempts_by_case[case["id"]],
            repeat_per_batch,
            independent_batches,
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
    )
    report_errors = validate_report_v3(report)
    if report_errors:
        print("internal report validation failed:", file=sys.stderr)
        for error in report_errors:
            print(f"- {error}", file=sys.stderr)
        return 2
    write_or_print(report, args.output)
    summary = report["summary"]
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
