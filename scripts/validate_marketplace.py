"""Validate Tessera marketplaces, pieces, registry, skills, and policy fixtures."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import yaml

from admission_score import evaluate, grade_for_score
from doctor_status import overall_status
from version_status import classify_version


ROOT = Path(__file__).resolve().parents[1]
PIECES = ROOT / "pieces"
SUPPORTED_AVAILABILITY = {"installable", "reference-only", "unverified", "unsupported"}
EXPECTED_PLATFORMS = {
    "claude": "native",
    "codex": "native",
    "gemini": "unsupported",
    "domestic": "unsupported",
}
REQUIRED_PIECE_FIELDS = {
    "id",
    "kind",
    "summary",
    "when_to_use",
    "avoid_when",
    "platforms",
    "external_deps",
    "upgrade_policy",
}


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{relative(path)}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{relative(path)}: 根节点必须是对象")
    return value


def read_yaml(path: Path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"{relative(path)}: {exc}") from exc


def plugin_map(marketplace: dict, label: str, errors: list[str]) -> dict[str, dict]:
    items = marketplace.get("plugins")
    if not isinstance(items, list):
        errors.append(f"{label}: plugins 必须是数组")
        return {}
    result: dict[str, dict] = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            errors.append(f"{label}: 每个插件都必须有字符串 name")
            continue
        name = item["name"]
        if name in result:
            errors.append(f"{label}: 插件 {name} 重复")
        result[name] = item
    return result


def validate_skill_frontmatter(path: Path, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        errors.append(f"{relative(path)}: 缺少完整 YAML frontmatter")
        return
    raw = text.split("\n---\n", 1)[0][4:]
    try:
        frontmatter = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        errors.append(f"{relative(path)}: frontmatter 无效: {exc}")
        return
    if not isinstance(frontmatter, dict):
        errors.append(f"{relative(path)}: frontmatter 必须是对象")
        return
    for field in ("name", "description"):
        if not isinstance(frontmatter.get(field), str) or not frontmatter[field].strip():
            errors.append(f"{relative(path)}: frontmatter 缺少 {field}")


def validate_decisions(errors: list[str]) -> None:
    for path in sorted((ROOT / "docs" / "decisions").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n") or "\n---\n" not in text[4:]:
            errors.append(f"{relative(path)}: 缺少决策 frontmatter")
            continue
        raw = text.split("\n---\n", 1)[0][4:]
        try:
            frontmatter = yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            errors.append(f"{relative(path)}: 决策 frontmatter 无效: {exc}")
            continue
        if not isinstance(frontmatter, dict) or frontmatter.get("status") not in {
            "pending",
            "approved",
            "superseded",
        }:
            errors.append(f"{relative(path)}: status 必须是 pending/approved/superseded")


def validate_registry(errors: list[str]) -> None:
    registry = read_yaml(ROOT / "registry.yaml")
    trust = read_yaml(ROOT / "trust.yaml")
    if not isinstance(registry, dict) or not isinstance(registry.get("external"), list):
        errors.append("registry.yaml: external 必须是数组")
        return
    if not isinstance(trust, dict) or not isinstance(trust.get("allowed_installs"), list):
        errors.append("trust.yaml: allowed_installs 必须是数组")
        return

    trust_by_id = {
        item.get("id"): item
        for item in trust["allowed_installs"]
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    seen: set[str] = set()
    for item in registry["external"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            errors.append("registry.yaml: 每个 external 条目必须有字符串 id")
            continue
        item_id = item["id"]
        if item_id in seen:
            errors.append(f"registry.yaml: external id {item_id} 重复")
        seen.add(item_id)
        availability = item.get("availability")
        if not isinstance(availability, dict) or set(availability) != {"claude", "codex"}:
            errors.append(f"registry.yaml: {item_id} 必须声明 claude/codex availability")
            continue
        for host, state in availability.items():
            if state not in SUPPORTED_AVAILABILITY:
                errors.append(f"registry.yaml: {item_id}.{host} availability 无效: {state}")

        kind = item.get("kind", "")
        if isinstance(kind, str) and kind.endswith("-candidate"):
            if item.get("status") != "not-integrated":
                errors.append(f"registry.yaml: 候选 {item_id} 必须是 not-integrated")
        if item.get("status") == "not-integrated" and "installable" in availability.values():
            errors.append(f"registry.yaml: 未集成候选 {item_id} 不得标为 installable")

        installable_hosts = [host for host, state in availability.items() if state == "installable"]
        if not installable_hosts:
            continue
        trust_ref = item.get("trust_ref")
        if trust_ref not in trust_by_id:
            errors.append(f"registry.yaml: 可安装项 {item_id} 缺少有效 trust_ref")
            continue
        commands = item.get("per_platform", {})
        trusted_command = trust_by_id[trust_ref].get("install")
        for host in installable_hosts:
            if not isinstance(commands, dict) or commands.get(host) != trusted_command:
                errors.append(f"registry.yaml: {item_id}.{host} 安装命令与 trust.yaml 不一致")


def validate_route_cases(valid_piece_ids: set[str], errors: list[str]) -> None:
    path = ROOT / "tests" / "routing-cases.yaml"
    cases = read_yaml(path)
    if not isinstance(cases, list) or not cases:
        errors.append(f"{relative(path)}: 必须是非空数组")
        return
    valid_targets = valid_piece_ids | {
        "direct",
        "piece-router",
        "piece-admission",
        "tessera-setup",
        "tessera-status",
        "tessera-doctor",
        "external-unavailable",
    }
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            errors.append(f"{relative(path)}: 每个案例必须是对象")
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id:
            errors.append(f"{relative(path)}: 案例缺少 id")
            continue
        if case_id in seen:
            errors.append(f"{relative(path)}: 案例 id {case_id} 重复")
        seen.add(case_id)
        if not isinstance(case.get("prompt"), str) or not case["prompt"].strip():
            errors.append(f"{relative(path)}: {case_id} 缺少 prompt")
        expected = case.get("expected_route")
        if expected not in valid_targets:
            errors.append(f"{relative(path)}: {case_id} 的 expected_route 无效: {expected}")
        excluded = case.get("must_not_route", [])
        if not isinstance(excluded, list) or any(target not in valid_targets for target in excluded):
            errors.append(f"{relative(path)}: {case_id} 的 must_not_route 无效")


def validate_admission_cases(errors: list[str]) -> None:
    path = ROOT / "tests" / "admission-cases.yaml"
    cases = read_yaml(path)
    if not isinstance(cases, list) or not cases:
        errors.append(f"{relative(path)}: 必须是非空数组")
        return
    grade_boundaries = {
        100: "S",
        90: "S",
        89: "A",
        80: "A",
        79: "B",
        70: "B",
        69: "C",
        60: "C",
        59: "D",
        50: "D",
        49: "E",
        40: "E",
        39: "F",
        0: "F",
    }
    for score, expected_grade in grade_boundaries.items():
        actual_grade = grade_for_score(score)
        if actual_grade != expected_grade:
            errors.append(
                f"准入等级边界 {score} 期望 {expected_grade}，实际 {actual_grade}"
            )
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str):
            errors.append(f"{relative(path)}: 每个案例必须有字符串 id")
            continue
        case_id = case["id"]
        if case_id in seen:
            errors.append(f"{relative(path)}: 案例 id {case_id} 重复")
        seen.add(case_id)
        try:
            actual = evaluate(case.get("scores", {}), case.get("flags", {}))
        except (TypeError, ValueError) as exc:
            errors.append(f"{relative(path)}: {case_id}: {exc}")
            continue
        expected = case.get("expected")
        if not isinstance(expected, dict):
            errors.append(f"{relative(path)}: {case_id} 缺少 expected")
            continue
        for field in ("raw_score", "raw_grade", "cap_grade", "final_grade"):
            if actual[field] != expected.get(field):
                errors.append(
                    f"{relative(path)}: {case_id}.{field} 期望 {expected.get(field)!r}，实际 {actual[field]!r}"
                )


def validate_doctor_cases(errors: list[str]) -> None:
    path = ROOT / "tests" / "doctor-cases.yaml"
    cases = read_yaml(path)
    if not isinstance(cases, list) or not cases:
        errors.append(f"{relative(path)}: 必须是非空数组")
        return
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str):
            errors.append(f"{relative(path)}: 每个案例必须有字符串 id")
            continue
        case_id = case["id"]
        if case_id in seen:
            errors.append(f"{relative(path)}: 案例 id {case_id} 重复")
        seen.add(case_id)
        results = case.get("results")
        expected = case.get("expected_overall")
        if not isinstance(results, list) or expected not in {
            "healthy",
            "warning",
            "error",
            "unknown",
        }:
            errors.append(f"{relative(path)}: {case_id} 结果或 expected_overall 无效")
            continue
        try:
            actual = overall_status(results)
        except ValueError as exc:
            errors.append(f"{relative(path)}: {case_id}: {exc}")
            continue
        if actual != expected:
            errors.append(
                f"{relative(path)}: {case_id} 期望 {expected}，实际 {actual}"
            )

    version_cases = {
        ("1.2.3", "1.2.3"): "current",
        ("1.2.3+codex.old", "1.2.3+codex.new"): "refresh-available",
        ("1.2.3", "1.3.0"): "update-available",
        ("2.0.0", "1.9.9"): "ahead",
        (None, "1.0.0"): "unknown",
        ("1.0.0-beta.1", "1.0.0"): "unknown",
    }
    for versions, expected in version_cases.items():
        actual = classify_version(*versions)
        if actual != expected:
            errors.append(f"版本状态 {versions} 期望 {expected}，实际 {actual}")


def main() -> int:
    errors: list[str] = []
    try:
        claude = read_json(ROOT / ".claude-plugin" / "marketplace.json")
        codex = read_json(ROOT / ".agents" / "plugins" / "marketplace.json")
        claude_plugins = plugin_map(claude, "Claude 市集", errors)
        codex_plugins = plugin_map(codex, "Codex 市集", errors)

        if set(claude_plugins) != set(codex_plugins):
            errors.append("Claude 与 Codex 市集的拼图名称不一致")

        piece_dirs = {path.name for path in PIECES.iterdir() if path.is_dir()}
        marketplace_ids = set(claude_plugins) | set(codex_plugins)
        if piece_dirs != marketplace_ids:
            errors.append(
                f"pieces/ 与市集不一致: orphan={sorted(piece_dirs - marketplace_ids)}, missing={sorted(marketplace_ids - piece_dirs)}"
            )

        for piece_id in sorted(marketplace_ids):
            piece_dir = PIECES / piece_id
            claude_entry = claude_plugins.get(piece_id, {})
            codex_entry = codex_plugins.get(piece_id, {})
            expected_source = f"./pieces/{piece_id}"
            if claude_entry.get("source") != expected_source:
                errors.append(f"{piece_id}: Claude source 应为 {expected_source}")
            if codex_entry.get("source", {}).get("path") != expected_source:
                errors.append(f"{piece_id}: Codex source 应为 {expected_source}")

            for manifest_path in (
                piece_dir / ".claude-plugin" / "plugin.json",
                piece_dir / ".codex-plugin" / "plugin.json",
            ):
                if not manifest_path.is_file():
                    errors.append(f"{piece_id}: 缺少 {relative(manifest_path)}")
                    continue
                manifest = read_json(manifest_path)
                if manifest.get("name") != piece_id:
                    errors.append(f"{piece_id}: {relative(manifest_path)} 的 name 不匹配")
                if manifest.get("version") != claude_entry.get("version"):
                    errors.append(f"{piece_id}: 市集与 manifest 的 version 不匹配")

            piece_path = piece_dir / "piece.yaml"
            if not piece_path.is_file():
                errors.append(f"{piece_id}: 缺少 piece.yaml")
                continue
            piece = read_yaml(piece_path)
            if not isinstance(piece, dict):
                errors.append(f"{piece_id}: piece.yaml 必须是对象")
                continue
            missing_fields = REQUIRED_PIECE_FIELDS - set(piece)
            if missing_fields:
                errors.append(f"{piece_id}: piece.yaml 缺少 {sorted(missing_fields)}")
            if piece.get("id") != piece_id:
                errors.append(f"{piece_id}: piece.yaml id 不匹配")
            if piece.get("platforms") != EXPECTED_PLATFORMS:
                errors.append(f"{piece_id}: platforms 必须明确 Codex/Claude native，其余 unsupported")
            if not isinstance(piece.get("when_to_use"), list) or not piece["when_to_use"]:
                errors.append(f"{piece_id}: when_to_use 必须是非空数组")
            if not isinstance(piece.get("external_deps"), list):
                errors.append(f"{piece_id}: external_deps 必须是数组")

            for skill_path in sorted((piece_dir / "skills").glob("*/SKILL.md")):
                validate_skill_frontmatter(skill_path, errors)
            if piece_id == "tessera-core":
                for retired in ("hooks", "bin", "gate-rules.json"):
                    if (piece_dir / retired).exists():
                        errors.append(f"tessera-core: 已移除的 {retired} 不应存在")
                admission_reference = (
                    piece_dir
                    / "skills"
                    / "piece-router"
                    / "references"
                    / "piece-admission.md"
                )
                if not admission_reference.is_file():
                    errors.append("tessera-core: 缺少 piece-router 准入量表 reference")
                for required_path in (
                    piece_dir / "skills" / "tessera-doctor" / "SKILL.md",
                    piece_dir / "commands" / "tessera-doctor.md",
                ):
                    if not required_path.is_file():
                        errors.append(f"tessera-core: 缺少 {relative(required_path)}")

        active_instruction_paths = list(PIECES.glob("**/SKILL.md")) + list(
            PIECES.glob("**/commands/*.md")
        )
        for path in active_instruction_paths:
            text = path.read_text(encoding="utf-8")
            for forbidden in ("AskUserQuestion", "bd version"):
                if forbidden in text:
                    errors.append(f"{relative(path)}: 不得包含宿主/已移除能力残留 {forbidden!r}")

        validate_registry(errors)
        validate_decisions(errors)
        validate_route_cases(marketplace_ids, errors)
        validate_admission_cases(errors)
        validate_doctor_cases(errors)
    except ValueError as exc:
        errors.append(str(exc))

    if errors:
        print("插件与策略校验失败:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    print(
        f"校验通过：{len(claude_plugins)} 个拼图，双市集、YAML/frontmatter、registry/trust、路由与准入案例一致。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
