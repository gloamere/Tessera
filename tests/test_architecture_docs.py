from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "docs" / "decisions"
CURRENT_DECISION = "git-marketplace-v4-release"


class ArchitectureDocsTests(unittest.TestCase):
    def test_current_index_points_to_marketplace_decision_and_migration(self) -> None:
        index = (ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
        self.assertIn(f"decisions/{CURRENT_DECISION}.md", index)
        self.assertIn("../MIGRATION.md", index)
        self.assertIn("gloamere-eval", index)
        self.assertIn("gloamere-workflows", index)

    def test_marketplace_workflows_decision_is_accepted(self) -> None:
        text = (DECISIONS / f"{CURRENT_DECISION}.md").read_text(encoding="utf-8")
        status = re.search(r"^status:\s*(.+)$", text, re.MULTILINE)
        self.assertIsNotNone(status)
        self.assertEqual(status.group(1), "accepted")
        for token in (
            "Git marketplace",
            "release-manifest.json",
            "4.0.0",
            "1.0.0",
            "gloamere-eval",
            "gloamere-workflows",
        ):
            self.assertIn(token, text)

    def test_historical_decisions_remain_available(self) -> None:
        for decision in (
            "business-workflow-suite-admission",
            "professional-skill-portfolio",
            "self-contained-plugin-distribution",
            "eval-lab-incubation",
        ):
            self.assertTrue((DECISIONS / f"{decision}.md").is_file())

    def test_existing_supersession_chain_is_preserved(self) -> None:
        expected = {
            "native-routing-reliability-layer": "current-runtime-architecture",
            "native-first-runtime-simplification": "current-runtime-architecture",
            "current-runtime-architecture": "frontend-design-core-admission",
            "frontend-design-core-admission": "business-workflow-suite-admission",
            "codex-only-v4-release": "universal-workflows-v4-release",
            "universal-workflows-v4-release": "git-marketplace-v4-release",
        }
        for decision, replacement in expected.items():
            text = (DECISIONS / f"{decision}.md").read_text(encoding="utf-8")
            status = re.search(r"^status:\s*(.+)$", text, re.MULTILINE)
            superseded_by = re.search(
                r"^superseded_by:\s*(.+)$", text, re.MULTILINE
            )
            self.assertEqual(status.group(1), "superseded")
            self.assertEqual(superseded_by.group(1), replacement)

    def test_public_docs_describe_only_current_openai_v4_surface(self) -> None:
        for name in ("README.md", "docs/ARCHITECTURE.md", "docs/DEPLOYMENT.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("Gloamere", text)
            self.assertNotIn("Claude Code", text)
            self.assertNotIn(".claude-plugin", text)
            self.assertNotIn("gloamere/Tessera", text)

    def test_readme_points_to_current_decision_and_migration(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(
            f"docs/decisions/{CURRENT_DECISION}.md",
            readme,
        )
        self.assertIn("MIGRATION.md", readme)

    def test_marketplace_support_and_migration_do_not_wait_for_directory(self) -> None:
        support = (ROOT / "SUPPORT.md").read_text(encoding="utf-8")
        migration = (ROOT / "MIGRATION.md").read_text(encoding="utf-8")
        architecture = (ROOT / "docs" / "ARCHITECTURE.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("Git marketplace release candidate", support)
        self.assertIn("intended Workflows targets", support)
        self.assertIn("pre-release smoke-test gate", support)
        self.assertNotIn("support begins only after the universal-directory", support)

        self.assertIn("After the immutable `v4.0.0` tag", migration)
        self.assertIn("explicit local checkout", migration)
        self.assertNotIn("After directory publication", migration)

        self.assertIn("intended repository-marketplace targets", architecture)
        self.assertIn("ChatGPT desktop smoke test", architecture)


if __name__ == "__main__":
    unittest.main()
