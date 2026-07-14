"""Opt-in, local-only usage journal for first-party Tessera skills."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import time
import uuid
from typing import Any, Iterator


SCHEMA_VERSION = 1
DEFAULT_RETENTION_DAYS = 90
VALID_EVENTS = {"started", "completed", "failed", "feedback"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def tessera_home(home: Path | None = None) -> Path:
    return (home or (Path.home() / ".tessera")).expanduser()


def config_path(home: Path | None = None) -> Path:
    return tessera_home(home) / "config.json"


def events_path(home: Path | None = None) -> Path:
    return tessera_home(home) / "usage" / "events.jsonl"


def _default_config() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "usage_logging": False,
        "retention_days": DEFAULT_RETENTION_DAYS,
        "project_salt": secrets.token_hex(16),
    }


def load_config(home: Path | None = None) -> dict[str, Any] | None:
    path = config_path(home)
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    if not isinstance(value.get("usage_logging"), bool):
        return None
    if not isinstance(value.get("project_salt"), str) or not value["project_salt"]:
        return None
    retention = value.get("retention_days")
    if not isinstance(retention, int) or retention < 1:
        return None
    return value


def _write_config(config: dict[str, Any], home: Path | None = None) -> None:
    path = config_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f".tmp-{uuid.uuid4().hex}")
    temporary.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def enable(home: Path | None = None, retention_days: int = DEFAULT_RETENTION_DAYS) -> dict[str, Any]:
    if retention_days < 1:
        raise ValueError("retention_days must be positive")
    config = load_config(home) or _default_config()
    config.update(
        {
            "schema_version": SCHEMA_VERSION,
            "usage_logging": True,
            "retention_days": retention_days,
        }
    )
    _write_config(config, home)
    return config


def disable(home: Path | None = None) -> dict[str, Any]:
    config = load_config(home) or _default_config()
    config["usage_logging"] = False
    _write_config(config, home)
    return config


def is_enabled(home: Path | None = None) -> bool:
    config = load_config(home)
    return bool(config and config["usage_logging"])


def hash_project(project: Path | str | None, salt: str) -> str:
    raw = Path(project or Path.cwd()).expanduser().resolve(strict=False)
    normalized = os.path.normcase(str(raw))
    return hashlib.sha256(f"{salt}\0{normalized}".encode("utf-8")).hexdigest()[:16]


@contextmanager
def _usage_lock(home: Path | None = None, timeout_seconds: float = 3.0) -> Iterator[None]:
    lock = events_path(home).with_suffix(".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(descriptor, str(os.getpid()).encode("ascii"))
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > 30:
                    lock.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            if time.monotonic() >= deadline:
                raise TimeoutError("timed out waiting for usage journal lock")
            time.sleep(0.02)
    try:
        yield
    finally:
        if descriptor is not None:
            os.close(descriptor)
        lock.unlink(missing_ok=True)


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _read_events(home: Path | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    path = events_path(home)
    if not path.exists():
        return [], []
    events: list[dict[str, Any]] = []
    corrupt: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            corrupt.append(line)
            continue
        if not isinstance(value, dict) or value.get("event") not in VALID_EVENTS:
            corrupt.append(line)
            continue
        events.append(value)
    return events, corrupt


def _prune_locked(config: dict[str, Any], home: Path | None = None, now: datetime | None = None) -> None:
    path = events_path(home)
    if not path.exists():
        return
    cutoff = (now or utc_now()) - timedelta(days=config["retention_days"])
    events, corrupt = _read_events(home)
    kept = [event for event in events if (_parse_timestamp(event.get("timestamp_utc")) or cutoff) >= cutoff]
    if len(kept) == len(events):
        return
    lines = [json.dumps(event, ensure_ascii=False, separators=(",", ":")) for event in kept]
    lines.extend(corrupt)
    temporary = path.with_suffix(f".tmp-{uuid.uuid4().hex}")
    temporary.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")
    os.replace(temporary, path)


def _append(event: dict[str, Any], config: dict[str, Any], home: Path | None = None) -> None:
    path = events_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _usage_lock(home):
        _prune_locked(config, home)
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")


def _event(
    event_id: str,
    host: str,
    skill: str,
    event: str,
    project_hash: str,
    duration_ms: int | None = None,
    useful: bool | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": event_id,
        "timestamp_utc": (now or utc_now()).isoformat(),
        "host": host,
        "skill": skill,
        "event": event,
        "project_hash": project_hash,
        "duration_ms": duration_ms,
        "useful": useful,
    }


def record_start(
    host: str,
    skill: str,
    project: Path | str | None = None,
    home: Path | None = None,
    now: datetime | None = None,
) -> str | None:
    config = load_config(home)
    if not config or not config["usage_logging"]:
        return None
    event_id = uuid.uuid4().hex
    _append(
        _event(event_id, host, skill, "started", hash_project(project, config["project_salt"]), now=now),
        config,
        home,
    )
    return event_id


def record_finish(
    event_id: str,
    host: str,
    skill: str,
    outcome: str,
    project: Path | str | None = None,
    duration_ms: int | None = None,
    home: Path | None = None,
    now: datetime | None = None,
) -> bool:
    if outcome not in {"completed", "failed"}:
        raise ValueError("outcome must be completed or failed")
    config = load_config(home)
    if not config or not config["usage_logging"]:
        return False
    _append(
        _event(
            event_id,
            host,
            skill,
            outcome,
            hash_project(project, config["project_salt"]),
            duration_ms,
            now=now,
        ),
        config,
        home,
    )
    return True


def record_feedback(
    useful: bool,
    skill: str | None = None,
    home: Path | None = None,
    now: datetime | None = None,
) -> str | None:
    config = load_config(home)
    if not config or not config["usage_logging"]:
        return None
    events, _ = _read_events(home)
    target = next(
        (
            event
            for event in reversed(events)
            if event.get("event") in {"completed", "failed"}
            and (skill is None or event.get("skill") == skill)
        ),
        None,
    )
    if target is None:
        return None
    _append(
        _event(
            str(target["event_id"]),
            str(target["host"]),
            str(target["skill"]),
            "feedback",
            str(target["project_hash"]),
            useful=useful,
            now=now,
        ),
        config,
        home,
    )
    return str(target["event_id"])


def summarize(days: int, home: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    if days < 1:
        raise ValueError("days must be positive")
    current = now or utc_now()
    cutoff = current - timedelta(days=days)
    events, corrupt = _read_events(home)
    selected = [
        event
        for event in events
        if (_parse_timestamp(event.get("timestamp_utc")) or datetime.min.replace(tzinfo=timezone.utc))
        >= cutoff
    ]
    started = [event for event in selected if event["event"] == "started"]
    completed_ids = {event["event_id"] for event in selected if event["event"] == "completed"}
    failed_ids = {event["event_id"] for event in selected if event["event"] == "failed"}
    feedback = [event for event in selected if event["event"] == "feedback"]

    def grouped(field: str) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for event in started:
            key = str(event.get(field) or "unknown")
            item = result.setdefault(
                key,
                {"started": 0, "completed": 0, "failed": 0, "projects": set()},
            )
            item["started"] += 1
            event_id = event["event_id"]
            item["completed"] += int(event_id in completed_ids)
            item["failed"] += int(event_id in failed_ids)
            item["projects"].add(event.get("project_hash"))
        for item in result.values():
            item["projects"] = len(item["projects"] - {None})
        return result

    total = len(started)
    completed = sum(event["event_id"] in completed_ids for event in started)
    failed = sum(event["event_id"] in failed_ids for event in started)
    return {
        "schema_version": SCHEMA_VERSION,
        "days": days,
        "generated_at": current.isoformat(),
        "coverage": "first-party Tessera skills only; direct external skill invocations are not observed",
        "corrupt_lines": len(corrupt),
        "started": total,
        "completed": completed,
        "failed": failed,
        "incomplete": max(total - completed - failed, 0),
        "completion_rate": (completed / total) if total else 0.0,
        "feedback": len(feedback),
        "useful": sum(event.get("useful") is True for event in feedback),
        "not_useful": sum(event.get("useful") is False for event in feedback),
        "projects": len({event.get("project_hash") for event in started} - {None}),
        "by_skill": grouped("skill"),
        "by_host": grouped("host"),
    }


def purge(home: Path | None = None) -> None:
    path = events_path(home)
    with _usage_lock(home):
        path.unlink(missing_ok=True)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--home", type=Path, help=argparse.SUPPRESS)
    commands = result.add_subparsers(dest="command", required=True)
    enable_parser = commands.add_parser("enable")
    enable_parser.add_argument("--retention-days", type=int, default=DEFAULT_RETENTION_DAYS)
    commands.add_parser("disable")
    start = commands.add_parser("start")
    start.add_argument("--host", required=True)
    start.add_argument("--skill", required=True)
    start.add_argument("--project", type=Path)
    finish = commands.add_parser("finish")
    finish.add_argument("--event-id", required=True)
    finish.add_argument("--host", required=True)
    finish.add_argument("--skill", required=True)
    finish.add_argument("--outcome", choices=("completed", "failed"), required=True)
    finish.add_argument("--duration-ms", type=int)
    finish.add_argument("--project", type=Path)
    feedback = commands.add_parser("feedback")
    feedback.add_argument("--latest", action="store_true", required=True)
    feedback.add_argument("--skill")
    feedback.add_argument("--useful", choices=("yes", "no"), required=True)
    summary = commands.add_parser("summary")
    summary.add_argument("--days", choices=(30, 90), type=int, required=True)
    commands.add_parser("purge")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "enable":
            config = enable(args.home, args.retention_days)
            print(json.dumps({"usage_logging": True, "retention_days": config["retention_days"]}))
        elif args.command == "disable":
            disable(args.home)
            print(json.dumps({"usage_logging": False, "history_preserved": True}))
        elif args.command == "start":
            event_id = record_start(args.host, args.skill, args.project, args.home)
            print(event_id or "disabled")
        elif args.command == "finish":
            recorded = record_finish(
                args.event_id,
                args.host,
                args.skill,
                args.outcome,
                args.project,
                args.duration_ms,
                args.home,
            )
            print("recorded" if recorded else "disabled")
        elif args.command == "feedback":
            event_id = record_feedback(args.useful == "yes", args.skill, args.home)
            print(event_id or "no-matching-event")
        elif args.command == "summary":
            print(json.dumps(summarize(args.days, args.home), ensure_ascii=False, indent=2))
        elif args.command == "purge":
            purge(args.home)
            print(json.dumps({"purged": True}))
    except (OSError, TimeoutError, ValueError) as exc:
        print(f"usage journal unavailable: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
