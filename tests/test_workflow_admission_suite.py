import json
import hashlib
import re
import unittest
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUITE_PATH = ROOT / "eval-suites" / "gloamere-workflows" / "admission-v2.json"
POLICY_PATH = ROOT / "eval-suites" / "gloamere-workflows" / "risk-tiered-v2.json"
QUALITY_PATH = ROOT / "eval-suites" / "gloamere-workflows" / "quality-v1.json"
RELEASE_PATH = ROOT / "release-manifest.json"
PLUGIN_ID = "gloamere-workflows"
SKILL_IDS = frozenset(
    {
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
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        cls.quality = json.loads(QUALITY_PATH.read_text(encoding="utf-8"))
        cls.release = json.loads(RELEASE_PATH.read_text(encoding="utf-8"))

    def test_suite_identity_and_execution_policy(self):
        self.assertEqual(self.suite["schema_version"], 2)
        self.assertEqual(self.suite["plugin_id"], PLUGIN_ID)
        self.assertEqual(
            self.suite["execution_policy"],
            {
                "policy_id": "risk-tiered-v2",
                "repeat": 1,
                "independent_batches": 1,
            },
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

    def test_risk_policy_is_bounded_and_references_public_cases(self):
        case_ids = {case["id"] for case in self.cases}
        self.assertEqual(self.policy["policy_id"], "risk-tiered-v2")
        modes = self.policy["modes"]
        self.assertEqual(modes["pr"]["max_calls"], 12)
        self.assertEqual(modes["release"]["max_calls"], 40)
        self.assertEqual(modes["exhaustive"]["initial_calls"], 102)
        self.assertEqual(modes["exhaustive"]["max_calls"], 120)
        self.assertEqual(modes["exhaustive"]["case_ids"], ["*"])

        pr_ids = set()
        for skill_id, selected in modes["pr"]["per_focus_case_ids"].items():
            self.assertIn(skill_id, SKILL_IDS)
            self.assertEqual(len(selected), 4)
            self.assertLessEqual(set(selected), case_ids)
            pr_ids.update(selected)
        self.assertEqual(len(pr_ids), 12)

        release = modes["release"]
        self.assertEqual(len(release["fixed_case_ids"]), 6)
        self.assertEqual(len(release["multi_intent_case_ids"]), 4)
        self.assertEqual(release["rotating_count"], 6)
        self.assertGreater(len(release["rotating_case_ids"]), 6)
        configured_ids = (
            release["fixed_case_ids"]
            + release["rotating_case_ids"]
            + release["multi_intent_case_ids"]
        )
        self.assertEqual(len(configured_ids), len(set(configured_ids)))
        self.assertLessEqual(set(configured_ids), case_ids)
        case_by_id = {case["id"]: case for case in self.cases}
        rotating_cases = [
            case_by_id[case_id] for case_id in release["rotating_case_ids"]
        ]
        self.assertTrue(
            all(
                "kind:adjacent-negative" in case["tags"]
                and "risk:ordinary" in case["tags"]
                for case in rotating_cases
            )
        )
        all_changed = set(
            release["fixed_case_ids"] + release["multi_intent_case_ids"]
        )
        for skill_id, selected in release["per_focus_case_ids"].items():
            self.assertIn(skill_id, SKILL_IDS)
            self.assertEqual(len(selected), 4)
            self.assertLessEqual(set(selected), case_ids)
            self.assertFalse(set(selected) & set(release["rotating_case_ids"]))
            all_changed.update(selected)
        self.assertEqual(len(all_changed) + release["rotating_count"], 28)
        quality_calls = (
            self.policy["quality"]["release_cases_per_changed_skill"]
            * len(SKILL_IDS)
        )
        self.assertLessEqual(
            len(all_changed) + release["rotating_count"] + quality_calls,
            release["max_calls"],
        )

    def test_quality_suite_has_two_semantic_rubrics_per_skill(self):
        counts = Counter()
        required_rubric = {
            "evidence_fidelity",
            "actionability",
            "boundary_compliance",
            "no_fabrication",
        }
        suite_root = QUALITY_PATH.parent.resolve()
        for case in self.quality["cases"]:
            self.assertIn(case["skill_id"], SKILL_IDS)
            self.assertIn(case["language"], LANGUAGES)
            counts[(case["skill_id"], case["language"])] += 1
            self.assertEqual(set(case["rubric"]), required_rubric)
            for value in case["rubric"].values():
                self.assertTrue(value.strip())
            for relative_path in case["fixture_paths"]:
                fixture = (QUALITY_PATH.parent / relative_path).resolve()
                fixture.relative_to(suite_root)
                self.assertTrue(fixture.is_file(), relative_path)
        self.assertEqual(len(self.quality["cases"]), 6)
        for skill_id in SKILL_IDS:
            for language in LANGUAGES:
                self.assertEqual(counts[(skill_id, language)], 1)

    def test_release_manifest_locks_suite_policy_quality_and_skill_hashes(self):
        workflows = next(
            plugin
            for plugin in self.release["plugins"]
            if plugin["id"] == PLUGIN_ID
        )
        admission = workflows["admission"]
        for path, field in (
            (SUITE_PATH, "suite_sha256"),
            (POLICY_PATH, "policy_sha256"),
            (QUALITY_PATH, "quality_suite_sha256"),
        ):
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                admission[field],
            )
        for skill_id in SKILL_IDS:
            skill = (
                ROOT
                / "plugins"
                / PLUGIN_ID
                / "skills"
                / skill_id
                / "SKILL.md"
            )
            self.assertEqual(
                hashlib.sha256(skill.read_bytes()).hexdigest(),
                admission["target_sha256"][skill_id],
            )


if __name__ == "__main__":
    unittest.main()
