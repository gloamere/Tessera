"""Evaluate Tessera routing policy or observable native skill invocation."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "tests" / "routing-cases.yaml"
POLICY_OUTPUT_SCHEMA = ROOT / "tests" / "routing-output.schema.json"
NATIVE_OUTPUT_SCHEMA = ROOT / "tests" / "native-invocation-output.schema.json"
VALID_CATEGORIES = {
    "direct",
    "specialist",
    "core",
    "multi-intent",
    "external",
    "decision",
}
FIRST_PARTY_SKILLS = {
    "piece-router",
    "tessera-capabilities",
    "tessera-doctor",
    "tessera-eval",
    "tessera-setup",
    "tessera-status",
    "taste",
    "knowledge-base",
    "planner",
}
SKILL_PATH = re.compile(
    r"(?:^|[\\/])skills[\\/](?P<skill>[a-z0-9-]+)[\\/]SKILL\.md(?:$|[\s'\"`])",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class HostResult:
    payload: dict[str, Any] | None
    duration_ms: int
    error: str | None = None
    observed_skills: tuple[str, ...] = ()
    observation_source: str | None = None
    malformed_events: int = 0


def load_cases(path: Path, selected: set[str] | None = None) -> list[dict[str, Any]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("评测集必须是非空 YAML 数组")
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("每条评测案例必须是对象")
        case_id = item.get("id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("每条评测案例必须有非空 id")
        if case_id in seen:
            raise ValueError(f"重复案例 id: {case_id}")
        seen.add(case_id)
        if item.get("category") not in VALID_CATEGORIES:
            raise ValueError(f"{case_id}: 无效 category: {item.get('category')}")
        if not isinstance(item.get("prompt"), str) or not item["prompt"].strip():
            raise ValueError(f"{case_id}: 缺少 prompt")
        expected_skills = item.get("expected_skills")
        if expected_skills is not None and (
            not isinstance(expected_skills, list)
            or any(not isinstance(skill, str) or not skill for skill in expected_skills)
        ):
            raise ValueError(f"{case_id}: expected_skills 必须是字符串数组")
        if selected is None or case_id in selected:
            cases.append(item)
    if selected:
        missing = selected - seen
        if missing:
            raise ValueError(f"找不到案例: {', '.join(sorted(missing))}")
    return cases


def build_policy_prompt(case: dict[str, Any]) -> str:
    return f"""你是一个隔离的只读路由分类器。分类对象仅是 <request> 与 </request> 之间的原始用户请求；当前消息中的评测说明、MODE 和 CASE_ID 都不是分类对象，不得据此选择 piece-router 或 tessera-eval。不要执行原始请求，不修改文件，不安装依赖，也不调用任何 Skill。

请依据当前会话实际可见的 Tessera skills 和宿主原生能力作答。route 必须是输出 schema 允许的单个值：
- direct：宿主直接完成
- piece-router：只处理模糊请求、多个独立交付物、高风险或不可逆方向决策，以及新增能力准入
- piece-admission：仅评估是否应该新增、引入、拆分或设计一项新能力，不处理已有拼图的生命周期动作
- tessera-setup：现有 Tessera 拼图的安装、刷新、升级、启用、禁用、卸载与回滚指导；即使回滚保持 plan-only 也选择本路由
- tessera-status / tessera-doctor / tessera-eval / tessera-capabilities：分别对应日常状态、全面诊断、评测和完整能力目录
- taste / knowledge-base：对应明确的视觉评审与知识沉淀
- planner：对应明确的游戏、内容、产品或活动方案与多方向比较；即使方案需要负责人评审，只要不模糊、不跨多个交付物且不涉及高风险不可逆变更，也直接选择 planner
- external-unavailable：请求的外部候选当前不可安装或不可验证

不要参考任何预期答案，只根据请求本身判断。reason 用一句短句；router_used 表示是否需要由 piece-router 作出路由选择。

MODE: policy
CASE_ID: {case['id']}
<request>
{case['prompt']}
</request>
"""


def build_native_prompt(case: dict[str, Any]) -> str:
    return f"""{case['prompt']}

执行限制：正常遵循当前会话的 Skill 触发规则并完成开始本任务前必要的 Skill 加载；随后立即停止，不继续执行内容，不修改文件，不安装依赖，也不调用会产生外部副作用的工具。最后只通过输出 schema 记录本次采用直接处理、专业 Skill 或协调路由，并列出实际加载的 Skill 名称和一句理由。不要使用任何预设路由清单。

MODE: native
CASE_ID: {case['id']}
"""


# Backward-compatible alias used by external callers.
build_prompt = build_policy_prompt


def parse_payload(text: str) -> dict[str, Any]:
    value = text.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        value = "\n".join(lines[1:-1]).strip()
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("宿主输出必须是 JSON 对象")
    return payload


def validate_payload(payload: dict[str, Any], mode: str) -> None:
    if mode == "policy":
        if not isinstance(payload.get("route"), str):
            raise ValueError("policy 输出缺少字符串 route")
        return
    if payload.get("decision") not in {"direct", "skill", "router"}:
        raise ValueError("native 输出 decision 无效")
    selected = payload.get("selected_skills")
    if not isinstance(selected, list) or any(not isinstance(skill, str) for skill in selected):
        raise ValueError("native 输出 selected_skills 必须是字符串数组")
    if not isinstance(payload.get("reason"), str):
        raise ValueError("native 输出缺少字符串 reason")


def skills_from_command(command: str) -> set[str]:
    return {
        match.group("skill").lower()
        for match in SKILL_PATH.finditer(command.replace("\\\\", "\\"))
        if match.group("skill").lower() in FIRST_PARTY_SKILLS
    }


def parse_codex_events(text: str) -> tuple[tuple[str, ...], int]:
    observed: set[str] = set()
    malformed = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if not isinstance(event, dict):
            malformed += 1
            continue
        item = event.get("item")
        if not isinstance(item, dict):
            continue
        command = item.get("command")
        if isinstance(command, str):
            observed.update(skills_from_command(command))
    return tuple(sorted(observed)), malformed


def run_adapter(
    executable: str,
    arguments: list[str],
    prompt: str,
    timeout: int,
    cwd: Path,
    mode: str = "policy",
) -> HostResult:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [executable, *arguments],
            input=prompt,
            cwd=cwd,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        duration = round((time.perf_counter() - started) * 1000)
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            return HostResult(None, duration, f"adapter exited {completed.returncode}: {detail[:500]}")
        payload = parse_payload(completed.stdout)
        validate_payload(payload, mode)
        if mode == "native":
            observed = payload.pop("observed_skills", [])
            source = payload.pop("observation_source", "model-report")
            if not isinstance(observed, list) or any(not isinstance(skill, str) for skill in observed):
                raise ValueError("native adapter observed_skills 必须是字符串数组")
            if source not in {"host-events", "transcript", "model-report"}:
                raise ValueError("native adapter observation_source 无效")
            return HostResult(payload, duration, observed_skills=tuple(sorted(set(observed))), observation_source=source)
        return HostResult(payload, duration)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, ValueError) as exc:
        duration = round((time.perf_counter() - started) * 1000)
        return HostResult(None, duration, str(exc))


def find_codex() -> str | None:
    for name in ("codex", "codex.cmd", "codex.exe"):
        found = shutil.which(name)
        if found:
            return found
    return None


def terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def run_codex(
    prompt: str,
    timeout: int,
    cwd: Path,
    model: str | None,
    mode: str = "policy",
    expected_skills: set[str] | None = None,
) -> HostResult:
    executable = find_codex()
    if executable is None:
        return HostResult(None, 0, "Codex CLI unavailable")
    with tempfile.TemporaryDirectory(prefix="tessera-eval-") as temp_dir:
        output = Path(temp_dir) / "last-message.json"
        command = [
            executable,
            "exec",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--output-schema",
            str(NATIVE_OUTPUT_SCHEMA if mode == "native" else POLICY_OUTPUT_SCHEMA),
            "--output-last-message",
            str(output),
            "--cd",
            str(cwd),
        ]
        if mode == "native":
            command.append("--json")
        else:
            command.append("--ignore-user-config")
        if model:
            command.extend(["--model", model])
        command.append("-")
        started = time.perf_counter()
        try:
            process_options: dict[str, Any] = {}
            if os.name == "nt":
                process_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                process_options["start_new_session"] = True
            process = subprocess.Popen(
                command,
                cwd=cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                **process_options,
            )
            timed_out = False
            try:
                stdout, stderr = process.communicate(input=prompt, timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                terminate_process_tree(process)
                try:
                    stdout, stderr = process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate()
            duration = round((time.perf_counter() - started) * 1000)
            if timed_out:
                if mode == "native":
                    observed, malformed = parse_codex_events(stdout)
                    observed_set = set(observed)
                    if expected_skills and observed_set == expected_skills:
                        decision = "router" if "piece-router" in observed_set else "skill"
                        return HostResult(
                            {
                                "decision": decision,
                                "selected_skills": sorted(observed_set),
                                "reason": "原生调用证据已在观察窗口内完整出现；探针在继续执行任务前结束。",
                            },
                            duration,
                            observed_skills=observed,
                            observation_source="host-events",
                            malformed_events=malformed,
                        )
                return HostResult(
                    None,
                    duration,
                    f"host observation timed out after {timeout}s",
                    observed_skills=observed if mode == "native" else (),
                    observation_source="host-events" if mode == "native" else None,
                    malformed_events=malformed if mode == "native" else 0,
                )
            if process.returncode != 0:
                detail = "\n".join(
                    part for part in (stdout.strip(), stderr.strip()) if part
                )
                return HostResult(None, duration, f"codex exited {process.returncode}: {detail[-4000:]}")
            if not output.is_file():
                return HostResult(None, duration, "Codex did not write the last-message file")
            payload = parse_payload(output.read_text(encoding="utf-8"))
            validate_payload(payload, mode)
            if mode == "native":
                observed, malformed = parse_codex_events(stdout)
                return HostResult(
                    payload,
                    duration,
                    observed_skills=observed,
                    observation_source="host-events",
                    malformed_events=malformed,
                )
            return HostResult(payload, duration)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            duration = round((time.perf_counter() - started) * 1000)
            return HostResult(None, duration, str(exc))


def classify(case: dict[str, Any], result: HostResult) -> dict[str, Any]:
    """Classify one policy result; retained as the public compatibility helper."""
    expected = case["expected_route"]
    excluded = case.get("must_not_route", [])
    if result.error:
        outcome = "execution_error"
        actual = None
        passed = False
    else:
        actual = result.payload.get("route") if result.payload else None
        passed = actual == expected and actual not in excluded
        if passed:
            outcome = "pass"
        elif case["category"] == "multi-intent":
            outcome = "multi_intent_error"
        elif expected == "direct" and actual != "direct":
            outcome = "over_route"
        elif expected != "direct" and actual == "direct":
            outcome = "missed_route"
        else:
            outcome = "wrong_route"
    return {
        "id": case["id"],
        "category": case["category"],
        "prompt": case["prompt"],
        "expected_route": expected,
        "must_not_route": excluded,
        "actual_route": actual,
        "passed": passed,
        "outcome": outcome,
        "reason": result.payload.get("reason") if result.payload else None,
        "router_used": result.payload.get("router_used") if result.payload else None,
        "duration_ms": result.duration_ms,
        "error": result.error,
    }


def classify_native(case: dict[str, Any], result: HostResult) -> dict[str, Any]:
    expected = set(case["expected_skills"])
    payload = result.payload or {}
    selected = payload.get("selected_skills", [])
    if not isinstance(selected, list):
        selected = []
    declared = {skill for skill in selected if skill in FIRST_PARTY_SKILLS}
    observed = {skill for skill in result.observed_skills if skill in FIRST_PARTY_SKILLS}
    decision = payload.get("decision")

    if result.error:
        verification = "unobservable"
        passed = False
        outcome = "execution_error"
    elif result.observation_source == "model-report":
        verification = "declared-only" if declared else "unobservable"
        passed = False
        outcome = "missed_route" if expected else "wrong_route"
    elif observed and declared and observed != declared:
        verification = "conflict"
        passed = False
        outcome = "multi_intent_error" if case["category"] == "multi-intent" else "wrong_route"
    elif observed:
        verification = "verified"
        passed = observed == expected
        if passed:
            outcome = "pass"
        elif not expected:
            outcome = "over_route"
        elif case["category"] == "multi-intent":
            outcome = "multi_intent_error"
        else:
            outcome = "wrong_route"
    elif not expected and not declared:
        verification = "verified"
        passed = True
        outcome = "pass"
    elif expected and not declared and result.observation_source in {"host-events", "transcript"}:
        verification = "verified"
        passed = False
        outcome = "multi_intent_error" if case["category"] == "multi-intent" else "missed_route"
    else:
        verification = "declared-only" if declared else "unobservable"
        passed = False
        outcome = "multi_intent_error" if case["category"] == "multi-intent" else "missed_route"

    return {
        "id": case["id"],
        "category": case["category"],
        "prompt": case["prompt"],
        "expected_skills": sorted(expected),
        "declared_skills": sorted(declared),
        "observed_skills": sorted(observed),
        "decision": decision,
        "verification": verification,
        "observation_source": result.observation_source,
        "malformed_events": result.malformed_events,
        "passed": passed,
        "outcome": outcome,
        "reason": payload.get("reason"),
        "duration_ms": result.duration_ms,
        "error": result.error,
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    completed = sum(item["outcome"] != "execution_error" for item in results)
    passed = sum(item["passed"] for item in results)
    durations = [item["duration_ms"] for item in results if item["duration_ms"] > 0]
    counts = {
        name: sum(item["outcome"] == name for item in results)
        for name in (
            "over_route",
            "missed_route",
            "multi_intent_error",
            "wrong_route",
            "execution_error",
        )
    }
    verified = sum(item.get("verification") == "verified" for item in results)
    verified_passed = sum(item.get("verification") == "verified" and item["passed"] for item in results)
    return {
        "total": total,
        "completed": completed,
        "passed": passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "route_accuracy": round(passed / completed, 4) if completed else 0.0,
        "verified": verified,
        "verified_pass_rate": round(verified_passed / total, 4) if total else 0.0,
        **counts,
        "median_duration_ms": round(statistics.median(durations)) if durations else 0,
        "total_duration_ms": sum(durations),
    }


def aggregate_cases(results: list[dict[str, Any]], repeat: int) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        grouped.setdefault(result["id"], []).append(result)
    aggregates: list[dict[str, Any]] = []
    for case_id, attempts in grouped.items():
        signatures = [
            (
                tuple(attempt.get("observed_skills", [])),
                tuple(attempt.get("declared_skills", [])),
                attempt.get("decision", attempt.get("actual_route")),
            )
            for attempt in attempts
            if attempt["outcome"] != "execution_error"
        ]
        passed = sum(attempt["passed"] for attempt in attempts)
        aggregates.append(
            {
                "id": case_id,
                "attempts": len(attempts),
                "expected_attempts": repeat,
                "passed_attempts": passed,
                "pass_rate": round(passed / len(attempts), 4),
                "stable": bool(signatures) and len(set(signatures)) == 1,
                "outcomes": dict(Counter(attempt["outcome"] for attempt in attempts)),
                "verifications": dict(Counter(attempt.get("verification", "policy") for attempt in attempts)),
            }
        )
    return aggregates


def suggest_tuning(results: list[dict[str, Any]], aggregates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        by_id.setdefault(result["id"], []).append(result)
    suggestions: list[dict[str, Any]] = []
    actions = {
        "missed_route": "补充目标 Skill description 中缺失的真实触发语言，不扩大其它边界。",
        "over_route": "收窄被误调 Skill description，并增加该直接任务的排除边界。",
        "wrong_route": "同时检查目标与竞争 Skill description 的重叠，只修改一个边界后复测。",
        "multi_intent_error": "澄清 piece-router 对多个独立交付物和高影响协调的触发边界。",
    }
    for aggregate in aggregates:
        attempts = by_id[aggregate["id"]]
        eligible = [
            attempt
            for attempt in attempts
            if attempt["outcome"] in actions and attempt.get("verification") in {"verified", "conflict"}
        ]
        if not eligible:
            continue
        outcome, count = Counter(attempt["outcome"] for attempt in eligible).most_common(1)[0]
        if count < 2:
            continue
        targets: set[str] = set()
        for attempt in eligible:
            if attempt["outcome"] != outcome:
                continue
            if outcome in {"missed_route", "wrong_route"}:
                targets.update(attempt.get("expected_skills", []))
            if outcome in {"over_route", "wrong_route"}:
                targets.update(attempt.get("observed_skills", []))
            if outcome == "multi_intent_error":
                targets.add("piece-router")
        suggestions.append(
            {
                "case_id": aggregate["id"],
                "failure": outcome,
                "reproduced_attempts": count,
                "target_skills": sorted(targets),
                "action": actions[outcome],
                "automatic_edit": False,
            }
        )
    return suggestions


def default_output(host: str, mode: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return ROOT / "eval-results" / f"{mode}-{host}-{stamp}.json"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--host", choices=("codex", "claude"), required=True)
    result.add_argument("--mode", choices=("policy", "native"), default="policy")
    result.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    result.add_argument("--case", action="append", dest="case_ids")
    result.add_argument("--repeat", type=int, default=1)
    result.add_argument("--suggest-tuning", action="store_true")
    result.add_argument("--output", type=Path)
    result.add_argument("--timeout", type=int)
    result.add_argument("--model")
    result.add_argument("--adapter-executable")
    result.add_argument("--adapter-arg", action="append", default=[])
    result.add_argument("--dry-run", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.repeat < 1 or args.repeat > 10:
        print("--repeat 必须在 1 到 10 之间", file=sys.stderr)
        return 2
    timeout = args.timeout if args.timeout is not None else (45 if args.mode == "native" else 120)
    if timeout < 1:
        print("--timeout 必须大于 0", file=sys.stderr)
        return 2
    if args.suggest_tuning and (args.mode != "native" or args.repeat < 3):
        print("--suggest-tuning 仅支持 native 模式且要求 --repeat >= 3", file=sys.stderr)
        return 2
    try:
        cases = load_cases(args.cases.resolve(), set(args.case_ids) if args.case_ids else None)
        if args.mode == "native":
            missing = [case["id"] for case in cases if "expected_skills" not in case]
            if missing:
                raise ValueError(f"native 案例缺少 expected_skills: {', '.join(missing)}")
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"评测集无效: {exc}", file=sys.stderr)
        return 2

    if args.host == "claude" and not args.adapter_executable:
        print(
            "Claude adapter unavailable: 本机未验证 Claude CLI 接口。请通过 "
            "--adapter-executable 提供 stdin/stdout 适配器。",
            file=sys.stderr,
        )
        return 2

    if args.dry_run:
        print(f"host={args.host} mode={args.mode} cases={len(cases)} repeat={args.repeat} timeout={timeout}s")
        for case in cases:
            expected = case.get("expected_skills") if args.mode == "native" else case["expected_route"]
            print(f"- {case['id']}: {expected} ({case['category']})")
        return 0

    results: list[dict[str, Any]] = []
    total_runs = len(cases) * args.repeat
    run_index = 0
    for case in cases:
        for attempt in range(1, args.repeat + 1):
            run_index += 1
            print(f"[{run_index}/{total_runs}] {case['id']} attempt={attempt} ...", flush=True)
            prompt = build_native_prompt(case) if args.mode == "native" else build_policy_prompt(case)
            if args.adapter_executable:
                host_result = run_adapter(
                    args.adapter_executable,
                    args.adapter_arg,
                    prompt,
                    timeout,
                    ROOT,
                    args.mode,
                )
            else:
                host_result = run_codex(
                    prompt,
                    timeout,
                    ROOT,
                    args.model,
                    args.mode,
                    set(case.get("expected_skills", [])) if args.mode == "native" else None,
                )
            classified = classify_native(case, host_result) if args.mode == "native" else classify(case, host_result)
            classified["attempt"] = attempt
            results.append(classified)

    summary = summarize(results)
    aggregates = aggregate_cases(results, args.repeat)
    summary["stable_cases"] = sum(case["stable"] for case in aggregates)
    summary["case_count"] = len(aggregates)
    tuning = suggest_tuning(results, aggregates) if args.suggest_tuning else []
    output = (args.output or default_output(args.host, args.mode)).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host": args.host,
        "mode": args.mode,
        "repeat": args.repeat,
        "timeout_seconds": timeout,
        "claim": (
            "routing-policy-classification; not native invocation evidence"
            if args.mode == "policy"
            else "observable native skill invocation"
        ),
        "cases_file": str(args.cases.resolve()),
        "model": args.model,
        "adapter": Path(args.adapter_executable).name if args.adapter_executable else "codex-cli",
        "summary": summary,
        "cases": aggregates,
        "results": results,
        "tuning_candidates": tuning,
    }
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    metric = summary["verified_pass_rate"] if args.mode == "native" else summary["route_accuracy"]
    label = "可验证调用通过率" if args.mode == "native" else "政策路由正确率"
    print(
        f"通过 {summary['passed']}/{summary['total']} | {label} {metric:.1%} | "
        f"执行错误 {summary['execution_error']} | {output}"
    )
    if tuning:
        print(f"提示边界优化候选 {len(tuning)} 个；仅输出建议，未修改任何 Skill。")
    for item in results:
        if not item["passed"]:
            actual = item.get("actual_route", item.get("observed_skills"))
            print(f"- {item['id']}#{item['attempt']}: {item['outcome']} actual={actual}")
    if summary["execution_error"]:
        return 2
    return 0 if summary["passed"] == summary["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
