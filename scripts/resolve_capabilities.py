"""Resolve Tessera capabilities from manifests, skills, registry, trust, and host evidence."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
CATALOG_STATES = {"installable", "reference-only", "unverified", "unsupported"}
RUNTIME_STATES = {"active", "installed", "available", "unknown", "unsupported"}


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: root must be an object")
    return value


def read_skill_frontmatter(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise ValueError(f"{path}: missing frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError(f"{path}: incomplete frontmatter") from exc
    value = yaml.safe_load("\n".join(lines[1:end]))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: frontmatter must be an object")
    return value


def marketplace_entries(root: Path, host: str) -> dict[str, dict[str, Any]]:
    path = (
        root / ".agents" / "plugins" / "marketplace.json"
        if host == "codex"
        else root / ".claude-plugin" / "marketplace.json"
    )
    marketplace = read_json(path)
    entries = marketplace.get("plugins")
    if not isinstance(entries, list):
        raise ValueError(f"{path}: plugins must be an array")
    return {
        entry["name"]: entry
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    }


def probe_installed_plugins(host: str, root: Path) -> tuple[set[str] | None, str]:
    names = ("codex.cmd", "codex", "codex.exe") if os.name == "nt" else ("codex",)
    if host == "claude":
        names = ("claude.cmd", "claude", "claude.exe") if os.name == "nt" else ("claude",)
    executable = next((found for name in names if (found := shutil.which(name))), None)
    if executable is None:
        return None, f"{host} CLI unavailable"
    command = [executable, "plugin", "list"]
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        return None, f"plugin list exited {completed.returncode}: {detail[:300]}"
    installed = set(re.findall(r"(?m)^\s*([a-z0-9][a-z0-9-]*)@[^\s]+", completed.stdout))
    return installed, f"{host} plugin list"


def _manifest_version(piece_dir: Path, host: str, entry: dict[str, Any]) -> str | None:
    if isinstance(entry.get("version"), str):
        return entry["version"]
    manifest = piece_dir / f".{host}-plugin" / "plugin.json"
    if manifest.is_file():
        version = read_json(manifest).get("version")
        return version if isinstance(version, str) else None
    return None


def _trusted_external_state(
    item: dict[str, Any], host: str, trust_by_id: dict[str, dict[str, Any]]
) -> tuple[str, str]:
    availability = item.get("availability", {})
    state = availability.get(host) if isinstance(availability, dict) else None
    if state not in CATALOG_STATES:
        return "unverified", "registry availability missing or invalid"
    if item.get("status") == "not-integrated" or str(item.get("kind", "")).endswith("-candidate"):
        return "unverified", "candidate is not integrated"
    if state != "installable":
        return state, f"registry marks {host} as {state}"
    trust_ref = item.get("trust_ref")
    trusted = trust_by_id.get(trust_ref)
    commands = item.get("per_platform", {})
    command = commands.get(host) if isinstance(commands, dict) else None
    if not trusted or command != trusted.get("install"):
        return "unverified", "install command lacks an exact trust match"
    return "installable", "registry and trust command match"


def resolve_capabilities(
    root: Path,
    host: str,
    installed_plugins: set[str] | None = None,
    active_skills: set[str] | None = None,
    probe_evidence: str = "not probed",
) -> dict[str, Any]:
    if host not in {"codex", "claude"}:
        raise ValueError(f"unsupported host: {host}")
    active_skills = active_skills or set()
    entries = marketplace_entries(root, host)
    capabilities: list[dict[str, Any]] = []
    seen_skills: set[str] = set()

    for piece_id, entry in sorted(entries.items()):
        piece_dir = root / "pieces" / piece_id
        piece = read_yaml(piece_dir / "piece.yaml")
        if not isinstance(piece, dict):
            raise ValueError(f"{piece_dir / 'piece.yaml'}: root must be an object")
        platforms = piece.get("platforms", {})
        host_support = platforms.get(host) if isinstance(platforms, dict) else None
        catalog_state = "installable" if host_support == "native" else "unsupported"
        if catalog_state == "unsupported":
            piece_runtime = "unsupported"
        elif installed_plugins is None:
            piece_runtime = "unknown"
        elif piece_id in installed_plugins:
            piece_runtime = "installed"
        else:
            piece_runtime = "available"

        skill_paths = sorted((piece_dir / "skills").glob("*/SKILL.md"))
        for skill_path in skill_paths:
            frontmatter = read_skill_frontmatter(skill_path)
            skill_id = frontmatter.get("name")
            if not isinstance(skill_id, str) or not skill_id:
                raise ValueError(f"{skill_path}: skill name missing")
            if skill_id in seen_skills:
                raise ValueError(f"duplicate skill id: {skill_id}")
            seen_skills.add(skill_id)
            runtime_state = "active" if skill_id in active_skills else piece_runtime
            capabilities.append(
                {
                    "id": skill_id,
                    "piece": piece_id,
                    "kind": "skill",
                    "catalog_state": catalog_state,
                    "runtime_state": runtime_state,
                    "host_support": host_support or "unknown",
                    "version": _manifest_version(piece_dir, host, entry),
                    "description": frontmatter.get("description", ""),
                    "source": skill_path.relative_to(root).as_posix(),
                    "evidence": "current session" if runtime_state == "active" else probe_evidence,
                }
            )

    registry_path = root / "registry.yaml"
    trust_path = root / "trust.yaml"
    if registry_path.is_file():
        registry = read_yaml(registry_path)
        trust = read_yaml(trust_path) if trust_path.is_file() else {"allowed_installs": []}
        trust_items = trust.get("allowed_installs", []) if isinstance(trust, dict) else []
        trust_by_id = {
            item["id"]: item
            for item in trust_items
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        external = registry.get("external", []) if isinstance(registry, dict) else []
        for item in external:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            state, evidence = _trusted_external_state(item, host, trust_by_id)
            capabilities.append(
                {
                    "id": item["id"],
                    "piece": None,
                    "kind": "external",
                    "catalog_state": state,
                    "runtime_state": "unknown" if state != "unsupported" else "unsupported",
                    "host_support": state,
                    "version": None,
                    "description": item.get("summary", ""),
                    "source": "registry.yaml",
                    "evidence": evidence,
                }
            )

    counts: dict[str, int] = {}
    for capability in capabilities:
        state = capability["runtime_state"]
        counts[state] = counts.get(state, 0) + 1
    return {
        "schema_version": 1,
        "host": host,
        "probe_evidence": probe_evidence,
        "summary": {"total": len(capabilities), **counts},
        "capabilities": capabilities,
    }


def print_table(catalog: dict[str, Any]) -> None:
    print("能力 | 来源拼图 | 类型 | 目录状态 | 运行时状态 | 证据")
    print("---|---|---|---|---|---")
    for item in catalog["capabilities"]:
        print(
            f"{item['id']} | {item['piece'] or '-'} | {item['kind']} | "
            f"{item['catalog_state']} | {item['runtime_state']} | {item['evidence']}"
        )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--host", choices=("codex", "claude"), required=True)
    result.add_argument("--root", type=Path, default=ROOT)
    result.add_argument("--probe", action="store_true")
    result.add_argument("--installed-plugin", action="append", default=[])
    result.add_argument("--active-skill", action="append", default=[])
    result.add_argument("--format", choices=("json", "table"), default="table")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    installed: set[str] | None = set(args.installed_plugin) if args.installed_plugin else None
    evidence = "explicit --installed-plugin" if installed is not None else "not probed"
    if args.probe:
        installed, evidence = probe_installed_plugins(args.host, args.root.resolve())
    try:
        catalog = resolve_capabilities(
            args.root.resolve(),
            args.host,
            installed,
            set(args.active_skill),
            evidence,
        )
    except (OSError, ValueError, yaml.YAMLError, json.JSONDecodeError) as exc:
        print(f"能力解析失败: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(catalog, ensure_ascii=False, indent=2))
    else:
        print_table(catalog)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
