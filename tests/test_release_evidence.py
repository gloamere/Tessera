from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from scripts import validate_release_evidence as gate


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "release-manifest.json"
SYNTHETIC_NON_RELEASE_MARKER = (
    "Synthetic fixture: never declare this object as release evidence."
)


class ReleaseEvidenceGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract, cls.contract_errors = gate.load_contract(ROOT, MANIFEST)

    def test_release_contract_is_current_and_risk_classified(self) -> None:
        self.assertEqual(self.contract_errors, [])
        self.assertIsNotNone(self.contract)
        admission = self.contract["admission"]
        self.assertEqual(admission["repeat"], 3)
        self.assertEqual(admission["independent_batches"], 2)
        self.assertEqual(admission["thresholds"], gate.REQUIRED_THRESHOLDS)

        risk_counts = {"ordinary": 0, "high": 0}
        for case in self.contract["suite_cases"].values():
            if gate.one_tag(case["tags"], "kind:") != "adjacent-negative":
                continue
            risk_counts[gate.one_tag(case["tags"], "risk:")] += 1
        self.assertEqual(risk_counts, {"ordinary": 54, "high": 10})

    def test_missing_reports_are_pending_unless_required(self) -> None:
        result, code = gate.assess(ROOT, MANIFEST, require=False)
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "pending")
        self.assertIn("no native report v3", result["evidence_errors"][0])

        required_result, required_code = gate.assess(
            ROOT,
            MANIFEST,
            require=True,
        )
        self.assertEqual(required_code, 1)
        self.assertEqual(required_result["status"], "pending")

    def test_thresholds_are_inclusive_at_the_release_boundary(self) -> None:
        # This is a scalar-only synthetic fixture; it is not a native report.
        self.assertTrue(SYNTHETIC_NON_RELEASE_MARKER.startswith("Synthetic"))
        metrics = {
            "evidence_coverage": 1.0,
            "verified_exact_match": 0.95,
            "ordinary_over_route": 0.02,
            "multi_intent_complete": 0.9,
            "high_risk_over_route": 0,
        }
        self.assertEqual(
            gate.threshold_failures(metrics, gate.REQUIRED_THRESHOLDS),
            [],
        )
        metrics["high_risk_over_route"] = 0.01
        self.assertIn(
            "high_risk_over_route",
            gate.threshold_failures(
                metrics,
                gate.REQUIRED_THRESHOLDS,
            )[0],
        )

    def test_metrics_are_recomputed_from_attempt_records(self) -> None:
        # Synthetic records exercise arithmetic only and are never eligible
        # for release_evidence_eligible=true.
        records = [
            {
                "status": "verified",
                "exact": True,
                "observed": {"a"},
                "expected": {"a"},
                "kind": "positive",
                "risk": None,
            },
            {
                "status": "verified",
                "exact": False,
                "observed": {"a", "b"},
                "expected": {"a"},
                "kind": "adjacent-negative",
                "risk": "ordinary",
            },
            {
                "status": "verified",
                "exact": True,
                "observed": set(),
                "expected": set(),
                "kind": "adjacent-negative",
                "risk": "high",
            },
            {
                "status": "unobservable",
                "exact": False,
                "observed": set(),
                "expected": {"a", "b"},
                "kind": "multi-intent",
                "risk": None,
            },
        ]
        metrics = gate.recompute_metrics(records)
        self.assertEqual(metrics["evidence_coverage"], 0.75)
        self.assertEqual(metrics["verified_exact_match"], 2 / 3)
        self.assertEqual(metrics["ordinary_over_route"], 1.0)
        self.assertEqual(metrics["high_risk_over_route"], 0.0)
        self.assertEqual(metrics["multi_intent_complete"], 0.0)

    def synthetic_report(self, provenance: str) -> tuple[dict, dict]:
        self.assertIsNotNone(self.contract)
        lock_sha = "a" * 64
        targets = [
            gate.expected_target(self.contract, skill_id)
            for skill_id in self.contract["target_sha"]
        ]
        report = {
            "schema_version": 3,
            "generated_at": "2099-01-01T00:00:00Z",
            "producer": {
                "id": "gloamere-skill-eval",
                "plugin_id": "gloamere-eval",
                "plugin_version": self.contract["eval_plugin"]["version"],
            },
            "command": "native",
            "event_adapter": {
                "id": "codex-exec-jsonl",
                "schema_version": 1,
            },
            "execution_provenance": provenance,
            "release_evidence_eligible": provenance == "codex_cli",
            "preflight": {
                "evidence_status": "verified",
                "reasons": [],
            },
            "suite": {
                "suite_id": self.contract["suite"]["suite_id"],
                "plugin_id": self.contract["suite"]["plugin_id"],
                "execution_policy": self.contract["suite"]["execution_policy"],
                "sha256": self.contract["suite_hash"],
            },
            "target_lock": {
                "sha256": lock_sha,
                "targets": targets,
            },
            "environment": {
                "codex_version": "synthetic-non-release",
                "model": "synthetic-non-release",
                "python_version": "3.12.0",
                "platform": "synthetic-non-release",
            },
            "privacy": {
                "prompts_included": False,
                "absolute_paths_included": False,
            },
            "repeat": 3,
            "independent_batches": 2,
            "timeout_seconds": 1,
            "summary": {},
            "cases": [],
        }
        entry = {
            "path": "synthetic-non-release.json",
            "sha256": "b" * 64,
            "target_lock_sha256": lock_sha,
        }
        return report, entry

    def populate_complete_synthetic_report(self, report: dict) -> None:
        """Build a contract-shaped fixture that remains ineligible evidence."""
        target_ids = {
            skill_id: f"gloamere-workflows:{skill_id}"
            for skill_id in self.contract["target_sha"]
        }
        report_cases = []
        for case in self.contract["suite_cases"].values():
            expected_skills = sorted(case["expected_skills"])
            forbidden_skills = sorted(case["forbidden_skills"])
            expected_target_ids = sorted(
                target_ids[skill_id] for skill_id in expected_skills
            )
            forbidden_target_ids = sorted(
                target_ids[skill_id] for skill_id in forbidden_skills
            )
            attempts = []
            for batch_id in range(1, 3):
                for attempt_id in range(1, 4):
                    attempts.append(
                        {
                            "batch_id": batch_id,
                            "attempt": attempt_id,
                            "prompt_sha256": gate.sha256_text(case["prompt"]),
                            "expected_skills": expected_skills,
                            "forbidden_skills": forbidden_skills,
                            "expected_target_ids": expected_target_ids,
                            "forbidden_target_ids": forbidden_target_ids,
                            "declared_skills": expected_skills,
                            "declared_target_ids": expected_target_ids,
                            "unbound_declared_skills": [],
                            "observed_skills": expected_skills,
                            "observed_target_ids": expected_target_ids,
                            "unbound_skill_names": [],
                            "evidence_status": "verified",
                            "verdict": "pass",
                            "reason": SYNTHETIC_NON_RELEASE_MARKER,
                            "duration_ms": 1,
                            "event_diagnostics": {
                                "complete": True,
                                "event_count": 3,
                                "malformed_lines": 0,
                                "unknown_event_types": [],
                                "unknown_item_types": [],
                                "rejected_target_references": [],
                                "terminal_event": "turn.completed",
                            },
                            "usage": None,
                        }
                    )
            report_cases.append(
                {
                    "id": case["id"],
                    "plugin_id": case["plugin_id"],
                    "language": case["language"],
                    "tags": sorted(case["tags"]),
                    "prompt_sha256": gate.sha256_text(case["prompt"]),
                    "expected_skills": expected_skills,
                    "forbidden_skills": forbidden_skills,
                    **gate.expected_case_metrics(attempts, 3, 2),
                    "attempts": attempts,
                }
            )
        report["cases"] = report_cases
        report["summary"] = gate.expected_report_summary(
            report_cases,
            {
                case["id"]: {
                    field: case[field]
                    for field in (
                        "attempt_count",
                        "expected_attempts",
                        "scored_attempts",
                        "unscored_attempts",
                        "passed_attempts",
                        "failed_attempts",
                        "evidence_coverage",
                        "conditional_accuracy",
                        "stable",
                        "evidence_statuses",
                        "verdicts",
                    )
                }
                for case in report_cases
            },
        )

    def test_complete_synthetic_shape_is_still_non_release(self) -> None:
        report, entry = self.synthetic_report("fixture_adapter")
        self.populate_complete_synthetic_report(report)
        records, errors = gate.validate_report(
            report,
            entry,
            self.contract,
            "synthetic-non-release",
        )
        self.assertEqual(
            errors,
            [
                "synthetic-non-release: fixture_adapter is not release evidence",
                "synthetic-non-release: report is not release-evidence eligible",
            ],
        )
        self.assertEqual(len(records), 136 * 3 * 2)
        metrics = gate.recompute_metrics(records)
        self.assertEqual(metrics["evidence_coverage"], 1.0)
        self.assertEqual(metrics["verified_exact_match"], 1.0)
        self.assertEqual(metrics["ordinary_over_route"], 0.0)
        self.assertEqual(metrics["high_risk_over_route"], 0.0)
        self.assertEqual(metrics["multi_intent_complete"], 1.0)

    def test_fixture_adapter_is_always_rejected(self) -> None:
        report, entry = self.synthetic_report("fixture_adapter")
        _, errors = gate.validate_report(
            report,
            entry,
            self.contract,
            "synthetic-non-release",
        )
        self.assertTrue(
            any("fixture_adapter is not release evidence" in error for error in errors)
        )

    def test_prompt_plaintext_is_rejected(self) -> None:
        report, entry = self.synthetic_report("codex_cli")
        report["prompt"] = SYNTHETIC_NON_RELEASE_MARKER
        report["privacy"]["prompts_included"] = True
        _, errors = gate.validate_report(
            report,
            entry,
            self.contract,
            "synthetic-non-release",
        )
        self.assertTrue(any("prompt plaintext is forbidden" in error for error in errors))
        self.assertTrue(any("privacy contract" in error for error in errors))

    def test_disabled_or_wrong_sha_target_is_rejected(self) -> None:
        report, entry = self.synthetic_report("codex_cli")
        report["target_lock"]["targets"][0]["enabled"] = False
        report["target_lock"]["targets"][1]["sha256"] = "c" * 64
        _, errors = gate.validate_report(
            report,
            entry,
            self.contract,
            "synthetic-non-release",
        )
        self.assertTrue(any("enabled" in error for error in errors))
        self.assertTrue(any("sha256" in error for error in errors))

    def test_suite_and_lock_sha_are_bound(self) -> None:
        report, entry = self.synthetic_report("codex_cli")
        report["suite"]["sha256"] = "c" * 64
        entry["target_lock_sha256"] = "d" * 64
        _, errors = gate.validate_report(
            report,
            entry,
            self.contract,
            "synthetic-non-release",
        )
        self.assertTrue(any("suite identity or SHA" in error for error in errors))
        self.assertTrue(any("target lock SHA" in error for error in errors))

    def test_attempt_verdict_is_recomputed(self) -> None:
        case = next(iter(self.contract["suite_cases"].values()))
        target_ids = {
            skill_id: f"gloamere-workflows:{skill_id}"
            for skill_id in self.contract["target_sha"]
        }
        observed = sorted(
            set(case["expected_skills"]) | {case["forbidden_skills"][0]}
        )
        observed_ids = sorted(target_ids[skill] for skill in observed)
        attempt = {
            "batch_id": 1,
            "attempt": 1,
            "prompt_sha256": gate.sha256_text(case["prompt"]),
            "expected_skills": sorted(case["expected_skills"]),
            "forbidden_skills": sorted(case["forbidden_skills"]),
            "expected_target_ids": sorted(
                target_ids[skill] for skill in case["expected_skills"]
            ),
            "forbidden_target_ids": sorted(
                target_ids[skill] for skill in case["forbidden_skills"]
            ),
            "declared_skills": observed,
            "declared_target_ids": observed_ids,
            "unbound_declared_skills": [],
            "observed_skills": observed,
            "observed_target_ids": observed_ids,
            "unbound_skill_names": [],
            "evidence_status": "verified",
            "verdict": "pass",
            "reason": SYNTHETIC_NON_RELEASE_MARKER,
            "duration_ms": 1,
            "event_diagnostics": {
                "complete": True,
                "event_count": 3,
                "malformed_lines": 0,
                "unknown_event_types": [],
                "unknown_item_types": [],
                "rejected_target_references": [],
                "terminal_event": "turn.completed",
            },
            "usage": None,
        }
        _, errors = gate.validate_attempt(
            attempt,
            case,
            {(1, 1)},
            target_ids,
            "synthetic-non-release",
        )
        self.assertTrue(any("verdict does not match" in error for error in errors))

    def test_verified_attempt_requires_realistic_terminal_diagnostics(self) -> None:
        report, entry = self.synthetic_report("codex_cli")
        self.populate_complete_synthetic_report(report)
        attempt = report["cases"][0]["attempts"][0]
        attempt["event_diagnostics"]["event_count"] = 0
        attempt["event_diagnostics"]["terminal_event"] = "turn.failed"
        _, errors = gate.validate_report(
            report,
            entry,
            self.contract,
            "synthetic-non-release",
        )
        self.assertTrue(
            any("verified stream has too few events" in error for error in errors)
        )
        self.assertTrue(
            any(
                "verified stream did not end with turn.completed" in error
                for error in errors
            )
        )

    def test_tag_workflow_requires_evidence_and_brand_site_checks(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("validate_release_evidence.py --require", workflow)
        self.assertIn("actions/setup-node@v7", workflow)
        self.assertIn("node-version: '22.13.0'", workflow)
        self.assertIn("npm ci", workflow)
        self.assertIn("npm test", workflow)
        self.assertIn("npm run lint", workflow)
        self.assertIn("npm audit --audit-level=high", workflow)
        self.assertIn('if [ "$GITHUB_REF_NAME" != "$manifest_tag" ]', workflow)
        self.assertIn('["distribution"]["tag"]', workflow)
        self.assertLess(
            workflow.index("Match Git tag to release manifest"),
            workflow.index("Build deterministic plugin archives"),
        )


if __name__ == "__main__":
    unittest.main()
