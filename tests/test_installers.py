from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
POSIX_SHELL = shutil.which("sh") or shutil.which("bash")


class InstallerTests(unittest.TestCase):
    def test_installers_use_only_native_codex_plugin_commands(self) -> None:
        for name in ("install.ps1", "install.sh"):
            source = (ROOT / name).read_text(encoding="utf-8")
            for token in ("plugin", "marketplace", "add"):
                self.assertIn(token, source)
            self.assertIn("plugin add", source)
            self.assertIn("plugin list --json", source)
            self.assertNotIn("planner", source)
            self.assertNotIn("pip install", source)
            self.assertNotIn("git clone", source)

    @unittest.skipUnless(POSIX_SHELL, "POSIX shell is unavailable")
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

    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell is unavailable")
    def test_powershell_installer_has_valid_syntax(self) -> None:
        command = (
            "$errors = $null; "
            "[System.Management.Automation.Language.Parser]::ParseFile("
            f"'{ROOT / 'install.ps1'}', [ref]$null, [ref]$errors) | Out-Null; "
            "if ($errors.Count) { $errors | ForEach-Object { Write-Error $_ }; exit 1 }"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_maintenance_entrypoints_cover_the_complete_check_surface(self) -> None:
        for name in ("scripts/check.ps1", "scripts/check.sh"):
            source = (ROOT / name).read_text(encoding="utf-8")
            for token in (
                "validate_marketplace.py",
                "unittest",
                "fake_eval_host.py",
                "personal-routing-cases.json",
                "--dry-run",
                "PYTHONUTF8",
                "PYTHONIOENCODING",
            ):
                self.assertIn(token, source, f"{name} is missing {token}")

    def test_ci_uses_complete_checks_on_linux_and_windows(self) -> None:
        for name in ("validate.yml", "release.yml"):
            source = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
            for token in (
                "ubuntu-latest",
                "macos-latest",
                "windows-latest",
                "scripts/check.sh",
                "scripts/check.ps1",
                "requirements-dev.txt",
                "cache-dependency-path: requirements-dev.txt",
            ):
                self.assertIn(token, source, f"{name} is missing {token}")

    @unittest.skipUnless(POSIX_SHELL, "POSIX shell is unavailable")
    def test_posix_maintenance_scripts_have_valid_shell_syntax(self) -> None:
        for name in ("scripts/check.sh", "scripts/run_native_eval.sh"):
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

    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell is unavailable")
    def test_powershell_maintenance_scripts_have_valid_syntax(self) -> None:
        paths = [ROOT / "scripts" / name for name in ("check.ps1", "run_native_eval.ps1")]
        quoted = ", ".join(f"'{path}'" for path in paths)
        command = (
            f"$paths = @({quoted}); $failed = $false; "
            "foreach ($path in $paths) { $errors = $null; "
            "[System.Management.Automation.Language.Parser]::ParseFile($path, [ref]$null, [ref]$errors) | Out-Null; "
            "if ($errors.Count) { $errors | ForEach-Object { Write-Error $_ }; $failed = $true } }; "
            "if ($failed) { exit 1 }"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
