from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest
from unittest import mock

from scripts import generate_release_files, validate_marketplace


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
# 根因：托管 runner 首次启动 pwsh 偶发超过 15 秒；修复要点：只放宽 PowerShell 进程预算，断言与安装器行为不变。
POWERSHELL_PROCESS_TIMEOUT_SECONDS = 45


class InstallerTests(unittest.TestCase):
    def test_git_marketplace_publication_state_is_fail_closed(self) -> None:
        def state_errors(
            release_status: str,
            directory_status: str,
            directory_url: str | None,
        ) -> list[str]:
            candidate = copy.deepcopy(RELEASE)
            distribution = candidate["distribution"]
            distribution["releaseStatus"] = release_status
            distribution["directoryStatus"] = directory_status
            distribution["directoryURL"] = directory_url
            errors: list[str] = []
            validate_marketplace.validate_release_identity(candidate, errors)
            return errors

        self.assertFalse(
            state_errors("release-candidate", "optional", None)
        )
        self.assertTrue(
            any(
                "directoryURL" in error
                for error in state_errors(
                    "release-candidate",
                    "approved",
                    None,
                )
            )
        )
        self.assertTrue(
            any(
                "directoryURL" in error
                for error in state_errors(
                    "release-candidate",
                    "submitted",
                    "https://example.com/listing",
                )
            )
        )
        self.assertFalse(
            state_errors(
                "release-candidate",
                "approved",
                "https://example.com/listing",
            )
        )
        self.assertFalse(state_errors("published", "optional", None))
        with mock.patch.dict(
            os.environ,
            {"GITHUB_REF_TYPE": "tag", "GITHUB_REF_NAME": "v4.0.0"},
        ):
            self.assertTrue(
                any(
                    "tag 发布" in error
                    for error in state_errors(
                        "release-candidate",
                        "approved",
                        "https://example.com/listing",
                    )
                )
            )
            self.assertFalse(
                state_errors(
                    "published",
                    "optional",
                    None,
                )
            )

    def test_release_manifest_defines_maturity_and_install_profiles(self) -> None:
        distribution = RELEASE["distribution"]
        self.assertEqual(
            distribution["installProfiles"],
            {
                "workflows": ["gloamere-workflows"],
                "maintainer": ["gloamere-eval"],
                "complete": ["gloamere-workflows", "gloamere-eval"],
            },
        )
        website_package = json.loads(
            (ROOT / "website" / "package.json").read_text(encoding="utf-8")
        )
        self.assertEqual(website_package["version"], distribution["version"])
        self.assertEqual(
            {plugin["id"]: plugin["maturity"] for plugin in RELEASE["plugins"]},
            {
                "gloamere-eval": "beta",
                "gloamere-workflows": "stable",
            },
        )
        self.assertEqual(
            {plugin["id"]: plugin["publicRole"] for plugin in RELEASE["plugins"]},
            {
                "gloamere-eval": "maintainer",
                "gloamere-workflows": "public",
            },
        )
        self.assertEqual(distribution["distributionChannel"], "git-marketplace")
        self.assertEqual(
            distribution["marketplaceSource"],
            "gloamere/codex-plugins",
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
        marketplace_source = distribution["marketplaceSource"]
        for name in ("install.ps1", "install.sh"):
            source = (ROOT / name).read_text(encoding="utf-8")
            for token in (
                marketplace_source,
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
            index["distributionChannel"],
            RELEASE["distribution"]["distributionChannel"],
        )
        self.assertEqual(
            index["marketplaceSource"],
            RELEASE["distribution"]["marketplaceSource"],
        )
        self.assertEqual(
            [plugin["id"] for plugin in index["plugins"]],
            [plugin["id"] for plugin in RELEASE["plugins"]],
        )
        self.assertEqual(
            index["installProfiles"],
            RELEASE["distribution"]["installProfiles"],
        )
        self.assertEqual(
            index["directoryURL"],
            RELEASE["distribution"]["directoryURL"],
        )
        self.assertEqual(
            [plugin["maturity"] for plugin in index["plugins"]],
            [plugin["maturity"] for plugin in RELEASE["plugins"]],
        )
        self.assertEqual(
            [plugin["skills"] for plugin in index["plugins"]],
            [plugin["skills"] for plugin in RELEASE["plugins"]],
        )
        self.assertIsNone(index["releaseURL"])
        self.assertIsNone(index["manifestURL"])
        for plugin in index["plugins"]:
            self.assertIsNone(plugin["archiveURL"])
            self.assertIsNone(plugin["checksumURL"])

        published_release = copy.deepcopy(RELEASE)
        published_release["distribution"]["releaseStatus"] = "published"
        published_index = generate_release_files.build_release_index(
            published_release
        )
        self.assertTrue(published_index["releaseURL"].startswith("https://"))
        self.assertTrue(published_index["manifestURL"].startswith("https://"))
        for plugin in published_index["plugins"]:
            self.assertTrue(plugin["archiveURL"].startswith("https://"))
            self.assertTrue(plugin["checksumURL"].startswith("https://"))
        for plugin in RELEASE["plugins"]:
            plugin_manifest = json.loads(
                (
                    ROOT
                    / plugin["path"]
                    / ".codex-plugin"
                    / "plugin.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(plugin_manifest["version"], plugin["version"])
        generated = (ROOT / "website" / "app" / "generated-release.ts").read_text(
            encoding="utf-8"
        )
        payload = generated.split("export const releaseData = ", 1)[1].split(
            " as const;", 1
        )[0]
        website_release = json.loads(payload)
        self.assertEqual(
            website_release["releaseVersion"],
            RELEASE["distribution"]["version"],
        )
        self.assertEqual(
            website_release["distributionChannel"],
            RELEASE["distribution"]["distributionChannel"],
        )
        self.assertEqual(
            website_release["marketplaceSource"],
            RELEASE["distribution"]["marketplaceSource"],
        )
        self.assertEqual(
            website_release["directoryStatus"],
            RELEASE["distribution"]["directoryStatus"],
        )
        self.assertEqual(
            website_release["directoryURL"],
            RELEASE["distribution"]["directoryURL"],
        )
        self.assertEqual(
            website_release["installProfiles"],
            RELEASE["distribution"]["installProfiles"],
        )

    def test_installers_expose_all_manifest_profiles_with_workflows_default(self):
        profiles = RELEASE["distribution"]["installProfiles"]

        powershell = (ROOT / "install.ps1").read_text(encoding="utf-8")
        powershell_profiles = {
            profile: re.findall(r"'([a-z0-9-]+)'", values)
            for profile, values in re.findall(
                r"(?m)^\s*'(workflows|maintainer|complete)'\s*"
                r"\{\s*@\(([^)]*)\)\s*\}\s*$",
                powershell,
            )
        }
        self.assertIn(
            "[string]$Profile = 'workflows'",
            powershell,
        )
        self.assertIn("if ($All)", powershell)
        self.assertEqual(powershell_profiles, profiles)

        posix = (ROOT / "install.sh").read_text(encoding="utf-8")
        posix_profiles = {
            profile: values.split()
            for profile, values in re.findall(
                r"(?m)^\s*(workflows|maintainer|complete)\)\s*"
                r"PLUGINS='([^']*)'\s*;;\s*$",
                posix,
            )
        }
        self.assertIn("PROFILE=${GLOAMERE_PROFILE:-workflows}", posix)
        self.assertIn("--profile)", posix)
        self.assertIn("--all)", posix)
        self.assertEqual(posix_profiles, profiles)

    def test_candidate_installers_allow_only_explicit_local_sources(self) -> None:
        powershell = (ROOT / "install.ps1").read_text(encoding="utf-8")
        self.assertIn("$PSBoundParameters.ContainsKey('Source')", powershell)
        self.assertIn("$releaseStatus -ne 'published'", powershell)
        self.assertIn("existing local repository checkout", powershell)

        posix = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn("SOURCE_WAS_EXPLICIT", posix)
        self.assertIn('"$RELEASE_STATUS" != published', posix)
        self.assertIn("existing local repository checkout", posix)

    @unittest.skipUnless(POWERSHELL, "PowerShell is unavailable")
    def test_candidate_powershell_installer_rejects_remote_source(self) -> None:
        result = subprocess.run(
            [
                POWERSHELL,
                "-NoProfile",
                "-File",
                str(ROOT / "install.ps1"),
                "-Source",
                "https://example.invalid/gloamere.git",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=POWERSHELL_PROCESS_TIMEOUT_SECONDS,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "remote installation is unavailable",
            result.stdout + result.stderr,
        )

    @unittest.skipUnless(POSIX_SHELL, "usable POSIX shell is unavailable")
    def test_candidate_posix_installer_rejects_remote_source(self) -> None:
        result = subprocess.run(
            [
                POSIX_SHELL,
                "install.sh",
                "--source",
                "https://example.invalid/gloamere.git",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 4)
        self.assertIn(
            "remote installation is unavailable",
            result.stdout + result.stderr,
        )

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
            timeout=POWERSHELL_PROCESS_TIMEOUT_SECONDS,
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
                "validate_release_evidence.py",
                "validate_quality_evidence.py",
                "unittest",
                "inspect",
                "lint",
                "gloamere-eval",
                "gloamere-workflows",
                "target-lock.json",
                "empty_plugin_catalog.json",
                "PYTHONUTF8",
                "PYTHONIOENCODING",
            ):
                self.assertIn(token, source, f"{name} is missing {token}")
            self.assertNotIn("--host claude", source)
            self.assertNotIn("'--host', 'claude'", source)
            self.assertNotIn("validate_directory_submission.py", source)

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
            self.assertIn(
                "npm audit --audit-level=high --omit=dev",
                source,
                f"{name} is missing the production dependency audit",
            )

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
        self.assertIn("--expect-commit", workflow)
        self.assertIn('"release-provenance.json"', workflow)
        self.assertIn("validate_quality_evidence.py --require", workflow)
        self.assertNotIn("--require-exhaustive", workflow)
        self.assertNotIn("validate_directory_submission.py --require-complete", workflow)
        self.assertIn("npm audit --audit-level=high --omit=dev", workflow)
        self.assertNotIn("--prerelease", workflow)
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
            timeout=POWERSHELL_PROCESS_TIMEOUT_SECONDS,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
