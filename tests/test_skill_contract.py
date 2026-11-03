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
