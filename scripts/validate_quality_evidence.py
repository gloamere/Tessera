"""Validate human or independently reviewed workflow output-quality evidence.

The validator never calls a model and never scores output text.  A v4 report may
cover any non-empty subset of Skills, which lets unchanged evidence be reused.
The configured reports are eligible only when their shared execution identity
covers all published Skills exactly once.  Without ``--require``, an empty
``quality_reports`` list is pending and exits successfully.  Once a report path
is configured, malformed, incomplete, or failing evidence is always an error.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "release-manifest.json"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,127}$")
REQUIRED_RUBRICS = {
    "evidence_fidelity",
    "actionability",
    "boundary_compliance",
    "no_fabrication",
}
REPORT_FIELDS = {
    "schema_version",
    "report_id",
    "generated_at",
    "execution",
    "quality_suite",
    "policy",
    "skills",
    "review",
    "cases",
    "summary",
}
EXECUTION_FIELDS = {"commit_sha", "model", "cli"}
CLI_FIELDS = {"name", "version", "compatibility"}
SUITE_FIELDS = {"id", "path", "sha256"}
POLICY_FIELDS = {"id", "path", "sha256"}
REVIEW_FIELDS = {"mode", "reviewer_id", "scoring_basis", "automated_scoring"}
CASE_FIELDS = {
    "id",
    "skill_id",
    "language",
    "prompt_sha256",
    "target_sha256",
    "model_calls",
    "baseline",
    "current",
    "rubrics",
    "critical_regression",
}
BASELINE_FIELDS = {"report_id", "output_sha256"}
CURRENT_FIELDS = {"output_sha256"}
RUBRIC_FIELDS = {"baseline", "current", "regression", "rationale_sha256"}
SUMMARY_FIELDS = {
    "cases_total",
    "cases_passed",
    "quality_model_calls",
    "critical_regressions",
    "verdict",
}
REVIEW_MODES = {"human_semantic_review", "independent_semantic_review"}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
        errors.append(f"{label} must be relative")
        return None
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        errors.append(f"{label} escapes the repository")
        return None
    return resolved


def exact_fields(
    value: Any,
    expected: set[str],
    label: str,
    errors: list[str],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return {}
    if set(value) != expected:
        errors.append(f"{label} fields do not match the quality report contract")
    return value


def valid_identifier(value: Any) -> bool:
    return isinstance(value, str) and IDENTIFIER.fullmatch(value) is not None


def valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def commit_is_current_or_ancestor(root: Path, commit_sha: str) -> bool:
    result = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={root.resolve().as_posix()}",
            "merge-base",
            "--is-ancestor",
            commit_sha,
            "HEAD",
        ],
        cwd=root,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def workflow_plugin(manifest: dict[str, Any]) -> dict[str, Any] | None:
    plugins = manifest.get("plugins")
    if not isinstance(plugins, list):
        return None
    matches = [
        plugin
        for plugin in plugins
        if isinstance(plugin, dict) and plugin.get("id") == "gloamere-workflows"
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

    workflow = workflow_plugin(manifest)
    if workflow is None:
        return None, ["release manifest must contain one gloamere-workflows plugin"]
    admission = workflow.get("admission")
    if not isinstance(admission, dict):
        return None, ["gloamere-workflows.admission must be an object"]
    if admission.get("report_schema_version") != 4:
        errors.append("admission.report_schema_version must be 4")

    suite_path = safe_path(
        root,
        admission.get("quality_suite_path"),
        "admission.quality_suite_path",
        errors,
    )
    suite: dict[str, Any] = {}
    if suite_path is not None:
        try:
            loaded_suite = read_json(suite_path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"cannot read quality suite: {exc}")
        else:
            if isinstance(loaded_suite, dict):
                suite = loaded_suite
            else:
                errors.append("quality suite must be an object")

    declared_suite_sha = admission.get("quality_suite_sha256")
    if not isinstance(declared_suite_sha, str) or not SHA256.fullmatch(
        declared_suite_sha
    ):
        errors.append("admission.quality_suite_sha256 is invalid")
    elif suite_path is not None and suite_path.is_file():
        if sha256_file(suite_path) != declared_suite_sha:
            errors.append("quality suite SHA does not match the release manifest")

    policy_path = safe_path(
        root,
        admission.get("policy_path"),
        "admission.policy_path",
        errors,
    )
    if not valid_identifier(admission.get("policy_id")):
        errors.append("admission.policy_id is invalid")
    declared_policy_sha = admission.get("policy_sha256")
    if not isinstance(declared_policy_sha, str) or not SHA256.fullmatch(
        declared_policy_sha
    ):
        errors.append("admission.policy_sha256 is invalid")
    elif policy_path is not None:
        if not policy_path.is_file():
            errors.append("admission policy is missing")
        else:
            if sha256_file(policy_path) != declared_policy_sha:
                errors.append(
                    "admission policy SHA does not match the release manifest"
                )
            try:
                policy = read_json(policy_path)
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"cannot read admission policy: {exc}")
            else:
                if (
                    not isinstance(policy, dict)
                    or policy.get("policy_id") != admission.get("policy_id")
                ):
                    errors.append(
                        "admission policy identity does not match the release manifest"
                    )

    skills = workflow.get("skills")
    target_sha = admission.get("target_sha256")
    if (
        not isinstance(skills, list)
        or any(not isinstance(skill, str) for skill in skills)
        or len(skills) != len(set(skills))
    ):
        errors.append("gloamere-workflows.skills must be a unique Skill ID array")
        skills = []
    if not isinstance(target_sha, dict):
        errors.append("admission.target_sha256 must be an object")
        target_sha = {}
    if set(target_sha) != set(skills):
        errors.append("target SHA keys must exactly match the published Skills")

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
            errors.append(f"published Skill is missing: {skill_id}")
        elif sha256_file(skill_path) != declared:
            errors.append(f"current Skill SHA does not match {skill_id}")

    cases = suite.get("cases")
    case_map: dict[str, dict[str, Any]] = {}
    if not isinstance(cases, list):
        errors.append("quality suite cases must be an array")
        cases = []
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str):
            errors.append("each quality case must have a string id")
            continue
        case_id = case["id"]
        if case_id in case_map:
            errors.append(f"duplicate quality case id: {case_id}")
            continue
        if case.get("skill_id") not in target_sha:
            errors.append(f"{case_id}: Skill is not published")
        if case.get("language") not in {"zh-CN", "en"}:
            errors.append(f"{case_id}: language is invalid")
        rubric = case.get("rubric")
        if not isinstance(rubric, dict) or set(rubric) != REQUIRED_RUBRICS:
            errors.append(f"{case_id}: semantic rubric set is invalid")
        case_map[case_id] = case
    if len(case_map) != 6:
        errors.append("quality suite must contain exactly six cases")
    if {case.get("skill_id") for case in case_map.values()} != set(skills):
        errors.append("quality suite must cover every published Skill")
    for skill_id in skills:
        skill_cases = [
            case for case in case_map.values() if case.get("skill_id") == skill_id
        ]
        if len(skill_cases) != 2 or {
            case.get("language") for case in skill_cases
        } != {"zh-CN", "en"}:
            errors.append(
                f"quality suite must contain one zh-CN and one en case for {skill_id}"
            )

    report_paths = admission.get("quality_reports")
    if not isinstance(report_paths, list):
        errors.append("admission.quality_reports must be an array")
        report_paths = []
    elif (
        any(not isinstance(path, str) or not path for path in report_paths)
        or len(report_paths) != len(set(report_paths))
    ):
        errors.append("admission.quality_reports must contain unique relative paths")

    contract = {
        "admission": admission,
        "suite": suite,
        "suite_path": admission.get("quality_suite_path"),
        "suite_sha": declared_suite_sha,
        "policy_id": admission.get("policy_id"),
        "policy_path": admission.get("policy_path"),
        "policy_sha": declared_policy_sha,
        "cases": case_map,
        "skills": target_sha,
        "report_paths": report_paths,
        "report_schema_version": admission.get("report_schema_version"),
    }
    return contract, errors


def validate_report(
    report: Any,
    contract: dict[str, Any],
    label: str = "quality report",
    root: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    report = exact_fields(report, REPORT_FIELDS, label, errors)
    if report.get("schema_version") != contract["report_schema_version"]:
        errors.append(f"{label}: schema_version must be 4")
    if not valid_identifier(report.get("report_id")):
        errors.append(f"{label}: report_id is invalid")
    if not valid_timestamp(report.get("generated_at")):
        errors.append(f"{label}: generated_at must be a timezone-aware timestamp")

    execution = exact_fields(
        report.get("execution"), EXECUTION_FIELDS, f"{label}.execution", errors
    )
    commit_sha = execution.get("commit_sha")
    if not isinstance(commit_sha, str) or not COMMIT_SHA.fullmatch(commit_sha):
        errors.append(f"{label}: execution.commit_sha must be a full Git SHA")
    elif root is not None and not commit_is_current_or_ancestor(root, commit_sha):
        errors.append(
            f"{label}: execution.commit_sha must be HEAD or an ancestor of HEAD"
        )
    if not valid_identifier(execution.get("model")):
        errors.append(f"{label}: execution.model is invalid")
    cli = exact_fields(
        execution.get("cli"), CLI_FIELDS, f"{label}.execution.cli", errors
    )
    if cli.get("name") != "codex":
        errors.append(f"{label}: execution.cli.name must be codex")
    if not valid_identifier(cli.get("version")):
        errors.append(f"{label}: execution.cli.version is invalid")
    if not valid_identifier(cli.get("compatibility")):
        errors.append(f"{label}: execution.cli.compatibility is invalid")

    suite = exact_fields(
        report.get("quality_suite"),
        SUITE_FIELDS,
        f"{label}.quality_suite",
        errors,
    )
    expected_suite = {
        "id": contract["suite"].get("suite_id"),
        "path": contract["suite_path"],
        "sha256": contract["suite_sha"],
    }
    if suite != expected_suite:
        errors.append(f"{label}: quality suite identity or SHA does not match")

    policy = exact_fields(
        report.get("policy"), POLICY_FIELDS, f"{label}.policy", errors
    )
    expected_policy = {
        "id": contract["policy_id"],
        "path": contract["policy_path"],
        "sha256": contract["policy_sha"],
    }
    if policy != expected_policy:
        errors.append(f"{label}: policy identity or SHA does not match")

    report_skills = report.get("skills")
    if not isinstance(report_skills, dict) or not report_skills:
        errors.append(f"{label}: skills must be a non-empty Skill SHA subset")
        report_skills = {}
    elif not set(report_skills) <= set(contract["skills"]):
        errors.append(f"{label}: skills contain an unpublished Skill")
    for skill_id, skill_sha in report_skills.items():
        if contract["skills"].get(skill_id) != skill_sha:
            errors.append(
                f"{label}: current Skill SHA does not match {skill_id}"
            )
    expected_case_ids = {
        case_id
        for case_id, case in contract["cases"].items()
        if case.get("skill_id") in report_skills
    }

    review = exact_fields(
        report.get("review"), REVIEW_FIELDS, f"{label}.review", errors
    )
    if review.get("mode") not in REVIEW_MODES:
        errors.append(
            f"{label}: review.mode must name a human or independent semantic review"
        )
    if not valid_identifier(review.get("reviewer_id")):
        errors.append(f"{label}: review.reviewer_id is invalid")
    if review.get("scoring_basis") != "semantic_judgment":
        errors.append(
            f"{label}: scoring must use semantic judgment, not keyword, "
            "substring, or regex matching"
        )
    if review.get("automated_scoring") is not False:
        errors.append(
            f"{label}: automated keyword/substring scoring is not quality evidence"
        )

    report_cases = report.get("cases")
    if not isinstance(report_cases, list):
        errors.append(f"{label}.cases must be an array")
        report_cases = []
    by_id: dict[str, dict[str, Any]] = {}
    passed_cases = 0
    quality_model_calls = 0
    critical_regressions = 0
    for index, case_report in enumerate(report_cases):
        case_label = f"{label}.cases[{index}]"
        case_report = exact_fields(
            case_report, CASE_FIELDS, case_label, errors
        )
        case_id = case_report.get("id")
        if not isinstance(case_id, str) or case_id not in contract["cases"]:
            errors.append(f"{case_label}: id is not registered in the quality suite")
            continue
        if case_id in by_id:
            errors.append(f"{case_label}: duplicate case id {case_id}")
            continue
        by_id[case_id] = case_report
        suite_case = contract["cases"][case_id]
        skill_id = suite_case.get("skill_id")
        if skill_id not in report_skills:
            errors.append(f"{case_label}: case Skill is outside the report subset")
        if case_report.get("skill_id") != skill_id:
            errors.append(f"{case_label}: skill_id does not match the suite")
        if case_report.get("language") != suite_case.get("language"):
            errors.append(f"{case_label}: language does not match the suite")
        if case_report.get("prompt_sha256") != sha256_text(suite_case["prompt"]):
            errors.append(f"{case_label}: prompt SHA does not match the suite")
        if case_report.get("target_sha256") != contract["skills"].get(skill_id):
            errors.append(f"{case_label}: target SHA does not match the Skill")
        model_calls = case_report.get("model_calls")
        # release 的 40 次额度由 routing 与 quality 共用；六个质量案例各只占一次。
        if (
            not isinstance(model_calls, int)
            or isinstance(model_calls, bool)
            or model_calls != 1
        ):
            errors.append(
                f"{case_label}: model_calls must be 1 for the registered execution"
            )
        else:
            quality_model_calls += model_calls

        baseline = exact_fields(
            case_report.get("baseline"),
            BASELINE_FIELDS,
            f"{case_label}.baseline",
            errors,
        )
        if not valid_identifier(baseline.get("report_id")):
            errors.append(f"{case_label}: baseline.report_id is invalid")
        if not isinstance(baseline.get("output_sha256"), str) or not SHA256.fullmatch(
            baseline["output_sha256"]
        ):
            errors.append(f"{case_label}: baseline output SHA is invalid")
        current = exact_fields(
            case_report.get("current"),
            CURRENT_FIELDS,
            f"{case_label}.current",
            errors,
        )
        if not isinstance(current.get("output_sha256"), str) or not SHA256.fullmatch(
            current["output_sha256"]
        ):
            errors.append(f"{case_label}: current output SHA is invalid")

        rubrics = case_report.get("rubrics")
        if not isinstance(rubrics, dict) or set(rubrics) != REQUIRED_RUBRICS:
            errors.append(f"{case_label}: all four semantic rubrics are required")
            rubrics = {}
        case_passed = True
        for rubric_name in REQUIRED_RUBRICS:
            result = exact_fields(
                rubrics.get(rubric_name),
                RUBRIC_FIELDS,
                f"{case_label}.rubrics.{rubric_name}",
                errors,
            )
            if result.get("baseline") not in {"pass", "fail"}:
                errors.append(
                    f"{case_label}.{rubric_name}: baseline verdict is invalid"
                )
                case_passed = False
            if result.get("current") != "pass":
                errors.append(
                    f"{case_label}.{rubric_name}: current semantic verdict must pass"
                )
                case_passed = False
            if result.get("regression") != "none":
                errors.append(
                    f"{case_label}.{rubric_name}: rubric regression is not allowed"
                )
                case_passed = False
            rationale_sha = result.get("rationale_sha256")
            if not isinstance(rationale_sha, str) or not SHA256.fullmatch(
                rationale_sha
            ):
                errors.append(
                    f"{case_label}.{rubric_name}: semantic rationale SHA is invalid"
                )
                case_passed = False

        if case_report.get("critical_regression") is not False:
            errors.append(f"{case_label}: critical regression is not allowed")
            critical_regressions += 1
            case_passed = False
        if case_passed:
            passed_cases += 1

    if set(by_id) != expected_case_ids:
        errors.append(
            f"{label}: cases must contain the zh-CN and en task for each "
            "declared Skill"
        )
    if quality_model_calls > len(expected_case_ids):
        errors.append(f"{label}: quality model calls exceed the report subset")

    summary = exact_fields(
        report.get("summary"), SUMMARY_FIELDS, f"{label}.summary", errors
    )
    expected_summary = {
        "cases_total": len(expected_case_ids),
        "cases_passed": passed_cases,
        "quality_model_calls": quality_model_calls,
        "critical_regressions": critical_regressions,
        "verdict": "pass"
        if passed_cases == len(expected_case_ids)
        and expected_case_ids
        and not critical_regressions
        else "fail",
    }
    if summary != expected_summary:
        errors.append(f"{label}: summary does not match recomputed quality results")
    if expected_summary["verdict"] != "pass":
        errors.append(f"{label}: output quality verdict is not pass")
    return errors


def validate_reports(
    reports: list[tuple[str, Any]],
    contract: dict[str, Any],
    root: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    covered_skills: set[str] = set()
    report_ids: set[str] = set()
    shared_identities: set[tuple[Any, Any, Any]] = set()
    quality_model_calls = 0

    for label, report in reports:
        report_errors = validate_report(report, contract, label, root)
        errors.extend(report_errors)
        if report_errors or not isinstance(report, dict):
            continue

        report_id = report["report_id"]
        if report_id in report_ids:
            errors.append(f"{label}: duplicate report_id {report_id}")
        report_ids.add(report_id)

        report_skill_ids = set(report["skills"])
        duplicated = covered_skills & report_skill_ids
        if duplicated:
            errors.append(
                f"{label}: Skill evidence is registered more than once: "
                + ", ".join(sorted(duplicated))
            )
        covered_skills.update(report_skill_ids)

        execution = report["execution"]
        cli = execution["cli"]
        shared_identities.add(
            (execution["model"], cli["name"], cli["compatibility"])
        )
        quality_model_calls += report["summary"]["quality_model_calls"]

    if len(shared_identities) > 1:
        errors.append(
            "quality reports must share the same model and Codex CLI compatibility"
        )
    expected_skills = set(contract["skills"])
    if covered_skills != expected_skills:
        missing = expected_skills - covered_skills
        unexpected = covered_skills - expected_skills
        details = []
        if missing:
            details.append("missing " + ", ".join(sorted(missing)))
        if unexpected:
            details.append("unexpected " + ", ".join(sorted(unexpected)))
        errors.append(
            "quality reports must cover every published Skill exactly once"
            + (": " + "; ".join(details) if details else "")
        )
    if quality_model_calls != len(contract["cases"]):
        errors.append(
            "combined quality_model_calls must equal the six-case reservation"
        )
    return errors


def validate(
    root: Path = ROOT,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> tuple[list[str], list[str]]:
    contract, errors = load_contract(root, manifest_path)
    if contract is None or errors:
        return errors, []
    report_paths = contract["report_paths"]
    if not report_paths:
        return [], ["no output-quality report is registered"]

    reports: list[tuple[str, Any]] = []
    for relative_path in report_paths:
        path_errors: list[str] = []
        report_path = safe_path(
            root, relative_path, "admission.quality_reports[]", path_errors
        )
        errors.extend(path_errors)
        if report_path is None:
            continue
        try:
            report = read_json(report_path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"cannot read quality report {relative_path}: {exc}")
            continue
        reports.append((relative_path, report))
    errors.extend(validate_reports(reports, contract, root))
    return errors, []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate zero-model-call workflow output-quality evidence."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Release manifest to validate.",
    )
    parser.add_argument(
        "--require",
        action="store_true",
        help="Fail when no quality report has been registered.",
    )
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    root = manifest_path.parent
    errors, pending = validate(root, manifest_path)
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    for item in pending:
        print(f"pending: {item}", file=sys.stderr)
    if errors or (args.require and pending):
        return 1
    if pending:
        print("Output-quality evidence contract is valid; report pending.")
    else:
        print("Output-quality evidence is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
