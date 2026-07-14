from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from usage_events import (  # noqa: E402
    disable,
    enable,
    events_path,
    hash_project,
    is_enabled,
    load_config,
    purge,
    record_feedback,
    record_finish,
    record_start,
    summarize,
)


class UsageEventTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.home = Path(self.temporary.name)
        self.now = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.temporary.cleanup()

    def test_disabled_by_default_writes_nothing(self):
        self.assertFalse(is_enabled(self.home))
        self.assertIsNone(record_start("codex", "taste", "D:/Secret/Project", self.home))
        self.assertFalse(events_path(self.home).exists())

    def test_enable_disable_preserves_history(self):
        enable(self.home)
        self.assertTrue(is_enabled(self.home))
        event_id = record_start("codex", "taste", "D:/Secret/Project", self.home)
        self.assertIsNotNone(event_id)
        disable(self.home)
        self.assertFalse(is_enabled(self.home))
        self.assertTrue(events_path(self.home).exists())

    def test_records_start_finish_feedback_and_summary(self):
        enable(self.home)
        event_id = record_start(
            "codex", "planner", "D:/Secret/Project", self.home, self.now
        )
        self.assertIsNotNone(event_id)
        self.assertTrue(
            record_finish(
                event_id,
                "codex",
                "planner",
                "completed",
                "D:/Secret/Project",
                1250,
                self.home,
                self.now + timedelta(seconds=2),
            )
        )
        self.assertEqual(
            record_feedback(True, "planner", self.home, self.now + timedelta(seconds=3)),
            event_id,
        )
        result = summarize(30, self.home, self.now + timedelta(days=1))
        self.assertEqual(result["started"], 1)
        self.assertEqual(result["completed"], 1)
        self.assertEqual(result["useful"], 1)
        self.assertEqual(result["projects"], 1)
        self.assertEqual(result["by_skill"]["planner"]["completed"], 1)

    def test_failed_and_incomplete_are_distinct(self):
        enable(self.home)
        failed = record_start("codex", "taste", None, self.home, self.now)
        record_finish(
            failed,
            "codex",
            "taste",
            "failed",
            None,
            None,
            self.home,
            self.now,
        )
        record_start("codex", "planner", None, self.home, self.now)
        result = summarize(30, self.home, self.now)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["incomplete"], 1)

    def test_project_hash_is_salted_and_stable(self):
        config = enable(self.home)
        first = hash_project("D:/Secret/Project", config["project_salt"])
        second = hash_project("D:/Secret/Project", config["project_salt"])
        other = hash_project("D:/Secret/Other", config["project_salt"])
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)
        self.assertNotIn("Secret", first)

    def test_events_never_store_prompt_or_real_path(self):
        enable(self.home)
        record_start("codex", "knowledge-base", "D:/Secret/Project", self.home, self.now)
        raw = events_path(self.home).read_text(encoding="utf-8")
        event = json.loads(raw)
        self.assertNotIn("D:/Secret/Project", raw)
        self.assertNotIn("prompt", event)
        self.assertNotIn("response", event)
        self.assertEqual(
            set(event),
            {
                "schema_version",
                "event_id",
                "timestamp_utc",
                "host",
                "skill",
                "event",
                "project_hash",
                "duration_ms",
                "useful",
            },
        )

    def test_retention_prunes_old_valid_events(self):
        enable(self.home, retention_days=90)
        old = self.now - timedelta(days=91)
        record_start("codex", "taste", None, self.home, old)
        record_start("codex", "planner", None, self.home, self.now)
        events = [
            json.loads(line)
            for line in events_path(self.home).read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual([event["skill"] for event in events], ["planner"])

    def test_summary_reports_corrupt_lines_without_rewriting(self):
        enable(self.home)
        path = events_path(self.home)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not-json\n", encoding="utf-8")
        result = summarize(30, self.home, self.now)
        self.assertEqual(result["corrupt_lines"], 1)
        self.assertEqual(path.read_text(encoding="utf-8"), "not-json\n")

    def test_concurrent_appends_remain_valid(self):
        enable(self.home)
        with ThreadPoolExecutor(max_workers=8) as executor:
            event_ids = list(
                executor.map(
                    lambda index: record_start(
                        "codex", f"skill-{index}", None, self.home, self.now
                    ),
                    range(24),
                )
            )
        self.assertEqual(len(set(event_ids)), 24)
        lines = events_path(self.home).read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 24)
        self.assertTrue(all(json.loads(line)["event"] == "started" for line in lines))

    def test_malformed_config_fails_closed(self):
        config = self.home / "config.json"
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text("not-json", encoding="utf-8")
        self.assertIsNone(load_config(self.home))
        self.assertIsNone(record_start("codex", "taste", None, self.home))
        self.assertFalse(events_path(self.home).exists())

    def test_purge_requires_explicit_call(self):
        enable(self.home)
        record_start("codex", "taste", None, self.home, self.now)
        purge(self.home)
        self.assertFalse(events_path(self.home).exists())


if __name__ == "__main__":
    unittest.main()
