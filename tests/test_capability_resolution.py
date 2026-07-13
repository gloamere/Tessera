from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from resolve_capabilities import resolve_capabilities  # noqa: E402


class CapabilityResolutionTests(unittest.TestCase):
    def test_discovers_skills_and_trust_gates_external_capabilities(self):
        catalog = resolve_capabilities(
            ROOT,
            "codex",
            installed_plugins={"tessera-core", "taste"},
            active_skills={"piece-router"},
            probe_evidence="fixture",
        )
        by_id = {item["id"]: item for item in catalog["capabilities"]}
        self.assertEqual(by_id["piece-router"]["runtime_state"], "active")
        self.assertEqual(by_id["taste"]["runtime_state"], "installed")
        self.assertEqual(by_id["knowledge-base"]["runtime_state"], "available")
        self.assertEqual(by_id["superpowers"]["catalog_state"], "unverified")
        self.assertEqual(by_id["browser-use"]["catalog_state"], "unverified")

    def test_claude_installable_external_requires_exact_trust_match(self):
        catalog = resolve_capabilities(ROOT, "claude", installed_plugins=set())
        by_id = {item["id"]: item for item in catalog["capabilities"]}
        self.assertEqual(by_id["superpowers"]["catalog_state"], "installable")
        self.assertIn("trust", by_id["superpowers"]["evidence"])

    def test_missing_probe_is_unknown_not_not_installed(self):
        catalog = resolve_capabilities(ROOT, "codex")
        local = [item for item in catalog["capabilities"] if item["kind"] == "skill"]
        self.assertTrue(local)
        self.assertTrue(all(item["runtime_state"] == "unknown" for item in local))


if __name__ == "__main__":
    unittest.main()
