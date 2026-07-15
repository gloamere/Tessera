from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "docs" / "decisions"


class ArchitectureDocsTests(unittest.TestCase):
    def test_current_index_points_to_current_runtime_decisions(self) -> None:
        index = (ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
        for decision in (
            "business-workflow-suite-admission",
            "professional-skill-portfolio",
            "self-contained-plugin-distribution",
            "eval-lab-incubation",
        ):
            self.assertIn(f"decisions/{decision}.md", index)

    def test_replaced_runtime_decisions_are_marked_superseded(self) -> None:
        expected = {
            "native-routing-reliability-layer": "current-runtime-architecture",
            "native-first-runtime-simplification": "current-runtime-architecture",
            "current-runtime-architecture": "frontend-design-core-admission",
            "frontend-design-core-admission": "business-workflow-suite-admission",
        }
        for decision, replacement in expected.items():
            text = (DECISIONS / f"{decision}.md").read_text(encoding="utf-8")
            status = re.search(r"^status:\s*(.+)$", text, re.MULTILINE)
            superseded_by = re.search(
                r"^superseded_by:\s*(.+)$", text, re.MULTILINE
            )
            self.assertEqual(status.group(1), "superseded")
            self.assertEqual(superseded_by.group(1), replacement)

    def test_readme_points_to_current_decisions(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/decisions/business-workflow-suite-admission.md", readme)
        self.assertIn("docs/decisions/professional-skill-portfolio.md", readme)


if __name__ == "__main__":
    unittest.main()
