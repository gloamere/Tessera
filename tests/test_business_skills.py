from __future__ import annotations

import hashlib
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
PUBLISHED_ROOT = ROOT / "plugins" / "gloamere-workflows" / "skills"
EXPERIMENT_ROOT = ROOT / "experiments" / "workflows"
PUBLISHED_SKILLS = (
    "gloamere-ui-system",
    "gloamere-visual-review",
    "gloamere-knowledge-capture",
    "gloamere-product-decision",
)
EXPERIMENTAL_SKILLS = (
    "gloamere-finance-ops",
    "gloamere-growth-loop",
    "gloamere-internal-ops",
)
DISPLAY_NAMES = {
    "gloamere-ui-system": "Gloamere UI 系统",
    "gloamere-visual-review": "Gloamere 视觉评审",
    "gloamere-knowledge-capture": "Gloamere 知识沉淀",
    "gloamere-product-decision": "Gloamere 产品决策",
    "gloamere-finance-ops": "Gloamere 财务运营",
    "gloamere-growth-loop": "Gloamere 增长闭环",
    "gloamere-internal-ops": "Gloamere 内部运营",
}
LEGACY_IDS = (
    "frontend-design",
    "taste",
    "knowledge-base",
    "product-planning",
    "finance-ops",
    "growth-ops",
    "business-ops",
)


class BusinessSkillTests(unittest.TestCase):
    def skill_text(self, name: str) -> str:
        root = PUBLISHED_ROOT if name in PUBLISHED_SKILLS else EXPERIMENT_ROOT
        return (root / name / "SKILL.md").read_text(encoding="utf-8")

    def skill_root(self, name: str) -> Path:
        root = PUBLISHED_ROOT if name in PUBLISHED_SKILLS else EXPERIMENT_ROOT
        return root / name

    def test_ids_folders_and_openai_metadata_are_consistent(self) -> None:
        for name in (*PUBLISHED_SKILLS, *EXPERIMENTAL_SKILLS):
            with self.subTest(name=name):
                root = self.skill_root(name)
                text = self.skill_text(name)
                metadata = (root / "agents" / "openai.yaml").read_text(encoding="utf-8")
                self.assertIn(f"name: {name}", text)
                self.assertNotIn("TODO", text)
                self.assertIn(f"${name}", metadata)
                self.assertIn("allow_implicit_invocation: true", metadata)
                self.assertIn(
                    f'display_name: "{DISPLAY_NAMES[name]}"',
                    metadata,
                )

                match = re.search(r'short_description: "([^"]+)"', metadata)
                self.assertIsNotNone(match)
                self.assertGreaterEqual(len(match.group(1)), 25)
                self.assertLessEqual(len(match.group(1)), 64)

                for legacy_id in LEGACY_IDS:
                    self.assertNotIn(f"name: {legacy_id}\n", text)
                    self.assertNotIn(f"${legacy_id} ", metadata)

    def test_experimental_skills_remain_outside_published_plugin(self) -> None:
        published_text = "\n".join(self.skill_text(name) for name in PUBLISHED_SKILLS)
        for name in EXPERIMENTAL_SKILLS:
            self.assertTrue((EXPERIMENT_ROOT / name / "SKILL.md").is_file())
            self.assertFalse((PUBLISHED_ROOT / name).exists())
            self.assertNotIn(name, published_text)
        self.assertFalse(any(EXPERIMENT_ROOT.rglob("plugin.json")))

    def test_visual_review_is_evidence_based_and_clean_room(self) -> None:
        text = self.skill_text("gloamere-visual-review")
        for token in (
            "可见证据",
            "不把个人偏好",
            "P0/P1/P2",
            "gloamere-ui-system",
            "没有足够视觉证据",
        ):
            self.assertIn(token, text)
        for legacy_phrase in ("六维评审", "反套路清单", "紫蓝渐变", "Elevate / Seamless / Unleash"):
            self.assertNotIn(legacy_phrase, text)

    def test_knowledge_capture_preserves_repository_conventions(self) -> None:
        text = self.skill_text("gloamere-knowledge-capture")
        for token in (
            "目标目录",
            "相同标题",
            "aliases",
            "sources",
            "owner",
            "断链",
            "Token",
        ):
            self.assertIn(token, text)
        for legacy_phrase in ("个人知识库", "一则一事", "双链代替目录", "llama_index", "milvus"):
            self.assertNotIn(legacy_phrase, text)

    def test_product_decision_retains_decision_safety_fields(self) -> None:
        text = self.skill_text("gloamere-product-decision")
        for token in (
            "维持现状或延后",
            "护栏指标",
            "停止条件",
            "主要风险",
            "开放问题",
            "下一验证动作",
            "不模拟受访者",
            "独立的增长执行流程",
        ):
            self.assertIn(token, text)
        self.assertNotIn("gloamere-growth-loop", text)
        self.assertNotIn("产品策划", text)

    def test_original_workflow_provenance_hashes_match_current_files(self) -> None:
        provenance = (
            ROOT / "plugins" / "gloamere-workflows" / "PROVENANCE.md"
        ).read_text(encoding="utf-8")
        for name in (
            "gloamere-visual-review",
            "gloamere-knowledge-capture",
            "gloamere-product-decision",
        ):
            with self.subTest(name=name):
                digest = hashlib.sha256(
                    (PUBLISHED_ROOT / name / "SKILL.md").read_bytes()
                ).hexdigest()
                row = re.search(
                    rf"^\| `{re.escape(name)}` \| `[^`]+` \| `([^`]+)` \|",
                    provenance,
                    re.MULTILINE,
                )
                self.assertIsNotNone(row)
                self.assertEqual(row.group(1), digest)

    def test_finance_requires_traceability_controls_and_human_review(self) -> None:
        text = self.skill_text("gloamere-finance-ops")
        for token in ("来源", "假设", "公式", "勾稽", "异常清单", "人工复核点"):
            self.assertIn(token, text)
        for prohibited in ("不发起付款", "不修改账簿", "不提交凭证", "不报税"):
            self.assertIn(prohibited, text)

    def test_growth_closes_the_measurement_loop(self) -> None:
        text = self.skill_text("gloamere-growth-loop")
        for token in (
            "当前基线",
            "主指标",
            "护栏指标",
            "成功阈值",
            "埋点",
            "继续、停止或迭代",
        ):
            self.assertIn(token, text)

    def test_internal_ops_has_approval_escalation_and_rollback_boundaries(self) -> None:
        text = self.skill_text("gloamere-internal-ops")
        for token in (
            "审批人",
            "回退",
            "RACI",
            "升级路径",
            "不签合同",
            "不批准变更",
            "DevOps",
        ):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
