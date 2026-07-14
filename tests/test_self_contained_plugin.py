from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "pieces" / "tessera-core"


class SelfContainedPluginTests(unittest.TestCase):
    def test_active_release_surface_excludes_retired_planner(self) -> None:
        planner = ROOT / "pieces" / "planner"
        self.assertFalse(
            planner.exists() and any(path.is_file() for path in planner.rglob("*"))
        )
        active_files = (
            ROOT / ".claude-plugin" / "marketplace.json",
            ROOT / ".agents" / "plugins" / "marketplace.json",
            PLUGIN / "skills" / "tessera-eval" / "SKILL.md",
            PLUGIN / "skills" / "tessera-eval" / "scripts" / "run_routing_eval.py",
            PLUGIN / "skills" / "tessera-eval" / "references" / "routing-cases.json",
            PLUGIN / "skills" / "tessera-eval" / "references" / "personal-routing-cases.json",
            PLUGIN / "skills" / "tessera-eval" / "references" / "schemas" / "routing-output.schema.json",
        )
        for path in active_files:
            self.assertNotIn("planner", path.read_text(encoding="utf-8"), path)

    def test_cached_plugin_copy_runs_without_repository_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            cached_plugin = temp_root / "plugin-cache" / "tessera-core"
            workdir = temp_root / "unrelated-project"
            shutil.copytree(PLUGIN, cached_plugin)
            workdir.mkdir()

            skill = cached_plugin / "skills" / "tessera-eval"
            runner = skill / "scripts" / "run_routing_eval.py"
            personal_cases = skill / "references" / "personal-routing-cases.json"
            environment = {**os.environ, "PYTHONNOUSERSITE": "1"}

            default = subprocess.run(
                [sys.executable, str(runner), "--host", "codex", "--mode", "native", "--dry-run"],
                cwd=workdir,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
                check=False,
            )
            self.assertEqual(default.returncode, 0, default.stderr)
            self.assertIn("cases=15", default.stdout)

            personal = subprocess.run(
                [
                    sys.executable,
                    str(runner),
                    "--host",
                    "codex",
                    "--mode",
                    "native",
                    "--cases",
                    str(personal_cases),
                    "--dry-run",
                ],
                cwd=workdir,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
                check=False,
            )
            self.assertEqual(personal.returncode, 0, personal.stderr)
            self.assertIn("cases=25", personal.stdout)
            self.assertNotIn(str(ROOT), personal.stdout)

    def test_runtime_uses_only_python_standard_library(self) -> None:
        runner = PLUGIN / "skills" / "tessera-eval" / "scripts" / "run_routing_eval.py"
        source = runner.read_text(encoding="utf-8")
        self.assertNotIn("import yaml", source)
        self.assertNotIn("site-packages", source)


if __name__ == "__main__":
    unittest.main()
