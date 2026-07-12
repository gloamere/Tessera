"""Validate Tessera's checked-in plugin structure without external dependencies."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path.relative_to(ROOT)}: {exc}") from exc


def main() -> int:
    errors: list[str] = []
    claude = read_json(ROOT / ".claude-plugin" / "marketplace.json")
    codex = read_json(ROOT / ".agents" / "plugins" / "marketplace.json")

    claude_plugins = {item["name"]: item for item in claude.get("plugins", [])}
    codex_plugins = {item["name"]: item for item in codex.get("plugins", [])}
    if claude_plugins.keys() != codex_plugins.keys():
        errors.append("Claude 与 Codex 市集的拼图名称不一致")

    for piece_id, entry in claude_plugins.items():
        piece_dir = ROOT / "pieces" / piece_id
        expected_source = f"./pieces/{piece_id}"
        if entry.get("source") != expected_source:
            errors.append(f"{piece_id}: Claude source 应为 {expected_source}")
        codex_source = codex_plugins.get(piece_id, {}).get("source", {})
        if codex_source.get("path") != expected_source:
            errors.append(f"{piece_id}: Codex source 应为 {expected_source}")

        claude_manifest = piece_dir / ".claude-plugin" / "plugin.json"
        codex_manifest = piece_dir / ".codex-plugin" / "plugin.json"
        for manifest_path in (claude_manifest, codex_manifest):
            if not manifest_path.is_file():
                errors.append(f"{piece_id}: 缺少 {manifest_path.relative_to(ROOT)}")
                continue
            manifest = read_json(manifest_path)
            if manifest.get("name") != piece_id:
                errors.append(f"{piece_id}: {manifest_path.name} 的 name 不匹配")
            if manifest.get("version") != entry.get("version"):
                errors.append(f"{piece_id}: 市集与 manifest 的 version 不匹配")

        if not (piece_dir / "piece.yaml").is_file():
            errors.append(f"{piece_id}: 缺少 piece.yaml")
        if piece_id == "tessera-core":
            if not (piece_dir / "skills").is_dir():
                errors.append("tessera-core: 缺少 skills/")
            for retired in ("hooks", "bin", "gate-rules.json"):
                if (piece_dir / retired).exists():
                    errors.append(f"tessera-core: 已移除的 {retired} 不应存在")

    if errors:
        print("插件结构校验失败:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    print(f"插件结构校验通过：{len(claude_plugins)} 个拼图，双市集一致，无 hooks/二进制残留。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
