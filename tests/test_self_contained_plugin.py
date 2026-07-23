from __future__ import annotations

import hashlib
import json
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
RELEASE = json.loads((ROOT / "release-manifest.json").read_text(encoding="utf-8"))
EVAL_PLUGIN = ROOT / "plugins" / "gloamere-eval"
EVAL_SKILL = EVAL_PLUGIN / "skills" / "gloamere-skill-eval"


class SelfContainedPluginTests(unittest.TestCase):
    def test_active_release_surface_has_exactly_two_codex_plugins(self) -> None:
        manifests = {
            path.relative_to(ROOT).as_posix()
            for path in ROOT.rglob("plugin.json")
            if path.parent.name == ".codex-plugin"
        }
        expected = {
            f"{plugin['path']}/.codex-plugin/plugin.json"
            for plugin in RELEASE["plugins"]
        }
        self.assertEqual(manifests, expected)
        self.assertFalse((ROOT / ".claude-plugin" / "marketplace.json").exists())

    def test_cached_eval_plugin_starts_without_repository_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            cached_plugin = temp_root / "plugin-cache" / "gloamere-eval"
            workdir = temp_root / "unrelated-project"
            shutil.copytree(EVAL_PLUGIN, cached_plugin)
            workdir.mkdir()

            runner = (
                cached_plugin
                / "skills"
                / "gloamere-skill-eval"
                / "scripts"
                / "run_routing_eval.py"
            )
            environment = {**os.environ, "PYTHONNOUSERSITE": "1"}
            result = subprocess.run(
                [sys.executable, str(runner), "--help"],
                cwd=workdir,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(str(ROOT), result.stdout)

    def test_eval_runtime_uses_only_python_standard_library(self) -> None:
        runner = EVAL_SKILL / "scripts" / "run_routing_eval.py"
        source = runner.read_text(encoding="utf-8")
        self.assertNotIn("import yaml", source)
        self.assertNotIn("site-packages", source)
        self.assertNotIn("requirements-dev.txt", source)

    def test_eval_skill_has_fixed_display_name_and_requires_explicit_use(self) -> None:
        metadata = (EVAL_SKILL / "agents" / "openai.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn('display_name: "Gloamere Skill 评测"', metadata)
        self.assertIn("allow_implicit_invocation: false", metadata)

    def test_release_packager_builds_two_verified_archives(self) -> None:
        with (
            tempfile.TemporaryDirectory() as first,
            tempfile.TemporaryDirectory() as second,
        ):
            for destination in (first, second):
                result = subprocess.run(
                    [
                        sys.executable,
                        "scripts/package_release.py",
                        "--output-dir",
                        destination,
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            output = Path(first)
            second_output = Path(second)
            expected_assets = {
                RELEASE["distribution"]["releaseManifestAsset"],
                RELEASE["distribution"]["releaseIndex"],
            }
            expected_assets.update(
                name
                for plugin in RELEASE["plugins"]
                for name in (plugin["archive"], plugin["checksum"])
            )
            self.assertEqual(
                {path.name for path in output.iterdir() if path.is_file()},
                expected_assets,
            )
            for field in ("releaseManifestAsset", "releaseIndex"):
                name = RELEASE["distribution"][field]
                self.assertEqual(
                    (output / name).read_bytes(),
                    (ROOT / name).read_bytes(),
                )
                self.assertEqual(
                    (output / name).read_bytes(),
                    (second_output / name).read_bytes(),
                )
            for plugin in RELEASE["plugins"]:
                archive = output / plugin["archive"]
                checksum = output / plugin["checksum"]
                self.assertTrue(archive.is_file())
                self.assertTrue(checksum.is_file())
                digest = hashlib.sha256(archive.read_bytes()).hexdigest()
                self.assertEqual(
                    archive.read_bytes(),
                    (second_output / plugin["archive"]).read_bytes(),
                )
                self.assertEqual(
                    checksum.read_text(encoding="utf-8"),
                    f"{digest}  {archive.name}\n",
                )
                with zipfile.ZipFile(archive) as bundle:
                    names = bundle.namelist()
                self.assertTrue(names)
                self.assertTrue(
                    all(name.startswith(f"{plugin['id']}/") for name in names)
                )
                self.assertIn(
                    f"{plugin['id']}/.codex-plugin/plugin.json",
                    names,
                )
                self.assertIn(f"{plugin['id']}/LICENSE", names)
                self.assertFalse(
                    any("__pycache__" in name or name.endswith(".pyc") for name in names)
                )


if __name__ == "__main__":
    unittest.main()
