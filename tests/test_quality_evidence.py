import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "validate_quality_evidence.py"
RELEASE_PATH = ROOT / "release-manifest.json"

SPEC = importlib.util.spec_from_file_location("validate_quality_evidence", SCRIPT_PATH)
gate = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(gate)


class QualityEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract, cls.contract_errors = gate.load_contract(ROOT, RELEASE_PATH)

    def setUp(self):
        self.assertEqual(self.contract_errors, [])
        self.assertIsNotNone(self.contract)

    def valid_report(
        self,
        skill_ids=None,
        report_id="quality-current-v1",
        model="gpt-5.6",
        cli_compatibility="codex-quality-v1",
    ):
        if skill_ids is None:
            skill_ids = set(self.contract["skills"])
        else:
            skill_ids = set(skill_ids)
        cases = []
        for case_id, suite_case in self.contract["cases"].items():
            if suite_case["skill_id"] not in skill_ids:
                continue
            rubrics = {
                name: {
                    "baseline": "pass",
                    "current": "pass",
                    "regression": "none",
                    "rationale_sha256": gate.sha256_text(
                        f"independent semantic rationale: {case_id}/{name}"
                    ),
                }
                for name in gate.REQUIRED_RUBRICS
            }
            cases.append(
                {
                    "id": case_id,
                    "skill_id": suite_case["skill_id"],
                    "language": suite_case["language"],
                    "prompt_sha256": gate.sha256_text(suite_case["prompt"]),
                    "target_sha256": self.contract["skills"][
                        suite_case["skill_id"]
                    ],
                    "model_calls": 1,
                    "baseline": {
                        "report_id": "quality-baseline-v1",
                        "output_sha256": gate.sha256_text(f"baseline:{case_id}"),
                    },
                    "current": {
                        "output_sha256": gate.sha256_text(f"current:{case_id}"),
                    },
                    "rubrics": rubrics,
                    "critical_regression": False,
                }
            )
        return {
            "schema_version": 4,
            "report_id": report_id,
            "generated_at": "2026-07-31T12:00:00+08:00",
            "execution": {
                "commit_sha": "a" * 40,
                "model": "gpt-5.6",
                "cli": {
                    "name": "codex",
                    "version": "0.99.0",
                    "compatibility": cli_compatibility,
                },
            },
            "quality_suite": {
                "id": self.contract["suite"]["suite_id"],
                "path": self.contract["suite_path"],
                "sha256": self.contract["suite_sha"],
            },
            "policy": {
                "id": self.contract["policy_id"],
                "path": self.contract["policy_path"],
                "sha256": self.contract["policy_sha"],
            },
            "skills": {
                skill_id: self.contract["skills"][skill_id]
                for skill_id in sorted(skill_ids)
            },
            "review": {
                "mode": "human_semantic_review",
                "reviewer_id": "reviewer-01",
                "scoring_basis": "semantic_judgment",
                "automated_scoring": False,
            },
            "cases": cases,
            "summary": {
                "cases_total": len(cases),
                "cases_passed": len(cases),
                "quality_model_calls": len(cases),
                "critical_regressions": 0,
                "verdict": "pass",
            },
        }

    def test_manifest_contract_is_current_and_no_report_is_pending(self):
        self.assertEqual(self.contract["report_paths"], [])
        errors, pending = gate.validate(ROOT, RELEASE_PATH)
        self.assertEqual(errors, [])
        self.assertEqual(pending, ["no output-quality report is registered"])

    def test_valid_human_semantic_report_passes(self):
        self.assertEqual(gate.validate_report(self.valid_report(), self.contract), [])

    def test_v4_report_may_cover_one_complete_skill_subset(self):
        skill_id = "gloamere-visual-review"
        report = self.valid_report({skill_id})
        self.assertEqual(set(report["skills"]), {skill_id})
        self.assertEqual(
            {(case["skill_id"], case["language"]) for case in report["cases"]},
            {(skill_id, "zh-CN"), (skill_id, "en")},
        )
        self.assertEqual(report["summary"]["quality_model_calls"], 2)
        self.assertEqual(gate.validate_report(report, self.contract), [])

    def test_unmodified_skill_report_ignores_unrelated_skill_sha_change(self):
        unchanged_skill = "gloamere-visual-review"
        changed_skill = "gloamere-product-decision"
        reusable_report = self.valid_report({unchanged_skill})
        changed_contract = {
            **self.contract,
            "skills": {
                **self.contract["skills"],
                changed_skill: "b" * 64,
            },
        }
        self.assertEqual(
            gate.validate_report(reusable_report, changed_contract),
            [],
        )

    def test_multiple_reports_reuse_matching_skill_evidence(self):
        reports = []
        for index, skill_id in enumerate(sorted(self.contract["skills"]), start=1):
            report = self.valid_report(
                {skill_id},
                report_id=f"quality-skill-{index}",
            )
            # 未变更 Skill 的祖先提交证据可以和新报告组合；共享身份不依赖提交时间。
            report["execution"]["commit_sha"] = str(index) * 40
            report["execution"]["cli"]["version"] = f"0.99.{index}"
            reports.append((f"report-{index}.json", report))
        self.assertEqual(gate.validate_reports(reports, self.contract), [])

    def test_manifest_validator_accepts_multiple_v4_report_paths(self):
        paths = ["evidence/one.json", "evidence/two.json", "evidence/three.json"]
        contract = {**self.contract, "report_paths": paths}
        reports_by_path = {}
        for index, (path, skill_id) in enumerate(
            zip(paths, sorted(self.contract["skills"])), start=1
        ):
            reports_by_path[(ROOT / path).resolve()] = self.valid_report(
                {skill_id}, report_id=f"quality-path-{index}"
            )

        with (
            mock.patch.object(
                gate, "load_contract", return_value=(contract, [])
            ),
            mock.patch.object(
                gate,
                "read_json",
                side_effect=lambda path: reports_by_path[path.resolve()],
            ),
            mock.patch.object(
                gate, "commit_is_current_or_ancestor", return_value=True
            ),
        ):
            errors, pending = gate.validate(ROOT, RELEASE_PATH)
        self.assertEqual(errors, [])
        self.assertEqual(pending, [])

    def test_composed_reports_fail_on_missing_duplicate_or_mixed_identity(self):
        skills = sorted(self.contract["skills"])
        two_reports = [
            (
                "one.json",
                self.valid_report({skills[0]}, report_id="quality-one"),
            ),
            (
                "two.json",
                self.valid_report({skills[1]}, report_id="quality-two"),
            ),
        ]
        errors = gate.validate_reports(two_reports, self.contract)
        self.assertTrue(any("cover every published Skill" in error for error in errors))

        duplicate = self.valid_report({skills[0]}, report_id="quality-duplicate")
        errors = gate.validate_reports(
            two_reports + [("duplicate.json", duplicate)], self.contract
        )
        self.assertTrue(any("registered more than once" in error for error in errors))

        third = self.valid_report(
            {skills[2]},
            report_id="quality-three",
            cli_compatibility="incompatible-cli-family",
        )
        errors = gate.validate_reports(two_reports + [("three.json", third)], self.contract)
        self.assertTrue(any("share the same model" in error for error in errors))

    def test_report_binds_commit_model_cli_suite_and_each_skill_sha(self):
        mutations = {
            "commit": lambda report: report["execution"].update(
                {"commit_sha": "short"}
            ),
            "model": lambda report: report["execution"].update({"model": ""}),
            "cli": lambda report: report["execution"]["cli"].update(
                {"name": "other"}
            ),
            "suite": lambda report: report["quality_suite"].update(
                {"sha256": "b" * 64}
            ),
            "policy": lambda report: report["policy"].update(
                {"sha256": "b" * 64}
            ),
            "compatibility": lambda report: report["execution"]["cli"].update(
                {"compatibility": ""}
            ),
            "skill-map": lambda report: report["skills"].update(
                {"gloamere-visual-review": "b" * 64}
            ),
            "case-skill": lambda report: report["cases"][0].update(
                {"target_sha256": "b" * 64}
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                report = self.valid_report()
                mutate(report)
                self.assertTrue(gate.validate_report(report, self.contract))

    def test_report_commit_must_be_current_or_an_ancestor_when_repository_bound(self):
        report = self.valid_report()
        errors = gate.validate_report(report, self.contract, root=ROOT)
        self.assertTrue(any("ancestor of HEAD" in error for error in errors))

    def test_each_declared_skill_requires_both_cases_and_all_four_rubrics(self):
        report = self.valid_report({"gloamere-visual-review"})
        report["cases"].pop()
        report["summary"]["cases_total"] = 1
        report["summary"]["cases_passed"] = 1
        report["summary"]["quality_model_calls"] = 1
        errors = gate.validate_report(report, self.contract)
        self.assertTrue(any("zh-CN and en task" in error for error in errors))

        report = self.valid_report()
        report["cases"][0]["rubrics"].pop("no_fabrication")
        errors = gate.validate_report(report, self.contract)
        self.assertTrue(any("all four semantic rubrics" in error for error in errors))

    def test_report_skill_subset_must_be_non_empty(self):
        report = self.valid_report(set())
        errors = gate.validate_report(report, self.contract)
        self.assertTrue(any("non-empty Skill SHA subset" in error for error in errors))

    def test_quality_model_calls_are_recomputed_within_the_six_call_reservation(self):
        report = self.valid_report()
        report["cases"][0]["model_calls"] = 2
        report["summary"]["quality_model_calls"] = 7
        errors = gate.validate_report(report, self.contract)
        self.assertTrue(any("model_calls must be 1" in error for error in errors))
        self.assertTrue(any("summary does not match" in error for error in errors))

    def test_output_plaintext_is_rejected_and_only_hash_slots_are_allowed(self):
        report = self.valid_report()
        report["cases"][0]["current"]["output"] = "plaintext model output"
        errors = gate.validate_report(report, self.contract)
        self.assertTrue(
            any("fields do not match the quality report contract" in error for error in errors)
        )

    def test_keyword_substring_or_automated_scoring_cannot_claim_review(self):
        report = self.valid_report()
        report["review"]["mode"] = "keyword_match"
        report["review"]["scoring_basis"] = "substring_match"
        report["review"]["automated_scoring"] = True
        errors = gate.validate_report(report, self.contract)
        self.assertTrue(any("semantic review" in error for error in errors))
        self.assertTrue(any("substring" in error for error in errors))
        self.assertTrue(any("automated" in error for error in errors))

    def test_failed_rubric_or_critical_regression_fails_closed(self):
        report = self.valid_report()
        result = report["cases"][0]["rubrics"]["evidence_fidelity"]
        result["current"] = "fail"
        result["regression"] = "critical"
        report["cases"][0]["critical_regression"] = True
        errors = gate.validate_report(report, self.contract)
        self.assertTrue(any("current semantic verdict must pass" in error for error in errors))
        self.assertTrue(any("rubric regression is not allowed" in error for error in errors))
        self.assertTrue(any("critical regression is not allowed" in error for error in errors))
        self.assertTrue(any("output quality verdict is not pass" in error for error in errors))

    def test_cli_pending_is_non_blocking_until_require_is_set(self):
        default = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        required = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--require"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(default.returncode, 0, default.stderr)
        self.assertIn("pending:", default.stderr)
        self.assertEqual(required.returncode, 1)
        self.assertIn("pending:", required.stderr)

    def test_check_scripts_run_non_require_quality_validation(self):
        powershell = (ROOT / "scripts" / "check.ps1").read_text(encoding="utf-8")
        shell = (ROOT / "scripts" / "check.sh").read_text(encoding="utf-8")
        self.assertIn("scripts/validate_quality_evidence.py", powershell)
        self.assertIn("scripts/validate_quality_evidence.py", shell)
        self.assertNotIn("validate_quality_evidence.py', '--require", powershell)
        self.assertNotIn("validate_quality_evidence.py --require", shell)


if __name__ == "__main__":
    unittest.main()
