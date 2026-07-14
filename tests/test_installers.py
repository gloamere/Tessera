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


if __name__ == "__main__":
    unittest.main()
