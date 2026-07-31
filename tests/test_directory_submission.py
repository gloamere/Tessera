from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DirectorySubmissionTests(unittest.TestCase):
    def run_validator(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "scripts/validate_directory_submission.py",
                *arguments,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )

    def test_submission_structure_is_valid_while_external_items_are_pending(self):
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("item(s) pending", result.stdout)

    def test_complete_gate_fails_closed_before_publisher_inputs_and_evidence(self):
        result = self.run_validator("--require-complete")
        self.assertEqual(result.returncode, 1)
        self.assertIn("country availability", result.stderr)
        self.assertIn("demo recording", result.stderr)
        self.assertIn("pilot requires 5", result.stderr)
        self.assertIn("report-v4", result.stderr)
        self.assertIn("102-case exhaustive evidence", result.stderr)
        self.assertIn("output-quality evidence", result.stderr)

    def test_submission_has_exact_public_scope_and_case_counts(self):
        submission = json.loads(
            (ROOT / "docs" / "directory" / "submission.json").read_text(
                encoding="utf-8"
            )
        )
        cases = json.loads(
            (ROOT / submission["testCases"]).read_text(encoding="utf-8")
        )
        self.assertEqual(set(submission["listing"]), {"en-US", "zh-CN"})
        self.assertTrue(
            all(
                len(localized["starterPrompts"]) == 3
                for localized in submission["listing"].values()
            )
        )
        self.assertEqual(len(cases["positive"]), 5)
        self.assertEqual(len(cases["negative"]), 3)
        self.assertEqual(submission["pilot"]["participants"], 0)
        self.assertEqual(submission["pilot"]["completedTasks"], 0)


if __name__ == "__main__":
    unittest.main()
