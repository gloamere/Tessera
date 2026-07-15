"""Validate Tessera's slim dual-host release surface."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
PIECES = ROOT / "pieces"
EXPECTED_PLATFORMS = {
    "claude": "native",
    "codex": "native",
    "gemini": "unsupported",
    "domestic": "unsupported",
}
EXPECTED_SKILLS = {
    "tessera-core": {"tessera-eval"},
    "taste": {"taste"},
    "frontend-design": {"frontend-design"},
    "knowledge-base": {"knowledge-base"},
}
ROUTES = {"direct", "tessera-eval", "taste", "frontend-design", "knowledge-base"}
RETIRED_RUNTIME_NAMES = {
    "planner",
    "piece-router",
    "tessera-setup",
    "tessera-status",
    "tessera-capabilities",
    "tessera-doctor",
    "usage_events.py",
}


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{relative(path)}: 必须是 JSON 对象")
    return value


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def marketplace_entries(path: Path, errors: list[str]) -> dict[str, dict[str, Any]]:
    marketplace = read_json(path)
    items = marketplace.get("plugins")
    if not isinstance(items, list):
        errors.append(f"{relative(path)}: plugins 必须是数组")
        return {}
    entries: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            errors.append(f"{relative(path)}: 每个插件必须有字符串 name")
            continue
        name = item["name"]
        if name in entries:
            errors.append(f"{relative(path)}: 插件 {name} 重复")
        entries[name] = item
    return entries


def parse_frontmatter(path: Path, errors: list[str]) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        errors.append(f"{relative(path)}: 缺少 YAML frontmatter")
        return {}
    try:
        _, raw, _ = text.split("---", 2)
        value = yaml.safe_load(raw)
    except (ValueError, yaml.YAMLError) as exc:
        errors.append(f"{relative(path)}: frontmatter 无效: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{relative(path)}: frontmatter 必须是对象")
        return {}
    if not isinstance(value.get("name"), str) or not value["name"]:
        errors.append(f"{relative(path)}: frontmatter 缺少 name")
    if not isinstance(value.get("description"), str) or not value["description"].strip():
        errors.append(f"{relative(path)}: frontmatter 缺少 description")
    return value


def validate_piece(
    piece_id: str,
    claude_entry: dict[str, Any],
    codex_entry: dict[str, Any],
    errors: list[str],
) -> None:
    piece_dir = PIECES / piece_id
    expected_source = f"./pieces/{piece_id}"
    if claude_entry.get("source") != expected_source:
        errors.append(f"{piece_id}: Claude source 应为 {expected_source}")
    codex_source = codex_entry.get("source")
    if not isinstance(codex_source, dict) or codex_source.get("path") != expected_source:
        errors.append(f"{piece_id}: Codex source 应为 {expected_source}")

    version = claude_entry.get("version")
    if not isinstance(version, str) or not version:
        errors.append(f"{piece_id}: Claude marketplace 缺少 version")
    for host in ("claude", "codex"):
        manifest_path = piece_dir / f".{host}-plugin" / "plugin.json"
        if not manifest_path.is_file():
            errors.append(f"{piece_id}: 缺少 {relative(manifest_path)}")
            continue
        manifest = read_json(manifest_path)
        if manifest.get("name") != piece_id:
            errors.append(f"{relative(manifest_path)}: name 不匹配")
        if manifest.get("version") != version:
            errors.append(f"{relative(manifest_path)}: version 与 marketplace 不一致")

    piece_path = piece_dir / "piece.yaml"
    piece = read_yaml(piece_path) if piece_path.is_file() else None
    if not isinstance(piece, dict):
        errors.append(f"{piece_id}: 缺少或无效的 piece.yaml")
    else:
        for field in ("id", "kind", "summary", "when_to_use", "avoid_when", "platforms", "external_deps"):
            if field not in piece:
                errors.append(f"{relative(piece_path)}: 缺少 {field}")
        if piece.get("id") != piece_id:
            errors.append(f"{relative(piece_path)}: id 不匹配")
        if piece.get("platforms") != EXPECTED_PLATFORMS:
            errors.append(f"{relative(piece_path)}: platforms 与双宿主边界不一致")

    skill_paths = sorted((piece_dir / "skills").glob("*/SKILL.md"))
    actual_skills: set[str] = set()
    for skill_path in skill_paths:
        frontmatter = parse_frontmatter(skill_path, errors)
        if isinstance(frontmatter.get("name"), str):
            actual_skills.add(frontmatter["name"])
        text = skill_path.read_text(encoding="utf-8")
        for retired in RETIRED_RUNTIME_NAMES:
            if retired in text:
                errors.append(f"{relative(skill_path)}: 包含已移除运行时入口 {retired}")
    if actual_skills != EXPECTED_SKILLS[piece_id]:
        errors.append(
            f"{piece_id}: Skill 集合应为 {sorted(EXPECTED_SKILLS[piece_id])}，实际 {sorted(actual_skills)}"
        )

    command_names = {path.stem for path in (piece_dir / "commands").glob("*.md")}
    expected_commands = {"tessera-eval"} if piece_id == "tessera-core" else set()
    if command_names != expected_commands:
        errors.append(
            f"{piece_id}: Claude command 集合应为 {sorted(expected_commands)}，实际 {sorted(command_names)}"
        )


def validate_eval_cases(errors: list[str]) -> None:
    eval_root = PIECES / "tessera-core" / "skills" / "tessera-eval"
    required_runtime = (
        eval_root / "scripts" / "run_routing_eval.py",
        eval_root / "scripts" / "run.ps1",
        eval_root / "scripts" / "run.sh",
        eval_root / "references" / "routing-cases.json",
        eval_root / "references" / "personal-routing-cases.json",
        eval_root / "references" / "schemas" / "routing-output.schema.json",
        eval_root / "references" / "schemas" / "native-invocation-output.schema.json",
    )
    for path in required_runtime:
        if not path.is_file():
            errors.append(f"{relative(path)}: 自包含 eval 运行资产缺失")

    for cache_dir in eval_root.rglob("__pycache__"):
        errors.append(f"{relative(cache_dir)}: 插件包不得包含 Python 字节码缓存")

    runner_path = eval_root / "scripts" / "run_routing_eval.py"
    if runner_path.is_file():
        runner = runner_path.read_text(encoding="utf-8")
        for forbidden in ("import yaml", "ROOT / \"tests\"", "requirements-dev.txt"):
            if forbidden in runner:
                errors.append(f"{relative(runner_path)}: 包含仓库或第三方运行时依赖 {forbidden!r}")

    schema_path = eval_root / "references" / "schemas" / "routing-output.schema.json"
    schema = read_json(schema_path)
    enum = schema.get("properties", {}).get("route", {}).get("enum")
    if not isinstance(enum, list) or set(enum) != ROUTES:
        errors.append(f"{relative(schema_path)}: route enum 与精简能力面不一致")

    native_schema_path = eval_root / "references" / "schemas" / "native-invocation-output.schema.json"
    native_schema = read_json(native_schema_path)
    decisions = native_schema.get("properties", {}).get("decision", {}).get("enum")
    if decisions != ["direct", "skill"]:
        errors.append(f"{relative(native_schema_path)}: decision 只能是 direct/skill")

    for filename in ("routing-cases.json", "personal-routing-cases.json"):
        path = eval_root / "references" / filename
        cases = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(cases, list) or not cases:
            errors.append(f"{relative(path)}: 必须是非空数组")
            continue
        seen: set[str] = set()
        profiles = {"development": 0, "product": 0}
        for case in cases:
            if not isinstance(case, dict):
                errors.append(f"{relative(path)}: 案例必须是对象")
                continue
            case_id = case.get("id")
            if not isinstance(case_id, str) or not case_id:
                errors.append(f"{relative(path)}: 案例缺少 id")
                continue
            if case_id in seen:
                errors.append(f"{relative(path)}: 案例 {case_id} 重复")
            seen.add(case_id)
            if case.get("expected_route") not in ROUTES:
                errors.append(f"{relative(path)}: {case_id} 的 expected_route 无效")
            skills = case.get("expected_skills")
            if not isinstance(skills, list) or any(
                skill not in {"tessera-eval", "taste", "frontend-design", "knowledge-base"}
                for skill in skills
            ):
                errors.append(f"{relative(path)}: {case_id} 的 expected_skills 无效")
            if filename == "personal-routing-cases.json":
                profile = case.get("profile")
                if profile not in profiles:
                    errors.append(f"{relative(path)}: {case_id} 的 profile 无效")
                else:
                    profiles[profile] += 1
        if filename == "personal-routing-cases.json" and (
            len(cases) != 25 or profiles != {"development": 15, "product": 10}
        ):
            errors.append(
                f"{relative(path)}: 必须保持 25 个案例及 15/10 profile，实际 {profiles}"
            )


def validate_frontend_design(errors: list[str]) -> None:
    plugin = PIECES / "frontend-design"
    skill = plugin / "skills" / "frontend-design"
    required = (
        plugin / "LICENSE.upstream",
        skill / "SKILL.md",
        skill / "references" / "UPSTREAM.md",
        skill / "references" / "quick-reference.md",
        skill / "references" / "pro-rules.md",
        skill / "scripts" / "core.py",
        skill / "scripts" / "design_system.py",
        skill / "scripts" / "search.py",
        skill / "scripts" / "validate_data.py",
        skill / "scripts" / "run.ps1",
        skill / "scripts" / "run.sh",
        skill / "scripts" / "tests" / "test_core.py",
    )
    for path in required:
        if not path.is_file():
            errors.append(f"{relative(path)}: frontend-design 核心资产缺失")
    data_files = list((skill / "data").rglob("*.csv"))
    if len(data_files) != 35:
        errors.append(f"frontend-design: 应包含 35 个上游核心数据表，实际 {len(data_files)}")
    skill_path = skill / "SKILL.md"
    if skill_path.is_file() and len(skill_path.read_text(encoding="utf-8").splitlines()) > 70:
        errors.append(f"{relative(skill_path)}: 超过 70 行上下文预算")


def main() -> int:
    errors: list[str] = []
    try:
        version_path = ROOT / "VERSION"
        distribution_version = version_path.read_text(encoding="utf-8").strip()
        if not distribution_version:
            errors.append("VERSION: 分发版本不能为空")
        claude_path = ROOT / ".claude-plugin" / "marketplace.json"
        codex_path = ROOT / ".agents" / "plugins" / "marketplace.json"
        claude_marketplace = read_json(claude_path)
        metadata = claude_marketplace.get("metadata")
        marketplace_version = metadata.get("version") if isinstance(metadata, dict) else None
        if marketplace_version != distribution_version:
            errors.append(
                ".claude-plugin/marketplace.json: metadata.version "
                f"应与 VERSION ({distribution_version}) 一致"
            )
        claude = marketplace_entries(claude_path, errors)
        codex = marketplace_entries(codex_path, errors)
        if set(claude) != set(codex):
            errors.append("Claude 与 Codex marketplace 插件集合不一致")
        if set(claude) != set(EXPECTED_SKILLS):
            errors.append(
                f"marketplace 应包含 {sorted(EXPECTED_SKILLS)}，实际 {sorted(set(claude) | set(codex))}"
            )
        piece_dirs = {path.name for path in PIECES.iterdir() if path.is_dir()}
        if piece_dirs != set(EXPECTED_SKILLS):
            errors.append(f"pieces/ 集合与目标发布面不一致: {sorted(piece_dirs)}")
        for piece_id in sorted(set(claude) & set(codex) & set(EXPECTED_SKILLS)):
            validate_piece(piece_id, claude[piece_id], codex[piece_id], errors)
        validate_eval_cases(errors)
        validate_frontend_design(errors)
        for installer in (ROOT / "install.ps1", ROOT / "install.sh"):
            if not installer.is_file():
                errors.append(f"{relative(installer)}: 缺少一键安装入口")
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        errors.append(str(exc))

    if errors:
        print("Tessera 发布物校验失败:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    count = len(EXPECTED_SKILLS)
    print(f"校验通过：{count} 个插件、{count} 个运行时 Skill，双宿主发布物与 eval 案例一致。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
