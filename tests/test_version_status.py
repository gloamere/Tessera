from __future__ import annotations

from pathlib import Path
import sys
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from version_status import classify_version  # noqa: E402
from doctor_status import overall_status  # noqa: E402


class VersionStatusTests(unittest.TestCase):
    def test_version_states(self) -> None:
        cases = {
            ("1.2.3", "1.2.3"): "current",
            ("1.2.3+codex.old", "1.2.3+codex.new"): "refresh-available",
            ("1.2.3", "1.3.0"): "update-available",
            ("2.0.0", "1.9.9"): "ahead",
            (None, "1.0.0"): "unknown",
            ("1.0.0-beta.1", "1.0.0"): "unknown",
        }
        for versions, expected in cases.items():
            with self.subTest(versions=versions):
                self.assertEqual(classify_version(*versions), expected)

    def test_doctor_overall_status_cases(self) -> None:
        cases = yaml.safe_load(
            (ROOT / "tests" / "doctor-cases.yaml").read_text(encoding="utf-8")
        )
        for case in cases:
            with self.subTest(case=case["id"]):
                self.assertEqual(
                    overall_status(case["results"]), case["expected_overall"]
                )

    def test_doctor_rejects_unknown_result(self) -> None:
        with self.assertRaisesRegex(ValueError, "未知 doctor 结果"):
            overall_status(["PASS", "MAYBE"])


if __name__ == "__main__":
    unittest.main()
