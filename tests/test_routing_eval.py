from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_routing_eval import (  # noqa: E402
    HostResult,
    aggregate_cases,
    classify,
    classify_native,
    load_cases,
    parse_codex_events,
    skills_from_command,
    suggest_tuning,
    summarize,
)


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
        self.assertTrue(all("expected_skills" in case for case in cases))

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

    def test_extracts_first_party_skills_from_windows_and_unix_commands(self):
        windows = r"powershell Get-Content C:\cache\taste\skills\taste\SKILL.md"
        unix = "cat /cache/tessera/skills/piece-router/SKILL.md"
        self.assertEqual(skills_from_command(windows), {"taste"})
        self.assertEqual(skills_from_command(unix), {"piece-router"})

    def test_parses_multiple_skills_and_reports_malformed_events(self):
        events = "\n".join(
            [
                '{"item":{"command":"cat /p/skills/taste/SKILL.md"}}',
                "not-json",
                '{"item":{"command":"cat /p/skills/planner/SKILL.md"}}',
            ]
        )
        observed, malformed = parse_codex_events(events)
        self.assertEqual(observed, ("planner", "taste"))
        self.assertEqual(malformed, 1)

    def test_native_distinguishes_verified_declared_and_conflict(self):
        case = {
            "id": "visual",
            "category": "specialist",
            "prompt": "x",
            "expected_skills": ["taste"],
        }
        verified = classify_native(
            case,
            HostResult(
                {"decision": "skill", "selected_skills": ["taste"], "reason": "x"},
                10,
                observed_skills=("taste",),
                observation_source="host-events",
            ),
        )
        declared = classify_native(
            case,
            HostResult(
                {"decision": "skill", "selected_skills": ["taste"], "reason": "x"},
                10,
                observation_source="model-report",
            ),
        )
        conflict = classify_native(
            case,
            HostResult(
                {"decision": "skill", "selected_skills": ["taste"], "reason": "x"},
                10,
                observed_skills=("planner",),
                observation_source="host-events",
            ),
        )
        self.assertEqual((verified["verification"], verified["passed"]), ("verified", True))
        self.assertEqual((declared["verification"], declared["passed"]), ("declared-only", False))
        self.assertEqual((conflict["verification"], conflict["passed"]), ("conflict", False))

    def test_native_direct_is_verified_by_complete_host_event_stream(self):
        case = {"id": "direct", "category": "direct", "prompt": "x", "expected_skills": []}
        result = classify_native(
            case,
            HostResult(
                {"decision": "direct", "selected_skills": [], "reason": "x"},
                5,
                observation_source="host-events",
            ),
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["verification"], "verified")

    def test_native_complete_event_stream_can_verify_a_missed_skill(self):
        case = {"id": "miss", "category": "specialist", "prompt": "x", "expected_skills": ["taste"]}
        result = classify_native(
            case,
            HostResult(
                {"decision": "direct", "selected_skills": [], "reason": "x"},
                5,
                observation_source="host-events",
            ),
        )
        self.assertFalse(result["passed"])
        self.assertEqual(result["verification"], "verified")
        self.assertEqual(result["outcome"], "missed_route")

    def test_repeat_aggregation_tracks_stability(self):
        results = [
            {"id": "x", "passed": True, "outcome": "pass", "observed_skills": ["taste"]},
            {"id": "x", "passed": False, "outcome": "wrong_route", "observed_skills": ["planner"]},
        ]
        aggregate = aggregate_cases(results, repeat=2)[0]
        self.assertEqual(aggregate["pass_rate"], 0.5)
        self.assertFalse(aggregate["stable"])

    def test_tuning_requires_two_observed_matching_failures(self):
        base = {
            "id": "x",
            "passed": False,
            "outcome": "missed_route",
            "verification": "verified",
            "expected_skills": ["taste"],
            "observed_skills": [],
        }
        results = [dict(base), dict(base), {**base, "verification": "unobservable"}]
        aggregates = aggregate_cases(results, repeat=3)
        suggestions = suggest_tuning(results, aggregates)
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["target_skills"], ["taste"])
        self.assertFalse(suggestions[0]["automatic_edit"])


if __name__ == "__main__":
    unittest.main()
