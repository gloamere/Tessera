"""Gate tagged releases on current, path-bound Codex native evidence.

Without ``--require`` an otherwise valid candidate with no evidence (or metrics
below the release thresholds) is reported as pending and exits successfully.
Configured evidence that is malformed, synthetic, privacy-unsafe, or bound to
the wrong identity always fails. Tagged releases call this command with
``--require``.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "release-manifest.json"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")
REQUIRED_THRESHOLDS = {
    "evidence_coverage": 1.0,
    "verified_exact_match": 0.95,
    "ordinary_over_route": 0.02,
    "multi_intent_complete": 0.9,
    "high_risk_over_route": 0,
}
CASE_COUNTS = {
    "positive": 6,
    "adjacent-negative": 8,
    "multi-intent": 3,
}
EVIDENCE_STATUSES = {
    "verified",
    "unobservable",
    "unavailable",
    "identity_conflict",
    "execution_error",
}
REPORT_FIELDS = {
    "schema_version",
    "generated_at",
    "producer",
    "command",
    "event_adapter",
    "execution_provenance",
    "release_evidence_eligible",
    "preflight",
    "suite",
    "target_lock",
    "environment",
    "privacy",
    "repeat",
    "independent_batches",
    "timeout_seconds",
    "summary",
    "cases",
}
TARGET_FIELDS = {
    "target_id",
    "plugin_id",
    "plugin_selector",
    "plugin_version",
    "installed",
    "enabled",
    "plugin_manifest_relative_path",
    "plugin_manifest_sha256",
    "skill_name",
    "relative_path",
    "sha256",
    "agent_config_relative_path",
    "agent_config_sha256",
}
CASE_FIELDS = {
    "id",
    "plugin_id",
    "language",
    "tags",
    "prompt_sha256",
    "expected_skills",
    "forbidden_skills",
    "attempt_count",
    "expected_attempts",
    "scored_attempts",
    "unscored_attempts",
    "passed_attempts",
    "failed_attempts",
    "evidence_coverage",
    "conditional_accuracy",
    "stable",
    "evidence_statuses",
    "verdicts",
    "attempts",
}
ATTEMPT_FIELDS = {
    "batch_id",
    "attempt",
    "prompt_sha256",
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
    "evidence_status",
    "verdict",
    "reason",
    "duration_ms",
    "event_diagnostics",
    "usage",
}
DIAGNOSTIC_FIELDS = {
    "complete",
    "event_count",
    "malformed_lines",
    "unknown_event_types",
    "unknown_item_types",
    "rejected_target_references",
    "terminal_event",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_object(value: Any) -> str:
    rendered = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256_text(rendered)


def rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def one_tag(tags: Any, prefix: str) -> str | None:
    if not isinstance(tags, list):
        return None
    values = [
        tag.removeprefix(prefix)
        for tag in tags
        if isinstance(tag, str) and tag.startswith(prefix)
    ]
    return values[0] if len(values) == 1 else None


def safe_path(
    root: Path,
    value: Any,
    label: str,
    errors: list[str],
) -> Path | None:
    if not isinstance(value, str) or not value:
        errors.append(f"{label} must be a non-empty relative path")
        return None
    candidate = Path(value)
    if candidate.is_absolute():
        errors.append(f"{label} must not be absolute")
        return None
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        errors.append(f"{label} escapes the repository")
        return None
    return resolved


def plugin_by_id(
    manifest: dict[str, Any],
    plugin_id: str,
) -> dict[str, Any] | None:
    plugins = manifest.get("plugins")
    if not isinstance(plugins, list):
        return None
    matches = [
        plugin
        for plugin in plugins
        if isinstance(plugin, dict) and plugin.get("id") == plugin_id
    ]
    return matches[0] if len(matches) == 1 else None


def load_contract(
    root: Path,
    manifest_path: Path,
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    try:
        manifest = read_json(manifest_path)
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"cannot read release manifest: {exc}"]
    if not isinstance(manifest, dict):
        return None, ["release manifest must be an object"]

    workflow = plugin_by_id(manifest, "gloamere-workflows")
    eval_plugin = plugin_by_id(manifest, "gloamere-eval")
    if workflow is None:
        errors.append("release manifest must contain one gloamere-workflows plugin")
        workflow = {}
    if eval_plugin is None:
        errors.append("release manifest must contain one gloamere-eval plugin")
        eval_plugin = {}

    admission = workflow.get("admission")
    if not isinstance(admission, dict):
        errors.append("gloamere-workflows.admission must be an object")
        admission = {}
    if admission.get("repeat") != 3:
        errors.append("admission.repeat must be 3")
    if admission.get("independent_batches") != 2:
        errors.append("admission.independent_batches must be 2")
    if admission.get("thresholds") != REQUIRED_THRESHOLDS:
        errors.append(
            "admission.thresholds must exactly match the release contract"
        )

    suite_path = safe_path(
        root,
        admission.get("suite_path"),
        "admission.suite_path",
        errors,
    )
    suite: dict[str, Any] = {}
    if suite_path is not None:
        try:
            value = read_json(suite_path)
            if isinstance(value, dict):
                suite = value
            else:
                errors.append("admission suite must be an object")
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"cannot read admission suite: {exc}")

    target_sha = admission.get("target_sha256")
    if not isinstance(target_sha, dict):
        errors.append("admission.target_sha256 must be an object")
        target_sha = {}
    skills = workflow.get("skills")
    if not isinstance(skills, list) or any(
        not isinstance(skill, str) for skill in skills
    ):
        errors.append("gloamere-workflows.skills must be a Skill ID array")
        skills = []
    if set(target_sha) != set(skills):
        errors.append(
            "admission.target_sha256 keys must exactly match published workflow Skills"
        )

    workflow_path = safe_path(
        root,
        workflow.get("path"),
        "gloamere-workflows.path",
        errors,
    )
    for skill_id in skills:
        declared = target_sha.get(skill_id)
        if not isinstance(declared, str) or not SHA256.fullmatch(declared):
            errors.append(f"target SHA for {skill_id} is invalid")
            continue
        if workflow_path is None:
            continue
        skill_path = workflow_path / "skills" / skill_id / "SKILL.md"
        if not skill_path.is_file():
            errors.append(f"published Skill is missing: {skill_path}")
        elif sha256_file(skill_path) != declared:
            errors.append(f"current target SHA does not match {skill_id}")

    suite_cases = suite.get("cases")
    if not isinstance(suite_cases, list):
        errors.append("admission suite cases must be an array")
        suite_cases = []
    suite_case_map: dict[str, dict[str, Any]] = {}
    counts: Counter[tuple[str, str, str]] = Counter()
    mirrors: dict[str, dict[str, dict[str, Any]]] = {}
    for case in suite_cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str):
            errors.append("each admission case must have a string id")
            continue
        case_id = case["id"]
        if case_id in suite_case_map:
            errors.append(f"duplicate admission case id: {case_id}")
            continue
        suite_case_map[case_id] = case
        if case.get("plugin_id") != "gloamere-workflows":
            errors.append(f"{case_id}: plugin identity is not gloamere-workflows")
        focus = one_tag(case.get("tags"), "focus:")
        kind = one_tag(case.get("tags"), "kind:")
        language = case.get("language")
        if focus is None or kind is None or not isinstance(language, str):
            errors.append(f"{case_id}: focus, kind, or language is invalid")
            continue
        counts[(focus, kind, language)] += 1
        if kind == "adjacent-negative":
            risk = one_tag(case.get("tags"), "risk:")
            if risk not in {"ordinary", "high"}:
                errors.append(
                    f"{case_id}: adjacent-negative requires one risk tag"
                )
        base_id, separator, suffix = case_id.rpartition(".")
        expected_suffix = {"zh-CN": "zh", "en": "en"}.get(language)
        if separator != "." or suffix != expected_suffix:
            errors.append(f"{case_id}: bilingual mirror suffix is invalid")
        else:
            mirrors.setdefault(base_id, {})[language] = case

    for skill_id in skills:
        for language in ("zh-CN", "en"):
            for kind, expected_count in CASE_COUNTS.items():
                actual = counts[(skill_id, kind, language)]
                if actual != expected_count:
                    errors.append(
                        f"{skill_id}/{language}/{kind}: "
                        f"expected {expected_count} cases, found {actual}"
                    )
    for base_id, pair in mirrors.items():
        if set(pair) != {"zh-CN", "en"}:
            errors.append(f"{base_id}: bilingual mirror is incomplete")
            continue
        for field in (
            "plugin_id",
            "expected_skills",
            "forbidden_skills",
            "tags",
        ):
            if pair["zh-CN"].get(field) != pair["en"].get(field):
                errors.append(f"{base_id}: bilingual {field} does not mirror")

    execution_policy = suite.get("execution_policy")
    expected_policy = {
        "repeat": admission.get("repeat"),
        "independent_batches": admission.get("independent_batches"),
    }
    if execution_policy != expected_policy:
        errors.append("suite execution_policy does not mirror admission policy")
    if suite.get("plugin_id") != "gloamere-workflows":
        errors.append("suite plugin_id must be gloamere-workflows")

    reports = admission.get("reports")
    if not isinstance(reports, list):
        errors.append("admission.reports must be an array")
        reports = []

    contract = {
        "manifest": manifest,
        "workflow": workflow,
        "eval_plugin": eval_plugin,
        "admission": admission,
        "suite": suite,
        "suite_hash": sha256_object(suite) if suite else None,
        "suite_cases": suite_case_map,
        "target_sha": target_sha,
        "workflow_path": workflow_path,
        "reports": reports,
    }
    return contract, errors


def prompt_or_absolute_path_errors(
    value: Any,
    path: str = "report",
) -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key == "prompt":
                errors.append(f"{child_path}: prompt plaintext is forbidden")
            if key in {"plugin_root", "plugin_manifest_path", "skill_path"}:
                errors.append(f"{child_path}: absolute path field is forbidden")
            errors.extend(prompt_or_absolute_path_errors(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(
                prompt_or_absolute_path_errors(child, f"{path}[{index}]")
            )
    elif isinstance(value, str) and (
        WINDOWS_ABSOLUTE.match(value)
        or value.startswith(("/Users/", "/home/", "/private/", "/tmp/"))
    ):
        errors.append(f"{path}: absolute path plaintext is forbidden")
    return errors


def expected_target(
    contract: dict[str, Any],
    skill_id: str,
) -> dict[str, Any] | None:
    workflow = contract["workflow"]
    workflow_path = contract["workflow_path"]
    if workflow_path is None:
        return None
    manifest_path = workflow_path / ".codex-plugin" / "plugin.json"
    agent_path = workflow_path / "skills" / skill_id / "agents" / "openai.yaml"
    if not manifest_path.is_file() or not agent_path.is_file():
        return None
    return {
        "target_id": f"gloamere-workflows:{skill_id}",
        "plugin_id": "gloamere-workflows",
        "plugin_selector": "gloamere-workflows@gloamere",
        "plugin_version": workflow.get("version"),
        "installed": True,
        "enabled": True,
        "plugin_manifest_relative_path": ".codex-plugin/plugin.json",
        "plugin_manifest_sha256": sha256_file(manifest_path),
        "skill_name": skill_id,
        "relative_path": f"skills/{skill_id}/SKILL.md",
        "sha256": contract["target_sha"].get(skill_id),
        "agent_config_relative_path": f"skills/{skill_id}/agents/openai.yaml",
        "agent_config_sha256": sha256_file(agent_path),
    }


def validate_target_identity(
    report: dict[str, Any],
    evidence_entry: dict[str, Any],
    contract: dict[str, Any],
) -> tuple[dict[str, str], list[str]]:
    errors: list[str] = []
    lock = report.get("target_lock")
    if not isinstance(lock, dict):
        return {}, ["report target_lock must be an object"]
    expected_lock_sha = evidence_entry.get("target_lock_sha256")
    if not isinstance(expected_lock_sha, str) or not SHA256.fullmatch(
        expected_lock_sha
    ):
        errors.append("evidence entry target_lock_sha256 is invalid")
    if lock.get("sha256") != expected_lock_sha:
        errors.append("report target lock SHA does not match release manifest")

    targets = lock.get("targets")
    if not isinstance(targets, list):
        return {}, errors + ["report target_lock.targets must be an array"]
    by_skill: dict[str, dict[str, Any]] = {}
    for target in targets:
        if not isinstance(target, dict) or not isinstance(
            target.get("skill_name"), str
        ):
            errors.append("report target identity is malformed")
            continue
        if set(target) != TARGET_FIELDS:
            errors.append(
                f"{target.get('skill_name', '<unknown>')}: "
                "report target fields do not match report v3"
            )
        skill_id = target["skill_name"]
        if skill_id in by_skill:
            errors.append(f"duplicate report target identity: {skill_id}")
        by_skill[skill_id] = target
    if set(by_skill) != set(contract["target_sha"]):
        errors.append("report targets do not exactly match release targets")

    target_ids: dict[str, str] = {}
    for skill_id in contract["target_sha"]:
        expected = expected_target(contract, skill_id)
        actual = by_skill.get(skill_id)
        if expected is None:
            errors.append(f"cannot resolve local identity assets for {skill_id}")
            continue
        if actual is None:
            continue
        for field, expected_value in expected.items():
            if actual.get(field) != expected_value:
                errors.append(
                    f"{skill_id}: report target {field} does not match "
                    "the enabled release identity"
                )
        target_ids[skill_id] = expected["target_id"]
    return target_ids, errors


def validate_attempt(
    attempt: Any,
    case: dict[str, Any],
    expected_batch: set[tuple[int, int]],
    target_ids: dict[str, str],
    label: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    if not isinstance(attempt, dict):
        return None, [f"{label}: attempt must be an object"]
    if set(attempt) != ATTEMPT_FIELDS:
        errors.append(f"{label}: fields do not match prompt-free report v3")
    batch_id = attempt.get("batch_id")
    attempt_id = attempt.get("attempt")
    key = (batch_id, attempt_id)
    if key not in expected_batch:
        errors.append(f"{label}: attempt batch/number is outside the release grid")

    prompt_hash = sha256_text(case["prompt"])
    if attempt.get("prompt_sha256") != prompt_hash:
        errors.append(f"{label}: prompt hash does not match the suite")
    for field in ("expected_skills", "forbidden_skills"):
        if attempt.get(field) != sorted(case[field]):
            errors.append(f"{label}: {field} does not match the suite")

    expected_ids = sorted(target_ids[skill] for skill in case["expected_skills"])
    forbidden_ids = sorted(
        target_ids[skill] for skill in case["forbidden_skills"]
    )
    if attempt.get("expected_target_ids") != expected_ids:
        errors.append(f"{label}: expected_target_ids do not match target lock")
    if attempt.get("forbidden_target_ids") != forbidden_ids:
        errors.append(f"{label}: forbidden_target_ids do not match target lock")

    status = attempt.get("evidence_status")
    if status not in EVIDENCE_STATUSES:
        errors.append(f"{label}: evidence_status is invalid")
    observed = attempt.get("observed_skills")
    observed_ids = attempt.get("observed_target_ids")
    declared = attempt.get("declared_skills")
    declared_ids = attempt.get("declared_target_ids")
    array_fields = {
        "observed_skills": observed,
        "observed_target_ids": observed_ids,
        "declared_skills": declared,
        "declared_target_ids": declared_ids,
        "unbound_declared_skills": attempt.get("unbound_declared_skills"),
        "unbound_skill_names": attempt.get("unbound_skill_names"),
    }
    for field, values in array_fields.items():
        if (
            not isinstance(values, list)
            or any(not isinstance(value, str) for value in values)
            or len(values) != len(set(values))
        ):
            errors.append(f"{label}: {field} must be a unique string array")
    if (
        not isinstance(attempt.get("duration_ms"), int)
        or isinstance(attempt.get("duration_ms"), bool)
        or attempt["duration_ms"] < 0
    ):
        errors.append(f"{label}: duration_ms is invalid")
    if (
        not isinstance(attempt.get("reason"), str)
        or not attempt["reason"].strip()
    ):
        errors.append(f"{label}: reason must be a non-empty string")
    usage = attempt.get("usage")
    if usage is not None and (
        not isinstance(usage, dict)
        or any(
            not isinstance(key, str)
            or not isinstance(amount, int)
            or isinstance(amount, bool)
            or amount < 0
            for key, amount in usage.items()
        )
    ):
        errors.append(f"{label}: usage is invalid")

    observed_set = set(observed) if isinstance(observed, list) else set()
    expected_set = set(case["expected_skills"])
    forbidden_set = set(case["forbidden_skills"])
    exact = observed_set == expected_set and not observed_set & forbidden_set
    expected_verdict = "pass" if exact else "fail"

    if status == "verified":
        if attempt.get("verdict") != expected_verdict:
            errors.append(f"{label}: verdict does not match observed evidence")
        if attempt.get("unbound_declared_skills") or attempt.get(
            "unbound_skill_names"
        ):
            errors.append(f"{label}: verified evidence contains unbound Skills")
        if declared != observed or declared_ids != observed_ids:
            errors.append(
                f"{label}: verified declaration and host observation disagree"
            )
        resolved_observed_ids = sorted(
            target_ids[skill]
            for skill in observed_set
            if skill in target_ids
        )
        if observed_ids != resolved_observed_ids:
            errors.append(
                f"{label}: observed Skill names and target IDs disagree"
            )
        diagnostics = attempt.get("event_diagnostics")
        if not isinstance(diagnostics, dict):
            errors.append(f"{label}: event diagnostics are missing")
        else:
            # 根因：仅信任 complete 布尔值时，可伪造没有完整起止事件的
            # “verified” attempt；修复为同时约束事件数量和精确终态。
            if set(diagnostics) != DIAGNOSTIC_FIELDS:
                errors.append(
                    f"{label}: event diagnostic fields do not match report v3"
                )
            if diagnostics.get("complete") is not True:
                errors.append(f"{label}: verified event stream is incomplete")
            event_count = diagnostics.get("event_count")
            if (
                not isinstance(event_count, int)
                or isinstance(event_count, bool)
                or event_count < 3
            ):
                errors.append(f"{label}: verified stream has too few events")
            malformed_lines = diagnostics.get("malformed_lines")
            if (
                not isinstance(malformed_lines, int)
                or isinstance(malformed_lines, bool)
                or malformed_lines != 0
            ):
                errors.append(f"{label}: verified stream has malformed lines")
            for field in (
                "unknown_event_types",
                "unknown_item_types",
                "rejected_target_references",
            ):
                if diagnostics.get(field) != []:
                    errors.append(f"{label}: verified stream has {field}")
            if diagnostics.get("terminal_event") != "turn.completed":
                errors.append(
                    f"{label}: verified stream did not end with turn.completed"
                )
    elif attempt.get("verdict") is not None:
        errors.append(f"{label}: unverified evidence must have null verdict")

    record = {
        "status": status,
        "exact": exact,
        "observed": observed_set,
        "expected": expected_set,
        "kind": one_tag(case["tags"], "kind:"),
        "risk": one_tag(case["tags"], "risk:"),
        "key": key,
    }
    return record, errors


def expected_case_metrics(
    attempts: list[Any],
    repeat: int,
    independent_batches: int,
) -> dict[str, Any]:
    valid_attempts = [
        attempt for attempt in attempts if isinstance(attempt, dict)
    ]
    expected_pairs = {
        (batch, attempt)
        for batch in range(1, independent_batches + 1)
        for attempt in range(1, repeat + 1)
    }
    actual_pairs = [
        (attempt.get("batch_id"), attempt.get("attempt"))
        for attempt in valid_attempts
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
        for attempt in valid_attempts
    ]
    all_completed = (
        len(valid_attempts) == len(expected_pairs)
        and len(actual_pairs) == len(set(actual_pairs))
        and set(actual_pairs) == expected_pairs
        and all(
            attempt.get("evidence_status") == "verified"
            and attempt.get("verdict") in {"pass", "fail"}
            for attempt in valid_attempts
        )
    )
    scored = sum(
        attempt.get("evidence_status") == "verified"
        and attempt.get("verdict") in {"pass", "fail"}
        for attempt in valid_attempts
    )
    passed = sum(
        attempt.get("evidence_status") == "verified"
        and attempt.get("verdict") == "pass"
        for attempt in valid_attempts
    )
    expected_attempts = repeat * independent_batches
    return {
        "attempt_count": len(valid_attempts),
        "expected_attempts": expected_attempts,
        "scored_attempts": scored,
        "unscored_attempts": len(valid_attempts) - scored,
        "passed_attempts": passed,
        "failed_attempts": sum(
            attempt.get("evidence_status") == "verified"
            and attempt.get("verdict") == "fail"
            for attempt in valid_attempts
        ),
        "evidence_coverage": round(scored / expected_attempts, 4),
        "conditional_accuracy": round(passed / scored, 4) if scored else None,
        "stable": all_completed and len(set(signatures)) == 1,
        "evidence_statuses": dict(
            Counter(attempt.get("evidence_status") for attempt in valid_attempts)
        ),
        "verdicts": dict(
            Counter(
                str(attempt.get("verdict"))
                if attempt.get("verdict") is not None
                else "null"
                for attempt in valid_attempts
            )
        ),
    }


def expected_report_summary(
    report_cases: list[dict[str, Any]],
    case_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    attempts = [
        attempt
        for case in report_cases
        if isinstance(case.get("attempts"), list)
        for attempt in case["attempts"]
        if isinstance(attempt, dict)
    ]
    total = len(attempts)
    scored = sum(
        attempt.get("evidence_status") == "verified"
        and attempt.get("verdict") in {"pass", "fail"}
        for attempt in attempts
    )
    passed = sum(
        attempt.get("evidence_status") == "verified"
        and attempt.get("verdict") == "pass"
        for attempt in attempts
    )
    return {
        "case_count": len(report_cases),
        "attempt_count": total,
        "scored_attempts": scored,
        "unscored_attempts": total - scored,
        "passed_attempts": passed,
        "failed_attempts": sum(
            attempt.get("evidence_status") == "verified"
            and attempt.get("verdict") == "fail"
            for attempt in attempts
        ),
        "unobservable_attempts": sum(
            attempt.get("evidence_status") == "unobservable"
            for attempt in attempts
        ),
        "unavailable_attempts": sum(
            attempt.get("evidence_status") == "unavailable"
            for attempt in attempts
        ),
        "identity_conflicts": sum(
            attempt.get("evidence_status") == "identity_conflict"
            for attempt in attempts
        ),
        "execution_errors": sum(
            attempt.get("evidence_status") == "execution_error"
            for attempt in attempts
        ),
        "evidence_coverage": round(scored / total, 4) if total else 0.0,
        "conditional_accuracy": round(passed / scored, 4) if scored else None,
        "evidence_statuses": dict(
            Counter(attempt.get("evidence_status") for attempt in attempts)
        ),
        "stable_cases": sum(
            bool(metrics.get("stable")) for metrics in case_metrics.values()
        ),
    }


def validate_report(
    report: Any,
    evidence_entry: dict[str, Any],
    contract: dict[str, Any],
    report_label: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    records: list[dict[str, Any]] = []
    if not isinstance(report, dict):
        return [], [f"{report_label}: report must be an object"]

    if set(report) != REPORT_FIELDS:
        errors.append(f"{report_label}: top-level fields do not match report v3")
    if report.get("schema_version") != 3:
        errors.append(f"{report_label}: report schema must be v3")
    if not isinstance(report.get("generated_at"), str) or not report[
        "generated_at"
    ]:
        errors.append(f"{report_label}: generated_at is invalid")
    if report.get("execution_provenance") != "codex_cli":
        errors.append(f"{report_label}: fixture_adapter is not release evidence")
    if report.get("release_evidence_eligible") is not True:
        errors.append(f"{report_label}: report is not release-evidence eligible")
    if report.get("command") != "native":
        errors.append(f"{report_label}: command must be native")
    adapter = report.get("event_adapter")
    if adapter != {"id": "codex-exec-jsonl", "schema_version": 1}:
        errors.append(f"{report_label}: event adapter identity is invalid")
    producer = report.get("producer")
    eval_plugin = contract["eval_plugin"]
    if not isinstance(producer, dict) or (
        producer.get("id") != "gloamere-skill-eval"
        or producer.get("plugin_id") != "gloamere-eval"
        or producer.get("plugin_version") != eval_plugin.get("version")
    ):
        errors.append(f"{report_label}: producer identity is invalid")
    preflight = report.get("preflight")
    if not isinstance(preflight, dict) or preflight.get(
        "evidence_status"
    ) != "verified":
        errors.append(f"{report_label}: native preflight was not verified")
    elif (
        set(preflight) != {"evidence_status", "reasons"}
        or not isinstance(preflight.get("reasons"), list)
        or any(not isinstance(reason, str) for reason in preflight["reasons"])
        or len(preflight["reasons"]) != len(set(preflight["reasons"]))
    ):
        errors.append(f"{report_label}: preflight reasons are invalid")
    privacy = report.get("privacy")
    if not isinstance(privacy, dict) or (
        privacy.get("prompts_included") is not False
        or privacy.get("absolute_paths_included") is not False
    ):
        errors.append(f"{report_label}: privacy contract is not release-safe")
    errors.extend(
        f"{report_label}: {error}"
        for error in prompt_or_absolute_path_errors(report)
    )
    if report.get("repeat") != contract["admission"].get("repeat"):
        errors.append(f"{report_label}: repeat does not match admission")
    if report.get("independent_batches") != contract["admission"].get(
        "independent_batches"
    ):
        errors.append(
            f"{report_label}: independent_batches does not match admission"
        )
    timeout_seconds = report.get("timeout_seconds")
    if (
        not isinstance(timeout_seconds, int)
        or isinstance(timeout_seconds, bool)
        or timeout_seconds < 1
    ):
        errors.append(f"{report_label}: timeout_seconds is invalid")
    environment = report.get("environment")
    if not isinstance(environment, dict) or any(
        not isinstance(environment.get(field), str)
        or not environment[field].strip()
        for field in ("codex_version", "model", "python_version", "platform")
    ):
        errors.append(f"{report_label}: environment identity is incomplete")

    report_suite = report.get("suite")
    suite = contract["suite"]
    if not isinstance(report_suite, dict) or (
        report_suite.get("suite_id") != suite.get("suite_id")
        or report_suite.get("plugin_id") != suite.get("plugin_id")
        or report_suite.get("execution_policy") != suite.get("execution_policy")
        or report_suite.get("sha256") != contract["suite_hash"]
    ):
        errors.append(f"{report_label}: suite identity or SHA does not match")

    target_ids, target_errors = validate_target_identity(
        report,
        evidence_entry,
        contract,
    )
    errors.extend(f"{report_label}: {error}" for error in target_errors)
    if set(target_ids) != set(contract["target_sha"]):
        return records, errors

    report_cases = report.get("cases")
    if not isinstance(report_cases, list):
        return records, errors + [f"{report_label}: cases must be an array"]
    by_id: dict[str, dict[str, Any]] = {}
    for report_case in report_cases:
        if not isinstance(report_case, dict) or not isinstance(
            report_case.get("id"), str
        ):
            errors.append(f"{report_label}: malformed report case")
            continue
        if set(report_case) != CASE_FIELDS:
            errors.append(
                f"{report_label}/{report_case['id']}: "
                "fields do not match report v3"
            )
        case_id = report_case["id"]
        if case_id in by_id:
            errors.append(f"{report_label}: duplicate report case {case_id}")
        by_id[case_id] = report_case
    if set(by_id) != set(contract["suite_cases"]):
        errors.append(f"{report_label}: report does not cover the full suite")

    repeat = contract["admission"]["repeat"]
    batches = contract["admission"]["independent_batches"]
    expected_grid = {
        (batch, attempt)
        for batch in range(1, batches + 1)
        for attempt in range(1, repeat + 1)
    }
    computed_case_metrics: dict[str, dict[str, Any]] = {}
    for case_id, case in contract["suite_cases"].items():
        report_case = by_id.get(case_id)
        if report_case is None:
            continue
        for field in (
            "plugin_id",
            "language",
            "tags",
            "expected_skills",
            "forbidden_skills",
        ):
            expected_value = (
                sorted(case[field])
                if field in {"tags", "expected_skills", "forbidden_skills"}
                else case[field]
            )
            if report_case.get(field) != expected_value:
                errors.append(
                    f"{report_label}/{case_id}: {field} does not match suite"
                )
        if report_case.get("prompt_sha256") != sha256_text(case["prompt"]):
            errors.append(
                f"{report_label}/{case_id}: prompt hash does not match suite"
            )
        attempts = report_case.get("attempts")
        if not isinstance(attempts, list):
            errors.append(f"{report_label}/{case_id}: attempts must be an array")
            continue
        case_records: list[dict[str, Any]] = []
        seen: set[tuple[int, int]] = set()
        for index, attempt in enumerate(attempts):
            record, attempt_errors = validate_attempt(
                attempt,
                case,
                expected_grid,
                target_ids,
                f"{report_label}/{case_id}/attempt[{index}]",
            )
            errors.extend(attempt_errors)
            if record is not None:
                if record["key"] in seen:
                    errors.append(
                        f"{report_label}/{case_id}: duplicate attempt grid cell"
                    )
                seen.add(record["key"])
                case_records.append(record)
        if seen != expected_grid:
            errors.append(
                f"{report_label}/{case_id}: attempt grid is incomplete"
            )
        metrics = expected_case_metrics(attempts, repeat, batches)
        computed_case_metrics[case_id] = metrics
        for field, expected_value in metrics.items():
            if report_case.get(field) != expected_value:
                errors.append(
                    f"{report_label}/{case_id}: aggregate {field} "
                    "does not match attempts"
                )
        records.extend(case_records)
    expected_summary = expected_report_summary(
        [
            report_case
            for report_case in report_cases
            if isinstance(report_case, dict)
        ],
        computed_case_metrics,
    )
    if report.get("summary") != expected_summary:
        errors.append(
            f"{report_label}: report summary does not match full attempt data"
        )
    return records, errors


def recompute_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    verified_records = [
        record for record in records if record["status"] == "verified"
    ]
    exact = sum(record["exact"] for record in verified_records)
    ordinary = [
        record
        for record in records
        if record["kind"] == "adjacent-negative"
        and record["risk"] == "ordinary"
    ]
    high = [
        record
        for record in records
        if record["kind"] == "adjacent-negative"
        and record["risk"] == "high"
    ]
    multi = [
        record for record in records if record["kind"] == "multi-intent"
    ]

    def over_route(record: dict[str, Any]) -> bool:
        return bool(record["observed"] - record["expected"])

    ordinary_over = sum(
        record["status"] == "verified" and over_route(record)
        for record in ordinary
    )
    high_over = sum(
        record["status"] == "verified" and over_route(record)
        for record in high
    )
    multi_complete = sum(
        record["status"] == "verified"
        and record["expected"].issubset(record["observed"])
        for record in multi
    )
    return {
        "attempt_count": total,
        "verified_attempts": len(verified_records),
        "evidence_coverage": rate(len(verified_records), total),
        "verified_exact_matches": exact,
        "verified_exact_match": rate(exact, len(verified_records)),
        "ordinary_attempts": len(ordinary),
        "ordinary_over_routes": ordinary_over,
        "ordinary_over_route": rate(ordinary_over, len(ordinary)),
        "high_risk_attempts": len(high),
        "high_risk_over_routes": high_over,
        "high_risk_over_route": rate(high_over, len(high)),
        "multi_intent_attempts": len(multi),
        "multi_intent_complete_attempts": multi_complete,
        "multi_intent_complete": rate(multi_complete, len(multi)),
    }


def threshold_failures(
    metrics: dict[str, Any],
    thresholds: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    minimums = (
        "evidence_coverage",
        "verified_exact_match",
        "multi_intent_complete",
    )
    maximums = ("ordinary_over_route", "high_risk_over_route")
    for name in minimums:
        value = metrics.get(name)
        if value is None or value < thresholds[name]:
            failures.append(
                f"{name}={value!r} is below {thresholds[name]!r}"
            )
    for name in maximums:
        value = metrics.get(name)
        if value is None or value > thresholds[name]:
            failures.append(
                f"{name}={value!r} exceeds {thresholds[name]!r}"
            )
    return failures


def assess(
    root: Path = ROOT,
    manifest_path: Path = DEFAULT_MANIFEST,
    require: bool = False,
) -> tuple[dict[str, Any], int]:
    contract, configuration_errors = load_contract(root, manifest_path)
    result: dict[str, Any] = {
        "status": "fail",
        "required": require,
        "configuration_errors": configuration_errors,
        "evidence_errors": [],
        "threshold_failures": [],
        "metrics": None,
    }
    if contract is None or configuration_errors:
        return result, 1

    report_entries = contract["reports"]
    if not report_entries:
        result["status"] = "pending"
        result["evidence_errors"] = ["no native report v3 is declared"]
        return result, 1 if require else 0

    all_records: list[dict[str, Any]] = []
    evidence_errors: list[str] = []
    seen_paths: set[Path] = set()
    seen_hashes: set[str] = set()
    for index, entry in enumerate(report_entries):
        label = f"admission.reports[{index}]"
        if not isinstance(entry, dict):
            evidence_errors.append(f"{label}: entry must be an object")
            continue
        report_path = safe_path(
            root,
            entry.get("path"),
            f"{label}.path",
            evidence_errors,
        )
        if report_path is None:
            continue
        if report_path in seen_paths:
            evidence_errors.append(f"{label}: duplicate report path")
            continue
        seen_paths.add(report_path)
        expected_hash = entry.get("sha256")
        if not isinstance(expected_hash, str) or not SHA256.fullmatch(
            expected_hash
        ):
            evidence_errors.append(f"{label}.sha256 is invalid")
            continue
        if expected_hash in seen_hashes:
            evidence_errors.append(f"{label}: duplicate report SHA")
            continue
        seen_hashes.add(expected_hash)
        if not report_path.is_file():
            evidence_errors.append(f"{label}: report file is missing")
            continue
        if sha256_file(report_path) != expected_hash:
            evidence_errors.append(f"{label}: report file SHA mismatch")
            continue
        try:
            report = read_json(report_path)
        except (OSError, json.JSONDecodeError) as exc:
            evidence_errors.append(f"{label}: cannot read report: {exc}")
            continue
        records, errors = validate_report(
            report,
            entry,
            contract,
            report_path.relative_to(root).as_posix(),
        )
        evidence_errors.extend(errors)
        all_records.extend(records)

    result["evidence_errors"] = evidence_errors
    if evidence_errors:
        return result, 1

    metrics = recompute_metrics(all_records)
    failures = threshold_failures(
        metrics,
        contract["admission"]["thresholds"],
    )
    result["metrics"] = metrics
    result["threshold_failures"] = failures
    if failures:
        result["status"] = "pending"
        return result, 1 if require else 0
    result["status"] = "pass"
    return result, 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Release manifest to validate.",
    )
    parser.add_argument(
        "--require",
        action="store_true",
        help="Fail when evidence is missing or below release thresholds.",
    )
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    root = manifest_path.parent
    result, code = assess(root, manifest_path, args.require)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
