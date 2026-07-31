from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import validate_release_evidence as gate


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "release-manifest.json"


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


class ReleaseEvidenceGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract, cls.contract_errors = gate.load_contract(ROOT, MANIFEST)
        if cls.contract is None:
            raise AssertionError(cls.contract_errors)

    def test_release_contract_is_current_and_risk_tiered(self) -> None:
        self.assertEqual(self.contract_errors, [])
        admission = self.contract["admission"]
        self.assertEqual(admission["policy_id"], "risk-tiered-v2")
        self.assertEqual(admission["report_schema_version"], 4)
        for mode, amount in gate.REQUIRED_BUDGETS.items():
            self.assertEqual(admission["budgets"][mode], amount)
        self.assertGreaterEqual(admission["budgets"]["exhaustive"], 102)
        self.assertEqual(admission["budgets"]["exhaustive_initial"], 102)
        self.assertEqual(admission["thresholds"], gate.REQUIRED_THRESHOLDS)
        self.assertEqual(set(self.contract["skills"]), gate.PUBLIC_SKILLS)
        self.assertEqual(len(self.contract["suite_cases"]), 102)

        policy = self.contract["policy"]
        selected, _, _ = gate.runner_module().risk_selected_cases(
            self.contract["suite"],
            "release",
            None,
            "2026-07",
            policy,
            self.contract["skills"],
        )
        self.assertEqual(len(selected), 28)
        risk_counts = {"ordinary": 0, "high": 0}
        for case in self.contract["suite_cases"].values():
            if gate.one_tag(case["tags"], "kind:") != "adjacent-negative":
                continue
            risk_counts[gate.one_tag(case["tags"], "risk:")] += 1
        self.assertEqual(risk_counts, {"ordinary": 40, "high": 8})

    def test_missing_reports_are_pending_unless_required(self) -> None:
        result, code = gate.assess(ROOT, MANIFEST, require=False)
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "pending")
        self.assertIn("report v4", result["evidence_errors"][0])

        required_result, required_code = gate.assess(
            ROOT,
            MANIFEST,
            require=True,
        )
        self.assertEqual(required_code, 1)
        self.assertEqual(required_result["status"], "pending")
        exhaustive_result, exhaustive_code = gate.assess(
            ROOT,
            MANIFEST,
            require_exhaustive=True,
        )
        self.assertEqual(exhaustive_code, 1)
        self.assertEqual(exhaustive_result["exhaustive_status"], "pending")
        self.assertIn(
            "exhaustive native report v4",
            exhaustive_result["exhaustive_evidence_errors"][0],
        )

    def test_cli_require_exhaustive_fails_closed_when_empty(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "validate_release_evidence.py"),
                "--require-exhaustive",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(completed.returncode, 1)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["require_exhaustive"])
        self.assertEqual(payload["exhaustive_status"], "pending")

    def test_thresholds_are_inclusive_at_release_boundary(self) -> None:
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
        failures = gate.threshold_failures(
            metrics,
            gate.REQUIRED_THRESHOLDS,
        )
        self.assertIn("high_risk_over_route", failures[0])

    def test_metrics_are_recomputed_from_attempt_records(self) -> None:
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

    def _target_lock(self) -> dict:
        targets = [
            gate.expected_target(self.contract, skill)
            for skill in self.contract["skills"]
        ]
        self.assertNotIn(None, targets)
        return {
            "schema_version": 2,
            "targets": targets,
        }

    def _passing_attempt(self, case: dict) -> dict:
        expected = sorted(case["expected_skills"])
        forbidden = sorted(case["forbidden_skills"])
        expected_ids = sorted(
            f"gloamere-workflows:{skill}" for skill in expected
        )
        forbidden_ids = sorted(
            f"gloamere-workflows:{skill}" for skill in forbidden
        )
        return {
            "batch_id": 1,
            "attempt": 1,
            "prompt_sha256": gate.sha256_text(case["prompt"]),
            "expected_skills": expected,
            "forbidden_skills": forbidden,
            "expected_target_ids": expected_ids,
            "forbidden_target_ids": forbidden_ids,
            "declared_skills": expected,
            "declared_target_ids": expected_ids,
            "unbound_declared_skills": [],
            "observed_skills": expected,
            "observed_target_ids": expected_ids,
            "unbound_skill_names": [],
            "evidence_status": "verified",
            "verdict": "pass",
            "reason": "Observed from the complete native Codex event stream.",
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

    def _failing_attempt(self, case: dict, attempt_number: int) -> dict:
        attempt = self._passing_attempt(case)
        observed = sorted(
            set(case["expected_skills"]) | {case["forbidden_skills"][0]}
        )
        observed_ids = sorted(
            f"gloamere-workflows:{skill}" for skill in observed
        )
        attempt["attempt"] = attempt_number
        attempt["declared_skills"] = observed
        attempt["declared_target_ids"] = observed_ids
        attempt["observed_skills"] = observed
        attempt["observed_target_ids"] = observed_ids
        attempt["verdict"] = "fail"
        attempt["reason"] = "Observed the same unexpected bound Skill."
        return attempt

    def synthetic_report(
        self,
        failure_count: int = 0,
        changed_skills: list[str] | None = None,
    ) -> tuple[dict, dict]:
        runner = gate.runner_module()
        rotation_key = "2026-07"
        active_skills = changed_skills or self.contract["skills"]
        selected, roles, reason = runner.risk_selected_cases(
            self.contract["suite"],
            "release",
            None,
            rotation_key,
            self.contract["policy"],
            active_skills,
        )
        quality_reserved_calls = 2 * len(active_skills)
        reason += (
            f"; reserving {quality_reserved_calls} of 40 calls "
            "for output-quality evaluation"
        )
        retry_policy = runner.retry_policy_settings(self.contract["policy"])
        report_cases = []
        for case_index, case in enumerate(selected):
            if case_index == 0 and failure_count:
                attempts = [
                    self._failing_attempt(case, number)
                    if number <= failure_count
                    else {
                        **self._passing_attempt(case),
                        "attempt": number,
                    }
                    for number in range(1, 4)
                ]
                expected_attempts = 3
            else:
                attempts = [self._passing_attempt(case)]
                expected_attempts = 1
            adaptive = runner.adaptive_case_evaluation(
                attempts,
                expected_attempts,
                retry_policy,
                False,
                True,
            )
            report_cases.append(
                runner.aggregate_case(
                    case,
                    attempts,
                    repeat=1,
                    independent_batches=1,
                    adaptive_evaluation=adaptive,
                )
            )
        commit = gate._repository_commit(ROOT)
        self.assertIsNotNone(commit)
        report = runner.build_report(
            self.contract["suite"],
            self._target_lock(),
            report_cases,
            repeat=1,
            timeout=45,
            model="gpt-release-test",
            codex_version_value="codex-cli-test",
            include_prompts=False,
            execution_provenance="codex_cli",
            mode="release",
            selection_reason=reason,
            selection_roles=roles,
            rotation_key=rotation_key,
            max_calls=40,
            routing_max_calls=40 - quality_reserved_calls,
            quality_reserved_calls=quality_reserved_calls,
            actual_calls=sum(
                len(case["attempts"]) for case in report_cases
            ),
            resumed_calls=0,
            new_calls=sum(
                len(case["attempts"]) for case in report_cases
            ),
            complete=True,
            independent_batches=1,
            policy=self.contract["policy"],
            policy_sha256=self.contract["policy_hash"],
            policy_source=self.contract["policy_path"].name,
            changed_skills=active_skills,
            commit=commit,
            suite_sha256=self.contract["suite_hash"],
        )
        self.assertEqual(runner.validate_report_v4(report), [])
        entry = {
            "path": "synthetic-report-v4.json",
            "sha256": "a" * 64,
            "target_lock_sha256": report["target_lock"]["sha256"],
            "model": report["provenance"]["model"],
            "codex_cli": report["provenance"]["codex_cli"],
        }
        return report, entry

    def synthetic_exhaustive_report(
        self,
        failure_count: int = 0,
        retry_passing_case: bool = False,
    ) -> tuple[dict, dict]:
        runner = gate.runner_module()
        rotation_key = "2026-07"
        selected, roles, reason = runner.risk_selected_cases(
            self.contract["suite"],
            "exhaustive",
            None,
            rotation_key,
            self.contract["policy"],
            [],
        )
        exhaustive_budget = self.contract["admission"]["budgets"][
            "exhaustive"
        ]
        reason += (
            f"; complete all 102 initial calls before adaptive retries "
            f"(capacity {exhaustive_budget - 102})"
        )
        retry_policy = runner.retry_policy_settings(self.contract["policy"])
        report_cases = []
        for case_index, case in enumerate(selected):
            if case_index == 0 and failure_count:
                attempts = [
                    self._failing_attempt(case, number)
                    if number <= failure_count
                    else {
                        **self._passing_attempt(case),
                        "attempt": number,
                    }
                    for number in range(1, 4)
                ]
                expected_attempts = 3
            elif case_index == 0 and retry_passing_case:
                attempts = [
                    self._passing_attempt(case),
                    {
                        **self._passing_attempt(case),
                        "attempt": 2,
                    },
                ]
                expected_attempts = 2
            else:
                attempts = [self._passing_attempt(case)]
                expected_attempts = 1
            adaptive = runner.adaptive_case_evaluation(
                attempts,
                expected_attempts,
                retry_policy,
                False,
                True,
            )
            report_cases.append(
                runner.aggregate_case(
                    case,
                    attempts,
                    repeat=1,
                    independent_batches=1,
                    adaptive_evaluation=adaptive,
                )
            )
        actual_calls = sum(
            len(case["attempts"]) for case in report_cases
        )
        commit = gate._repository_commit(ROOT)
        self.assertIsNotNone(commit)
        report = runner.build_report(
            self.contract["suite"],
            self._target_lock(),
            report_cases,
            repeat=1,
            timeout=45,
            model="gpt-exhaustive-test",
            codex_version_value="codex-cli-test",
            include_prompts=False,
            execution_provenance="codex_cli",
            mode="exhaustive",
            selection_reason=reason,
            selection_roles=roles,
            rotation_key=rotation_key,
            max_calls=exhaustive_budget,
            routing_max_calls=exhaustive_budget,
            quality_reserved_calls=0,
            actual_calls=actual_calls,
            resumed_calls=0,
            new_calls=actual_calls,
            complete=True,
            independent_batches=1,
            policy=self.contract["policy"],
            policy_sha256=self.contract["policy_hash"],
            policy_source=self.contract["policy_path"].name,
            changed_skills=[],
            commit=commit,
            suite_sha256=self.contract["suite_hash"],
            execution_strategy="initial-coverage-then-adaptive-retry",
            initial_phase_complete=True,
            initial_actual_calls=102,
        )
        self.assertEqual(runner.validate_report_v4(report), [])
        entry = {
            "path": "synthetic-exhaustive-v4.json",
            "sha256": "e" * 64,
            "target_lock_sha256": report["target_lock"]["sha256"],
            "model": report["provenance"]["model"],
            "codex_cli": report["provenance"]["codex_cli"],
        }
        return report, entry

    def _assess_report(
        self,
        report: dict,
        entry: dict,
        require: bool,
    ) -> tuple[dict, int]:
        return self._assess_reports(
            release_reports=[(report, entry)],
            require=require,
        )

    def _assess_reports(
        self,
        release_reports: list[tuple[dict, dict]] | None = None,
        exhaustive_reports: list[tuple[dict, dict]] | None = None,
        require: bool = False,
        require_exhaustive: bool = False,
    ) -> tuple[dict, int]:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_value:
            temp = Path(temp_value)
            manifest = deepcopy(self.contract["manifest"])
            workflows = gate.plugin_by_id(manifest, "gloamere-workflows")
            self.assertIsNotNone(workflows)
            for field, values in (
                ("reports", release_reports or []),
                ("exhaustive_reports", exhaustive_reports or []),
            ):
                bound_entries = []
                for index, (report, entry) in enumerate(values):
                    report_path = temp / f"{field}-{index}.json"
                    write_json(report_path, report)
                    bound_entry = deepcopy(entry)
                    bound_entry["path"] = report_path.relative_to(
                        ROOT
                    ).as_posix()
                    bound_entry["sha256"] = gate.sha256_file(report_path)
                    bound_entries.append(bound_entry)
                workflows["admission"][field] = bound_entries
            manifest_path = temp / "release-manifest.json"
            write_json(manifest_path, manifest)
            return gate.assess(
                ROOT,
                manifest_path,
                require=require,
                require_exhaustive=require_exhaustive,
            )

    def test_complete_synthetic_v4_shape_passes_gate_validation(self) -> None:
        report, entry = self.synthetic_report()
        records, errors = gate.validate_report(
            report,
            entry,
            self.contract,
            "synthetic-report-v4.json",
        )
        self.assertEqual(errors, [])
        self.assertEqual(len(records), 28)
        metrics = gate.recompute_metrics(records)
        self.assertEqual(metrics["evidence_coverage"], 1.0)
        self.assertEqual(metrics["verified_exact_match"], 1.0)
        self.assertEqual(metrics["ordinary_over_route"], 0.0)
        self.assertEqual(metrics["high_risk_over_route"], 0.0)
        self.assertEqual(metrics["multi_intent_complete"], 1.0)

    def test_adaptive_consensus_keeps_one_of_three_pending(self) -> None:
        report, entry = self.synthetic_report(failure_count=1)
        self.assertEqual(
            report["evaluation"]["case_outcomes"][
                report["evaluation"]["selected_case_ids"][0]
            ],
            "pending",
        )
        records, errors = gate.validate_report(
            report,
            entry,
            self.contract,
            "one-of-three.json",
        )
        self.assertEqual(errors, [])
        metrics = gate.recompute_metrics(records)
        self.assertEqual(metrics["pending_cases"], 1)
        self.assertEqual(metrics["confirmed_failures"], 0)
        failures = gate.threshold_failures(
            metrics,
            gate.REQUIRED_THRESHOLDS,
        )
        self.assertTrue(
            any("evidence_coverage" in failure for failure in failures)
        )
        self.assertFalse(
            any("confirmed_failures" in failure for failure in failures)
        )
        result, code = self._assess_report(report, entry, require=False)
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "pending")

    def test_adaptive_consensus_blocks_same_failure_two_of_three(self) -> None:
        report, entry = self.synthetic_report(failure_count=2)
        self.assertEqual(
            report["evaluation"]["case_outcomes"][
                report["evaluation"]["selected_case_ids"][0]
            ],
            "fail",
        )
        records, errors = gate.validate_report(
            report,
            entry,
            self.contract,
            "two-of-three.json",
        )
        self.assertEqual(errors, [])
        metrics = gate.recompute_metrics(records)
        self.assertEqual(metrics["pending_cases"], 0)
        self.assertEqual(metrics["confirmed_failures"], 1)
        failures = gate.threshold_failures(
            metrics,
            gate.REQUIRED_THRESHOLDS,
        )
        self.assertTrue(
            any("confirmed_failures" in failure for failure in failures)
        )
        result, code = self._assess_report(report, entry, require=False)
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "fail")

    def test_exhaustive_report_covers_all_102_cases_once(self) -> None:
        report, entry = self.synthetic_exhaustive_report()
        records, errors = gate.validate_report(
            report,
            entry,
            self.contract,
            "exhaustive-v4.json",
            evidence_mode="exhaustive",
        )
        self.assertEqual(errors, [])
        self.assertEqual(len(records), 102)
        self.assertEqual(len({record["case_id"] for record in records}), 102)
        result, code = self._assess_reports(
            exhaustive_reports=[(report, entry)],
            require_exhaustive=True,
        )
        self.assertEqual(code, 0, result)
        self.assertEqual(result["exhaustive_status"], "pass")
        self.assertEqual(result["exhaustive_metrics"]["attempt_count"], 102)

    def test_exhaustive_one_of_three_is_pending(self) -> None:
        report, entry = self.synthetic_exhaustive_report(failure_count=1)
        result, code = self._assess_reports(
            exhaustive_reports=[(report, entry)],
            require_exhaustive=False,
        )
        self.assertEqual(code, 0, result)
        self.assertEqual(result["exhaustive_status"], "pending")
        self.assertEqual(
            result["exhaustive_metrics"]["confirmed_failures"],
            0,
        )
        required_result, required_code = self._assess_reports(
            exhaustive_reports=[(report, entry)],
            require_exhaustive=True,
        )
        self.assertEqual(required_code, 1)
        self.assertEqual(required_result["exhaustive_status"], "pending")

    def test_exhaustive_same_failure_two_of_three_blocks(self) -> None:
        report, entry = self.synthetic_exhaustive_report(failure_count=2)
        result, code = self._assess_reports(
            exhaustive_reports=[(report, entry)],
            require_exhaustive=False,
        )
        self.assertEqual(code, 1)
        self.assertEqual(result["exhaustive_status"], "fail")
        self.assertEqual(
            result["exhaustive_metrics"]["confirmed_failures"],
            1,
        )

    def test_exhaustive_never_retries_a_passing_first_round_case(self) -> None:
        report, entry = self.synthetic_exhaustive_report(
            retry_passing_case=True,
        )
        _, errors = gate.validate_report(
            report,
            entry,
            self.contract,
            "unnecessary-retry.json",
            evidence_mode="exhaustive",
        )
        self.assertIn(
            "retried a passing first-round case",
            "\n".join(errors),
        )

    def test_exhaustive_coverage_and_hard_cap_fail_closed(self) -> None:
        report, entry = self.synthetic_exhaustive_report()
        report["evaluation"]["selected_case_ids"].pop()
        coverage_errors = gate._exhaustive_coverage_errors(
            [report],
            self.contract,
        )
        self.assertIn("all 102 suite cases exactly once", coverage_errors[0])

        hard_cap = self.contract["admission"]["budgets"]["exhaustive"]
        report["evaluation"]["actual_calls"] = hard_cap + 1
        report["evaluation"]["retry_actual_calls"] = hard_cap + 1 - 102
        report["evaluation"]["new_calls"] = hard_cap + 1
        report["evaluation"]["projected_total_calls"] = hard_cap + 1
        _, errors = gate.validate_report(
            report,
            entry,
            self.contract,
            "over-cap-exhaustive.json",
            evidence_mode="exhaustive",
        )
        self.assertIn(
            f"exhaustive budget {hard_cap}",
            "\n".join(errors),
        )

    def test_report_v3_is_explicitly_historical_only(self) -> None:
        report, entry = self.synthetic_report()
        report["schema_version"] = 3
        report.pop("evaluation")
        report.pop("provenance")
        records, errors = gate.validate_report(
            report,
            entry,
            self.contract,
            "historical-v3.json",
        )
        self.assertEqual(records, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("read-only historical", errors[0])
        self.assertIn("not eligible for release", errors[0])

    def test_prompt_plaintext_and_absolute_paths_are_rejected(self) -> None:
        report, entry = self.synthetic_report()
        attempt = report["cases"][0]["attempts"][0]
        attempt["prompt"] = "read C:\\Users\\secret\\prompt.txt"
        report["privacy"]["prompts_included"] = True
        _, errors = gate.validate_report(
            report,
            entry,
            self.contract,
            "leaking-report.json",
        )
        joined = "\n".join(errors)
        self.assertIn("prompt plaintext is forbidden", joined)
        self.assertIn("absolute path plaintext is forbidden", joined)
        self.assertIn("privacy contract must omit prompts", joined)

    def test_target_and_provenance_hashes_are_bound_to_current_files(self) -> None:
        report, entry = self.synthetic_report()
        report["target_lock"]["targets"][0]["sha256"] = "b" * 64
        report["provenance"]["target_sha256"][
            report["target_lock"]["targets"][0]["target_id"]
        ] = "b" * 64
        report["provenance"]["policy_sha256"] = "c" * 64
        _, errors = gate.validate_report(
            report,
            entry,
            self.contract,
            "stale-report.json",
        )
        joined = "\n".join(errors)
        self.assertIn("target sha256 does not match", joined)
        self.assertIn("target Skill SHAs are stale", joined)
        self.assertIn("policy SHA does not match current policy", joined)

    def test_selection_and_quality_budget_are_recomputed(self) -> None:
        report, entry = self.synthetic_report()
        report["evaluation"]["changed_skills"] = self.contract["skills"][:-1]
        report["evaluation"]["actual_calls"] = 37
        report["evaluation"]["new_calls"] = 37
        _, errors = gate.validate_report(
            report,
            entry,
            self.contract,
            "over-budget-report.json",
        )
        joined = "\n".join(errors)
        self.assertIn("reserved for quality evidence", joined)
        self.assertIn("selected case set does not match risk-tiered-v2", joined)

    def test_model_cli_time_and_commit_provenance_fail_closed(self) -> None:
        report, entry = self.synthetic_report()
        entry.pop("model")
        entry["codex_cli"] = "different-cli"
        report["generated_at"] = "2026-07-31T12:00:00"
        report["provenance"]["generated_at"] = report["generated_at"]
        report["provenance"]["commit"] = "f" * 40
        _, errors = gate.validate_report(
            report,
            entry,
            self.contract,
            "stale-provenance.json",
        )
        joined = "\n".join(errors)
        self.assertIn("entry model must be non-empty", joined)
        self.assertIn("entry codex_cli does not match report", joined)
        self.assertIn("ISO UTC", joined)
        self.assertIn("or one of its ancestors", joined)

    def test_assess_accepts_hash_bound_v4_without_model_calls(self) -> None:
        report, entry = self.synthetic_report()
        result, code = self._assess_report(report, entry, require=True)

        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["release_status"], "pass")
        self.assertEqual(result["exhaustive_status"], "pending")
        self.assertEqual(result["evidence_errors"], [])
        self.assertEqual(result["threshold_failures"], [])
        self.assertEqual(result["metrics"]["attempt_count"], 28)

    def test_release_evidence_reuses_disjoint_changed_skill_reports(self) -> None:
        report_pairs = [
            self.synthetic_report(changed_skills=[skill])
            for skill in self.contract["skills"]
        ]
        result, code = self._assess_reports(
            release_reports=report_pairs,
            require=True,
        )
        self.assertEqual(code, 0, result)
        self.assertEqual(result["release_status"], "pass")
        self.assertEqual(result["metrics"]["pending_cases"], 0)
        self.assertEqual(result["metrics"]["confirmed_failures"], 0)
        self.assertEqual(
            result["metrics"]["attempt_count"],
            result["metrics"]["case_count"],
        )

    def test_release_reuse_rejects_a_mixed_model_identity(self) -> None:
        report_pairs = [
            self.synthetic_report(changed_skills=[skill])
            for skill in self.contract["skills"]
        ]
        report, entry = report_pairs[-1]
        report["provenance"]["model"] = "different-model"
        report["environment"]["model"] = "different-model"
        entry["model"] = "different-model"
        result, code = self._assess_reports(
            release_reports=report_pairs,
            require=False,
        )
        self.assertEqual(code, 1)
        self.assertEqual(result["release_status"], "fail")
        self.assertIn(
            "release evidence reuse key must exactly match",
            "\n".join(result["evidence_errors"]),
        )

    def test_release_reuse_rejects_inconsistent_fixed_baseline(self) -> None:
        first_report, first_entry = self.synthetic_report(
            changed_skills=[self.contract["skills"][0]],
        )
        second_report, second_entry = self.synthetic_report(
            changed_skills=[self.contract["skills"][1]],
        )
        first_records, first_errors = gate.validate_report(
            first_report,
            first_entry,
            self.contract,
            "first.json",
        )
        second_records, second_errors = gate.validate_report(
            second_report,
            second_entry,
            self.contract,
            "second.json",
        )
        self.assertEqual(first_errors + second_errors, [])
        common_id = next(
            case_id
            for case_id in {item["case_id"] for item in first_records}
            if case_id in {item["case_id"] for item in second_records}
        )
        conflicting = next(
            item for item in second_records if item["case_id"] == common_id
        )
        conflicting["outcome"] = "pending"
        conflicting["status"] = "pending"
        _, errors = gate._deduplicate_release_records(
            [*first_records, *second_records],
        )
        self.assertIn(
            f"reused release baseline disagrees for case {common_id}",
            errors,
        )

    def test_configured_report_sha_mismatch_always_fails(self) -> None:
        report, entry = self.synthetic_report()
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_value:
            temp = Path(temp_value)
            report_path = temp / "report-v4.json"
            write_json(report_path, report)
            entry["path"] = report_path.relative_to(ROOT).as_posix()
            entry["sha256"] = "d" * 64
            manifest = deepcopy(self.contract["manifest"])
            workflows = gate.plugin_by_id(manifest, "gloamere-workflows")
            self.assertIsNotNone(workflows)
            workflows["admission"]["reports"] = [entry]
            manifest_path = temp / "release-manifest.json"
            write_json(manifest_path, manifest)

            result, code = gate.assess(ROOT, manifest_path, require=False)

        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "fail")
        self.assertIn("report file SHA mismatch", result["evidence_errors"][0])

    def test_tag_workflow_requires_release_evidence(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "validate_release_evidence.py --require --require-exhaustive",
            workflow,
        )
        self.assertLess(
            workflow.index("Match Git tag to release manifest"),
            workflow.index("Build deterministic plugin archives"),
        )


if __name__ == "__main__":
    unittest.main()
