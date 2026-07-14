from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_routing_eval import HostResult, classify, load_cases, summarize  # noqa: E402


class RoutingEvalTests(unittest.TestCase):
    def test_loads_versioned_categories(self):
        cases = load_cases(ROOT / "tests" / "routing-cases.yaml")
        self.assertGreaterEqual(len(cases), 15)
        self.assertTrue(all(case["category"] for case in cases))

    def test_personal_suite_keeps_60_40_profile(self):
        cases = load_cases(ROOT / "tests" / "personal-routing-cases.yaml")
        self.assertEqual(len(cases), 25)
        self.assertEqual(
            {profile: sum(case.get("profile") == profile for case in cases) for profile in ("development", "product")},
            {"development": 15, "product": 10},
        )

    def test_classifies_over_and_under_routing(self):
        direct = {"id": "d", "category": "direct", "prompt": "x", "expected_route": "direct"}
        specialist = {
            "id": "s",
            "category": "specialist",
            "prompt": "x",
            "expected_route": "taste",
        }
        over = classify(direct, HostResult({"route": "piece-router", "reason": "x"}, 10))
        missed = classify(specialist, HostResult({"route": "direct", "reason": "x"}, 20))
        self.assertEqual(over["outcome"], "over_route")
        self.assertEqual(missed["outcome"], "missed_route")

    def test_summary_keeps_execution_errors_in_pass_rate(self):
        results = [
            {"passed": True, "outcome": "pass", "duration_ms": 10},
            {"passed": False, "outcome": "execution_error", "duration_ms": 20},
        ]
        summary = summarize(results)
        self.assertEqual(summary["pass_rate"], 0.5)
        self.assertEqual(summary["route_accuracy"], 1.0)
        self.assertEqual(summary["execution_error"], 1)


if __name__ == "__main__":
    unittest.main()
