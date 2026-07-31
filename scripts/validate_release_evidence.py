"""Gate releases on current, path-bound report v4 evidence.

The gate is deliberately fail-closed for configured evidence.  With no
declared report, or with valid evidence that misses a metric threshold, the
candidate is ``pending`` and only ``--require`` changes that state into a
non-zero exit.  A malformed, stale, synthetic, privacy-unsafe, or otherwise
mis-bound report always fails.

Schema v3 remains readable by the eval runner for historical analysis, but it
is never eligible release evidence.

``--require`` gates the risk-tiered release sample.  The independent
``--require-exhaustive`` gate is used for the first directory submission and
requires all 102 cases to receive a first-round attempt before anomaly-only
retries.  Release reports may reuse unchanged-Skill evidence only when their
exact reuse key matches and their disjoint changed-Skill sets cover the public
plugin.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "release-manifest.json"
RUNNER_PATH = (
    ROOT
    / "plugins"
    / "gloamere-eval"
    / "skills"
    / "gloamere-skill-eval"
    / "scripts"
    / "run_routing_eval.py"
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_COMMIT = re.compile(r"^[0-9a-f]{40,64}$")
WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]|^\\\\")
WINDOWS_ABSOLUTE_ANYWHERE = re.compile(
    r"""(?:^|[\s"'(<\[])(?:[A-Za-z]:[\\/]|\\\\)"""
)
PUBLIC_SKILLS = {
    "gloamere-knowledge-capture",
    "gloamere-product-decision",
    "gloamere-visual-review",
}
REQUIRED_THRESHOLDS = {
    "evidence_coverage": 1.0,
    "verified_exact_match": 0.95,
    "ordinary_over_route": 0.02,
    "multi_intent_complete": 0.9,
    "high_risk_over_route": 0,
}
REQUIRED_BUDGETS = {
    "pr": 12,
    "release": 40,
    "monthly": 16,
}
CASE_COUNTS = {
    "positive": 6,
    "adjacent-negative": 8,
    "multi-intent": 3,
}
RUBRIC_FIELDS = {
    "evidence_fidelity",
    "actionability",
    "boundary_compliance",
    "no_fabrication",
}

REPORT_FIELDS = {
    "schema_version",
    "generated_at",
    "producer",
    "command",
    "event_adapter",
    "execution_provenance",
    "release_evidence_eligible",
    "evaluation",
    "provenance",
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
EVALUATION_FIELDS = {
    "policy_id",
    "policy",
    "policy_source",
    "mode",
    "selection_reason",
    "selection",
    "selected_case_ids",
    "changed_skills",
    "rotation_key",
    "execution_strategy",
    "max_calls",
    "routing_max_calls",
    "quality_reserved_calls",
    "projected_total_calls",
    "initial_planned_calls",
    "retry_planned_calls",
    "planned_calls",
    "actual_calls",
    "initial_actual_calls",
    "retry_actual_calls",
    "initial_phase_complete",
    "resumed_calls",
    "new_calls",
    "shard",
    "complete",
    "case_outcomes",
    "outcomes",
    "pending_case_ids",
    "failed_case_ids",
}
PROVENANCE_FIELDS = {
    "commit",
    "policy_sha256",
    "suite_sha256",
    "target_lock_sha256",
    "target_sha256",
    "codex_cli",
    "model",
    "generated_at",
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
ADAPTIVE_FIELDS = {
    "enabled",
    "outcome",
    "reason",
    "initial_anomaly",
    "retry_complete",
    "expected_attempts",
    "verified_passes",
    "verified_failures",
    "confirmed_same_failures",
    "infrastructure_failures",
    "identity_conflicts",
}
SUMMARY_FIELDS = {
    "case_count",
    "attempt_count",
    "scored_attempts",
    "unscored_attempts",
    "passed_attempts",
    "failed_attempts",
    "unobservable_attempts",
    "unavailable_attempts",
    "identity_conflicts",
    "execution_errors",
    "evidence_coverage",
    "conditional_accuracy",
    "evidence_statuses",
    "stable_cases",
}

_RUNNER: ModuleType | None = None


def runner_module() -> ModuleType:
    """Load the self-contained runner without making a model call."""
    global _RUNNER
    if _RUNNER is not None:
        return _RUNNER
    name = "_gloamere_release_gate_runner"
    spec = importlib.util.spec_from_file_location(name, RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load eval runner: {RUNNER_PATH}")
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves annotation metadata through sys.modules.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    _RUNNER = module
    return module


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
    if candidate.is_absolute() or WINDOWS_ABSOLUTE.match(value):
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


def _load_bound_json(
    root: Path,
    owner: dict[str, Any],
    path_field: str,
    hash_field: str,
    label: str,
    errors: list[str],
) -> tuple[Path | None, dict[str, Any]]:
    path = safe_path(root, owner.get(path_field), f"{label}.{path_field}", errors)
    declared = owner.get(hash_field)
    if not isinstance(declared, str) or not SHA256.fullmatch(declared):
        errors.append(f"{label}.{hash_field} must be a lowercase SHA-256")
    value: dict[str, Any] = {}
    if path is None:
        return None, value
    try:
        loaded = read_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"cannot read {label}: {exc}")
        return path, value
    if not isinstance(loaded, dict):
        errors.append(f"{label} must be a JSON object")
        return path, value
    value = loaded
    if isinstance(declared, str) and SHA256.fullmatch(declared):
        if sha256_file(path) != declared:
            errors.append(f"{label} file SHA does not match release manifest")
    return path, value


def _validate_suite(
    suite: dict[str, Any],
    skills: list[str],
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    if suite.get("schema_version") != 2:
        errors.append("admission suite schema_version must be 2")
    if suite.get("plugin_id") != "gloamere-workflows":
        errors.append("admission suite plugin_id must be gloamere-workflows")
    expected_execution = {
        "policy_id": "risk-tiered-v2",
        "repeat": 1,
        "independent_batches": 1,
    }
    if suite.get("execution_policy") != expected_execution:
        errors.append(
            "suite execution_policy must use risk-tiered-v2 with one attempt"
        )

    cases = suite.get("cases")
    if not isinstance(cases, list):
        errors.append("admission suite cases must be an array")
        return {}
    if len(cases) != 102:
        errors.append(f"admission suite must contain 102 cases, found {len(cases)}")

    by_id: dict[str, dict[str, Any]] = {}
    counts: Counter[tuple[str, str, str]] = Counter()
    mirrors: dict[str, dict[str, dict[str, Any]]] = {}
    for index, case in enumerate(cases):
        label = f"admission suite cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{label} must be an object")
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id:
            errors.append(f"{label}.id must be a non-empty string")
            continue
        if case_id in by_id:
            errors.append(f"duplicate admission case id: {case_id}")
            continue
        by_id[case_id] = case
        if case.get("plugin_id") != "gloamere-workflows":
            errors.append(f"{case_id}: plugin identity is invalid")
        if not isinstance(case.get("prompt"), str) or not case["prompt"].strip():
            errors.append(f"{case_id}: prompt must be non-empty")
        for field in ("expected_skills", "forbidden_skills"):
            values = case.get(field)
            if (
                not isinstance(values, list)
                or any(not isinstance(value, str) for value in values)
                or len(values) != len(set(values))
                or not set(values).issubset(skills)
            ):
                errors.append(f"{case_id}: {field} is invalid")
        focus = one_tag(case.get("tags"), "focus:")
        kind = one_tag(case.get("tags"), "kind:")
        language = case.get("language")
        if focus not in skills or kind not in CASE_COUNTS:
            errors.append(f"{case_id}: focus or kind tag is invalid")
            continue
        if language not in {"zh-CN", "en"}:
            errors.append(f"{case_id}: language is invalid")
            continue
        counts[(focus, kind, language)] += 1
        if kind == "adjacent-negative":
            if one_tag(case.get("tags"), "risk:") not in {"ordinary", "high"}:
                errors.append(
                    f"{case_id}: adjacent-negative requires one risk tag"
                )
        base_id, separator, suffix = case_id.rpartition(".")
        expected_suffix = {"zh-CN": "zh", "en": "en"}[language]
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
                        f"{skill_id}/{language}/{kind}: expected "
                        f"{expected_count} cases, found {actual}"
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
    return by_id


def _validate_quality_suite(
    root: Path,
    quality_path: Path | None,
    quality: dict[str, Any],
    skills: list[str],
    errors: list[str],
) -> None:
    if quality.get("schema_version") != 1:
        errors.append("quality suite schema_version must be 1")
    cases = quality.get("cases")
    if not isinstance(cases, list):
        errors.append("quality suite cases must be an array")
        return
    counts: Counter[tuple[str, str]] = Counter()
    ids: set[str] = set()
    for index, case in enumerate(cases):
        label = f"quality suite cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{label} must be an object")
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id or case_id in ids:
            errors.append(f"{label}.id must be unique and non-empty")
        else:
            ids.add(case_id)
        skill = case.get("skill_id")
        language = case.get("language")
        if skill not in skills or language not in {"zh-CN", "en"}:
            errors.append(f"{label}: skill_id or language is invalid")
        else:
            counts[(skill, language)] += 1
        rubric = case.get("rubric")
        if (
            not isinstance(rubric, dict)
            or set(rubric) != RUBRIC_FIELDS
            or any(
                not isinstance(value, str) or not value.strip()
                for value in rubric.values()
            )
        ):
            errors.append(f"{label}.rubric does not match the registered rubric")
        fixture_paths = case.get("fixture_paths")
        if not isinstance(fixture_paths, list) or not fixture_paths:
            errors.append(f"{label}.fixture_paths must be a non-empty array")
            continue
        if quality_path is None:
            continue
        for fixture_index, fixture in enumerate(fixture_paths):
            fixture_path = safe_path(
                quality_path.parent,
                fixture,
                f"{label}.fixture_paths[{fixture_index}]",
                errors,
            )
            if fixture_path is not None and not fixture_path.is_file():
                errors.append(f"{label}: fixture is missing: {fixture}")
    for skill in skills:
        for language in ("zh-CN", "en"):
            if counts[(skill, language)] != 1:
                errors.append(
                    f"quality suite requires one {language} case for {skill}"
                )


def load_contract(
    root: Path,
    manifest_path: Path,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Load and bind the manifest, suites, policy, and current Skill content."""
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

    if admission.get("policy_id") != "risk-tiered-v2":
        errors.append("admission.policy_id must be risk-tiered-v2")
    if admission.get("report_schema_version") != 4:
        errors.append("admission.report_schema_version must be 4")
    if admission.get("release_mode") != "release":
        errors.append("admission.release_mode must be release")
    budgets = admission.get("budgets")
    if not isinstance(budgets, dict):
        errors.append("admission.budgets must be an object")
        budgets = {}
    for mode, expected_budget in REQUIRED_BUDGETS.items():
        if budgets.get(mode) != expected_budget:
            errors.append(
                f"admission.budgets.{mode} must be {expected_budget}"
            )
    exhaustive_budget = budgets.get("exhaustive")
    if (
        not isinstance(exhaustive_budget, int)
        or isinstance(exhaustive_budget, bool)
        or exhaustive_budget < 102
    ):
        errors.append(
            "admission.budgets.exhaustive must cover 102 initial calls"
        )
    if budgets.get("exhaustive_initial") not in {None, 102}:
        errors.append("admission.budgets.exhaustive_initial must be 102")
    if admission.get("thresholds") != REQUIRED_THRESHOLDS:
        errors.append("admission.thresholds must match the release contract")

    suite_path, suite = _load_bound_json(
        root,
        admission,
        "suite_path",
        "suite_sha256",
        "admission suite",
        errors,
    )
    policy_path, policy = _load_bound_json(
        root,
        admission,
        "policy_path",
        "policy_sha256",
        "evaluation policy",
        errors,
    )
    quality_path, quality = _load_bound_json(
        root,
        admission,
        "quality_suite_path",
        "quality_suite_sha256",
        "quality suite",
        errors,
    )

    skills_value = workflow.get("skills")
    if (
        not isinstance(skills_value, list)
        or any(not isinstance(skill, str) for skill in skills_value)
        or len(skills_value) != len(set(skills_value))
    ):
        errors.append("gloamere-workflows.skills must be a unique Skill ID array")
        skills: list[str] = []
    else:
        skills = skills_value
    if set(skills) != PUBLIC_SKILLS:
        errors.append("the directory release must contain exactly three public Skills")

    target_sha = admission.get("target_sha256")
    if not isinstance(target_sha, dict):
        errors.append("admission.target_sha256 must be an object")
        target_sha = {}
    if set(target_sha) != set(skills):
        errors.append(
            "admission.target_sha256 keys must match the published Skills"
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
        agent_path = workflow_path / "skills" / skill_id / "agents" / "openai.yaml"
        if not skill_path.is_file():
            errors.append(f"published Skill is missing: {skill_id}")
        elif sha256_file(skill_path) != declared:
            errors.append(f"current target SHA does not match {skill_id}")
        if not agent_path.is_file():
            errors.append(f"published Skill agent config is missing: {skill_id}")

    suite_cases = _validate_suite(suite, skills, errors) if suite else {}
    if policy:
        policy_id = policy.get("id", policy.get("policy_id"))
        if policy_id != "risk-tiered-v2":
            errors.append("evaluation policy identity is invalid")
        if policy.get("suite_id") != suite.get("suite_id"):
            errors.append("evaluation policy suite_id does not match suite")
        modes = policy.get("modes")
        if not isinstance(modes, dict):
            errors.append("evaluation policy modes must be an object")
        else:
            for mode in ("pr", "release", "exhaustive"):
                mode_policy = modes.get(mode)
                budget = budgets.get(mode)
                if (
                    not isinstance(mode_policy, dict)
                    or mode_policy.get("max_calls") != budget
                ):
                    errors.append(
                        f"evaluation policy {mode}.max_calls must be {budget}"
                    )
            exhaustive_policy = modes.get("exhaustive")
            if isinstance(exhaustive_policy, dict) and (
                exhaustive_policy.get("initial_calls") != 102
            ):
                errors.append(
                    "evaluation policy exhaustive.initial_calls must be 102"
                )
        if suite:
            try:
                selected, _, _ = runner_module().risk_selected_cases(
                    suite,
                    "release",
                    None,
                    "contract-check",
                    policy,
                    skills,
                )
            except (KeyError, TypeError, ValueError) as exc:
                errors.append(f"release selection policy is invalid: {exc}")
            else:
                if not 22 <= len(selected) <= 34:
                    errors.append(
                        "release selection must contain 22-34 routing cases "
                        "when all Skills changed"
                    )
    if quality:
        _validate_quality_suite(
            root,
            quality_path,
            quality,
            skills,
            errors,
        )

    reports = admission.get("reports")
    if not isinstance(reports, list):
        errors.append("admission.reports must be an array")
        reports = []
    exhaustive_reports = admission.get("exhaustive_reports", [])
    if not isinstance(exhaustive_reports, list):
        errors.append("admission.exhaustive_reports must be an array")
        exhaustive_reports = []

    return {
        "root": root.resolve(),
        "manifest": manifest,
        "workflow": workflow,
        "eval_plugin": eval_plugin,
        "admission": admission,
        "suite": suite,
        # Report v4 and the release manifest both bind the exact suite bytes.
        "suite_hash": sha256_file(suite_path) if suite_path else None,
        "suite_file_hash": sha256_file(suite_path) if suite_path else None,
        "suite_cases": suite_cases,
        "suite_path": suite_path,
        "policy": policy,
        "policy_path": policy_path,
        "policy_hash": sha256_file(policy_path) if policy_path else None,
        "quality": quality,
        "quality_path": quality_path,
        "quality_hash": sha256_file(quality_path) if quality_path else None,
        "target_sha": target_sha,
        "workflow_path": workflow_path,
        "reports": reports,
        "exhaustive_reports": exhaustive_reports,
        "skills": skills,
    }, errors


def prompt_or_absolute_path_errors(
    value: Any,
    path: str = "report",
) -> list[str]:
    """Reject prompt plaintext and obvious absolute paths at any depth."""
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key == "prompt":
                errors.append(f"{child_path}: prompt plaintext is forbidden")
            if key in {
                "plugin_root",
                "plugin_manifest_path",
                "skill_path",
                "agent_config_path",
            }:
                errors.append(f"{child_path}: absolute path field is forbidden")
            errors.extend(prompt_or_absolute_path_errors(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(
                prompt_or_absolute_path_errors(child, f"{path}[{index}]")
            )
    elif isinstance(value, str) and (
        WINDOWS_ABSOLUTE_ANYWHERE.search(value)
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


def _field_error(value: Any, expected: set[str], label: str) -> str | None:
    if not isinstance(value, dict):
        return f"{label} must be an object"
    missing = sorted(expected.difference(value))
    extra = sorted(set(value).difference(expected))
    if missing or extra:
        return (
            f"{label} fields do not match report v4 "
            f"(missing={missing}, extra={extra})"
        )
    return None


def _shape_errors(report: dict[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    objects = (
        (report, REPORT_FIELDS, label),
        (report.get("evaluation"), EVALUATION_FIELDS, f"{label}.evaluation"),
        (report.get("provenance"), PROVENANCE_FIELDS, f"{label}.provenance"),
        (
            report.get("producer"),
            {"id", "plugin_id", "plugin_version"},
            f"{label}.producer",
        ),
        (
            report.get("event_adapter"),
            {"id", "schema_version"},
            f"{label}.event_adapter",
        ),
        (
            report.get("preflight"),
            {"evidence_status", "reasons"},
            f"{label}.preflight",
        ),
        (
            report.get("suite"),
            {"suite_id", "plugin_id", "execution_policy", "sha256"},
            f"{label}.suite",
        ),
        (
            report.get("environment"),
            {"codex_version", "model", "python_version", "platform"},
            f"{label}.environment",
        ),
        (
            report.get("privacy"),
            {"prompts_included", "absolute_paths_included"},
            f"{label}.privacy",
        ),
        (report.get("summary"), SUMMARY_FIELDS, f"{label}.summary"),
    )
    for value, fields, object_label in objects:
        error = _field_error(value, fields, object_label)
        if error:
            errors.append(error)
    lock = report.get("target_lock")
    error = _field_error(lock, {"sha256", "targets"}, f"{label}.target_lock")
    if error:
        errors.append(error)
    elif isinstance(lock.get("targets"), list):
        for index, target in enumerate(lock["targets"]):
            error = _field_error(
                target,
                TARGET_FIELDS,
                f"{label}.target_lock.targets[{index}]",
            )
            if error:
                errors.append(error)
    cases = report.get("cases")
    if isinstance(cases, list):
        for case_index, case in enumerate(cases):
            case_label = f"{label}.cases[{case_index}]"
            if not isinstance(case, dict):
                errors.append(f"{case_label} must be an object")
                continue
            missing = sorted(CASE_FIELDS.difference(case))
            extra = sorted(
                set(case).difference(CASE_FIELDS | {"adaptive_evaluation"})
            )
            if missing or extra:
                errors.append(
                    f"{case_label} fields do not match report v4 "
                    f"(missing={missing}, extra={extra})"
                )
                continue
            if "adaptive_evaluation" in case:
                error = _field_error(
                    case["adaptive_evaluation"],
                    ADAPTIVE_FIELDS,
                    f"{case_label}.adaptive_evaluation",
                )
                if error:
                    errors.append(error)
            attempts = case.get("attempts")
            if not isinstance(attempts, list):
                continue
            for attempt_index, attempt in enumerate(attempts):
                attempt_label = f"{case_label}.attempts[{attempt_index}]"
                error = _field_error(attempt, ATTEMPT_FIELDS, attempt_label)
                if error:
                    errors.append(error)
                    continue
                error = _field_error(
                    attempt.get("event_diagnostics"),
                    DIAGNOSTIC_FIELDS,
                    f"{attempt_label}.event_diagnostics",
                )
                if error:
                    errors.append(error)
    return errors


def _utc_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return (
        parsed.tzinfo is not None
        and parsed.utcoffset() == timezone.utc.utcoffset(parsed)
    )


def _repository_commit(root: Path) -> str | None:
    try:
        completed = subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={root.resolve().as_posix()}",
                "-C",
                str(root),
                "rev-parse",
                "HEAD",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = completed.stdout.strip().lower()
    return value if GIT_COMMIT.fullmatch(value) else None


def _is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    """Return whether evaluated commit is reachable from the release commit."""
    try:
        completed = subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={root.resolve().as_posix()}",
                "-C",
                str(root),
                "merge-base",
                "--is-ancestor",
                ancestor,
                descendant,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def _selection_for_report(
    report: dict[str, Any],
    contract: dict[str, Any],
    label: str,
    evidence_mode: str = "release",
) -> tuple[list[dict[str, Any]], dict[str, str], str, list[str]]:
    errors: list[str] = []
    evaluation = report.get("evaluation")
    if not isinstance(evaluation, dict):
        return [], {}, "", [f"{label}: evaluation contract is missing"]
    mode = evaluation.get("mode")
    changed = evaluation.get("changed_skills")
    rotation = evaluation.get("rotation_key")
    if mode != evidence_mode:
        errors.append(f"{label}: evaluation mode must be {evidence_mode}")
    if (
        not isinstance(changed, list)
        or any(not isinstance(skill, str) for skill in changed)
        or len(changed) != len(set(changed))
        or not set(changed).issubset(contract["skills"])
    ):
        errors.append(f"{label}: changed_skills is not a published Skill subset")
        changed = []
    elif evidence_mode == "release" and not changed:
        errors.append(
            f"{label}: release changed_skills must be a non-empty subset"
        )
    elif evidence_mode == "exhaustive" and changed:
        errors.append(
            f"{label}: exhaustive evidence must not narrow changed_skills"
        )
    if evidence_mode == "release" and (
        not isinstance(rotation, str) or not rotation
    ):
        errors.append(f"{label}: release rotation_key must be non-empty")
        rotation = ""
    elif rotation is not None and not isinstance(rotation, str):
        errors.append(f"{label}: rotation_key must be a string or null")
        rotation = ""
    try:
        selected, roles, reason = runner_module().risk_selected_cases(
            contract["suite"],
            evidence_mode,
            None,
            rotation or "",
            contract["policy"],
            changed,
        )
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"{label}: cannot recompute risk selection: {exc}")
        return [], {}, "", errors
    if evidence_mode == "release":
        quality_policy = contract["policy"].get("quality")
        quality_per_skill = (
            quality_policy.get("release_cases_per_changed_skill", 0)
            if isinstance(quality_policy, dict)
            else 0
        )
        quality_reserved = quality_per_skill * len(set(changed))
        if quality_reserved:
            reason += (
                f"; reserving {quality_reserved} of "
                f"{contract['admission']['budgets']['release']} calls "
                "for output-quality evaluation"
            )
    else:
        initial_calls = contract["policy"].get("modes", {}).get(
            "exhaustive",
            {},
        ).get("initial_calls")
        hard_cap = contract["admission"]["budgets"]["exhaustive"]
        if isinstance(initial_calls, int):
            reason += (
                f"; complete all {initial_calls} initial calls before "
                f"adaptive retries (capacity {hard_cap - initial_calls})"
            )

    shard = evaluation.get("shard")
    if shard is not None:
        if (
            not isinstance(shard, dict)
            or not isinstance(shard.get("index"), int)
            or isinstance(shard.get("index"), bool)
            or not isinstance(shard.get("total"), int)
            or isinstance(shard.get("total"), bool)
            or shard["index"] < 1
            or shard["total"] < shard["index"]
        ):
            errors.append(f"{label}: shard is invalid")
            return [], {}, "", errors
        selected = [
            case
            for offset, case in enumerate(selected)
            if offset % shard["total"] == shard["index"] - 1
        ]
        roles = {case["id"]: roles[case["id"]] for case in selected}
    return selected, roles, reason, errors


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
        skill = target["skill_name"]
        if skill in by_skill:
            errors.append(f"duplicate report target identity: {skill}")
        by_skill[skill] = target
    if set(by_skill) != set(contract["target_sha"]):
        errors.append("report targets do not exactly match release targets")

    target_ids: dict[str, str] = {}
    for skill in contract["skills"]:
        expected = expected_target(contract, skill)
        actual = by_skill.get(skill)
        if expected is None:
            errors.append(f"cannot resolve current identity assets for {skill}")
            continue
        if actual is None:
            continue
        for field, expected_value in expected.items():
            if actual.get(field) != expected_value:
                errors.append(
                    f"{skill}: report target {field} does not match "
                    "the enabled release identity"
                )
        target_ids[skill] = expected["target_id"]
    return target_ids, errors


def _entry_binding_errors(
    report: dict[str, Any],
    evidence_entry: dict[str, Any],
    label: str,
) -> list[str]:
    errors: list[str] = []
    provenance = report.get("provenance")
    if not isinstance(provenance, dict):
        return errors
    for entry_field in ("model", "codex_cli"):
        expected = evidence_entry.get(entry_field)
        if not isinstance(expected, str) or not expected.strip():
            errors.append(
                f"{label}: evidence entry {entry_field} must be non-empty"
            )
        elif expected != provenance.get(entry_field):
            errors.append(
                f"{label}: evidence entry {entry_field} does not match report"
            )
    if "commit" in evidence_entry and (
        evidence_entry["commit"] != provenance.get("commit")
    ):
        errors.append(f"{label}: evidence entry commit does not match report")
    return errors


def validate_report(
    report: Any,
    evidence_entry: dict[str, Any],
    contract: dict[str, Any],
    report_label: str,
    evidence_mode: str = "release",
) -> tuple[list[dict[str, Any]], list[str]]:
    """Validate one report and return independently recomputable records."""
    if not isinstance(report, dict):
        return [], [f"{report_label}: report must be an object"]
    version = report.get("schema_version")
    if version == 3:
        return [], [
            f"{report_label}: report v3 is read-only historical evidence and "
            "is not eligible for release"
        ]
    if version != 4:
        return [], [f"{report_label}: release evidence must use report v4"]

    errors = _shape_errors(report, report_label)
    errors.extend(
        f"{report_label}: {error}"
        for error in runner_module().validate_report_v4(report)
    )
    errors.extend(prompt_or_absolute_path_errors(report, report_label))
    errors.extend(_entry_binding_errors(report, evidence_entry, report_label))

    if report.get("execution_provenance") != "codex_cli":
        errors.append(f"{report_label}: only codex_cli is release evidence")
    evaluation_value = report.get("evaluation")
    pending_case_ids = (
        evaluation_value.get("pending_case_ids")
        if isinstance(evaluation_value, dict)
        else None
    )
    if (
        report.get("release_evidence_eligible") is not True
        and not pending_case_ids
    ):
        errors.append(f"{report_label}: report is not release-evidence eligible")
    privacy = report.get("privacy")
    if not isinstance(privacy, dict) or privacy.get("prompts_included") is not False:
        errors.append(f"{report_label}: privacy contract must omit prompts")
    preflight = report.get("preflight")
    if preflight != {"evidence_status": "verified", "reasons": []}:
        errors.append(f"{report_label}: native preflight must be verified")

    generated_at = report.get("generated_at")
    provenance = report.get("provenance")
    if not _utc_timestamp(generated_at):
        errors.append(f"{report_label}: generated_at must be an ISO UTC timestamp")
    if not isinstance(provenance, dict):
        provenance = {}
    if (
        not _utc_timestamp(provenance.get("generated_at"))
        or provenance.get("generated_at") != generated_at
    ):
        errors.append(
            f"{report_label}: provenance.generated_at must match ISO UTC time"
        )
    repository_root = contract["root"]
    current_commit = _repository_commit(repository_root)
    commit = provenance.get("commit")
    if current_commit is None:
        errors.append(f"{report_label}: current repository commit is unavailable")
    elif (
        not isinstance(commit, str)
        or not GIT_COMMIT.fullmatch(commit)
        or not _is_ancestor(repository_root, commit, current_commit)
    ):
        errors.append(
            f"{report_label}: provenance.commit is not the current commit "
            "or one of its ancestors"
        )
    codex_cli = provenance.get("codex_cli")
    model = provenance.get("model")
    if not isinstance(codex_cli, str) or not codex_cli.strip():
        errors.append(f"{report_label}: provenance.codex_cli must be non-empty")
    if not isinstance(model, str) or not model.strip():
        errors.append(f"{report_label}: provenance.model must be non-empty")

    evaluation = report.get("evaluation")
    if not isinstance(evaluation, dict):
        evaluation = {}
    if evaluation.get("policy_id") != contract["admission"].get("policy_id"):
        errors.append(f"{report_label}: evaluation policy ID is stale")
    if evaluation.get("policy") != contract["policy"]:
        errors.append(f"{report_label}: embedded evaluation policy is stale")
    expected_policy_source = (
        contract["policy_path"].name if contract["policy_path"] else None
    )
    if evaluation.get("policy_source") != expected_policy_source:
        errors.append(f"{report_label}: evaluation policy source is stale")
    if provenance.get("policy_sha256") != contract["policy_hash"]:
        errors.append(f"{report_label}: policy SHA does not match current policy")
    if provenance.get("suite_sha256") != contract["suite_hash"]:
        errors.append(f"{report_label}: suite SHA does not match current suite")
    suite_binding = report.get("suite")
    if not isinstance(suite_binding, dict) or (
        suite_binding.get("suite_id") != contract["suite"].get("suite_id")
        or suite_binding.get("plugin_id") != contract["suite"].get("plugin_id")
        or suite_binding.get("sha256") != contract["suite_hash"]
        or suite_binding.get("execution_policy")
        != {"repeat": 1, "independent_batches": 1}
    ):
        errors.append(f"{report_label}: suite identity or SHA is stale")
    if report.get("repeat") != 1 or report.get("independent_batches") != 1:
        errors.append(f"{report_label}: release evidence must run each case once")
    if evaluation.get("complete") is not True and not pending_case_ids:
        errors.append(f"{report_label}: evaluation is incomplete")

    budget = contract["admission"]["budgets"][evidence_mode]
    for field in (
        "max_calls",
        "routing_max_calls",
        "quality_reserved_calls",
        "projected_total_calls",
        "initial_planned_calls",
        "retry_planned_calls",
        "planned_calls",
        "actual_calls",
    ):
        amount = evaluation.get(field)
        if (
            not isinstance(amount, int)
            or isinstance(amount, bool)
            or amount < 0
            or amount > budget
        ):
            errors.append(
                f"{report_label}: evaluation.{field} exceeds "
                f"{evidence_mode} budget "
                f"{budget}"
            )
    changed_for_budget = evaluation.get("changed_skills", [])
    if evidence_mode == "release":
        quality_policy = contract["policy"].get("quality")
        quality_per_skill = (
            quality_policy.get("release_cases_per_changed_skill", 0)
            if isinstance(quality_policy, dict)
            else 0
        )
        quality_reserve = (
            quality_per_skill * len(set(changed_for_budget))
            if isinstance(changed_for_budget, list)
            else budget
        )
    else:
        quality_reserve = 0
    routing_budget = budget - quality_reserve
    actual_calls = evaluation.get("actual_calls")
    if (
        not isinstance(actual_calls, int)
        or isinstance(actual_calls, bool)
        or actual_calls > routing_budget
    ):
        errors.append(
            f"{report_label}: routing actual_calls exceeds {routing_budget}; "
            f"{quality_reserve} calls are reserved for quality evidence"
        )
    if evaluation.get("quality_reserved_calls") != quality_reserve:
        errors.append(
            f"{report_label}: quality_reserved_calls does not match "
            "changed Skills"
        )
    if evaluation.get("routing_max_calls") != routing_budget:
        errors.append(
            f"{report_label}: routing_max_calls does not preserve quality budget"
        )
    if evaluation.get("projected_total_calls") != (
        actual_calls + quality_reserve
        if isinstance(actual_calls, int)
        else None
    ):
        errors.append(
            f"{report_label}: projected_total_calls does not match "
            "routing plus quality"
        )

    selected, roles, reason, selection_errors = _selection_for_report(
        report,
        contract,
        report_label,
        evidence_mode,
    )
    errors.extend(selection_errors)
    expected_ids = [case["id"] for case in selected]
    if evaluation.get("selected_case_ids") != expected_ids:
        errors.append(
            f"{report_label}: selected case set does not match risk-tiered-v2"
        )
    if evaluation.get("selection") != roles:
        errors.append(f"{report_label}: selection roles do not match policy")
    if evaluation.get("selection_reason") != reason:
        errors.append(f"{report_label}: selection reason does not match policy")
    if evidence_mode == "exhaustive":
        expected_initial_calls = len(selected)
        if evaluation.get("execution_strategy") != (
            "initial-coverage-then-adaptive-retry"
        ):
            errors.append(
                f"{report_label}: exhaustive execution strategy is invalid"
            )
        if evaluation.get("initial_phase_complete") is not True:
            errors.append(
                f"{report_label}: exhaustive initial phase is incomplete"
            )
        if evaluation.get("initial_planned_calls") != expected_initial_calls:
            errors.append(
                f"{report_label}: exhaustive initial plan does not match "
                "selected cases"
            )
        if evaluation.get("initial_actual_calls") != expected_initial_calls:
            errors.append(
                f"{report_label}: every exhaustive case needs one "
                "first-round attempt"
            )
        if evaluation.get("retry_actual_calls") != (
            evaluation.get("actual_calls", 0) - expected_initial_calls
        ):
            errors.append(
                f"{report_label}: exhaustive retry call accounting is invalid"
            )
        if (
            evaluation.get("max_calls") != budget
            or evaluation.get("routing_max_calls") != budget
            or evaluation.get("quality_reserved_calls") != 0
        ):
            errors.append(
                f"{report_label}: exhaustive report must use the current "
                f"{budget}-call hard cap"
            )

    target_ids, target_errors = validate_target_identity(
        report,
        evidence_entry,
        contract,
    )
    errors.extend(f"{report_label}: {error}" for error in target_errors)
    expected_target_hashes = {
        target_ids[skill]: contract["target_sha"][skill]
        for skill in contract["skills"]
        if skill in target_ids
    }
    if provenance.get("target_sha256") != expected_target_hashes:
        errors.append(f"{report_label}: target Skill SHAs are stale")
    if provenance.get("target_lock_sha256") != evidence_entry.get(
        "target_lock_sha256"
    ):
        errors.append(f"{report_label}: provenance target lock SHA is stale")

    producer = report.get("producer")
    if not isinstance(producer, dict) or (
        producer.get("id") != "gloamere-skill-eval"
        or producer.get("plugin_id") != "gloamere-eval"
        or producer.get("plugin_version") != contract["eval_plugin"].get("version")
    ):
        errors.append(f"{report_label}: producer identity is stale")

    records: list[dict[str, Any]] = []
    case_values = report.get("cases")
    if not isinstance(case_values, list):
        return records, errors
    expected_by_id = contract["suite_cases"]
    for case in case_values:
        if not isinstance(case, dict):
            continue
        case_id = case.get("id")
        expected = expected_by_id.get(case_id)
        if expected is None:
            errors.append(f"{report_label}: unknown report case {case_id!r}")
            continue
        expected_metadata = {
            "plugin_id": expected["plugin_id"],
            "language": expected["language"],
            "tags": sorted(expected["tags"]),
            "prompt_sha256": sha256_text(expected["prompt"]),
            "expected_skills": sorted(expected["expected_skills"]),
            "forbidden_skills": sorted(expected["forbidden_skills"]),
        }
        for field, value in expected_metadata.items():
            if case.get(field) != value:
                errors.append(
                    f"{report_label}: {case_id}.{field} does not match suite"
                )
        kind = one_tag(expected["tags"], "kind:")
        risk = one_tag(expected["tags"], "risk:")
        attempts = case.get("attempts")
        if not isinstance(attempts, list):
            continue
        adaptive = case.get("adaptive_evaluation")
        if evidence_mode == "exhaustive":
            if not 1 <= len(attempts) <= 3:
                errors.append(
                    f"{report_label}: {case_id} must contain one initial "
                    "attempt and at most two anomaly retries"
                )
            if not isinstance(adaptive, dict) or adaptive.get("enabled") is not True:
                errors.append(
                    f"{report_label}: {case_id} must record adaptive "
                    "exhaustive evaluation"
                )
            elif attempts:
                first = attempts[0]
                first_passed = (
                    isinstance(first, dict)
                    and first.get("evidence_status") == "verified"
                    and first.get("verdict") == "pass"
                )
                if first_passed and len(attempts) != 1:
                    errors.append(
                        f"{report_label}: {case_id} retried a passing "
                        "first-round case"
                    )
                confirmed = adaptive.get("confirmed_same_failures")
                outcome = adaptive.get("outcome")
                verified_failures = adaptive.get("verified_failures")
                if (
                    isinstance(confirmed, int)
                    and confirmed >= 2
                    and outcome != "fail"
                ):
                    errors.append(
                        f"{report_label}: {case_id} must fail after the "
                        "same routing error reaches 2/3"
                    )
                if (
                    verified_failures == 1
                    and outcome != "pending"
                ):
                    errors.append(
                        f"{report_label}: {case_id} must remain pending "
                        "when only 1/3 attempts fail"
                    )
        outcome = evaluation.get("case_outcomes", {}).get(case_id)
        expected_set = set(expected["expected_skills"])
        failed_attempts = [
            attempt
            for attempt in attempts
            if isinstance(attempt, dict)
            and attempt.get("evidence_status") == "verified"
            and attempt.get("verdict") == "fail"
        ]
        observed_set = set(expected_set)
        if failed_attempts:
            signatures = Counter(
                sha256_object(
                    {
                        "observed_target_ids": attempt.get(
                            "observed_target_ids",
                            [],
                        ),
                        "declared_target_ids": attempt.get(
                            "declared_target_ids",
                            [],
                        ),
                        "unbound_declared_skills": attempt.get(
                            "unbound_declared_skills",
                            [],
                        ),
                        "unbound_skill_names": attempt.get(
                            "unbound_skill_names",
                            [],
                        ),
                    }
                )
                for attempt in failed_attempts
            )
            winning_signature = signatures.most_common(1)[0][0]
            representative = next(
                attempt
                for attempt in failed_attempts
                if sha256_object(
                    {
                        "observed_target_ids": attempt.get(
                            "observed_target_ids",
                            [],
                        ),
                        "declared_target_ids": attempt.get(
                            "declared_target_ids",
                            [],
                        ),
                        "unbound_declared_skills": attempt.get(
                            "unbound_declared_skills",
                            [],
                        ),
                        "unbound_skill_names": attempt.get(
                            "unbound_skill_names",
                            [],
                        ),
                    }
                )
                == winning_signature
            )
            observed = representative.get("observed_skills")
            observed_set = (
                set(observed) if isinstance(observed, list) else set()
            )
        records.append(
            {
                "case_id": case_id,
                "status": (
                    "verified" if outcome in {"pass", "fail"} else "pending"
                ),
                "outcome": outcome,
                "exact": outcome == "pass",
                "observed": observed_set,
                "expected": expected_set,
                "kind": kind,
                "risk": risk,
                "attempts": len(attempts),
                "confirmed_failure": outcome == "fail",
                "adaptive": adaptive,
            }
        )
    return records, errors


def recompute_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    attempt_count = sum(
        record.get("attempts", 1)
        if isinstance(record.get("attempts", 1), int)
        else 1
        for record in records
    )
    verified_records = [
        record for record in records if record["status"] == "verified"
    ]
    exact = sum(bool(record["exact"]) for record in verified_records)
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
        "case_count": total,
        "attempt_count": attempt_count,
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
        "pending_cases": sum(
            record.get("outcome") == "pending"
            or record.get("status") == "pending"
            for record in records
        ),
        "confirmed_failures": sum(
            bool(record.get("confirmed_failure"))
            for record in records
        ),
    }


def threshold_failures(
    metrics: dict[str, Any],
    thresholds: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    confirmed = metrics.get("confirmed_failures", 0)
    if isinstance(confirmed, int) and confirmed:
        failures.append(
            f"confirmed_failures={confirmed!r} must be 0 "
            "(the same routing failure occurred at least 2/3 times)"
        )
    for name in (
        "evidence_coverage",
        "verified_exact_match",
        "multi_intent_complete",
    ):
        value = metrics.get(name)
        if value is None or value < thresholds[name]:
            failures.append(
                f"{name}={value!r} is below {thresholds[name]!r}"
            )
    for name in ("ordinary_over_route", "high_risk_over_route"):
        value = metrics.get(name)
        if value is None or value > thresholds[name]:
            failures.append(
                f"{name}={value!r} exceeds {thresholds[name]!r}"
            )
    return failures


def _record_result_signature(record: dict[str, Any]) -> str:
    return sha256_object(
        {
            "outcome": record.get("outcome"),
            "status": record.get("status"),
            "exact": record.get("exact"),
            "observed": sorted(record.get("observed", set())),
            "expected": sorted(record.get("expected", set())),
            "kind": record.get("kind"),
            "risk": record.get("risk"),
            "attempts": record.get("attempts"),
            "adaptive": record.get("adaptive"),
        }
    )


def _deduplicate_release_records(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Deduplicate fixed baselines without allowing inconsistent cherry-picks."""
    by_case: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for record in records:
        case_id = record.get("case_id")
        if not isinstance(case_id, str):
            errors.append("release record is missing its suite case identity")
            continue
        existing = by_case.get(case_id)
        if existing is None:
            by_case[case_id] = record
            continue
        if _record_result_signature(existing) != _record_result_signature(
            record
        ):
            errors.append(
                f"reused release baseline disagrees for case {case_id}"
            )
    return list(by_case.values()), errors


def _release_reuse_errors(
    reports: list[dict[str, Any]],
    contract: dict[str, Any],
) -> list[str]:
    """Validate the exact reuse key and one logical owner per changed Skill."""
    if not reports:
        return []
    errors: list[str] = []
    identities: set[tuple[Any, ...]] = set()
    logical_runs: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for report in reports:
        evaluation = report.get("evaluation", {})
        provenance = report.get("provenance", {})
        identities.add(
            (
                provenance.get("suite_sha256"),
                provenance.get("policy_sha256"),
                json.dumps(
                    provenance.get("target_sha256"),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                provenance.get("target_lock_sha256"),
                provenance.get("model"),
                provenance.get("codex_cli"),
            )
        )
        shard = evaluation.get("shard")
        logical_key = (
            provenance.get("commit"),
            tuple(evaluation.get("changed_skills", [])),
            evaluation.get("rotation_key"),
            provenance.get("target_lock_sha256"),
            provenance.get("model"),
            provenance.get("codex_cli"),
            shard.get("total") if isinstance(shard, dict) else None,
        )
        logical_runs.setdefault(logical_key, []).append(report)
    if len(identities) != 1:
        errors.append(
            "release evidence reuse key must exactly match suite, policy, "
            "all Skill SHAs, model, and Codex CLI"
        )

    ownership: Counter[str] = Counter()
    for key, group in logical_runs.items():
        changed = key[1]
        ownership.update(changed)
        shards = [
            report.get("evaluation", {}).get("shard")
            for report in group
        ]
        if shards == [None]:
            continue
        if any(shard is None for shard in shards):
            errors.append(
                "one logical release run mixes sharded and unsharded reports"
            )
        elif len(group) != key[-1]:
            errors.append("one logical release shard set is incomplete")
    expected = set(contract["skills"])
    if set(ownership) != expected or any(
        ownership[skill] != 1 for skill in expected
    ):
        errors.append(
            "release report changed_skills must form one disjoint cover of "
            "the three published Skills"
        )
    return errors


def _shard_group_errors(
    reports: list[dict[str, Any]],
    contract: dict[str, Any],
) -> list[str]:
    """Require a complete, non-overlapping shard set before release."""
    errors: list[str] = []
    groups: dict[
        tuple[Any, ...],
        list[dict[str, Any]],
    ] = {}
    for report in reports:
        evaluation = report.get("evaluation", {})
        shard = evaluation.get("shard")
        if shard is None:
            continue
        provenance = report.get("provenance", {})
        key = (
            tuple(evaluation.get("changed_skills", [])),
            evaluation.get("rotation_key"),
            shard.get("total"),
            provenance.get("commit"),
            provenance.get("model"),
            provenance.get("codex_cli"),
            provenance.get("target_lock_sha256"),
        )
        groups.setdefault(key, []).append(report)
    for key, group in groups.items():
        total = key[2]
        indices = [item["evaluation"]["shard"]["index"] for item in group]
        if sorted(indices) != list(range(1, total + 1)):
            errors.append(
                "release shard group is incomplete or contains duplicate indexes"
            )
            continue
        selected, _, _ = runner_module().risk_selected_cases(
            contract["suite"],
            "release",
            None,
            key[1],
            contract["policy"],
            list(key[0]),
        )
        expected_ids = {case["id"] for case in selected}
        observed_ids = [
            case_id
            for item in group
            for case_id in item["evaluation"]["selected_case_ids"]
        ]
        if (
            len(observed_ids) != len(set(observed_ids))
            or set(observed_ids) != expected_ids
        ):
            errors.append("release shard group does not cover selection exactly")
        actual_calls = sum(
            item["evaluation"]["actual_calls"] for item in group
        )
        quality_policy = contract["policy"].get("quality")
        quality_per_skill = (
            quality_policy.get("release_cases_per_changed_skill", 0)
            if isinstance(quality_policy, dict)
            else 0
        )
        routing_cap = (
            contract["admission"]["budgets"]["release"]
            - quality_per_skill * len(set(key[0]))
        )
        if actual_calls > routing_cap:
            errors.append(
                f"release shard group exceeds its {routing_cap}-call "
                "routing budget"
            )
    return errors


def _exhaustive_coverage_errors(
    reports: list[dict[str, Any]],
    contract: dict[str, Any],
) -> list[str]:
    """Bind one complete 102-case first-round run, optionally sharded."""
    if not reports:
        return []
    errors: list[str] = []
    identities: set[tuple[Any, ...]] = set()
    for report in reports:
        evaluation = report.get("evaluation", {})
        provenance = report.get("provenance", {})
        identities.add(
            (
                provenance.get("commit"),
                provenance.get("suite_sha256"),
                provenance.get("policy_sha256"),
                json.dumps(
                    provenance.get("target_sha256"),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                provenance.get("target_lock_sha256"),
                provenance.get("model"),
                provenance.get("codex_cli"),
                evaluation.get("rotation_key"),
            )
        )
    if len(identities) != 1:
        errors.append(
            "exhaustive reports do not share one fully matching evidence identity"
        )

    shards = [
        report.get("evaluation", {}).get("shard")
        for report in reports
    ]
    if any(shard is None for shard in shards):
        if len(reports) != 1 or shards != [None]:
            errors.append(
                "exhaustive evidence cannot mix an unsharded report with "
                "other reports"
            )
    else:
        totals = {
            shard.get("total")
            for shard in shards
            if isinstance(shard, dict)
        }
        if len(totals) != 1:
            errors.append("exhaustive report shards disagree on total")
        else:
            total = next(iter(totals))
            indices = sorted(
                shard.get("index")
                for shard in shards
                if isinstance(shard, dict)
            )
            if (
                not isinstance(total, int)
                or indices != list(range(1, total + 1))
            ):
                errors.append(
                    "exhaustive shard set is incomplete or has duplicate indexes"
                )

    observed_ids = [
        case_id
        for report in reports
        for case_id in report.get("evaluation", {}).get(
            "selected_case_ids",
            [],
        )
    ]
    expected_ids = set(contract["suite_cases"])
    if (
        len(observed_ids) != 102
        or len(observed_ids) != len(set(observed_ids))
        or set(observed_ids) != expected_ids
    ):
        errors.append(
            "exhaustive evidence must cover all 102 suite cases exactly once "
            "in the first round"
        )
    actual_calls = sum(
        report.get("evaluation", {}).get("actual_calls", 0)
        for report in reports
    )
    hard_cap = contract["admission"]["budgets"]["exhaustive"]
    if (
        not isinstance(actual_calls, int)
        or isinstance(actual_calls, bool)
        or actual_calls > hard_cap
    ):
        errors.append(
            f"exhaustive evidence exceeds the {hard_cap}-call hard cap"
        )
    return errors


def _load_report_entries(
    root: Path,
    entries: list[Any],
    contract: dict[str, Any],
    manifest_field: str,
    evidence_mode: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    all_records: list[dict[str, Any]] = []
    loaded_reports: list[dict[str, Any]] = []
    evidence_errors: list[str] = []
    seen_paths: set[Path] = set()
    seen_hashes: set[str] = set()
    for index, entry in enumerate(entries):
        label = f"admission.{manifest_field}[{index}]"
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
            evidence_mode,
        )
        evidence_errors.extend(errors)
        all_records.extend(records)
        if isinstance(report, dict):
            loaded_reports.append(report)
    return all_records, loaded_reports, evidence_errors


def _assess_channel(
    root: Path,
    entries: list[Any],
    contract: dict[str, Any],
    manifest_field: str,
    evidence_mode: str,
) -> dict[str, Any]:
    if not entries:
        return {
            "status": "pending",
            "evidence_errors": [
                f"no {evidence_mode} native report v4 is declared"
            ],
            "threshold_failures": [],
            "metrics": None,
        }
    records, reports, evidence_errors = _load_report_entries(
        root,
        entries,
        contract,
        manifest_field,
        evidence_mode,
    )
    if evidence_mode == "release":
        evidence_errors.extend(_shard_group_errors(reports, contract))
        evidence_errors.extend(_release_reuse_errors(reports, contract))
        records, duplicate_errors = _deduplicate_release_records(records)
        evidence_errors.extend(duplicate_errors)
    else:
        evidence_errors.extend(_exhaustive_coverage_errors(reports, contract))
    if evidence_errors:
        return {
            "status": "fail",
            "evidence_errors": evidence_errors,
            "threshold_failures": [],
            "metrics": None,
        }
    metrics = recompute_metrics(records)
    failures = threshold_failures(
        metrics,
        contract["admission"]["thresholds"],
    )
    status = "pass"
    if failures:
        if metrics.get("confirmed_failures"):
            # A 2/3 consensus is a confirmed routing defect, not an
            # inconclusive sample awaiting optional review.
            status = "fail"
        else:
            status = "pending"
    return {
        "status": status,
        "evidence_errors": [],
        "threshold_failures": failures,
        "metrics": metrics,
    }


def assess(
    root: Path = ROOT,
    manifest_path: Path = DEFAULT_MANIFEST,
    require: bool = False,
    require_exhaustive: bool = False,
) -> tuple[dict[str, Any], int]:
    contract, configuration_errors = load_contract(root, manifest_path)
    result: dict[str, Any] = {
        "status": "fail",
        "required": require,
        "require_exhaustive": require_exhaustive,
        "configuration_errors": configuration_errors,
        "release_status": "fail",
        "evidence_errors": [],
        "threshold_failures": [],
        "metrics": None,
        "exhaustive_status": "fail",
        "exhaustive_evidence_errors": [],
        "exhaustive_threshold_failures": [],
        "exhaustive_metrics": None,
    }
    if contract is None or configuration_errors:
        return result, 1

    release = _assess_channel(
        root,
        contract["reports"],
        contract,
        "reports",
        "release",
    )
    exhaustive = _assess_channel(
        root,
        contract["exhaustive_reports"],
        contract,
        "exhaustive_reports",
        "exhaustive",
    )
    result.update(
        {
            "release_status": release["status"],
            "evidence_errors": release["evidence_errors"],
            "threshold_failures": release["threshold_failures"],
            "metrics": release["metrics"],
            "exhaustive_status": exhaustive["status"],
            "exhaustive_evidence_errors": exhaustive["evidence_errors"],
            "exhaustive_threshold_failures": exhaustive[
                "threshold_failures"
            ],
            "exhaustive_metrics": exhaustive["metrics"],
        }
    )
    statuses = {release["status"], exhaustive["status"]}
    if "fail" in statuses:
        result["status"] = "fail"
    elif statuses == {"pass"}:
        result["status"] = "pass"
    else:
        result["status"] = "pending"

    invalid_configured_evidence = (
        release["status"] == "fail" or exhaustive["status"] == "fail"
    )
    missing_required = (
        require and release["status"] != "pass"
        or require_exhaustive and exhaustive["status"] != "pass"
    )
    return result, 1 if invalid_configured_evidence or missing_required else 0


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
    parser.add_argument(
        "--require-exhaustive",
        action="store_true",
        help="Require the first-directory 102-case exhaustive evidence.",
    )
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    root = manifest_path.parent
    result, code = assess(
        root,
        manifest_path,
        args.require,
        args.require_exhaustive,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
