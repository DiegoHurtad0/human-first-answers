"""Guards for the skill's written contract. No model calls.

These tests read the instruction files as text. They stop accidental deletion of
load-bearing rules (precedence order, optional ADHD mode, untrusted content,
no-persistence stance). They do not show that any model follows the rules.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_evaluation as R  # noqa: E402

SKILL = (ROOT / "SKILL.md").read_text(encoding="utf-8")
REFS = {p.name: p.read_text(encoding="utf-8") for p in (ROOT / "references").glob("*.md")}


def section(text, heading):
    match = re.search(rf"(?ms)^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text)
    assert match, f"missing section {heading!r}"
    return match.group(1)


class Precedence(unittest.TestCase):
    ORDER = ["Safety, factuality", "Explicit user instructions", "persistent user preferences",
             "Context requirements", "general Natural Voice principles", "Optional stylistic"]

    def test_six_levels_appear_in_order(self):
        body = section(SKILL, "Instruction precedence")
        positions = [body.lower().find(fragment.lower()) for fragment in self.ORDER]
        self.assertTrue(all(p >= 0 for p in positions), positions)
        self.assertEqual(positions, sorted(positions))

    def test_skill_never_claims_to_override_the_host(self):
        body = section(SKILL, "Instruction precedence").lower()
        self.assertIn("cannot override the host", body)
        self.assertIn("always outrank", body)

    def test_reference_repeats_the_same_levels(self):
        text = REFS["instruction-precedence.md"]
        rows = re.findall(r"(?m)^\| (\d) \|", text)
        self.assertEqual(rows, ["1", "2", "3", "4", "5", "6"])

    def test_persistence_requires_a_real_mechanism(self):
        self.assertIn("real host persistence mechanism", SKILL)


class UntrustedContent(unittest.TestCase):
    def test_skill_treats_embedded_text_as_data(self):
        body = section(SKILL, "Untrusted content").lower()
        self.assertIn("data, not instructions", body)

    def test_revision_reference_treats_text_as_data(self):
        self.assertIn("data", REFS["revising-text.md"].lower())


class AdhdMode(unittest.TestCase):
    def test_mode_is_optional_and_off_by_default(self):
        line = next(l for l in SKILL.splitlines() if l.startswith("- **ADHD-friendly"))
        self.assertIn("off by default", line)
        self.assertIn("only when the user asks", line)

    def test_activation_is_not_inferred_from_style(self):
        self.assertIn("Do not infer it", REFS["adhd-friendly-output.md"])

    def test_list_cap_never_drops_content(self):
        self.assertIn("Never drop items", REFS["adhd-friendly-output.md"])

    def test_cross_session_persistence_needs_consent(self):
        self.assertIn("authorized", REFS["adhd-friendly-output.md"])

    def test_mode_yields_to_emotional_and_safety_contexts(self):
        text = REFS["adhd-friendly-output.md"]
        self.assertIn("Emotional or personal conversation", text)
        self.assertIn("Safety, medical, legal", text)


class SizeAndPortability(unittest.TestCase):
    def test_skill_is_within_project_target(self):
        self.assertLessEqual(len(SKILL.splitlines()), 250)

    def test_skill_body_is_within_the_recommended_token_budget(self):
        self.assertLess(len(SKILL) / 4, 5000)

    def test_no_universal_style_bans(self):
        banned = re.compile(r"(?i)\b(never|always) (use|include|write) (an? )?(em dash|bullet|list|contraction|semicolon)")
        for name, text in {**REFS, "SKILL.md": SKILL}.items():
            self.assertIsNone(banned.search(text), name)

    def test_no_detector_evasion_framing(self):
        self.assertIn("Do not optimize for detector evasion", REFS["ai-writing-patterns.md"])

    def test_voice_profile_does_not_generalize_one_correction(self):
        self.assertIn("One correction is not a personality", REFS["voice-profile.md"])

    def test_frameworks_state_limits(self):
        text = REFS["consultative-thinking.md"]
        for framework in ("Pyramid", "SCQA", "MECE", "First principles", "Hypothesis-driven", "Cost-benefit"):
            self.assertIn(framework, text)
        self.assertIn("Do not use it for", text)


class ConversationContinuity(unittest.TestCase):
    TEXT = REFS["conversation-continuity.md"]

    def test_skill_makes_it_part_of_the_contract_and_loads_the_reference(self):
        contract = section(SKILL, "Core contract")
        self.assertIn("do not echo it", contract)
        self.assertIn("references/conversation-continuity.md", contract)
        self.assertIn("conversation-continuity.md", section(SKILL, "Workflow"))
        self.assertIn("conversation-continuity.md", section(SKILL, "Reference loading"))

    def test_skill_does_not_duplicate_the_reference(self):
        self.assertLess(SKILL.count("echo"), 4)

    def test_sibling_references_point_to_the_owner_instead_of_copying_it(self):
        for name in ("natural-conversation.md", "context-adaptation.md"):
            self.assertIn("conversation-continuity.md", REFS[name], name)
            self.assertNotIn("Ah, perfecto", REFS[name], name)

    def test_short_reply_vocabulary_is_covered_in_both_languages(self):
        for phrase in ("Sí.", "No.", "Claro.", "Exactamente.", "Ya veo.", "Puede ser.", "No estoy seguro.", "Ahorita te digo.",
                       "Yes.", "Sure.", "Exactly.", "I see.", "Maybe.", "I'm not sure.", "I'll let you know."):
            self.assertIn(phrase, self.TEXT, phrase)

    def test_automatic_questioning_is_rejected_as_a_fix(self):
        self.assertIn("replacing an echo with an automatic question fixes nothing", self.TEXT)
        self.assertIn("a rule that every answer needs another question", self.TEXT)

    def test_useful_repetition_is_preserved(self):
        for fragment in ("Safety", "Confirmation of a consequential action", "disambiguation", "summary or read-back the user asked for",
                         "Never drop a protective confirmation"):
            self.assertIn(fragment, self.TEXT, fragment)

    def test_no_invented_capability(self):
        self.assertIn("Never invent an action or a capability", self.TEXT)

    def test_other_modes_and_contexts_are_respected(self):
        self.assertIn("ADHD mode", self.TEXT)
        self.assertIn("not echo; keep it", self.TEXT)
        self.assertIn("strict output formats", self.TEXT)
        self.assertIn("Instruction precedence", self.TEXT)

    def test_paraphrasing_and_acknowledgment_are_not_universally_banned(self):
        self.assertIsNone(re.search(r"(?i)\b(never|always) (repeat|paraphrase|restate|acknowledge|ask)\b", self.TEXT))
        self.assertIn("A brief acknowledgment is often the best reply", self.TEXT)

    def test_required_regression_scenarios_exist_with_honest_manual_flags(self):
        import case_schema
        cases = case_schema.load_all_cases(ROOT / "tests")
        manual = {"echo_spanish_yes_no_answer", "echo_english_yes_no_answer", "echo_short_confirmation_after_offer",
                  "continuity_multi_turn_advances", "continuity_follow_up_uses_prior_context",
                  "continuity_correction_updates_state", "continuity_topic_change_drops_old_topic"}
        automated = {"echo_emotional_disclosure", "repetition_confirms_consequential_action",
                     "repetition_is_right_when_summary_requested"}
        for cid in manual:
            self.assertTrue(cases[cid]["manual"] and cases[cid]["turns"], cid)
        for cid in automated:
            self.assertFalse(cases[cid]["manual"], cid)
            self.assertTrue(cases[cid]["prompt"], cid)
        self.assertEqual(len(manual | automated), 10)

    def test_both_languages_have_a_yes_no_case_and_neither_requires_a_reflex_question(self):
        import case_schema
        cases = case_schema.load_all_cases(ROOT / "tests")
        self.assertEqual(cases["echo_spanish_yes_no_answer"]["language"], "es")
        self.assertEqual(cases["echo_english_yes_no_answer"]["language"], "en")
        for cid in ("echo_spanish_yes_no_answer", "continuity_short_answer_no_reflex_question_es"):
            self.assertTrue(any("unless" in x or "only" in x or "when_useful" in x for x in cases[cid]["expected"]), cid)


class ResponseRelevance(unittest.TestCase):
    TEXT = REFS["response-relevance.md"]

    def test_skill_states_the_rule_and_loads_the_reference(self):
        self.assertIn("references/response-relevance.md", section(SKILL, "Core contract"))
        self.assertIn("response-relevance.md", section(SKILL, "Workflow"))
        self.assertIn("response-relevance.md", section(SKILL, "Reference loading"))

    def test_four_kinds_of_information_are_distinguished(self):
        for fragment in ("Needs a response", "Needs only to be understood", "Must be confirmed", "Adds nothing if repeated"):
            self.assertIn(fragment, self.TEXT, fragment)

    def test_confirmations_and_obligations_are_not_banned(self):
        for fragment in ("Restate the date, amount, or terms", "The principle is judgment, not a ban",
                         "keep it and keep it short", "explicitly asked for a commitment"):
            self.assertIn(fragment, self.TEXT, fragment)

    def test_drafting_and_editing_are_distinguished(self):
        self.assertIn("Drafting a new reply", self.TEXT)
        self.assertIn("Editing a reply the user wrote", self.TEXT)
        self.assertIn("response-relevance.md", REFS["revising-text.md"])
        self.assertIn("protected", REFS["revising-text.md"].lower())

    def test_echo_and_carryover_are_kept_separate(self):
        self.assertIn("response-relevance.md", REFS["conversation-continuity.md"])
        self.assertIn("different habit", REFS["conversation-continuity.md"])
        self.assertIn("separate habits", self.TEXT)

    def test_context_adaptation_points_to_owner_without_copying_examples(self):
        self.assertIn("response-relevance.md", REFS["context-adaptation.md"])
        self.assertNotIn("bank account", REFS["context-adaptation.md"])

    def test_both_languages_have_examples(self):
        self.assertIn("Incoming (en)", self.TEXT)
        self.assertIn("Incoming (es)", self.TEXT)

    def test_cases_cover_both_languages_and_both_directions(self):
        import case_schema
        cases = case_schema.load_all_cases(ROOT / "tests")
        rel = {k: v for k, v in cases.items() if k.startswith("relevance_")}
        self.assertGreaterEqual(len(rel), 16)
        for cid, case in rel.items():
            self.assertFalse(case["manual"], cid)
            self.assertTrue(case["prompt"], cid)
        self.assertTrue({c["language"] for c in rel.values()} >= {"en", "es"})
        # Brevity cases and cases where the detail must survive both exist.
        for cid in ("relevance_unneeded_commitment_en", "relevance_legitimate_confirmation_en",
                    "relevance_legitimate_confirmation_es", "relevance_requested_commitment_en",
                    "relevance_edit_preserves_commitment_en", "relevance_editing_preserves_commitment_es"):
            self.assertIn(cid, rel)


class JudgmentAndAdaptation(unittest.TestCase):
    CONT = REFS["conversation-continuity.md"]

    def test_implicit_intent_has_limits_against_mind_reading(self):
        for fragment in ("Reading implicit intent", "Do not manufacture a concern", "Ask one focused question",
                         "not automatically a request for advice", "Use only the facts given"):
            self.assertIn(fragment, self.CONT, fragment)

    def test_completeness_and_initiative(self):
        for fragment in ("Knowing when the reply is complete", "Keep going when the objective is unresolved",
                         "Initiative adds value; it does not add turns"):
            self.assertIn(fragment, self.CONT, fragment)

    def test_boilerplate_is_context_dependent_not_banned(self):
        text = REFS["response-relevance.md"]
        self.assertIn("are not banned", text)
        self.assertIn("Casual", text)
        self.assertIn("Executive", text)
        self.assertIn("Formal", text)

    def test_proportion_covers_task_types_and_keeps_safety(self):
        text = REFS["clear-communication.md"]
        for fragment in ("Proportion to the task", "Informational", "Consequential decision", "Emotional conversation",
                         "Operational task", "Do not cut a safety limit"):
            self.assertIn(fragment, text, fragment)

    def test_corrections_are_task_scoped_and_memory_claims_honest(self):
        text = REFS["voice-profile.md"]
        for fragment in ("Corrections within a task", "Scope it to the task", "Never claim to remember across sessions"):
            self.assertIn(fragment, text, fragment)
        self.assertIn("voice-profile.md", self.CONT)

    def test_skill_stays_small_and_adds_no_new_reference_for_this(self):
        self.assertLess(len(SKILL.splitlines()), 160)
        self.assertEqual(len([n for n in REFS if n.endswith(".md")]), 13)

    def test_new_cases_cover_both_languages_and_keep_multi_turn_manual(self):
        import case_schema
        cases = case_schema.load_all_cases(ROOT / "tests")
        groups = {"intent_": 7, "feedback_": 6, "restraint_": 5, "proportion_": 4}
        for prefix, minimum in groups.items():
            group = {k: v for k, v in cases.items() if k.startswith(prefix)}
            self.assertGreaterEqual(len(group), minimum, prefix)
            self.assertTrue({"en", "es"} <= {c["language"] for c in group.values()} or prefix == "restraint_", prefix)
            for cid, case in group.items():
                self.assertEqual(bool(case["turns"]), bool(case["manual"]), cid)
        # A case where asking is right, and a case where a stated request must not be overridden.
        self.assertIn("intent_two_offers_one_focused_question_en", cases)
        self.assertIn("intent_stated_request_not_overridden_en", cases)
        # Brevity cannot win by dropping details.
        self.assertIn("relevance_executive_approval_es", cases)
        self.assertIn("relevance_obligation_amount_kept_es", cases)


class CiWorkflow(unittest.TestCase):
    """The workflow is read as data; these tests do not prove GitHub runs it successfully."""

    @classmethod
    def setUpClass(cls):
        import yaml
        cls.workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8"))
        cls.job = cls.workflow["jobs"]["validate"]

    def test_python_versions_are_pinned_to_the_runners_that_provide_them(self):
        pairs = {(e["python-version"], e["os"]) for e in self.job["strategy"]["matrix"]["include"]}
        self.assertEqual(pairs, {("3.9", "ubuntu-24.04"), ("3.12", "ubuntu-26.04")})

    def test_matrix_is_explicit_pairs_only(self):
        matrix = self.job["strategy"]["matrix"]
        self.assertEqual(set(matrix), {"include"})  # no extra axes that would expand into a cross product
        self.assertFalse(self.job["strategy"]["fail-fast"])

    def test_job_uses_the_matrix_values(self):
        self.assertEqual(self.job["runs-on"], "${{ matrix.os }}")
        setup = next(s for s in self.job["steps"] if str(s.get("uses", "")).startswith("actions/setup-python"))
        self.assertEqual(setup["with"]["python-version"], "${{ matrix.python-version }}")

    def test_no_floating_runner_label(self):
        labels = [e["os"] for e in self.job["strategy"]["matrix"]["include"]]
        self.assertEqual([label for label in labels if "latest" in label], [])

    def test_all_required_steps_remain_in_order(self):
        commands = [s.get("run") or s.get("uses") for s in self.job["steps"]]
        expected = ["actions/checkout", "actions/setup-python", "requirements-dev.txt",
                    "scripts/validate_project.py", "pytest", "run_evaluation.py --dry-run"]
        positions = []
        for fragment in expected:
            matches = [i for i, c in enumerate(commands) if fragment in c]
            self.assertTrue(matches, fragment)
            positions.append(matches[0])
        self.assertEqual(positions, sorted(positions))

    def test_workflow_has_read_only_permissions(self):
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})


class RepositoryPolicy(unittest.TestCase):
    AGENTS = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    CONTRIBUTING = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")

    def test_attribution_policy_is_in_the_agent_instructions(self):
        self.assertIn("## AI Tool Attribution Policy", self.AGENTS)
        for fragment in ("Never add attribution", "Co-Authored-By", "git log -1 --format=%B",
                         "never record an AI tool as author, committer, or co-author"):
            self.assertIn(fragment, self.AGENTS)

    def test_attribution_policy_is_in_the_contributor_guide(self):
        self.assertIn("Do not add AI-tool attribution", self.CONTRIBUTING)
        self.assertIn("AI Tool Attribution Policy", self.CONTRIBUTING)

    def test_policy_keeps_license_and_third_party_attribution(self):
        self.assertIn("MIT License and copyright notice", self.AGENTS)
        self.assertIn("ATTRIBUTION.md", self.AGENTS)

    def test_license_and_copyright_are_unchanged(self):
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertTrue(license_text.startswith("MIT License\n\nCopyright (c) 2026 Diego Hurtado\n"))

    def test_project_files_carry_no_tool_credit(self):
        credit = re.compile(r"(?i)(made with|created with|generated (by|with)|powered by) (claude|cursor|gemini|chatgpt|copilot|windsurf)|co-authored-by")
        for rel in ("README.md", "CHANGELOG.md", "SKILL.md", "ATTRIBUTION.md", "CONTRIBUTING.md"):
            self.assertIsNone(credit.search((ROOT / rel).read_text(encoding="utf-8")), rel)


class RunnerPromptBoundaries(unittest.TestCase):
    def test_candidate_gets_every_reference_but_the_rubric(self):
        system = R.build_candidate_system()
        for name in REFS:
            marker = f"# references/{name}"
            if name in R.EXCLUDED_REFERENCES:
                self.assertNotIn(marker, system)
            else:
                self.assertIn(marker, system)


if __name__ == "__main__":
    unittest.main()
