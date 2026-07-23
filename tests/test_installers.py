from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
RELEASE = json.loads((ROOT / "release-manifest.json").read_text(encoding="utf-8"))


def find_usable_posix_shell() -> str | None:
    """Return a real POSIX shell, excluding Windows launcher/store stubs."""

    seen: set[str] = set()
    for executable in ("sh", "bash"):
        candidate = shutil.which(executable)
        if not candidate:
            continue
        normalized = str(Path(candidate).resolve()).replace("\\", "/").lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        if os.name == "nt" and (
            normalized.endswith("/windows/system32/bash.exe")
            or "/windowsapps/" in normalized
        ):
            # 根因：System32/bash.exe 是 WSL 启动器或商店桩，不支持本测试的
            # Windows 工作目录语义；将它当作 sh 会得到 Access is denied。
            continue
        try:
            probe = subprocess.run(
                [candidate, "-c", ":"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if probe.returncode == 0:
            return candidate
    return None


POSIX_SHELL = find_usable_posix_shell()
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


class InstallerTests(unittest.TestCase):
    def test_release_manifest_defines_maturity_and_install_profiles(self) -> None:
        distribution = RELEASE["distribution"]
        self.assertEqual(
            distribution["installProfiles"],
            {
                "eval": ["gloamere-eval"],
                "complete": ["gloamere-eval", "gloamere-workflows"],
            },
        )
        self.assertEqual(
            {plugin["id"]: plugin["maturity"] for plugin in RELEASE["plugins"]},
            {
                "gloamere-eval": "beta",
                "gloamere-workflows": "beta",
            },
        )

    def test_windows_wsl_launcher_is_not_treated_as_posix_shell(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows-only launcher regression")
        if POSIX_SHELL:
            normalized = str(Path(POSIX_SHELL).resolve()).replace("\\", "/").lower()
            self.assertFalse(normalized.endswith("/windows/system32/bash.exe"))
            self.assertNotIn("/windowsapps/", normalized)

    def test_installers_pin_release_and_use_native_codex_commands(self) -> None:
        distribution = RELEASE["distribution"]
        repository = distribution["repository"].removeprefix("https://github.com/")
        for name in ("install.ps1", "install.sh"):
            source = (ROOT / name).read_text(encoding="utf-8")
            for token in (
                repository,
                distribution["tag"],
                "plugin",
                "marketplace",
                "add",
                "plugin list --json",
                "gloamere-eval",
                "gloamere-workflows",
                "@gloamere",
            ):
                self.assertIn(token, source, f"{name} is missing {token}")
            self.assertNotIn("gloamere/Tessera", source)
            self.assertNotIn("git clone", source)
            self.assertNotIn("pip install", source)

    def test_release_manifest_generates_current_marketplace_and_index(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/generate_release_files.py",
                "--check",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        index = json.loads((ROOT / "release-index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["version"], RELEASE["distribution"]["version"])
        self.assertEqual(
            [plugin["id"] for plugin in index["plugins"]],
            [plugin["id"] for plugin in RELEASE["plugins"]],
        )
        self.assertEqual(
            index["installProfiles"],
            RELEASE["distribution"]["installProfiles"],
        )
        self.assertEqual(
            [plugin["maturity"] for plugin in index["plugins"]],
            [plugin["maturity"] for plugin in RELEASE["plugins"]],
        )

    def test_installer_defaults_and_all_mirror_install_profiles(self) -> None:
        profiles = RELEASE["distribution"]["installProfiles"]

        powershell = (ROOT / "install.ps1").read_text(encoding="utf-8")
        default_match = re.findall(
            r"(?m)^\$plugins\s*=\s*@\(([^)]*)\)\s*$",
            powershell,
        )
        self.assertEqual(len(default_match), 1)
        powershell_default = re.findall(r"'([a-z0-9-]+)'", default_match[0])
        powershell_all = powershell_default + re.findall(
            r"(?m)^\s*\$plugins\s*\+=\s*'([a-z0-9-]+)'\s*$",
            powershell,
        )
        self.assertEqual(powershell_default, profiles["eval"])
        self.assertEqual(powershell_all, profiles["complete"])

        posix = (ROOT / "install.sh").read_text(encoding="utf-8")
        assignments = re.findall(r"(?m)^\s*PLUGINS='([^']*)'\s*$", posix)
        self.assertEqual(len(assignments), 2)
        self.assertEqual(assignments[0].split(), profiles["eval"])
        self.assertEqual(assignments[1].split(), profiles["complete"])

    def test_release_validator_accepts_profile_mirrors(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/validate_marketplace.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_legacy_tessera_handling_is_read_only(self) -> None:
        for name in ("install.ps1", "install.sh"):
            source = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("@tessera", source)
            self.assertIn("MIGRATION.md", source)
            self.assertIn("plugin remove", source)
            self.assertIn("marketplace remove", source)
            self.assertIn("No installation changes were made", source)
            self.assertNotRegex(
                source,
                re.compile(
                    r"(?m)^\s*(?:&\s+\$codex\S*|codex)\s+plugin\s+remove\b"
                ),
            )
            self.assertNotRegex(
                source,
                re.compile(
                    r"(?m)^\s*(?:&\s+\$codex\S*|codex)\s+plugin\s+"
                    r"marketplace\s+remove\b"
                ),
            )

    @unittest.skipUnless(POSIX_SHELL, "usable POSIX shell is unavailable")
    def test_posix_installer_has_valid_shell_syntax(self) -> None:
        result = subprocess.run(
            [POSIX_SHELL, "-n", "install.sh"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(POWERSHELL, "PowerShell is unavailable")
    def test_powershell_installer_has_valid_syntax(self) -> None:
        command = (
            "$errors = $null; "
            "[System.Management.Automation.Language.Parser]::ParseFile("
            f"'{ROOT / 'install.ps1'}', [ref]$null, [ref]$errors) | Out-Null; "
            "if ($errors.Count) { $errors | ForEach-Object { Write-Error $_ }; exit 1 }"
        )
        result = subprocess.run(
            [POWERSHELL, "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_maintenance_entrypoints_cover_complete_codex_checks(self) -> None:
        for name in ("scripts/check.ps1", "scripts/check.sh"):
            source = (ROOT / name).read_text(encoding="utf-8")
            for token in (
                "generate_release_files.py",
                "--check",
                "validate_marketplace.py",
                "unittest",
                "inspect",
                "lint",
                "gloamere-eval",
                "gloamere-workflows",
                "target-lock.json",
                "PYTHONUTF8",
                "PYTHONIOENCODING",
            ):
                self.assertIn(token, source, f"{name} is missing {token}")
            self.assertNotIn("--host claude", source)
            self.assertNotIn("'--host', 'claude'", source)

    def test_ci_uses_complete_checks_on_three_platforms(self) -> None:
        for name in ("validate.yml", "release.yml"):
            source = (ROOT / ".github" / "workflows" / name).read_text(
                encoding="utf-8"
            )
            for token in (
                "ubuntu-latest",
                "macos-latest",
                "windows-latest",
                "scripts/check.sh",
                "scripts/check.ps1",
                "requirements-dev.txt",
                "cache-dependency-path: requirements-dev.txt",
                "npm install --global @openai/codex@0.145.0",
                "test_plugin_lifecycle.ps1 -IncludeLegacyMigration",
            ):
                self.assertIn(token, source, f"{name} is missing {token}")

    def test_validation_covers_python_310_through_314_and_both_powershells(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text(
            encoding="utf-8"
        )
        for version in ("'3.10'", "'3.11'", "'3.12'", "'3.13'", "'3.14'"):
            self.assertIn(version, workflow)
        self.assertIn("shell: powershell", workflow)
        self.assertIn("shell: pwsh", workflow)
        self.assertGreaterEqual(workflow.count("run.ps1 --help"), 2)

    def test_release_workflow_publishes_two_archives_and_checksums(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("scripts/package_release.py", workflow)
        self.assertIn('Path("release-manifest.json")', workflow)
        self.assertIn("dist/*.zip", workflow)
        self.assertIn("dist/*.sha256", workflow)
        self.assertIn("dist/*.json", workflow)
        self.assertIn("actual != expected", workflow)
        self.assertIn('"releaseManifestAsset"', workflow)
        self.assertIn('"releaseIndex"', workflow)
        for plugin in RELEASE["plugins"]:
            self.assertNotIn(plugin["archive"], workflow)

    @unittest.skipUnless(POSIX_SHELL, "usable POSIX shell is unavailable")
    def test_posix_maintenance_scripts_have_valid_shell_syntax(self) -> None:
        for name in (
            "scripts/check.sh",
            "scripts/run_native_eval.sh",
        ):
            result = subprocess.run(
                [POSIX_SHELL, "-n", name],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                check=False,
            )
            self.assertEqual(result.returncode, 0, f"{name}: {result.stderr}")

    @unittest.skipUnless(POWERSHELL, "PowerShell is unavailable")
    def test_powershell_maintenance_scripts_have_valid_syntax(self) -> None:
        paths = [
            ROOT / "scripts" / name
            for name in (
                "check.ps1",
                "run_native_eval.ps1",
                "test_plugin_lifecycle.ps1",
            )
        ]
        quoted = ", ".join(f"'{path}'" for path in paths)
        command = (
            f"$paths = @({quoted}); $failed = $false; "
            "foreach ($path in $paths) { $errors = $null; "
            "[System.Management.Automation.Language.Parser]::ParseFile("
            "$path, [ref]$null, [ref]$errors) | Out-Null; "
            "if ($errors.Count) { $errors | ForEach-Object { Write-Error $_ }; "
            "$failed = $true } }; if ($failed) { exit 1 }"
        )
        result = subprocess.run(
            [POWERSHELL, "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
