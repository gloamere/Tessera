from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "pieces" / "frontend-design"
SKILL = PLUGIN / "skills" / "frontend-design"
SCRIPTS = SKILL / "scripts"
UPSTREAM_COMMIT = "f8ac5e1266dba8354ea96e19994d9f4345e7ec31"
POSIX_SHELL = shutil.which("sh") or shutil.which("bash")
POWERSHELL = shutil.which("powershell")


class FrontendDesignTests(unittest.TestCase):
    def run_python(self, *arguments: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, *arguments],
            cwd=cwd or ROOT,
            env={
                **os.environ,
                "PYTHONNOUSERSITE": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONUTF8": "1",
            },
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )

    def test_upstream_core_is_pinned_and_attributed(self) -> None:
        provenance = (SKILL / "references" / "UPSTREAM.md").read_text(encoding="utf-8")
        piece = (PLUGIN / "piece.yaml").read_text(encoding="utf-8")
        license_text = (PLUGIN / "LICENSE.upstream").read_text(encoding="utf-8")
        self.assertIn(UPSTREAM_COMMIT, provenance)
        self.assertIn(UPSTREAM_COMMIT, piece)
        self.assertIn("Copyright (c) 2024 Next Level Builder", license_text)

    def test_imported_data_and_core_tests_pass(self) -> None:
        data_files = list((SKILL / "data").rglob("*.csv"))
        self.assertEqual(len(data_files), 35)

        validation = self.run_python(str(SCRIPTS / "validate_data.py"))
        self.assertEqual(validation.returncode, 0, validation.stderr)
        self.assertIn("22 stack files", validation.stdout)

        tests = self.run_python(
            "-m",
            "unittest",
            "discover",
            "-s",
            str(SCRIPTS / "tests"),
            "-p",
            "test_*.py",
        )
        self.assertEqual(tests.returncode, 0, tests.stderr)
        self.assertIn("Ran 16 tests", tests.stderr)

    def test_cached_search_generates_structured_design_system(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp) / "plugin-cache" / "frontend-design"
            workdir = Path(temp) / "unrelated-project"
            shutil.copytree(PLUGIN, cache)
            workdir.mkdir()
            search = cache / "skills" / "frontend-design" / "scripts" / "search.py"

            result = self.run_python(
                str(search),
                "B2B analytics dashboard calm technical",
                "--design-system",
                "--json",
                cwd=workdir,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            design = payload["design_system"]
            for field in ("pattern", "style", "colors", "typography", "anti_patterns"):
                self.assertIn(field, design)
            for token in ("primary", "background", "foreground", "accent"):
                self.assertIn(token, design["colors"])
            self.assertNotIn(str(ROOT), result.stdout)

    @unittest.skipUnless(
        POSIX_SHELL and os.name != "nt", "macOS/Linux POSIX shell is unavailable"
    )
    def test_posix_wrapper_supports_macos_and_linux(self) -> None:
        syntax = subprocess.run(
            [POSIX_SHELL, "-n", str(SCRIPTS / "run.sh")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
        self.assertEqual(syntax.returncode, 0, syntax.stderr)

        result = subprocess.run(
            [
                POSIX_SHELL,
                str(SCRIPTS / "run.sh"),
                "technical documentation calm",
                "--domain",
                "typography",
                "--json",
            ],
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("results", json.loads(result.stdout))

    @unittest.skipUnless(POWERSHELL, "Windows PowerShell is unavailable")
    def test_powershell_wrapper_runs_search(self) -> None:
        result = subprocess.run(
            [
                POWERSHELL,
                "-NoProfile",
                "-File",
                str(SCRIPTS / "run.ps1"),
                "B2B dashboard calm",
                "--domain",
                "color",
                "--json",
            ],
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("results", json.loads(result.stdout))

    def test_skill_keeps_frontend_design_and_taste_boundaries_distinct(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(text.splitlines()), 70)
        self.assertIn("设计系统与实现约束", text)
        self.assertIn("纯审美评审", text)
        self.assertIn("taste", text)
        self.assertIn("用户研究", text)


if __name__ == "__main__":
    unittest.main()
