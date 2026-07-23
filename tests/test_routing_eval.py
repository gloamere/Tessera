from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = (
    ROOT
    / "plugins"
    / "gloamere-eval"
    / "skills"
    / "gloamere-skill-eval"
)
RUNNER = SKILL_ROOT / "scripts" / "run_routing_eval.py"
ROOT_RUNNER = ROOT / "scripts" / "run_routing_eval.py"
FAKE_HOST = ROOT / "tests" / "fixtures" / "fake_eval_host.py"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from run_routing_eval import (  # noqa: E402
    HostResult,
    aggregate_case,
    build_report,
    classify_native_attempt,
    inspect_plugins,
    load_report_compat,
    parse_codex_events,
    sha256_file,
    summarize_cases,
    validate_report_v3,
    validate_suite,
    validate_suite_binding,
    validate_target_lock,
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def create_plugin(
    root: Path,
    plugin_id: str,
    skill_name: str,
    version: str = "1.2.3",
) -> Path:
    write_json(
        root / ".codex-plugin" / "plugin.json",
        {
            "name": plugin_id,
            "version": version,
        },
    )
    skill_path = root / "skills" / skill_name / "SKILL.md"
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    skill_path.write_text(
        "\n".join(
            (
                "---",
                f"name: {skill_name}",
                "description: Test-only routing target.",
                "---",
                "",
                f"# {skill_name}",
                "",
            )
        ),
        encoding="utf-8",
    )
    agent_config_path = skill_path.parent / "agents" / "openai.yaml"
    agent_config_path.parent.mkdir(parents=True, exist_ok=True)
    agent_config_path.write_text(
        "\n".join(
            (
                "interface:",
                f'  display_name: "{skill_name}"',
                '  short_description: "Test-only routing target"',
                "policy:",
                "  allow_implicit_invocation: true",
                "",
            )
        ),
        encoding="utf-8",
    )
    return skill_path.resolve()


def complete_events(
    command: str | None = None,
    *,
    output: str | None = None,
    event_type: str = "item.completed",
    status: str = "completed",
    exit_code: int = 0,
) -> str:
    events: list[dict[str, object]] = [
        {
            "type": "thread.started",
            "thread_id": "test-thread",
        },
        {
            "type": "turn.started",
        },
    ]
    if command is not None:
        events.append(
            {
                "type": event_type,
                "item": {
                    "id": "command-1",
                    "type": "command_execution",
                    "command": command,
                    "status": status,
                    "exit_code": exit_code,
                    "aggregated_output": output,
                },
            }
        )
    events.append(
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 12,
                "cached_input_tokens": 2,
                "output_tokens": 3,
                "reasoning_output_tokens": 1,
            },
        }
    )
    return "\n".join(json.dumps(item) for item in events)


class RoutingEvalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.temp = Path(self.temporary.name)
        self.plugin_root = self.temp / "plugin one"
        self.skill_path = create_plugin(
            self.plugin_root,
            "example-plugin",
            "example-skill",
        )
        self.catalog = {
            "installed": [
                {
                    "pluginId": "example-plugin@local",
                    "name": "example-plugin",
                    "marketplaceName": "local",
                    "version": "1.2.3",
                    "installed": True,
                    "enabled": True,
                    "source": {
                        "source": "local",
                        "path": str(self.plugin_root.resolve()),
                    },
                }
            ],
            "available": [],
        }
        self.catalog_path = self.temp / "plugin-catalog.json"
        write_json(self.catalog_path, self.catalog)
        self.lock = inspect_plugins(
            [self.plugin_root],
            marketplace="local",
            catalog=self.catalog,
            catalog_source="fixture",
            catalog_codex_version="fixture-adapter",
        )
        self.target = self.lock["targets"][0]
        self.suite = {
            "schema_version": 1,
            "suite_id": "test-suite",
            "description": "Test-only routing suite.",
            "plugin_id": "example-plugin",
            "execution_policy": {
                "repeat": 1,
                "independent_batches": 1,
            },
            "cases": [
                {
                    "id": "loads-target",
                    "plugin_id": "example-plugin",
                    "prompt": "Use the example capability.",
                    "expected_skills": ["example-skill"],
                    "forbidden_skills": [],
                    "language": "en",
                    "tags": ["test", "kind:positive"],
                }
            ],
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_inspect_binds_path_sha_plugin_and_selector(self):
        self.assertEqual(self.lock["errors"], [])
        self.assertEqual(self.lock["conflicts"], [])
        self.assertEqual(
            self.target["target_id"],
            "example-plugin:example-skill",
        )
        self.assertEqual(self.target["plugin_selector"], "example-plugin@local")
        self.assertTrue(self.target["installed"])
        self.assertTrue(self.target["enabled"])
        self.assertTrue(self.lock["catalog"]["observable"])
        self.assertEqual(Path(self.target["skill_path"]), self.skill_path)
        self.assertEqual(
            self.target["relative_path"],
            "skills/example-skill/SKILL.md",
        )
        self.assertEqual(self.target["sha256"], sha256_file(self.skill_path))
        manifest_path = self.plugin_root / ".codex-plugin" / "plugin.json"
        agent_config_path = (
            self.skill_path.parent / "agents" / "openai.yaml"
        )
        self.assertEqual(
            self.target["plugin_manifest_sha256"],
            sha256_file(manifest_path),
        )
        self.assertEqual(
            Path(self.target["agent_config_path"]),
            agent_config_path,
        )
        self.assertEqual(
            self.target["agent_config_sha256"],
            sha256_file(agent_config_path),
        )
        self.assertEqual(validate_target_lock(self.lock), [])
        self.assertEqual(validate_suite(self.suite), [])
        self.assertEqual(validate_suite_binding(self.suite, self.lock), [])

    def test_inspect_reports_same_name_conflicts_across_plugins(self):
        second_root = self.temp / "plugin two"
        create_plugin(second_root, "second-plugin", "example-skill")

        lock = inspect_plugins(
            [self.plugin_root, second_root],
            catalog=self.catalog,
            catalog_source="fixture",
        )

        self.assertEqual(lock["errors"], [])
        self.assertEqual(len(lock["conflicts"]), 1)
        self.assertEqual(
            lock["conflicts"][0]["kind"],
            "duplicate-skill-name",
        )
        self.assertIn(
            "same-name target conflict is in evaluation scope",
            "\n".join(validate_suite_binding(self.suite, lock)),
        )

    def test_validators_reject_identity_and_content_drift(self):
        invalid_suite = json.loads(json.dumps(self.suite))
        invalid_suite["cases"][0]["plugin_id"] = "other-plugin"
        self.assertIn(
            "plugin_id does not match suite plugin_id",
            "\n".join(validate_suite(invalid_suite)),
        )

        self.skill_path.write_text(
            self.skill_path.read_text(encoding="utf-8") + "\nchanged\n",
            encoding="utf-8",
        )
        self.assertIn(
            "SHA-256 does not match skill contents",
            "\n".join(validate_target_lock(self.lock)),
        )

    def test_target_lock_rejects_manifest_and_agent_policy_drift(self):
        artifacts = (
            (
                self.plugin_root / ".codex-plugin" / "plugin.json",
                "plugin manifest SHA-256 does not match contents",
            ),
            (
                self.skill_path.parent / "agents" / "openai.yaml",
                "agent config SHA-256 does not match contents",
            ),
        )
        for path, expected_error in artifacts:
            with self.subTest(path=path.name):
                original = path.read_text(encoding="utf-8")
                path.write_text(original + "\n# drift\n", encoding="utf-8")
                self.assertIn(
                    expected_error,
                    "\n".join(validate_target_lock(self.lock)),
                )
                path.write_text(original, encoding="utf-8")

    def test_suite_requires_explicit_unique_target_expectations(self):
        invalid = json.loads(json.dumps(self.suite))
        invalid["cases"][0].pop("forbidden_skills")
        invalid["cases"][0]["expected_skills"] *= 2

        errors = "\n".join(validate_suite(invalid))

        self.assertIn("is missing forbidden_skills", errors)
        self.assertIn("contains duplicate Skills", errors)

    def test_complete_events_bind_observation_to_locked_path(self):
        evidence = parse_codex_events(
            complete_events(
                f'type "{self.skill_path}"',
                output=self.skill_path.read_text(encoding="utf-8"),
            ),
            self.lock,
            self.suite,
        )

        self.assertTrue(evidence.complete)
        self.assertEqual(
            evidence.observed_target_ids,
            (self.target["target_id"],),
        )
        self.assertEqual(evidence.malformed_lines, 0)
        self.assertEqual(evidence.terminal_event, "turn.completed")

    def test_only_successful_completed_file_reads_count_as_evidence(self):
        content = self.skill_path.read_text(encoding="utf-8")
        streams = {
            "failed-read": complete_events(
                f'type "{self.skill_path}"',
                output=content,
                status="failed",
                exit_code=1,
            ),
            "started-only": complete_events(
                f'type "{self.skill_path}"',
                output=content,
                event_type="item.started",
            ),
            "updated-only": complete_events(
                f'type "{self.skill_path}"',
                output=content,
                event_type="item.updated",
            ),
            "path-mention": complete_events(
                f'echo "{self.skill_path}"',
                output=str(self.skill_path),
            ),
        }
        for label, stream in streams.items():
            with self.subTest(label=label):
                attempt = classify_native_attempt(
                    self.suite["cases"][0],
                    self.suite,
                    self.lock,
                    HostResult(
                        {
                            "selected_skills": ["example-skill"],
                            "reason": "fixture",
                        },
                        stream,
                        1,
                    ),
                    1,
                )
                self.assertEqual(attempt["evidence_status"], "unobservable")
                self.assertIsNone(attempt["verdict"])
                self.assertEqual(
                    attempt["event_diagnostics"][
                        "rejected_target_references"
                    ],
                    [self.target["target_id"]],
                )

    def test_malformed_truncated_and_unknown_events_are_unobservable(self):
        valid_lines = complete_events(
            f'type "{self.skill_path}"',
            output=self.skill_path.read_text(encoding="utf-8"),
        ).splitlines()
        streams = {
            "malformed": "\n".join([*valid_lines[:-1], "{bad-json", valid_lines[-1]]),
            "truncated": "\n".join(valid_lines[:-1]),
            "unknown-event": "\n".join(
                [*valid_lines[:-1], '{"type":"future.event"}', valid_lines[-1]]
            ),
            "unknown-item": "\n".join(
                [
                    *valid_lines[:-1],
                    '{"type":"item.completed","item":{"type":"future_item"}}',
                    valid_lines[-1],
                ]
            ),
        }
        case = self.suite["cases"][0]
        for label, stream in streams.items():
            with self.subTest(label=label):
                attempt = classify_native_attempt(
                    case,
                    self.suite,
                    self.lock,
                    HostResult(
                        {
                            "selected_skills": ["example-skill"],
                            "reason": "fixture",
                        },
                        stream,
                        1,
                    ),
                    1,
                )
                self.assertEqual(attempt["evidence_status"], "unobservable")
                self.assertIsNone(attempt["verdict"])
                self.assertFalse(attempt["event_diagnostics"]["complete"])

    def test_complete_empty_observation_verifies_direct_routing(self):
        case = {
            "id": "direct",
            "plugin_id": "example-plugin",
            "prompt": "Make a tiny local edit.",
            "expected_skills": [],
            "forbidden_skills": ["example-skill"],
            "language": "en",
            "tags": ["test", "kind:negative"],
        }
        attempt = classify_native_attempt(
            case,
            self.suite,
            self.lock,
            HostResult(
                {
                    "selected_skills": [],
                    "reason": "No specialist was loaded.",
                },
                complete_events(),
                2,
            ),
            1,
        )

        self.assertEqual(attempt["evidence_status"], "verified")
        self.assertEqual(attempt["verdict"], "pass")

    def test_declaration_mismatch_and_unbound_same_name_are_conflicts(self):
        case = self.suite["cases"][0]
        declaration_conflict = classify_native_attempt(
            case,
            self.suite,
            self.lock,
            HostResult(
                {
                    "selected_skills": [],
                    "reason": "fixture",
                },
                complete_events(
                    f'type "{self.skill_path}"',
                    output=self.skill_path.read_text(encoding="utf-8"),
                ),
                1,
            ),
            1,
        )
        other_path = (
            self.temp
            / "different plugin"
            / "skills"
            / "example-skill"
            / "SKILL.md"
        ).resolve()
        unbound_conflict = classify_native_attempt(
            case,
            self.suite,
            self.lock,
            HostResult(
                {
                    "selected_skills": ["example-skill"],
                    "reason": "fixture",
                },
                complete_events(
                    f'type "{other_path}"',
                    output="unbound fixture Skill",
                ),
                1,
            ),
            1,
        )

        self.assertEqual(
            (declaration_conflict["evidence_status"], declaration_conflict["verdict"]),
            ("identity_conflict", None),
        )
        self.assertEqual(
            (unbound_conflict["evidence_status"], unbound_conflict["verdict"]),
            ("identity_conflict", None),
        )
        self.assertEqual(
            unbound_conflict["unbound_skill_names"],
            ["example-skill"],
        )

    def test_aggregation_separates_evidence_coverage_and_accuracy(self):
        case = self.suite["cases"][0]
        attempts = [
            {
                "batch_id": 1,
                "attempt": 1,
                "evidence_status": "verified",
                "verdict": "pass",
                "observed_target_ids": [self.target["target_id"]],
                "declared_target_ids": [self.target["target_id"]],
                "declared_skills": ["example-skill"],
            },
            {
                "batch_id": 1,
                "attempt": 2,
                "evidence_status": "identity_conflict",
                "verdict": None,
                "observed_target_ids": [self.target["target_id"]],
                "declared_target_ids": [],
                "declared_skills": [],
            },
            {
                "batch_id": 1,
                "attempt": 3,
                "evidence_status": "unobservable",
                "verdict": None,
                "observed_target_ids": [],
                "declared_target_ids": [],
                "declared_skills": [],
            },
        ]
        aggregate = aggregate_case(case, attempts, repeat=3)
        summary = summarize_cases([aggregate])

        self.assertFalse(aggregate["stable"])
        self.assertEqual(summary["evidence_coverage"], 0.3333)
        self.assertEqual(summary["conditional_accuracy"], 1.0)

    def test_report_v3_hashes_prompts_and_omits_absolute_paths(self):
        case = self.suite["cases"][0]
        attempt = classify_native_attempt(
            case,
            self.suite,
            self.lock,
            HostResult(
                {
                    "selected_skills": ["example-skill"],
                    "reason": "fixture",
                },
                complete_events(
                    f'type "{self.skill_path}"',
                    output=self.skill_path.read_text(encoding="utf-8"),
                ),
                3,
                codex_version="fixture",
            ),
            1,
        )
        aggregate = aggregate_case(case, [attempt], repeat=1)
        report = build_report(
            self.suite,
            self.lock,
            [aggregate],
            repeat=1,
            timeout=45,
            model=None,
            codex_version_value="fixture",
            include_prompts=False,
            execution_provenance="fixture_adapter",
        )

        self.assertEqual(validate_report_v3(report), [])
        self.assertFalse(report["privacy"]["prompts_included"])
        self.assertEqual(
            report["execution_provenance"],
            "fixture_adapter",
        )
        self.assertFalse(report["release_evidence_eligible"])
        self.assertNotIn("prompt", report["cases"][0]["attempts"][0])
        serialized_targets = json.dumps(report["target_lock"]["targets"])
        self.assertNotIn(str(self.plugin_root.resolve()), serialized_targets)
        self.assertNotIn(str(self.skill_path), serialized_targets)
        self.assertNotIn(str(self.temp.resolve()), json.dumps(report))

    def test_report_validator_recomputes_case_metrics_and_privacy(self):
        case = self.suite["cases"][0]
        attempt = classify_native_attempt(
            case,
            self.suite,
            self.lock,
            HostResult(
                {
                    "selected_skills": ["example-skill"],
                    "reason": "fixture",
                },
                complete_events(
                    f'type "{self.skill_path}"',
                    output=self.skill_path.read_text(encoding="utf-8"),
                ),
                1,
                codex_version="fixture",
            ),
            1,
        )
        report = build_report(
            self.suite,
            self.lock,
            [aggregate_case(case, [attempt], repeat=1)],
            repeat=1,
            timeout=45,
            model=None,
            codex_version_value="fixture",
            include_prompts=False,
            execution_provenance="fixture_adapter",
        )
        self.assertEqual(validate_report_v3(report), [])

        tampered_metrics = json.loads(json.dumps(report))
        tampered_metrics["cases"][0]["evidence_coverage"] = 0.0
        self.assertIn(
            "evidence_coverage does not match attempts",
            "\n".join(validate_report_v3(tampered_metrics)),
        )

        leaked_path = json.loads(json.dumps(report))
        leaked_path["cases"][0]["attempts"][0][
            "reason"
        ] = r"read C:\Users\secret\SKILL.md"
        self.assertIn(
            "contains absolute paths",
            "\n".join(validate_report_v3(leaked_path)),
        )

        forged_provenance = json.loads(json.dumps(report))
        forged_provenance["release_evidence_eligible"] = True
        self.assertIn(
            "does not match execution_provenance",
            "\n".join(validate_report_v3(forged_provenance)),
        )

        forged_verdict = json.loads(json.dumps(report))
        forged_attempt = forged_verdict["cases"][0]["attempts"][0]
        forged_attempt["verdict"] = "fail"
        forged_verdict["cases"][0] = aggregate_case(
            case,
            [forged_attempt],
            repeat=1,
        )
        forged_verdict["summary"] = summarize_cases(forged_verdict["cases"])
        self.assertIn(
            "verdict does not match observed evidence",
            "\n".join(validate_report_v3(forged_verdict)),
        )

        forged_identity = json.loads(json.dumps(report))
        forged_identity["cases"][0]["attempts"][0]["observed_target_ids"] = []
        self.assertIn(
            "observed Skill names and target IDs disagree",
            "\n".join(validate_report_v3(forged_identity)),
        )

    def test_reads_legacy_v2_report_without_publishing_an_alias(self):
        path = self.temp / "legacy-report.json"
        legacy = {
            "schema_version": 2,
            "generated_at": "2026-07-23T00:00:00+00:00",
            "host": "codex",
            "mode": "native",
            "repeat": 1,
            "model": None,
            "adapter": "codex-cli",
            "summary": {},
            "cases": [],
            "results": [],
            "tuning_candidates": [],
            "producer": "tessera-eval",
            "plugin": "tessera-core@tessera",
        }
        write_json(path, legacy)

        normalized, compatible = load_report_compat(path)

        self.assertTrue(compatible)
        self.assertEqual(normalized["producer"], "gloamere-skill-eval")
        self.assertEqual(normalized["plugin"], "gloamere-eval@gloamere")
        self.assertFalse(
            normalized["_compatibility"]["release_evidence_eligible"]
        )
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), legacy)
        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: gloamere-skill-eval", skill_text)
        self.assertNotIn("name: tessera-eval", skill_text)

    def test_rejects_structurally_invalid_legacy_v2_report(self):
        path = self.temp / "invalid-legacy-report.json"
        write_json(path, {"schema_version": 2})

        with self.assertRaisesRegex(
            ValueError,
            "invalid legacy schema v2 report",
        ):
            load_report_compat(path)

    def test_cli_inspect_uses_stdout_and_optional_explicit_output(self):
        command = [
            sys.executable,
            str(ROOT_RUNNER),
            "inspect",
            "--plugin-root",
            str(self.plugin_root),
            "--catalog",
            str(self.catalog_path),
        ]
        stdout_only = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        output = self.temp / "target-lock.json"
        explicit = subprocess.run(
            [*command, "--output", str(output)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

        self.assertEqual(stdout_only.returncode, 0, stdout_only.stderr)
        self.assertEqual(explicit.returncode, 0, explicit.stderr)
        self.assertEqual(json.loads(explicit.stdout), json.loads(output.read_text()))
        self.assertEqual(
            json.loads(stdout_only.stdout)["targets"][0]["target_id"],
            self.target["target_id"],
        )

    def test_cli_native_runs_fixture_adapter_end_to_end(self):
        suite_path = self.temp / "suite.json"
        lock_path = self.temp / "target-lock.json"
        report_path = self.temp / "report.json"
        write_json(suite_path, self.suite)
        write_json(lock_path, self.lock)
        command = [
            sys.executable,
            str(ROOT_RUNNER),
            "native",
            "--suite",
            str(suite_path),
            "--target-lock",
            str(lock_path),
            "--catalog",
            str(self.catalog_path),
            "--adapter-executable",
            sys.executable,
            "--adapter-arg",
            str(FAKE_HOST),
            "--adapter-arg=--skill-path",
            "--adapter-arg",
            str(self.skill_path),
            "--adapter-arg=--skill-name",
            "--adapter-arg",
            "example-skill",
            "--output",
            str(report_path),
        ]

        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report, json.loads(report_path.read_text(encoding="utf-8")))
        self.assertEqual(report["schema_version"], 3)
        self.assertEqual(
            report["event_adapter"],
            {"id": "codex-exec-jsonl", "schema_version": 1},
        )
        self.assertEqual(
            report["execution_provenance"],
            "fixture_adapter",
        )
        self.assertFalse(report["release_evidence_eligible"])
        self.assertEqual(report["summary"]["passed_attempts"], 1)
        self.assertEqual(
            report["cases"][0]["attempts"][0]["evidence_status"],
            "verified",
        )
        self.assertEqual(
            report["cases"][0]["attempts"][0]["batch_id"],
            1,
        )

    def test_native_runs_each_independent_batch_in_a_fresh_workspace(self):
        suite = json.loads(json.dumps(self.suite))
        suite["execution_policy"]["independent_batches"] = 2
        suite_path = self.temp / "suite-batches.json"
        lock_path = self.temp / "target-lock-batches.json"
        workspace_log = self.temp / "workspace.log"
        write_json(suite_path, suite)
        write_json(lock_path, self.lock)

        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT_RUNNER),
                "native",
                "--suite",
                str(suite_path),
                "--target-lock",
                str(lock_path),
                "--catalog",
                str(self.catalog_path),
                "--adapter-executable",
                sys.executable,
                "--adapter-arg",
                str(FAKE_HOST),
                "--adapter-arg=--skill-path",
                "--adapter-arg",
                str(self.skill_path),
                "--adapter-arg=--skill-name",
                "--adapter-arg",
                "example-skill",
                "--adapter-arg=--workspace-log",
                "--adapter-arg",
                str(workspace_log),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        attempts = report["cases"][0]["attempts"]
        self.assertEqual(
            [(item["batch_id"], item["attempt"]) for item in attempts],
            [(1, 1), (2, 1)],
        )
        self.assertTrue(report["cases"][0]["stable"])
        self.assertEqual(report["repeat"], 1)
        self.assertEqual(report["independent_batches"], 2)
        workspaces = workspace_log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(workspaces), 2)
        self.assertEqual(len(set(workspaces)), 2)

    def test_identity_drift_during_a_batch_invalidates_batch_evidence(self):
        suite = json.loads(json.dumps(self.suite))
        suite["execution_policy"]["independent_batches"] = 2
        suite_path = self.temp / "suite-drift.json"
        lock_path = self.temp / "target-lock-drift.json"
        workspace_log = self.temp / "drift-workspace.log"
        agent_config = self.skill_path.parent / "agents" / "openai.yaml"
        write_json(suite_path, suite)
        write_json(lock_path, self.lock)

        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT_RUNNER),
                "native",
                "--suite",
                str(suite_path),
                "--target-lock",
                str(lock_path),
                "--catalog",
                str(self.catalog_path),
                "--adapter-executable",
                sys.executable,
                "--adapter-arg",
                str(FAKE_HOST),
                "--adapter-arg=--skill-path",
                "--adapter-arg",
                str(self.skill_path),
                "--adapter-arg=--skill-name",
                "--adapter-arg",
                "example-skill",
                "--adapter-arg=--workspace-log",
                "--adapter-arg",
                str(workspace_log),
                "--adapter-arg=--mutate-path",
                "--adapter-arg",
                str(agent_config),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

        self.assertEqual(completed.returncode, 1, completed.stderr)
        report = json.loads(completed.stdout)
        attempts = report["cases"][0]["attempts"]
        self.assertEqual(
            [item["evidence_status"] for item in attempts],
            ["identity_conflict", "identity_conflict"],
        )
        self.assertEqual(report["summary"]["evidence_coverage"], 0.0)
        self.assertFalse(report["cases"][0]["stable"])
        self.assertEqual(
            len(workspace_log.read_text(encoding="utf-8").splitlines()),
            1,
        )
        self.assertNotIn(str(self.temp.resolve()), completed.stdout)

    def test_native_preflight_identity_conflict_is_structured_and_unscored(self):
        suite_path = self.temp / "suite.json"
        lock_path = self.temp / "target-lock.json"
        write_json(suite_path, self.suite)
        write_json(lock_path, self.lock)
        self.skill_path.write_text(
            self.skill_path.read_text(encoding="utf-8") + "\nidentity drift\n",
            encoding="utf-8",
        )

        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT_RUNNER),
                "native",
                "--suite",
                str(suite_path),
                "--target-lock",
                str(lock_path),
                "--catalog",
                str(self.catalog_path),
                "--adapter-executable",
                str(self.temp / "adapter-must-not-run"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

        self.assertEqual(completed.returncode, 1, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(
            report["preflight"]["evidence_status"],
            "identity_conflict",
        )
        attempt = report["cases"][0]["attempts"][0]
        self.assertEqual(attempt["evidence_status"], "identity_conflict")
        self.assertIsNone(attempt["verdict"])
        self.assertEqual(report["summary"]["evidence_coverage"], 0.0)
        self.assertFalse(report["cases"][0]["stable"])
        self.assertNotIn(str(self.temp.resolve()), completed.stdout)

    def test_native_catalog_unavailable_and_execution_error_are_unscored(self):
        suite_path = self.temp / "suite.json"
        lock_path = self.temp / "target-lock.json"
        write_json(suite_path, self.suite)
        write_json(lock_path, self.lock)
        base = [
            sys.executable,
            str(ROOT_RUNNER),
            "native",
            "--suite",
            str(suite_path),
            "--target-lock",
            str(lock_path),
        ]
        unavailable = subprocess.run(
            [*base, "--catalog", str(self.temp / "missing-catalog.json")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        execution_error = subprocess.run(
            [
                *base,
                "--catalog",
                str(self.catalog_path),
                "--adapter-executable",
                str(self.temp / "missing-adapter"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

        self.assertEqual(unavailable.returncode, 2, unavailable.stderr)
        unavailable_report = json.loads(unavailable.stdout)
        self.assertEqual(
            unavailable_report["cases"][0]["attempts"][0]["evidence_status"],
            "unavailable",
        )
        self.assertIsNone(
            unavailable_report["cases"][0]["attempts"][0]["verdict"]
        )
        self.assertEqual(execution_error.returncode, 2, execution_error.stderr)
        error_report = json.loads(execution_error.stdout)
        self.assertEqual(
            error_report["cases"][0]["attempts"][0]["evidence_status"],
            "execution_error",
        )
        self.assertIsNone(error_report["cases"][0]["attempts"][0]["verdict"])
        self.assertNotIn(str(self.temp.resolve()), execution_error.stdout)

    def test_contract_schemas_are_json_and_runner_has_no_workflow_names(self):
        schema_root = SKILL_ROOT / "references" / "schemas"
        expected = {
            "eval-suite.schema.json",
            "native-invocation-output.schema.json",
            "report.schema.json",
            "target-lock.schema.json",
        }
        self.assertEqual(
            {path.name for path in schema_root.glob("*.json")},
            expected,
        )
        for filename in expected:
            self.assertIsInstance(
                json.loads((schema_root / filename).read_text(encoding="utf-8")),
                dict,
            )
        source = RUNNER.read_text(encoding="utf-8")
        for forbidden in (
            "business-ops",
            "finance-ops",
            "frontend-design",
            "growth-ops",
            "knowledge-base",
            "product-planning",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn(
            "sys.version_info >= (3, 10)",
            (SKILL_ROOT / "scripts" / "run.ps1").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
