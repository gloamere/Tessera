import json
import re
import unittest
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUITE_PATH = ROOT / "eval-suites" / "gloamere-workflows" / "admission-v1.json"
PLUGIN_ID = "gloamere-workflows"
SKILL_IDS = frozenset(
    {
        "gloamere-ui-system",
        "gloamere-visual-review",
        "gloamere-knowledge-capture",
        "gloamere-product-decision",
    }
)
LANGUAGES = frozenset({"zh-CN", "en"})
EXPECTED_COUNTS = {
    "positive": 6,
    "adjacent-negative": 8,
    "multi-intent": 3,
}


def _tag_value(case, prefix):
    values = [tag.removeprefix(prefix) for tag in case["tags"] if tag.startswith(prefix)]
    if len(values) != 1:
        raise AssertionError(f"{case['id']} must have exactly one {prefix} tag")
    return values[0]


class WorkflowAdmissionSuiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite = json.loads(SUITE_PATH.read_text(encoding="utf-8"))
        cls.cases = cls.suite["cases"]

    def test_suite_identity_and_execution_policy(self):
        self.assertEqual(self.suite["schema_version"], 1)
        self.assertEqual(self.suite["plugin_id"], PLUGIN_ID)
        self.assertEqual(
            self.suite["execution_policy"],
            {"repeat": 3, "independent_batches": 2},
        )

    def test_case_ids_are_unique_and_fields_are_public(self):
        ids = [case["id"] for case in self.cases]
        self.assertEqual(len(ids), len(set(ids)))
        required = {
            "id",
            "plugin_id",
            "prompt",
            "expected_skills",
            "forbidden_skills",
            "language",
            "tags",
        }
        for case in self.cases:
            self.assertEqual(set(case), required, case["id"])
            self.assertTrue(case["prompt"].strip(), case["id"])
            self.assertIsInstance(case["tags"], list, case["id"])
            self.assertTrue(case["tags"], case["id"])

    def test_counts_per_skill_kind_and_language(self):
        counts = Counter()
        for case in self.cases:
            focus = _tag_value(case, "focus:")
            kind = _tag_value(case, "kind:")
            counts[(focus, kind, case["language"])] += 1

        self.assertEqual(len(self.cases), len(SKILL_IDS) * sum(EXPECTED_COUNTS.values()) * 2)
        for skill_id in SKILL_IDS:
            for language in LANGUAGES:
                for kind, expected in EXPECTED_COUNTS.items():
                    self.assertEqual(
                        counts[(skill_id, kind, language)],
                        expected,
                        (skill_id, kind, language),
                    )

    def test_plugin_and_skill_ids_use_exact_allowlists(self):
        for case in self.cases:
            self.assertEqual(case["plugin_id"], PLUGIN_ID, case["id"])
            self.assertIn(case["language"], LANGUAGES, case["id"])
            expected = case["expected_skills"]
            forbidden = case["forbidden_skills"]
            self.assertEqual(len(expected), len(set(expected)), case["id"])
            self.assertEqual(len(forbidden), len(set(forbidden)), case["id"])
            self.assertLessEqual(set(expected), SKILL_IDS, case["id"])
            self.assertLessEqual(set(forbidden), SKILL_IDS, case["id"])
            self.assertFalse(set(expected) & set(forbidden), case["id"])
            self.assertEqual(set(expected) | set(forbidden), SKILL_IDS, case["id"])

    def test_case_semantics_match_kind(self):
        multi_partners = defaultdict(set)
        for case in self.cases:
            focus = _tag_value(case, "focus:")
            kind = _tag_value(case, "kind:")
            expected = set(case["expected_skills"])
            forbidden = set(case["forbidden_skills"])
            self.assertIn(focus, SKILL_IDS, case["id"])
            self.assertIn("admission", case["tags"], case["id"])

            if kind == "positive":
                self.assertEqual(expected, {focus}, case["id"])
            elif kind == "adjacent-negative":
                self.assertNotIn(focus, expected, case["id"])
                self.assertIn(focus, forbidden, case["id"])
            elif kind == "multi-intent":
                self.assertIn(focus, expected, case["id"])
                self.assertEqual(len(expected), 2, case["id"])
                if case["language"] == "zh-CN":
                    multi_partners[focus].add(next(iter(expected - {focus})))
            else:
                self.fail(f"unknown kind {kind!r} in {case['id']}")

        for focus in SKILL_IDS:
            self.assertEqual(multi_partners[focus], SKILL_IDS - {focus}, focus)

    def test_chinese_and_english_cases_are_mirrored(self):
        mirrors = defaultdict(dict)
        for case in self.cases:
            base_id, separator, suffix = case["id"].rpartition(".")
            self.assertEqual(separator, ".", case["id"])
            expected_suffix = {"zh-CN": "zh", "en": "en"}[case["language"]]
            self.assertEqual(suffix, expected_suffix, case["id"])
            mirrors[base_id][case["language"]] = case

        for base_id, pair in mirrors.items():
            self.assertEqual(set(pair), LANGUAGES, base_id)
            zh_case = pair["zh-CN"]
            en_case = pair["en"]
            self.assertEqual(zh_case["plugin_id"], en_case["plugin_id"], base_id)
            self.assertEqual(zh_case["expected_skills"], en_case["expected_skills"], base_id)
            self.assertEqual(zh_case["forbidden_skills"], en_case["forbidden_skills"], base_id)
            self.assertEqual(zh_case["tags"], en_case["tags"], base_id)
            self.assertNotEqual(zh_case["prompt"], en_case["prompt"], base_id)

    def test_prompts_do_not_name_products_or_skills(self):
        forbidden_terms = [
            "gloamere",
            "skill",
            "技能",
            *SKILL_IDS,
        ]
        pattern = re.compile("|".join(re.escape(term) for term in forbidden_terms), re.IGNORECASE)
        for case in self.cases:
            self.assertIsNone(pattern.search(case["prompt"]), case["id"])


if __name__ == "__main__":
    unittest.main()
