"""Deterministic Codex JSONL-envelope adapter used by eval runner tests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--skill-path", type=Path)
    result.add_argument("--skill-name")
    result.add_argument("--observed-path", type=Path)
    result.add_argument("--declared-skill", action="append")
    result.add_argument("--workspace-log", type=Path)
    result.add_argument("--mutate-path", type=Path)
    result.add_argument(
        "--mode",
        choices=(
            "valid",
            "failed-read",
            "started-only",
            "updated-only",
            "path-mention",
            "malformed",
            "truncated",
            "unknown-event",
            "unknown-item",
        ),
        default="valid",
    )
    return result


def main() -> int:
    args = parser().parse_args()
    sys.stdin.read()
    if args.workspace_log is not None:
        existing = (
            args.workspace_log.read_text(encoding="utf-8")
            if args.workspace_log.is_file()
            else ""
        )
        args.workspace_log.write_text(
            existing + str(Path.cwd().resolve()) + "\n",
            encoding="utf-8",
        )
    selected = (
        args.declared_skill
        if args.declared_skill is not None
        else ([args.skill_name] if args.skill_name else [])
    )
    events: list[object] = [
        {
            "type": "thread.started",
            "thread_id": "fixture-thread",
        },
        {
            "type": "turn.started",
        },
    ]
    observed_path = args.observed_path or args.skill_path
    if observed_path is not None:
        if args.mode == "path-mention":
            command = f'echo "{observed_path}"'
            output = str(observed_path)
        else:
            command = f'type "{observed_path}"'
            output = (
                observed_path.read_text(encoding="utf-8")
                if observed_path.is_file()
                else "unbound fixture Skill"
            )
        event_type = {
            "started-only": "item.started",
            "updated-only": "item.updated",
        }.get(args.mode, "item.completed")
        events.append(
            {
                "type": event_type,
                "item": {
                    "id": "fixture-command",
                    "type": "command_execution",
                    "command": command,
                    "status": (
                        "failed"
                        if args.mode == "failed-read"
                        else "completed"
                    ),
                    "exit_code": 1 if args.mode == "failed-read" else 0,
                    "aggregated_output": output,
                },
            }
        )
    if args.mode == "unknown-event":
        events.append({"type": "future.event"})
    elif args.mode == "unknown-item":
        events.append(
            {
                "type": "item.completed",
                "item": {
                    "id": "future-item",
                    "type": "future_item",
                },
            }
        )
    if args.mode != "truncated":
        events.append(
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 10,
                    "cached_input_tokens": 0,
                    "output_tokens": 2,
                    "reasoning_output_tokens": 0,
                },
            }
        )

    event_lines = [
        item if isinstance(item, str) else json.dumps(item, sort_keys=True)
        for item in events
    ]
    if args.mode == "malformed":
        event_lines.insert(-1, "{not-json")
    envelope = {
        "payload": {
            "selected_skills": selected,
            "reason": "deterministic fixture",
        },
        "event_stream": "\n".join(event_lines),
    }
    if args.mutate_path is not None and args.mutate_path.is_file():
        args.mutate_path.write_text(
            args.mutate_path.read_text(encoding="utf-8")
            + "\n# fixture identity drift\n",
            encoding="utf-8",
        )
    print(json.dumps(envelope))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
