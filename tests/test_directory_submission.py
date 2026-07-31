from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from scripts import validate_directory_submission as directory_validator


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
        self.assertIn("country availability for CN", result.stderr)
        self.assertIn("demo recording", result.stderr)
        self.assertIn("owner-dogfood requires exactly 1 maintainer", result.stderr)
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
        self.assertEqual(submission["availability"]["requestedCountries"], ["CN"])
        self.assertEqual(submission["pilot"]["validationMode"], "owner-dogfood")
        self.assertEqual(submission["pilot"]["participants"], 1)
        self.assertEqual(submission["pilot"]["completedTasks"], 0)
        self.assertEqual(
            set(submission["pilot"]["skillTaskCounts"]),
            {
                "gloamere-product-decision",
                "gloamere-visual-review",
                "gloamere-knowledge-capture",
            },
        )

    def test_completed_owner_dogfood_satisfies_internal_value_gate(self):
        submission = json.loads(
            (ROOT / "docs" / "directory" / "submission.json").read_text(
                encoding="utf-8"
            )
        )
        submission["pilot"].update(
            {
                "status": "complete",
                "completedTasks": 10,
                "majorRewriteTasks": 2,
                "readyWithoutMajorRewriteRate": 0.8,
                "skillTaskCounts": {
                    "gloamere-product-decision": 4,
                    "gloamere-visual-review": 3,
                    "gloamere-knowledge-capture": 3,
                },
                "confirmedHighRiskFalseActivations": 0,
            }
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            submission_path = Path(temporary_directory) / "submission.json"
            submission_path.write_text(
                json.dumps(submission, ensure_ascii=False),
                encoding="utf-8",
            )
            with mock.patch.object(
                directory_validator,
                "SUBMISSION_PATH",
                submission_path,
            ):
                errors, pending = directory_validator.validate(False)

        self.assertEqual(errors, [])
        self.assertFalse(
            any("owner-dogfood" in item for item in pending),
            pending,
        )


if __name__ == "__main__":
    unittest.main()
