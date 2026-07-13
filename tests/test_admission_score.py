from __future__ import annotations

from pathlib import Path
import sys
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from admission_score import evaluate, grade_for_score  # noqa: E402


class AdmissionScoreTests(unittest.TestCase):
    def test_documented_cases(self) -> None:
        cases = yaml.safe_load(
            (ROOT / "tests" / "admission-cases.yaml").read_text(encoding="utf-8")
        )
        for case in cases:
            with self.subTest(case=case["id"]):
                actual = evaluate(case["scores"], case.get("flags", {}))
                for field, expected in case["expected"].items():
                    self.assertEqual(actual[field], expected)

    def test_all_grade_boundaries(self) -> None:
        expected = {
            100: "S",
            90: "S",
            89: "A",
            80: "A",
            79: "B",
            70: "B",
            69: "C",
            60: "C",
            59: "D",
            50: "D",
            49: "E",
            40: "E",
            39: "F",
            0: "F",
        }
        for score, grade in expected.items():
            with self.subTest(score=score):
                self.assertEqual(grade_for_score(score), grade)

    def test_rejects_undocumented_intermediate_score(self) -> None:
        with self.assertRaisesRegex(ValueError, "不是允许的锚点分值"):
            evaluate(
                {
                    "demand": 19,
                    "value": 20,
                    "boundary": 15,
                    "evaluability": 15,
                    "lightweight": 15,
                    "portability": 10,
                    "safety": 5,
                }
            )


if __name__ == "__main__":
    unittest.main()
