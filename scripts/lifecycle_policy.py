"""Host lifecycle support and explicit-ref rollback inspection for Tessera pieces."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ACTIONS = {"install", "refresh", "update", "enable", "disable", "uninstall", "rollback"}
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def action_policy(host: str, action: str, plugin: str, marketplace: str = "tessera") -> dict[str, Any]:
    if host not in {"codex", "claude"}:
        raise ValueError(f"unsupported host: {host}")
    if action not in ACTIONS:
        raise ValueError(f"unsupported lifecycle action: {action}")
    if not IDENTIFIER.fullmatch(plugin) or not IDENTIFIER.fullmatch(marketplace):
        raise ValueError("plugin and marketplace must be canonical identifiers")
    selector = f"{plugin}@{marketplace}"
    if action == "rollback":
        return {
            "support": "plan-only",
            "command": None,
            "confirmation_required": True,
            "reload_hint": None,
        }
    if host == "codex":
        executable = "codex.cmd" if os.name == "nt" else "codex"
        if action in {"enable", "disable"}:
            return {
                "support": "unsupported",
                "command": None,
                "confirmation_required": False,
                "reload_hint": None,
            }
        subcommand = "remove" if action == "uninstall" else "add"
        command = [executable, "plugin", subcommand, selector]
        reload_hint = "新开 Codex 会话以加载变更"
    else:
        subcommand = {
            "install": "install",
            "refresh": "update",
            "update": "update",
            "enable": "enable",
            "disable": "disable",
            "uninstall": "uninstall",
        }[action]
        command = ["claude", "plugin", subcommand, selector, "--scope", "user"]
        reload_hint = "运行 /reload-plugins 以加载变更"
    return {
        "support": "execute",
        "command": command,
        "confirmation_required": True,
        "reload_hint": reload_hint,
    }


def inspect_rollback_ref(root: Path, piece: str, ref: str) -> dict[str, str]:
    if not IDENTIFIER.fullmatch(piece):
        raise ValueError("piece must be a canonical identifier")
    if not ref.strip() or ref.lower() in {"cache", "latest", "previous"}:
        raise ValueError("rollback requires an explicit Git tag or commit")
    completed = subprocess.run(
        ["git", "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"],
        cwd=root,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(f"unknown rollback ref: {ref}")
    commit = completed.stdout.strip()
    versions: set[str] = set()
    for host in ("codex", "claude"):
        path = f"pieces/{piece}/.{host}-plugin/plugin.json"
        shown = subprocess.run(
            ["git", "show", f"{commit}:{path}"],
            cwd=root,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        if shown.returncode != 0:
            raise ValueError(f"{ref} does not contain {path}")
        payload = json.loads(shown.stdout)
        version = payload.get("version")
        if not isinstance(version, str):
            raise ValueError(f"{path} has no version at {ref}")
        versions.add(version)
    if len(versions) != 1:
        raise ValueError(f"host manifests disagree at {ref}")
    return {"ref": ref, "commit": commit, "piece": piece, "version": versions.pop()}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--host", choices=("codex", "claude"), required=True)
    result.add_argument("--action", choices=sorted(ACTIONS), required=True)
    result.add_argument("--piece", required=True)
    result.add_argument("--marketplace", default="tessera")
    result.add_argument("--ref")
    result.add_argument("--root", type=Path, default=ROOT)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = action_policy(args.host, args.action, args.piece, args.marketplace)
        if args.action == "rollback":
            if not args.ref:
                raise ValueError("--ref is required for rollback")
            result["target"] = inspect_rollback_ref(args.root.resolve(), args.piece, args.ref)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"生命周期策略解析失败: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
