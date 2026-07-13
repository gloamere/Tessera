from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from resolve_capabilities import (  # noqa: E402
    PluginInstallation,
    parse_plugin_list_json,
    parse_plugin_list_text,
    probe_installed_plugins,
    resolve_capabilities,
)


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
        self.assertEqual(catalog["schema_version"], 2)
        self.assertEqual(by_id["piece-router"]["enabled_state"], "enabled")
        self.assertIsNone(by_id["taste"]["installed_version"])

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
        self.assertTrue(all(item["enabled_state"] == "unknown" for item in local))

    def test_json_probe_keeps_version_and_enabled_state(self):
        installed = parse_plugin_list_json(
            '{"installed": ['
            '{"pluginId":"tessera-core@tessera","version":"0.2.0","installed":true,"enabled":true},'
            '{"name":"taste","version":"0.1.0","enabled":false}'
            ']}'
        )
        catalog = resolve_capabilities(ROOT, "codex", installed_plugins=installed)
        by_id = {item["id"]: item for item in catalog["capabilities"]}
        self.assertEqual(by_id["tessera-status"]["installed_version"], "0.2.0")
        self.assertEqual(by_id["tessera-status"]["enabled_state"], "enabled")
        self.assertEqual(by_id["taste"]["enabled_state"], "disabled")
        self.assertEqual(by_id["knowledge-base"]["enabled_state"], "not-installed")

    def test_claude_json_array_and_text_fallback(self):
        installed = parse_plugin_list_json(
            '[{"name":"tessera-core","version":"0.2.0","enabled":false}]'
        )
        self.assertEqual(installed["tessera-core"].enabled_state, "disabled")
        fallback = parse_plugin_list_text("tessera-core@tessera 0.2.0\n")
        self.assertEqual(fallback["tessera-core"], PluginInstallation())

    @patch("resolve_capabilities.shutil.which", return_value="codex.cmd")
    @patch("resolve_capabilities.subprocess.run")
    def test_probe_falls_back_to_text_when_json_is_invalid(self, run, _which):
        run.side_effect = [
            subprocess.CompletedProcess([], 0, stdout="not-json", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="taste@tessera 0.1.0\n", stderr=""),
        ]
        installed, evidence = probe_installed_plugins("codex", ROOT)
        self.assertIn("taste", installed)
        self.assertIn("text fallback", evidence)

    @patch("resolve_capabilities.shutil.which", return_value=None)
    def test_probe_unavailable_remains_unknown(self, _which):
        installed, evidence = probe_installed_plugins("claude", ROOT)
        self.assertIsNone(installed)
        self.assertIn("unavailable", evidence)


if __name__ == "__main__":
    unittest.main()
