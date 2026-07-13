"""Run Tessera routing cases against a host and write a reproducible JSON report."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
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
OUTPUT_SCHEMA = ROOT / "tests" / "routing-output.schema.json"
VALID_CATEGORIES = {
    "direct",
    "specialist",
    "core",
    "multi-intent",
    "external",
    "decision",
}


@dataclass(frozen=True)
class HostResult:
    payload: dict[str, Any] | None
    duration_ms: int
    error: str | None = None


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
        if selected is None or case_id in selected:
            cases.append(item)
    if selected:
        missing = selected - seen
        if missing:
            raise ValueError(f"找不到案例: {', '.join(sorted(missing))}")
    return cases


def build_prompt(case: dict[str, Any]) -> str:
    return f"""你正在执行 Tessera 路由评测。只判断下面的用户请求应走哪个路由，不执行请求、不修改文件、不安装依赖。

请依据当前会话实际可见的 Tessera skills 和宿主原生能力作答。route 必须是输出 schema 允许的单个值：
- direct：宿主直接完成
- piece-router：需要 Tessera 路由网关处理复合、模糊或高影响请求
- piece-admission：新增、引入、拆分或设计拼图的准入评审
- tessera-setup / tessera-status / tessera-doctor / tessera-eval：对应核心能力
- taste / knowledge-base / planner：对应专业拼图
- external-unavailable：请求的外部候选当前不可安装或不可验证

不要参考任何预期答案，只根据请求本身判断。reason 用一句短句；router_used 表示是否需要由 piece-router 作出路由选择。

CASE_ID: {case['id']}
用户请求：{case['prompt']}
"""


def parse_payload(text: str) -> dict[str, Any]:
    value = text.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        value = "\n".join(lines[1:-1]).strip()
    payload = json.loads(value)
    if not isinstance(payload, dict) or not isinstance(payload.get("route"), str):
        raise ValueError("宿主输出缺少字符串 route")
    return payload


def run_adapter(
    executable: str,
    arguments: list[str],
    prompt: str,
    timeout: int,
    cwd: Path,
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
        return HostResult(parse_payload(completed.stdout), duration)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, ValueError) as exc:
        duration = round((time.perf_counter() - started) * 1000)
        return HostResult(None, duration, str(exc))


def find_codex() -> str | None:
    for name in ("codex", "codex.cmd", "codex.exe"):
        found = shutil.which(name)
        if found:
            return found
    return None


def run_codex(prompt: str, timeout: int, cwd: Path, model: str | None) -> HostResult:
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
            str(OUTPUT_SCHEMA),
            "--output-last-message",
            str(output),
            "--cd",
            str(cwd),
        ]
        if model:
            command.extend(["--model", model])
        command.append("-")
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
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
                return HostResult(None, duration, f"codex exited {completed.returncode}: {detail[-800:]}")
            if not output.is_file():
                return HostResult(None, duration, "Codex did not write the last-message file")
            return HostResult(parse_payload(output.read_text(encoding="utf-8")), duration)
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, ValueError) as exc:
            duration = round((time.perf_counter() - started) * 1000)
            return HostResult(None, duration, str(exc))


def classify(case: dict[str, Any], result: HostResult) -> dict[str, Any]:
    expected = case["expected_route"]
    excluded = case.get("must_not_route", [])
    if result.error:
        outcome = "execution_error"
        actual = None
        passed = False
    else:
        actual = result.payload["route"] if result.payload else None
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
    return {
        "total": total,
        "completed": completed,
        "passed": passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "route_accuracy": round(passed / completed, 4) if completed else 0.0,
        **counts,
        "median_duration_ms": round(statistics.median(durations)) if durations else 0,
        "total_duration_ms": sum(durations),
    }


def default_output(host: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return ROOT / "eval-results" / f"routing-{host}-{stamp}.json"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--host", choices=("codex", "claude"), required=True)
    result.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    result.add_argument("--case", action="append", dest="case_ids")
    result.add_argument("--output", type=Path)
    result.add_argument("--timeout", type=int, default=120)
    result.add_argument("--model")
    result.add_argument("--adapter-executable")
    result.add_argument("--adapter-arg", action="append", default=[])
    result.add_argument("--dry-run", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        cases = load_cases(args.cases.resolve(), set(args.case_ids) if args.case_ids else None)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"评测集无效: {exc}", file=sys.stderr)
        return 2

    if args.host == "claude" and not args.adapter_executable:
        print(
            "Claude adapter unavailable: 本机未验证 Claude CLI 接口。请通过 "
            "--adapter-executable 提供一个从 stdin 读取提示、向 stdout 输出路由 JSON 的适配器。",
            file=sys.stderr,
        )
        return 2

    if args.dry_run:
        print(f"host={args.host} cases={len(cases)} timeout={args.timeout}s")
        for case in cases:
            print(f"- {case['id']}: {case['expected_route']} ({case['category']})")
        return 0

    results: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] {case['id']} ...", flush=True)
        prompt = build_prompt(case)
        if args.adapter_executable:
            host_result = run_adapter(
                args.adapter_executable,
                args.adapter_arg,
                prompt,
                args.timeout,
                ROOT,
            )
        else:
            host_result = run_codex(prompt, args.timeout, ROOT, args.model)
        results.append(classify(case, host_result))

    summary = summarize(results)
    output = (args.output or default_output(args.host)).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host": args.host,
        "cases_file": str(args.cases.resolve()),
        "model": args.model,
        "adapter": Path(args.adapter_executable).name if args.adapter_executable else "codex-cli",
        "summary": summary,
        "results": results,
    }
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"通过 {summary['passed']}/{summary['total']} | "
        f"路由正确率 {summary['route_accuracy']:.1%} | "
        f"执行错误 {summary['execution_error']} | {output}"
    )
    for item in results:
        if not item["passed"]:
            print(
                f"- {item['id']}: {item['outcome']} "
                f"expected={item['expected_route']} actual={item['actual_route']}"
            )
    if summary["execution_error"]:
        return 2
    return 0 if summary["passed"] == summary["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
