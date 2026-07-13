from pathlib import Path
import sys
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lifecycle_policy import action_policy, inspect_rollback_ref  # noqa: E402
from remediation_policy import remediation_mode, resolve_outcomes  # noqa: E402


class LifecyclePolicyTests(unittest.TestCase):
    def test_host_action_matrix(self):
        self.assertEqual(action_policy("claude", "disable", "taste")["support"], "execute")
        codex_disable = action_policy("codex", "disable", "taste")
        self.assertEqual(codex_disable["support"], "unsupported")
        self.assertIsNone(codex_disable["command"])
        self.assertIn("remove", action_policy("codex", "uninstall", "taste")["command"])

    def test_rollback_requires_explicit_valid_ref(self):
        with self.assertRaisesRegex(ValueError, "explicit Git"):
            inspect_rollback_ref(ROOT, "tessera-core", "cache")
        target = inspect_rollback_ref(ROOT, "tessera-core", "HEAD")
        self.assertEqual(target["piece"], "tessera-core")
        self.assertTrue(target["commit"])
        self.assertTrue(target["version"])
        with self.assertRaisesRegex(ValueError, "canonical"):
            inspect_rollback_ref(ROOT, "../tessera-core", "HEAD")

    def test_remediation_scope_and_dependency_outcomes(self):
        self.assertEqual(remediation_mode("host-lifecycle"), "execute")
        self.assertEqual(remediation_mode("trust"), "plan-only")
        items = [
            {"id": "refresh", "scope": "host-lifecycle"},
            {"id": "enable", "scope": "host-lifecycle", "depends_on": ["refresh"]},
            {"id": "trust", "scope": "trust"},
            {"id": "independent", "scope": "host-lifecycle"},
        ]
        outcomes = resolve_outcomes(
            items,
            confirmations={"refresh": True, "enable": True, "independent": False},
            executions={"refresh": False, "enable": True},
            verifications={"refresh": False, "enable": True},
        )
        self.assertEqual(outcomes["refresh"], "failed")
        self.assertEqual(outcomes["enable"], "blocked")
        self.assertEqual(outcomes["trust"], "plan-only")
        self.assertEqual(outcomes["independent"], "skipped")

    def test_remediation_fixtures(self):
        cases = yaml.safe_load(
            (ROOT / "tests" / "remediation-cases.yaml").read_text(encoding="utf-8")
        )
        for case in cases:
            with self.subTest(case=case["id"]):
                self.assertEqual(
                    resolve_outcomes(
                        case["items"],
                        case.get("confirmations", {}),
                        case.get("executions", {}),
                        case.get("verifications", {}),
                    ),
                    case["expected"],
                )


if __name__ == "__main__":
    unittest.main()
