"""Unit tests for scripts/case_schema.py. No model calls."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import case_schema as C  # noqa: E402

REAL = C.read_yaml(ROOT / "tests" / "evaluation-cases.yaml")
REAL_REGRESSION = C.read_yaml(ROOT / "tests" / "regression-cases.yaml")


def mutated(fn):
    data = copy.deepcopy(REAL)
    fn(data)
    return C.validate_evaluation_file(data)


class EvaluationFile(unittest.TestCase):
    def test_real_file_is_valid(self):
        self.assertEqual(C.validate_evaluation_file(REAL), [])

    def test_dimension_list_must_match(self):
        errors = mutated(lambda d: d["scoring_dimensions"].pop())
        self.assertTrue(any("scoring_dimensions" in e for e in errors))

    def test_duplicate_id(self):
        errors = mutated(lambda d: d["cases"].append(copy.deepcopy(d["cases"][0])))
        self.assertTrue(any("duplicate id" in e for e in errors))

    def test_bad_id_language_category(self):
        def change(d):
            d["cases"][0].update(id="Bad Id", language="english", category="nonsense")
        errors = mutated(change)
        for fragment in ("'id' must match", "'language'", "not a known category"):
            self.assertTrue(any(fragment in e for e in errors), fragment)

    def test_missing_and_empty_fields(self):
        def change(d):
            del d["cases"][0]["prompt"]
            d["cases"][0]["expected"] = []
            d["cases"][0]["failure_modes"] = [""]
        errors = mutated(change)
        for fragment in ("'prompt'", "'expected'", "'failure_modes'"):
            self.assertTrue(any(fragment in e for e in errors), fragment)

    def test_unknown_field_and_bad_manual_flag(self):
        def change(d):
            d["cases"][0]["surprise"] = 1
            d["cases"][1]["manual"] = "yes"
        errors = mutated(change)
        self.assertTrue(any("unknown field" in e for e in errors))
        self.assertTrue(any("'manual'" in e for e in errors))

    def test_empty_cases(self):
        self.assertTrue(C.validate_evaluation_file({"version": 1, "scoring_dimensions": C.DIMENSIONS, "cases": []}))

    def test_non_mapping_case(self):
        errors = mutated(lambda d: d["cases"].append("text"))
        self.assertTrue(any("must be a mapping" in e for e in errors))


class Coverage(unittest.TestCase):
    def test_every_required_category_is_present(self):
        present = {c["category"] for c in REAL["cases"]}
        self.assertEqual(set(C.REQUIRED_CATEGORIES) - present, set())

    def test_removing_a_category_is_caught(self):
        errors = mutated(lambda d: d.update(cases=[c for c in d["cases"] if c["category"] != "ambiguous_question"]))
        self.assertTrue(any("'ambiguous_question'" in e for e in errors))

    def test_both_casual_languages_are_required(self):
        errors = mutated(lambda d: d.update(cases=[c for c in d["cases"]
                                                   if not (c["category"] == "casual_conversation" and c["language"] == "es")]))
        self.assertTrue(any("'casual_conversation' case in language 'es'" in e for e in errors))

    def test_spanish_minimum(self):
        errors = mutated(lambda d: d.update(cases=[c for c in d["cases"] if not c["language"].startswith("es")]))
        self.assertTrue(any("Spanish case" in e for e in errors))


def with_case(**overrides):
    data = copy.deepcopy(REAL)
    base = {"id": "scripted", "language": "en", "category": "conversation_continuity", "intent": "x",
            "manual": True, "turns": [{"role": "assistant", "text": "Did you eat?"}, {"role": "user", "text": "Yes."}],
            "expected": ["a"], "failure_modes": ["b"]}
    base.update(overrides)
    data["cases"].append(base)
    return C.validate_evaluation_file(data)


class ScriptedTurns(unittest.TestCase):
    def test_a_valid_transcript_passes(self):
        self.assertEqual(with_case(), [])

    def test_transcript_must_be_manual(self):
        errors = with_case(manual=False)
        self.assertTrue(any("must set 'manual: true'" in e for e in errors))
        data = copy.deepcopy(REAL)
        data["cases"].append({"id": "no_flag", "language": "en", "category": "conversation_continuity", "intent": "x",
                              "turns": [{"role": "assistant", "text": "a"}, {"role": "user", "text": "b"}],
                              "expected": ["a"], "failure_modes": ["b"]})
        self.assertTrue(any("must set 'manual: true'" in e for e in C.validate_evaluation_file(data)))

    def test_prompt_and_turns_are_mutually_exclusive(self):
        self.assertTrue(any("exactly one of" in e for e in with_case(prompt="also a prompt")))
        data = copy.deepcopy(REAL)
        del data["cases"][0]["prompt"]
        self.assertTrue(any("exactly one of" in e for e in C.validate_evaluation_file(data)))

    def test_transcript_must_end_on_a_user_turn(self):
        errors = with_case(turns=[{"role": "user", "text": "Hi"}, {"role": "assistant", "text": "Hello"}])
        self.assertTrue(any("last turn must be a user turn" in e for e in errors))

    def test_malformed_turns_are_reported(self):
        for bad in ([{"role": "user", "text": "only one"}],
                    [{"role": "bot", "text": "a"}, {"role": "user", "text": "b"}],
                    [{"role": "assistant", "text": ""}, {"role": "user", "text": "b"}],
                    [{"role": "assistant", "text": "a", "extra": 1}, {"role": "user", "text": "b"}],
                    "not a list"):
            self.assertTrue(with_case(turns=bad), bad)

    def test_multi_turn_coverage_per_language(self):
        data = copy.deepcopy(REAL)
        data["cases"] = [c for c in data["cases"] if not ("turns" in c and c["language"].startswith("es"))]
        self.assertTrue(any("multi-turn evaluation case in language 'es'" in e for e in C.validate_evaluation_file(data)))

    def test_regression_cases_accept_turns_under_the_same_rules(self):
        data = copy.deepcopy(REAL_REGRESSION)
        data["regressions"].append({"id": "bad_turns", "turns": [{"role": "user", "text": "a"}, {"role": "user", "text": "b"}],
                                    "must": ["x"], "must_not": ["y"]})
        self.assertTrue(any("must set 'manual: true'" in e for e in C.validate_regression_file(data)))

    def test_render_transcript(self):
        turns = [{"role": "assistant", "text": "¿Te bañaste hoy?"}, {"role": "user", "text": "Sí."}]
        self.assertEqual(C.render_transcript(turns), "Assistant: ¿Te bañaste hoy?\nUser: Sí.")

    def test_loaded_cases_expose_turns_and_no_prompt(self):
        cases = C.load_all_cases(ROOT / "tests")
        self.assertIsNone(cases["echo_spanish_yes_no_answer"]["prompt"])
        self.assertEqual(cases["echo_spanish_yes_no_answer"]["turns"][-1], {"role": "user", "text": "Sí."})
        self.assertEqual(cases["echo_emotional_disclosure"]["prompt"], "Estoy triste porque discutí con mi pareja.")


class RegressionFile(unittest.TestCase):
    def test_real_file_is_valid(self):
        self.assertEqual(C.validate_regression_file(REAL_REGRESSION), [])

    def test_problems_are_all_reported(self):
        data = {"version": "x", "regressions": [
            {"id": "a", "prompt": "", "must": [], "must_not": ["x"]},
            {"id": "a", "prompt": "p", "must": ["m"], "must_not": ["x"], "extra": 1},
        ]}
        text = " | ".join(C.validate_regression_file(data))
        for fragment in ("'version'", "'prompt'", "'must'", "duplicate id", "unknown field"):
            self.assertIn(fragment, text)

    def test_regression_prompts_have_no_leftover_annotations(self):
        for case in REAL_REGRESSION["regressions"]:
            if case.get("manual"):
                continue
            self.assertNotIn("(No mention", case.get("prompt", ""), case["id"])
            self.assertNotRegex(case.get("prompt", ""), r"^\(Turn", case["id"])


class Loading(unittest.TestCase):
    def test_load_all_merges_both_files(self):
        cases = C.load_all_cases(ROOT / "tests")
        self.assertIn("direct_simple_question", cases)
        self.assertIn("simple_answer_becomes_report", cases)

    def test_invalid_yaml_raises_actionable_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.yaml"
            path.write_text("a: [unclosed\n", encoding="utf-8")
            with self.assertRaises(C.CaseFileError) as ctx:
                C.read_yaml(path)
            self.assertIn("invalid YAML", str(ctx.exception))

    def test_missing_file_and_non_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(C.CaseFileError):
                C.read_yaml(Path(tmp) / "none.yaml")
            path = Path(tmp) / "list.yaml"
            path.write_text("- a\n- b\n", encoding="utf-8")
            with self.assertRaises(C.CaseFileError):
                C.read_yaml(path)

    def test_loading_an_invalid_file_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "e.yaml"
            path.write_text("version: 1\ncases: []\n", encoding="utf-8")
            with self.assertRaises(C.CaseFileError):
                C.load_evaluation_cases(path)


if __name__ == "__main__":
    unittest.main()
