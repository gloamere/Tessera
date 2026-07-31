"""Validate the local official-directory submission bundle without uploading it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
SUBMISSION_PATH = ROOT / "docs" / "directory" / "submission.json"
RELEASE_PATH = ROOT / "release-manifest.json"
PUBLIC_SKILLS = {
    "gloamere-product-decision",
    "gloamere-visual-review",
    "gloamere-knowledge-capture",
}


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a JSON object")
    return value


def is_https(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def validate(require_complete: bool) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    pending: list[str] = []
    submission = read_json(SUBMISSION_PATH)
    release = read_json(RELEASE_PATH)
    workflows = next(
        plugin for plugin in release["plugins"] if plugin["id"] == "gloamere-workflows"
    )
    manifest_path = ROOT / workflows["path"] / ".codex-plugin" / "plugin.json"
    manifest = read_json(manifest_path)

    package = submission.get("package", {})
    if package.get("name") != workflows["id"]:
        errors.append("submission package name does not match release manifest")
    if package.get("version") != workflows["version"]:
        errors.append("submission package version does not match release manifest")
    if set(workflows["skills"]) != PUBLIC_SKILLS:
        errors.append("release manifest must contain exactly the three public Skills")
    if set(manifest) & {"mcpServers", "apps"}:
        errors.append("skills-only manifest must not declare MCP or apps")
    if "screenshots" in manifest.get("interface", {}):
        errors.append("skills-only manifest without UI must not declare screenshots")

    listing = submission.get("listing")
    if not isinstance(listing, dict) or set(listing) != {"en-US", "zh-CN"}:
        errors.append("listing must contain exactly en-US and zh-CN")
    else:
        for locale, localized in listing.items():
            prompts = localized.get("starterPrompts")
            if (
                not isinstance(prompts, list)
                or len(prompts) != 3
                or len(prompts) != len(set(prompts))
                or any(
                    not isinstance(prompt, str)
                    or not prompt.strip()
                    or "\n" in prompt
                    or len(prompt) > 128
                    for prompt in prompts
                )
            ):
                errors.append(
                    f"{locale} must contain three unique one-line starter prompts"
                )

    for name, value in submission.get("urls", {}).items():
        if not is_https(value):
            errors.append(f"{name} URL must be HTTPS")

    cases_path = ROOT / submission.get("testCases", "")
    if not cases_path.is_file():
        errors.append("test case file is missing")
    else:
        cases = read_json(cases_path)
        positive = cases.get("positive")
        negative = cases.get("negative")
        if not isinstance(positive, list) or len(positive) != 5:
            errors.append("submission must contain exactly five positive cases")
        if not isinstance(negative, list) or len(negative) != 3:
            errors.append("submission must contain exactly three negative cases")
        all_cases: list[dict] = []
        if isinstance(positive, list):
            all_cases.extend(positive)
        if isinstance(negative, list):
            all_cases.extend(negative)
        ids = [case.get("id") for case in all_cases if isinstance(case, dict)]
        if len(ids) != len(set(ids)) or any(not case_id for case_id in ids):
            errors.append("submission case IDs must be unique and non-empty")
        for case in all_cases:
            if not isinstance(case, dict):
                errors.append("submission cases must be objects")
                continue
            for fixture_path in case.get("fixturePaths", []):
                fixture = (ROOT / fixture_path).resolve()
                try:
                    fixture.relative_to(ROOT)
                except ValueError:
                    errors.append(f"fixture escapes repository: {fixture_path}")
                    continue
                if not fixture.is_file():
                    errors.append(f"fixture is missing: {fixture_path}")

    availability = submission.get("availability", {})
    requested_countries = availability.get("requestedCountries", [])
    # 用户意向与门户可选范围分开记录，避免在门户确认前提前宣称已覆盖该地区。
    requested_codes_valid = (
        isinstance(requested_countries, list)
        and bool(requested_countries)
        and all(
            isinstance(country, str)
            and len(country) == 2
            and country == country.upper()
            for country in requested_countries
        )
        and len(requested_countries) == len(set(requested_countries))
    )
    if not requested_codes_valid:
        errors.append("requested country availability must use ISO alpha-2 codes")
    confirmed_countries = availability.get("countries", [])
    confirmed_codes_valid = (
        isinstance(confirmed_countries, list)
        and bool(confirmed_countries)
        and all(
            isinstance(country, str)
            and len(country) == 2
            and country == country.upper()
            for country in confirmed_countries
        )
        and len(confirmed_countries) == len(set(confirmed_countries))
    )
    if (
        availability.get("status") != "confirmed"
        or not confirmed_codes_valid
        or (
            requested_codes_valid
            and set(requested_countries) != set(confirmed_countries)
        )
    ):
        requested_label = (
            ", ".join(requested_countries)
            if requested_codes_valid
            else "the requested countries"
        )
        pending.append(
            f"country availability for {requested_label} requires "
            "submission-portal confirmation"
        )
    recording = submission.get("demoRecording", {})
    if recording.get("status") != "complete" or not is_https(recording.get("url")):
        pending.append("demo recording is not complete")
    pilot = submission.get("pilot", {})
    if not isinstance(pilot, dict):
        pilot = {}
    validation_mode = pilot.get("validationMode")
    # 官方门禁不要求外部试用人数；个人项目用透明 dogfood，避免伪造独立用户证据。
    if validation_mode != "owner-dogfood":
        errors.append("pilot validationMode must be owner-dogfood")
    participants = pilot.get("participants")
    completed_tasks = pilot.get("completedTasks")
    major_rewrite_tasks = pilot.get("majorRewriteTasks")
    pilot_rate = pilot.get("readyWithoutMajorRewriteRate")
    skill_task_counts = pilot.get("skillTaskCounts")
    confirmed_high_risk = pilot.get("confirmedHighRiskFalseActivations")
    skill_coverage_complete = (
        isinstance(skill_task_counts, dict)
        and set(skill_task_counts) == PUBLIC_SKILLS
        and all(
            isinstance(count, int)
            and not isinstance(count, bool)
            and count >= 2
            for count in skill_task_counts.values()
        )
        and isinstance(completed_tasks, int)
        and not isinstance(completed_tasks, bool)
        and sum(skill_task_counts.values()) == completed_tasks
    )
    rewrite_rate_consistent = (
        isinstance(completed_tasks, int)
        and not isinstance(completed_tasks, bool)
        and completed_tasks > 0
        and isinstance(major_rewrite_tasks, int)
        and not isinstance(major_rewrite_tasks, bool)
        and 0 <= major_rewrite_tasks <= completed_tasks
        and isinstance(pilot_rate, (int, float))
        and not isinstance(pilot_rate, bool)
        and abs(
            pilot_rate
            - ((completed_tasks - major_rewrite_tasks) / completed_tasks)
        )
        < 1e-9
    )
    high_risk_clear = (
        isinstance(confirmed_high_risk, int)
        and not isinstance(confirmed_high_risk, bool)
        and confirmed_high_risk == 0
    )
    if (
        pilot.get("status") != "complete"
        or not isinstance(participants, int)
        or isinstance(participants, bool)
        or participants != 1
        or not isinstance(completed_tasks, int)
        or isinstance(completed_tasks, bool)
        or completed_tasks < 10
        or not isinstance(pilot_rate, (int, float))
        or isinstance(pilot_rate, bool)
        or pilot_rate < 0.8
        or pilot_rate > 1
        or not rewrite_rate_consistent
        or not skill_coverage_complete
        or not high_risk_clear
    ):
        pending.append(
            f"{validation_mode or 'pilot'} requires exactly 1 maintainer, "
            "10 completed tasks, at least 2 tasks per public Skill, zero "
            "confirmed high-risk false activations, and at least 80% "
            "without major rewrite with a consistent aggregate"
        )
    pilot_report_value = pilot.get("report")
    pilot_report = (
        (ROOT / pilot_report_value).resolve()
        if isinstance(pilot_report_value, str)
        else None
    )
    report_is_local = False
    if pilot_report is not None:
        try:
            pilot_report.relative_to(ROOT)
            report_is_local = True
        except ValueError:
            pass
    if not report_is_local or not pilot_report.is_file():
        errors.append("owner-dogfood report is missing")
    if not workflows.get("admission", {}).get("reports"):
        pending.append("eligible report-v4 evidence has not been registered")
    if not workflows.get("admission", {}).get("exhaustive_reports"):
        pending.append("first-directory 102-case exhaustive evidence is not registered")
    if not workflows.get("admission", {}).get("quality_reports"):
        pending.append("six-case semantic output-quality evidence is not registered")

    artifact = ROOT / package.get("artifact", "")
    if require_complete and not artifact.is_file():
        pending.append("final directory ZIP has not been built")
    if require_complete and submission.get("status") != "ready":
        pending.append("submission status is not ready")
    return errors, pending


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    errors, pending = validate(args.require_complete)
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    for item in pending:
        print(f"pending: {item}", file=sys.stderr)
    if errors or (args.require_complete and pending):
        return 1
    print(
        "Directory submission structure is valid"
        + (" and complete." if not pending else f"; {len(pending)} item(s) pending.")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
