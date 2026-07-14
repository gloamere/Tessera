"""Run paired baseline/skill evaluations and report attributable score deltas."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from typing import Any


ROOT = Path(__file__).resolve().parent
RESPONSE_SCHEMA = ROOT / "response.schema.json"
SKILL_PATH = re.compile(
    r"(?:^|[\\/])skills[\\/](?P<skill>[a-z0-9-]+)[\\/]SKILL\.md(?:$|[\s'\"`])",
    re.IGNORECASE,
)
TOKEN_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)


def score(answer: str, criteria: list[dict[str, Any]]) -> tuple[float, list[str]]:
    passed: list[str] = []
    for criterion in criteria:
        all_terms = criterion.get("all", [])
        any_terms = criterion.get("any", [])
        pattern = criterion.get("regex")
        regex_passed = not pattern or len(re.findall(pattern, answer)) >= criterion.get("min_matches", 1)
        if (
            all(term in answer for term in all_terms)
            and (not any_terms or any(term in answer for term in any_terms))
            and regex_passed
        ):
            passed.append(criterion["id"])
    return (len(passed) / len(criteria) if criteria else 0.0), passed


def run_adapter(executable: str, arguments: list[str], condition: str, prompt: str) -> dict[str, Any]:
    started = time.perf_counter()
    completed = subprocess.run(
        [executable, *arguments, condition],
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"adapter exited {completed.returncode}")
    payload = json.loads(completed.stdout)
    if not isinstance(payload.get("answer"), str):
        raise ValueError("adapter answer must be a string")
    payload["_duration_ms"] = round((time.perf_counter() - started) * 1000)
    return payload


def parse_codex_events(
    events: str,
) -> tuple[list[str], int, int, dict[str, int] | None]:
    observed: set[str] = set()
    command_events = 0
    malformed = 0
    usage: dict[str, int] | None = None
    for line in events.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        item = event.get("item") if isinstance(event, dict) else None
        command = item.get("command") if isinstance(item, dict) else None
        if isinstance(command, str):
            command_events += 1
            observed.update(match.group("skill") for match in SKILL_PATH.finditer(command))
        event_usage = event.get("usage") if isinstance(event, dict) else None
        if (
            isinstance(event, dict)
            and event.get("type") == "turn.completed"
            and isinstance(event_usage, dict)
        ):
            usage = {
                field: value
                for field in TOKEN_FIELDS
                if isinstance((value := event_usage.get(field)), int)
            }
    return sorted(observed), command_events, malformed, usage


def resolve_codex(explicit: str | None) -> str:
    if explicit:
        return explicit
    names = ("codex.exe", "codex.cmd", "codex") if sys.platform == "win32" else ("codex", "codex.exe", "codex.cmd")
    for name in names:
        candidate = shutil.which(name)
        if not candidate:
            continue
        try:
            probe = subprocess.run(
                [candidate, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if probe.returncode == 0:
            return candidate
    raise RuntimeError("Codex CLI unavailable")


def run_codex(
    plugin: str,
    condition: str,
    prompt: str,
    workspace: Path,
    timeout: int,
    model: str | None,
    codex_executable: str | None,
) -> dict[str, Any]:
    executable = resolve_codex(codex_executable)
    with tempfile.TemporaryDirectory(prefix="tessera-eval-lab-") as temp:
        output = Path(temp) / "last-message.json"
        enabled = "true" if condition == "skill" else "false"
        quoted_plugin = f'\\"{plugin}\\"' if executable.lower().endswith((".cmd", ".bat")) else f'"{plugin}"'
        command = [
            executable,
            "exec",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--output-schema",
            str(RESPONSE_SCHEMA),
            "--output-last-message",
            str(output),
            "--cd",
            str(workspace),
            "--json",
            "-c",
            f"plugins.{quoted_plugin}.enabled={enabled}",
        ]
        if model:
            command.extend(["--model", model])
        command.append("-")
        started = time.perf_counter()
        completed = subprocess.run(
            command,
            input=prompt,
            cwd=workspace,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=False,
        )
        if completed.returncode != 0:
            detail = "\n".join(
                part for part in (completed.stdout.strip(), completed.stderr.strip()) if part
            )
            raise RuntimeError(f"codex exited {completed.returncode}: {detail[-2000:]}")
        if not output.is_file():
            raise RuntimeError("Codex did not write the last-message file")
        payload = json.loads(output.read_text(encoding="utf-8"))
        if not isinstance(payload.get("answer"), str):
            raise ValueError("Codex answer must be a string")
        skills, command_events, malformed, usage = parse_codex_events(completed.stdout)
        payload["observed_skills"] = skills
        payload["_host_event_lines"] = len(completed.stdout.splitlines())
        payload["_command_event_count"] = command_events
        payload["_malformed_event_count"] = malformed
        payload["_usage"] = usage
        payload["_duration_ms"] = round((time.perf_counter() - started) * 1000)
        return payload


def evaluate_run(payload: dict[str, Any], criteria: list[dict[str, Any]]) -> dict[str, Any]:
    run_score, passed = score(payload["answer"], criteria)
    return {
        "score": run_score,
        "passed_criteria": passed,
        "observed_skills": sorted(set(payload.get("observed_skills", []))),
        "duration_ms": payload.get("_duration_ms"),
        "host_event_lines": payload.get("_host_event_lines"),
        "command_event_count": payload.get("_command_event_count"),
        "malformed_event_count": payload.get("_malformed_event_count"),
        "usage": payload.get("_usage"),
        "answer": payload["answer"],
    }


def aggregate_usage(runs: list[dict[str, Any]]) -> dict[str, int] | None:
    if any(run["usage"] is None for run in runs):
        return None
    return {
        field: sum(run["usage"].get(field, 0) for run in runs)
        for field in TOKEN_FIELDS
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    result.add_argument("--cases", type=Path, required=True)
    result.add_argument("--case", action="append", dest="case_ids")
    result.add_argument("--adapter-executable")
    result.add_argument("--adapter-arg", action="append", default=[])
    result.add_argument("--repeat", type=int, default=1)
    result.add_argument("--output", type=Path, required=True)
    result.add_argument("--workspace", type=Path, default=Path.cwd())
    result.add_argument("--timeout", type=int, default=120)
    result.add_argument("--model")
    result.add_argument("--codex-executable")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.repeat < 1 or args.repeat > 10:
        print("--repeat must be between 1 and 10", file=sys.stderr)
        return 2
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if args.case_ids:
        selected = set(args.case_ids)
        cases = [case for case in cases if case.get("id") in selected]
        missing = selected.difference(case.get("id") for case in cases)
        if missing:
            print(f"unknown case ids: {', '.join(sorted(missing))}", file=sys.stderr)
            return 2
    workspace = args.workspace.resolve()
    results: list[dict[str, Any]] = []
    for case in cases:
        activation = case.get("activation", "native")
        skill_content: str | None = None
        skill_sha256: str | None = None
        skill_content_chars: int | None = None
        skill_content_bytes: int | None = None
        if activation == "injected":
            skill_file = Path(case["skill_file"])
            if not skill_file.is_absolute():
                skill_file = args.cases.resolve().parent / skill_file
            skill_content = skill_file.read_text(encoding="utf-8")
            skill_sha256 = hashlib.sha256(skill_content.encode("utf-8")).hexdigest()
            skill_content_chars = len(skill_content)
            skill_content_bytes = len(skill_content.encode("utf-8"))

        def execute(condition: str) -> dict[str, Any]:
            prompt = case["prompt"]
            if condition == "skill" and skill_content is not None:
                prompt = (
                    f"<skill_under_test sha256=\"{skill_sha256}\">\n"
                    f"{skill_content}\n</skill_under_test>\n\n"
                    f"Apply the skill under test to this task:\n<task>\n{prompt}\n</task>"
                )
            if args.adapter_executable:
                return run_adapter(
                    args.adapter_executable, args.adapter_arg, condition, prompt
                )
            host_condition = "baseline" if activation == "injected" else condition
            return run_codex(
                case["plugin"],
                host_condition,
                prompt,
                workspace,
                args.timeout,
                args.model,
                args.codex_executable,
            )

        try:
            baseline_runs = [
                evaluate_run(execute("baseline"), case["criteria"])
                for _ in range(args.repeat)
            ]
            skill_runs = [
                evaluate_run(execute("skill"), case["criteria"])
                for _ in range(args.repeat)
            ]
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
            results.append(
                {
                    "id": case["id"],
                    "plugin": case["plugin"],
                    "skill": case["skill"],
                    "activation": activation,
                    "skill_sha256": skill_sha256,
                    "skill_content_chars": skill_content_chars,
                    "skill_content_bytes": skill_content_bytes,
                    "attribution": "unverified",
                    "verdict": "execution_error",
                    "error": str(exc),
                }
            )
            continue
        baseline_score = statistics.median(run["score"] for run in baseline_runs)
        skill_score = statistics.median(run["score"] for run in skill_runs)
        baseline_usage = aggregate_usage(baseline_runs)
        skill_usage = aggregate_usage(skill_runs)
        usage_delta = (
            {
                field: skill_usage[field] - baseline_usage[field]
                for field in TOKEN_FIELDS
            }
            if baseline_usage is not None and skill_usage is not None
            else None
        )
        criterion_ids = [criterion["id"] for criterion in case["criteria"]]
        baseline_criterion_rates = {
            criterion_id: round(
                sum(
                    criterion_id in run["passed_criteria"]
                    for run in baseline_runs
                )
                / len(baseline_runs),
                6,
            )
            for criterion_id in criterion_ids
        }
        skill_criterion_rates = {
            criterion_id: round(
                sum(
                    criterion_id in run["passed_criteria"]
                    for run in skill_runs
                )
                / len(skill_runs),
                6,
            )
            for criterion_id in criterion_ids
        }
        criterion_deltas = {
            criterion_id: round(
                skill_criterion_rates[criterion_id]
                - baseline_criterion_rates[criterion_id],
                6,
            )
            for criterion_id in criterion_ids
        }
        delta = round(skill_score - baseline_score, 6)
        direction = "improvement" if delta > 0 else "regression" if delta < 0 else "tie"
        baseline_clean = all(case["skill"] not in run["observed_skills"] for run in baseline_runs)
        if activation == "injected":
            skill_clean = all(case["skill"] not in run["observed_skills"] for run in skill_runs)
            attribution = "verified-injection" if baseline_clean and skill_clean else "unverified"
        else:
            skill_loaded = all(case["skill"] in run["observed_skills"] for run in skill_runs)
            attribution = "verified" if baseline_clean and skill_loaded else "unverified"
        threshold = case["minimum_delta"]
        if not attribution.startswith("verified"):
            verdict = "unverified"
        elif delta >= threshold:
            verdict = "improvement"
        elif delta <= -threshold:
            verdict = "regression"
        else:
            verdict = "no_change"
        results.append(
            {
                "id": case["id"],
                "plugin": case["plugin"],
                "skill": case["skill"],
                "activation": activation,
                "skill_sha256": skill_sha256,
                "skill_content_chars": skill_content_chars,
                "skill_content_bytes": skill_content_bytes,
                "baseline_score": baseline_score,
                "skill_score": skill_score,
                "delta": delta,
                "direction": direction,
                "minimum_delta": threshold,
                "baseline_usage": baseline_usage,
                "skill_usage": skill_usage,
                "usage_delta": usage_delta,
                "baseline_criterion_rates": baseline_criterion_rates,
                "skill_criterion_rates": skill_criterion_rates,
                "criterion_deltas": criterion_deltas,
                "gained_criteria": [
                    criterion_id
                    for criterion_id in criterion_ids
                    if criterion_deltas[criterion_id] > 0
                ],
                "lost_criteria": [
                    criterion_id
                    for criterion_id in criterion_ids
                    if criterion_deltas[criterion_id] < 0
                ],
                "attribution": attribution,
                "verdict": verdict,
                "baseline_runs": baseline_runs,
                "skill_runs": skill_runs,
            }
        )
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "claim": (
            "paired adapter contract; not native utility evidence"
            if args.adapter_executable
            else "paired native skill utility with host-event attribution"
        ),
        "adapter": "adapter-fixture" if args.adapter_executable else "codex-cli",
        "evidence": "fixture" if args.adapter_executable else "native-host-events",
        "cases_file": str(args.cases.resolve()),
        "repeat": args.repeat,
        "model": args.model,
        "summary": {
            "total": len(results),
            "improvements": sum(item["verdict"] == "improvement" for item in results),
            "regressions": sum(item["verdict"] == "regression" for item in results),
            "no_change": sum(item["verdict"] == "no_change" for item in results),
            "unverified": sum(item["verdict"] == "unverified" for item in results),
            "execution_errors": sum(item["verdict"] == "execution_error" for item in results),
            "raw_improvements": sum(item.get("direction") == "improvement" for item in results),
            "raw_regressions": sum(item.get("direction") == "regression" for item in results),
            "raw_ties": sum(item.get("direction") == "tie" for item in results),
        },
        "cases": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 2 if report["summary"]["execution_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
