from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "experiments" / "eval-lab" / "run_eval_lab.py"
FIXTURE = ROOT / "tests" / "fixtures" / "fake_eval_lab_host.py"
FAKE_CODEX = ROOT / "tests" / "fixtures" / "fake_eval_lab_codex.py"


class EvalLabIntegrationTests(unittest.TestCase):
    def test_repository_cases_reference_only_current_skill_files(self) -> None:
        cases = json.loads(
            (ROOT / "experiments" / "eval-lab" / "cases.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual({case["skill"] for case in cases}, {"taste", "knowledge-base"})
        for case in cases:
            skill_file = (
                ROOT / "experiments" / "eval-lab" / case["skill_file"]
            ).resolve()
            self.assertTrue(skill_file.is_file(), skill_file)

    def run_lab(
        self,
        cases: list[dict[str, object]],
        repeat: int = 1,
        case_ids: list[str] | None = None,
        expected_returncode: int = 0,
    ) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            cases_path = temp_root / "cases.json"
            output_path = temp_root / "report.json"
            cases_path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
            command = [
                sys.executable,
                str(RUNNER),
                "--cases",
                str(cases_path),
                "--adapter-executable",
                sys.executable,
                "--adapter-arg",
                str(FIXTURE),
                "--repeat",
                str(repeat),
                "--output",
                str(output_path),
            ]
            for case_id in case_ids or []:
                command.extend(["--case", case_id])
            completed = subprocess.run(
                command,
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
                check=False,
            )
            self.assertEqual(completed.returncode, expected_returncode, completed.stderr)
            return json.loads(output_path.read_text(encoding="utf-8"))

    def test_reports_verified_improvement_from_paired_runs(self) -> None:
        cases = [
            {
                "id": "taste-contract",
                "plugin": "taste@tessera",
                "skill": "taste",
                "prompt": "评审这个页面。",
                "minimum_delta": 0.25,
                "criteria": [
                    {"id": "dimensions", "all": ["层级", "留白", "配色", "字体", "一致性", "细节"]},
                    {"id": "priorities", "any": ["Top 3", "top 3"]},
                ],
            }
        ]

        report = self.run_lab(cases)
        self.assertEqual(report["summary"]["improvements"], 1)
        self.assertEqual(report["cases"][0]["verdict"], "improvement")
        self.assertEqual(report["cases"][0]["attribution"], "verified")
        self.assertGreaterEqual(report["cases"][0]["delta"], 0.25)
        self.assertEqual(
            report["cases"][0]["gained_criteria"], ["dimensions", "priorities"]
        )

    def test_reports_verified_regression_from_paired_runs(self) -> None:
        cases = [
            {
                "id": "taste-regression",
                "plugin": "taste@tessera",
                "skill": "taste",
                "prompt": "SIMULATE_REGRESSION",
                "minimum_delta": 0.25,
                "criteria": [
                    {"id": "dimensions", "all": ["层级", "留白", "配色", "字体", "一致性", "细节"]},
                    {"id": "priorities", "any": ["Top 3", "top 3"]},
                ],
            }
        ]
        report = self.run_lab(cases)
        self.assertEqual(report["summary"]["regressions"], 1)
        self.assertEqual(report["cases"][0]["verdict"], "regression")
        self.assertLessEqual(report["cases"][0]["delta"], -0.25)
        self.assertEqual(
            report["cases"][0]["lost_criteria"], ["dimensions", "priorities"]
        )

    def test_repeats_each_condition_and_reports_median_scores(self) -> None:
        cases = [
            {
                "id": "taste-repeat",
                "plugin": "taste@tessera",
                "skill": "taste",
                "prompt": "评审这个页面。",
                "minimum_delta": 0.25,
                "criteria": [
                    {"id": "dimensions", "all": ["层级", "留白", "配色", "字体", "一致性", "细节"]},
                    {"id": "priorities", "any": ["Top 3", "top 3"]},
                ],
            }
        ]
        report = self.run_lab(cases, repeat=3)
        case = report["cases"][0]
        self.assertEqual(len(case["baseline_runs"]), 3)
        self.assertEqual(len(case["skill_runs"]), 3)
        self.assertEqual(case["baseline_score"], 0.0)
        self.assertEqual(case["skill_score"], 1.0)

    @unittest.skipUnless(os.name == "nt", "fake codex launcher uses a Windows command shim")
    def test_codex_mode_uses_per_run_plugin_toggle_and_host_events(self) -> None:
        cases = [
            {
                "id": "taste-codex",
                "plugin": "taste@tessera",
                "skill": "taste",
                "prompt": "评审这个页面。",
                "minimum_delta": 0.25,
                "criteria": [
                    {"id": "dimensions", "all": ["层级", "留白", "配色", "字体", "一致性", "细节"]},
                    {"id": "priorities", "any": ["Top 3", "top 3"]},
                ],
            }
        ]
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            cases_path = temp_root / "cases.json"
            output_path = temp_root / "report.json"
            shim = temp_root / "codex.cmd"
            cases_path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
            shim.write_text(
                f'@echo off\r\n"{sys.executable}" "{FAKE_CODEX}" %*\r\n',
                encoding="utf-8",
            )
            environment = {**os.environ, "PATH": f"{temp_root}{os.pathsep}{os.environ['PATH']}"}
            completed = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--cases",
                    str(cases_path),
                    "--output",
                    str(output_path),
                    "--workspace",
                    str(temp_root),
                    "--codex-executable",
                    str(shim),
                ],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(report["adapter"], "codex-cli")
            self.assertEqual(report["evidence"], "native-host-events")
            self.assertEqual(report["cases"][0]["verdict"], "improvement")
            self.assertEqual(report["cases"][0]["attribution"], "verified")
            self.assertEqual(report["cases"][0]["skill_runs"][0]["command_event_count"], 1)
            self.assertEqual(
                report["cases"][0]["baseline_usage"],
                {
                    "input_tokens": 100,
                    "cached_input_tokens": 40,
                    "output_tokens": 10,
                    "reasoning_output_tokens": 2,
                },
            )
            self.assertEqual(report["cases"][0]["skill_usage"]["input_tokens"], 120)
            self.assertEqual(report["cases"][0]["usage_delta"]["input_tokens"], 20)

    def test_controlled_injection_attributes_delta_to_exact_skill_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill_file = Path(temp) / "SKILL.md"
            skill_file.write_text("SIX_DIMENSION_CONTRACT", encoding="utf-8")
            cases = [
                {
                    "id": "controlled-injection",
                    "plugin": "taste@tessera",
                    "skill": "taste",
                    "activation": "injected",
                    "skill_file": str(skill_file),
                    "prompt": "CONTROLLED_INJECTION_TEST",
                    "minimum_delta": 0.25,
                    "criteria": [
                        {"id": "dimensions", "all": ["层级", "留白", "配色", "字体", "一致性", "细节"]},
                        {"id": "priorities", "any": ["Top 3", "top 3"]},
                    ],
                }
            ]
            report = self.run_lab(cases)
            case = report["cases"][0]
            self.assertEqual(case["verdict"], "improvement")
            self.assertEqual(case["attribution"], "verified-injection")
            self.assertEqual(len(case["skill_sha256"]), 64)
            self.assertEqual(case["skill_content_chars"], len("SIX_DIMENSION_CONTRACT"))
            self.assertEqual(
                case["skill_content_bytes"],
                len("SIX_DIMENSION_CONTRACT".encode("utf-8")),
            )
            self.assertEqual(case["baseline_runs"][0]["observed_skills"], [])
            self.assertEqual(case["skill_runs"][0]["observed_skills"], [])

    def test_regex_criterion_requires_minimum_match_count(self) -> None:
        cases = [
            {
                "id": "regex-count",
                "plugin": "taste@tessera",
                "skill": "taste",
                "prompt": "REGEX_CRITERIA_TEST",
                "minimum_delta": 0.5,
                "criteria": [
                    {"id": "three-scores", "regex": "[1-5]/5", "min_matches": 3}
                ],
            }
        ]
        report = self.run_lab(cases)
        case = report["cases"][0]
        self.assertEqual(case["baseline_score"], 0.0)
        self.assertEqual(case["skill_score"], 1.0)
        self.assertEqual(case["verdict"], "improvement")

    def test_can_select_one_case_for_targeted_reruns(self) -> None:
        base_case = {
            "plugin": "taste@tessera",
            "skill": "taste",
            "prompt": "评审这个页面。",
            "minimum_delta": 0.25,
            "criteria": [{"id": "hierarchy", "any": ["层级"]}],
        }
        cases = [{"id": "first", **base_case}, {"id": "second", **base_case}]
        report = self.run_lab(cases, case_ids=["second"])
        self.assertEqual(report["summary"]["total"], 1)
        self.assertEqual(report["cases"][0]["id"], "second")

    def test_execution_error_is_reported_not_classified_as_regression(self) -> None:
        cases = [
            {
                "id": "host-error",
                "plugin": "taste@tessera",
                "skill": "taste",
                "prompt": "SIMULATE_EXECUTION_ERROR",
                "minimum_delta": 0.25,
                "criteria": [{"id": "hierarchy", "any": ["层级"]}],
            }
        ]
        report = self.run_lab(cases, expected_returncode=2)
        self.assertEqual(report["summary"]["execution_errors"], 1)
        self.assertEqual(report["summary"]["regressions"], 0)
        self.assertEqual(report["cases"][0]["verdict"], "execution_error")

    def test_reports_raw_direction_below_practical_significance_threshold(self) -> None:
        cases = [
            {
                "id": "small-positive-delta",
                "plugin": "taste@tessera",
                "skill": "taste",
                "prompt": "评审这个页面。",
                "minimum_delta": 0.75,
                "criteria": [
                    {"id": "common", "any": ["层级"]},
                    {"id": "dimensions", "all": ["层级", "留白", "配色", "字体", "一致性", "细节"]},
                    {"id": "priorities", "any": ["Top 3", "top 3"]},
                ],
            }
        ]
        report = self.run_lab(cases)
        case = report["cases"][0]
        self.assertEqual(case["verdict"], "no_change")
        self.assertEqual(case["direction"], "improvement")
        self.assertGreater(case["delta"], 0)


if __name__ == "__main__":
    unittest.main()
