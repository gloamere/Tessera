from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PIECES = ROOT / "pieces"
BUSINESS_SKILLS = ("finance-ops", "growth-ops", "product-planning", "business-ops")


class BusinessSkillTests(unittest.TestCase):
    def skill_text(self, name: str) -> str:
        return (PIECES / name / "skills" / name / "SKILL.md").read_text(encoding="utf-8")

    def test_plugins_are_minimal_self_contained_skills(self) -> None:
        for name in BUSINESS_SKILLS:
            root = PIECES / name
            self.assertTrue((root / "piece.yaml").is_file())
            self.assertTrue((root / ".claude-plugin" / "plugin.json").is_file())
            manifest = json.loads((root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["name"], name)
            self.assertEqual(manifest["skills"], "./skills/")
            self.assertNotIn("mcpServers", manifest)
            self.assertNotIn("apps", manifest)
            self.assertNotIn("TODO", self.skill_text(name))

    def test_finance_requires_traceability_controls_and_human_review(self) -> None:
        text = self.skill_text("finance-ops")
        for token in ("数据来源", "假设", "勾稽", "异常清单", "默认只读", "专业人员复核"):
            self.assertIn(token, text)
        for prohibited in ("不得发起付款", "修改账簿", "提交凭证", "报税"):
            self.assertIn(prohibited, text)

    def test_growth_closes_the_measurement_loop(self) -> None:
        text = self.skill_text("growth-ops")
        for token in ("当前基线", "主指标", "护栏指标", "成功阈值", "复盘", "继续、停止、调整、待验证"):
            self.assertIn(token, text)

    def test_product_planning_keeps_previous_planner_failure_fields(self) -> None:
        text = self.skill_text("product-planning")
        for token in ("不做/延后", "成功指标", "失败/停止阈值", "风险", "开放问题", "下一验证动作"):
            self.assertIn(token, text)

    def test_business_ops_has_approval_and_rollback_boundaries(self) -> None:
        text = self.skill_text("business-ops")
        for token in ("审批人", "回退方案", "RACI", "升级路径", "不签合同", "不批准变更"):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
