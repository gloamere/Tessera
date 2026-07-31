from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "experiments" / "workflows" / "gloamere-ui-system"
SCRIPTS = SKILL / "scripts"
UPSTREAM_COMMIT = "f8ac5e1266dba8354ea96e19994d9f4345e7ec31"
VENDOR_DATA_DIGEST = "1140123a63f8a4253f438d05748b9647300cba5fa49269cccca867c8906552dd"
POSIX_SHELL = shutil.which("sh") or shutil.which("bash")
POWERSHELL = shutil.which("powershell")


class GloamereUISystemTests(unittest.TestCase):
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
        license_text = (
            SKILL / "THIRD_PARTY_NOTICES" / "next-level-builder-MIT.txt"
        ).read_text(encoding="utf-8")
        self.assertIn(UPSTREAM_COMMIT, provenance)
        self.assertIn("../THIRD_PARTY_NOTICES/next-level-builder-MIT.txt", provenance)
        self.assertIn("Gloamere orchestration", provenance)
        self.assertIn("byte-for-byte copies", provenance)
        self.assertIn("Copyright (c) 2024 Next Level Builder", license_text)
        self.assertFalse(
            (ROOT / "plugins" / "gloamere-workflows" / "skills" / "gloamere-ui-system").exists()
        )

    def test_vendored_data_is_unchanged_and_core_tests_pass(self) -> None:
        data_root = SKILL / "data"
        data_files = sorted(
            data_root.rglob("*.csv"),
            key=lambda path: path.relative_to(data_root).as_posix(),
        )
        self.assertEqual(len(data_files), 35)

        digest = hashlib.sha256()
        for path in data_files:
            digest.update(path.relative_to(data_root).as_posix().encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        self.assertEqual(digest.hexdigest(), VENDOR_DATA_DIGEST)

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
            cache = Path(temp) / "plugin-cache" / "gloamere-ui-system"
            workdir = Path(temp) / "unrelated-project"
            shutil.copytree(SKILL, cache)
            workdir.mkdir()
            search = cache / "scripts" / "search.py"

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

    def test_skill_uses_unique_id_and_visual_review_boundary(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(text.splitlines()), 70)
        self.assertIn("name: gloamere-ui-system", text)
        self.assertIn("设计系统与实现约束", text)
        self.assertIn("gloamere-visual-review", text)
        self.assertIn("用户研究", text)
        self.assertNotIn("name: frontend-design", text)
        self.assertNotIn("`taste`", text)

    def test_skill_resources_are_self_locating_and_search_is_bounded(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        for requirement in (
            "相对当前加载的 `SKILL.md` 所在目录解析",
            "检索最多两次",
            "不代表完成用户研究",
            "--persist --output-dir",
            "第三方来源与修改边界",
        ):
            self.assertIn(requirement, text)

    def test_openai_metadata_is_chinese_first_and_implicitly_invokable(self) -> None:
        metadata = (SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn('display_name: "Gloamere UI 系统"', metadata)
        self.assertIn("$gloamere-ui-system", metadata)
        self.assertIn("allow_implicit_invocation: true", metadata)
        self.assertNotIn("$frontend-design", metadata)


if __name__ == "__main__":
    unittest.main()
