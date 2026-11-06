"""Unit tests for scripts/validate_project.py. No model calls.

Each test builds a small skill in a temporary directory, breaks one thing, and
checks the validator reports exactly that problem.
"""
import contextlib
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import case_schema  # noqa: E402
import validate_project as V  # noqa: E402

VALID_SKILL = """---
name: natural-voice
description: Improve how an agent answers. Use when answering or drafting.
license: See LICENSE
metadata:
  version: "1.0.0"
---

# Title

Read `references/one.md` for detail.
"""


def rubric_text():
    rows = "\n".join(f"| {d.replace('_', ' ').capitalize()} | a | b | c |" for d in case_schema.DIMENSIONS)
    return f"# Rubric\n\n| Dimension | 1 | 3 | 5 |\n|---|---|---|---|\n{rows}\n"


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.root = self.tmp / "natural-voice"
        (self.root / "references").mkdir(parents=True)
        self.write("SKILL.md", VALID_SKILL)
        self.write("references/one.md", "# One\n")
        self.write("references/evaluation-rubric.md", rubric_text())
        self.write_reference_link()

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write_reference_link(self):
        # The rubric must be reachable from SKILL.md like every other reference.
        text = (self.root / "SKILL.md").read_text()
        if "evaluation-rubric.md" not in text:
            self.write("SKILL.md", text + "Review with `references/evaluation-rubric.md`.\n")

    def skill(self, text):
        self.write("SKILL.md", text)
        self.write_reference_link()

    def validate(self, **kwargs):
        return V.validate(self.root, project_files=False, **kwargs)

    def assert_error(self, report, fragment):
        self.assertTrue(any(fragment in e for e in report.errors), f"{fragment!r} not in {report.errors}")


class RealRepository(unittest.TestCase):
    def test_this_repository_is_valid(self):
        report = V.validate(ROOT)
        self.assertEqual(report.errors, [])

    def test_main_returns_zero_on_this_repository(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(V.main([]), 0)

    def test_an_installed_copy_passes_strict_install(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        installed = tmp / "natural-voice"
        installed.mkdir()
        shutil.copy(ROOT / "SKILL.md", installed / "SKILL.md")
        shutil.copytree(ROOT / "references", installed / "references")
        report = V.validate(installed, strict_install=True, project_files=False)
        self.assertEqual(report.errors, [])

    def test_the_checkout_directory_name_is_only_a_warning_by_default(self):
        if ROOT.name == "natural-voice":
            self.skipTest("checkout already named after the skill")
        self.assertTrue(any("differs from skill name" in w for w in V.validate(ROOT).warnings))
        self.assertTrue(any("differs from skill name" in e for e in V.validate(ROOT, strict_install=True).errors))


class Frontmatter(Fixture):
    def test_minimal_valid_skill_passes(self):
        self.assertEqual(self.validate().errors, [])

    def test_missing_skill_file(self):
        (self.root / "SKILL.md").unlink()
        self.assert_error(self.validate(), "file not found")

    def test_no_frontmatter(self):
        self.skill("# Title\n")
        self.assert_error(self.validate(), "must start with YAML frontmatter")

    def test_unclosed_frontmatter(self):
        self.skill("---\nname: natural-voice\n# Title\n")
        self.assert_error(self.validate(), "must start with YAML frontmatter")

    def test_invalid_yaml(self):
        self.skill("---\nname: [unclosed\n---\n# Title\n")
        self.assert_error(self.validate(), "not valid YAML")

    def test_unknown_field_is_rejected_for_portability(self):
        self.skill(VALID_SKILL.replace("license:", "when_to_use: x\nlicense:"))
        self.assert_error(self.validate(), "not in the Agent Skills spec")

    def test_metadata_values_must_be_strings(self):
        self.skill(VALID_SKILL.replace('version: "1.0.0"', "version: 1.0"))
        self.assert_error(self.validate(), "string keys to string values")

    def test_invalid_names(self):
        for bad in ("Natural-Voice", "-natural-voice", "natural-voice-", "natural--voice", "natural_voice"):
            self.skill(VALID_SKILL.replace("name: natural-voice", f"name: {bad}"))
            self.assert_error(self.validate(), "invalid name")

    def test_wrong_name(self):
        self.skill(VALID_SKILL.replace("name: natural-voice", "name: other-skill"))
        self.assert_error(self.validate(), "must be 'natural-voice'")

    def test_overlong_name(self):
        self.skill(VALID_SKILL.replace("name: natural-voice", "name: " + "a" * 65))
        self.assert_error(self.validate(), "invalid name")

    def test_description_required_and_limited(self):
        self.skill(VALID_SKILL.replace("description: Improve how an agent answers. Use when answering or drafting.", "description: ''"))
        self.assert_error(self.validate(), "'description' is required")
        self.skill(VALID_SKILL.replace("Improve how an agent answers.", "x" * 1100))
        self.assert_error(self.validate(), "spec maximum is 1024")

    def test_description_at_the_limit_passes(self):
        self.skill(VALID_SKILL.replace("Improve how an agent answers. Use when answering or drafting.", "x" * 1024))
        self.assertEqual(self.validate().errors, [])

    def test_compatibility_limit(self):
        self.skill(VALID_SKILL.replace("license: See LICENSE", "compatibility: " + "y" * 501))
        self.assert_error(self.validate(), "'compatibility'")

    def test_skill_body_needs_a_heading(self):
        self.skill(VALID_SKILL.replace("# Title", "Title"))
        self.assert_error(self.validate(), "top-level heading")

    def test_line_limits(self):
        long_body = VALID_SKILL + "line\n" * 300
        self.skill(long_body)
        report = self.validate()
        self.assertEqual(report.errors, [])
        self.assertTrue(any("project target" in w for w in report.warnings))
        self.skill(VALID_SKILL + "line\n" * 600)
        self.assert_error(self.validate(), "spec limit is 500")

    def test_non_utf8_skill_is_reported_not_raised(self):
        (self.root / "SKILL.md").write_bytes(b"---\nname: \xff\xfe\n---\n")
        self.assert_error(self.validate(), "cannot read as UTF-8")


class References(Fixture):
    def test_unreachable_reference(self):
        self.write("references/orphan.md", "# Orphan\n")
        self.assert_error(self.validate(), "references/orphan.md is not referenced from SKILL.md")

    def test_broken_backtick_reference(self):
        self.skill(VALID_SKILL + "See `references/missing.md`.\n")
        self.assert_error(self.validate(), "broken reference 'references/missing.md'")

    def test_broken_markdown_link(self):
        self.skill(VALID_SKILL + "See [x](references/gone.md).\n")
        self.assert_error(self.validate(), "broken reference")

    def test_links_with_anchors_and_urls_are_accepted(self):
        self.skill(VALID_SKILL + "See [a](references/one.md#section) and [b](https://example.com/x.md) and [c](#top).\n")
        self.assertEqual(self.validate().errors, [])

    def test_reference_files_may_name_siblings_by_bare_name(self):
        self.write("references/one.md", "# One\nSee `evaluation-rubric.md`.\n")
        self.assertEqual(self.validate().errors, [])
        self.write("references/one.md", "# One\nSee `nonexistent.md`.\n")
        self.assert_error(self.validate(), "broken reference 'nonexistent.md'")

    def test_nested_reference_directory_warns(self):
        (self.root / "references" / "deep").mkdir()
        self.assertTrue(any("one level deep" in w for w in self.validate().warnings))


class RubricAgreement(Fixture):
    def test_missing_dimension_row(self):
        self.write("references/evaluation-rubric.md", rubric_text().replace("| Logical coherence |", "| Coherence |"))
        self.assert_error(self.validate(), "Logical coherence")


class ReadmeLayout(unittest.TestCase):
    TREE = """## Repository layout

```text
natural-voice/
├── SKILL.md
├── docs/
│   ├── A.md   # note
│   └── deep/
│       └── B.md
└── tests/
    └── t.py
```
"""

    def test_parses_nested_paths_and_ignores_comments(self):
        self.assertEqual(V.readme_layout_paths(self.TREE),
                         ["SKILL.md", "docs", "docs/A.md", "docs/deep", "docs/deep/B.md", "tests", "tests/t.py"])

    def test_no_layout_block(self):
        self.assertEqual(V.readme_layout_paths("# Title\n"), [])

    def test_missing_listed_path_is_an_error(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        (tmp / "README.md").write_text(self.TREE, encoding="utf-8")
        (tmp / "SKILL.md").write_text("x", encoding="utf-8")
        report = V.Report()
        V.check_readme(tmp, report)
        self.assertTrue(any("'docs/A.md', which does not exist" in e for e in report.errors))
        self.assertFalse(any("'SKILL.md'" in e for e in report.errors))


class Hygiene(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / ".gitignore").write_text("\n".join(V.REQUIRED_GITIGNORE) + "\n", encoding="utf-8")

    def run_hygiene(self):
        report = V.Report()
        V.check_hygiene(self.tmp, report)
        return report

    def test_clean_tree(self):
        self.assertEqual(self.run_hygiene().errors, [])

    def test_missing_gitignore_entries(self):
        (self.tmp / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        errors = self.run_hygiene().errors
        self.assertTrue(any("evaluation-results/" in e for e in errors))
        self.assertTrue(any(".natural-voice/" in e for e in errors))

    def test_detects_credential_patterns(self):
        # Built at runtime so this file does not itself contain a credential-shaped string.
        fakes = {"ant": "sk-ant-" + "a1" * 15, "gh": "ghp_" + "b2" * 20, "aws": "AKIA" + "C3" * 8,
                 "pem": "-----BEGIN RSA " + "PRIVATE KEY-----"}
        for name, value in fakes.items():
            (self.tmp / f"{name}.txt").write_text(f"token = {value}\n", encoding="utf-8")
        errors = self.run_hygiene().errors
        for name in fakes:
            self.assertTrue(any(f"{name}.txt" in e for e in errors), name)

    def test_env_file_is_flagged(self):
        (self.tmp / ".env").write_text("A=1\n", encoding="utf-8")
        self.assertTrue(any("credentials file" in e for e in self.run_hygiene().errors))

    def test_ignored_directories_are_not_scanned(self):
        (self.tmp / "evaluation-results").mkdir()
        (self.tmp / "evaluation-results" / "r.txt").write_text("sk-ant-" + "z9" * 15, encoding="utf-8")
        self.assertEqual(self.run_hygiene().errors, [])

    def test_binary_files_are_skipped_without_crashing(self):
        (self.tmp / "blob.bin").write_bytes(b"\xff\xfe\x00\x01")
        self.assertEqual(self.run_hygiene().errors, [])


class CaseFilesAcrossTheValidator(unittest.TestCase):
    def test_duplicate_ids_across_files_are_reported(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        (tmp / "tests").mkdir()
        shutil.copy(ROOT / "tests" / "evaluation-cases.yaml", tmp / "tests")
        text = (ROOT / "tests" / "regression-cases.yaml").read_text(encoding="utf-8")
        text = text.replace("id: simple_answer_becomes_report", "id: strict_format", 1)
        (tmp / "tests" / "regression-cases.yaml").write_text(text, encoding="utf-8")
        report = V.Report()
        V.check_cases(tmp, report)
        self.assertTrue(any("used more than once" in e for e in report.errors), report.errors)

    def test_missing_case_files_are_reported(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        report = V.Report()
        V.check_cases(tmp, report)
        self.assertTrue(any("file not found" in e for e in report.errors))


class License(Fixture):
    MIT = "MIT License\n\nCopyright (c) 2026 Jane Doe\n\nPermission is hereby granted...\n"

    def check(self, skill_license, license_text):
        self.skill(VALID_SKILL.replace("license: See LICENSE", f"license: {skill_license}"))
        self.write("LICENSE", license_text)
        report = V.Report()
        V.check_license(self.root, (self.root / "SKILL.md").read_text(), report)
        return report

    def test_matching_mit_passes(self):
        self.assertEqual(self.check("MIT", self.MIT).errors, [])

    def test_declared_mit_with_apache_file_fails(self):
        report = self.check("MIT", "                                 Apache License\n Version 2.0\n")
        self.assertTrue(any("does not start with 'MIT License'" in e for e in report.errors))

    def test_mit_without_copyright_line_fails(self):
        report = self.check("MIT", "MIT License\n\nPermission is hereby granted...\n")
        self.assertTrue(any("Copyright (c)" in e for e in report.errors))

    def test_unknown_declared_license_fails(self):
        self.assertTrue(any("not one of" in e for e in self.check("See LICENSE", self.MIT).errors))

    def test_this_repository_declares_mit(self):
        text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("MIT License"))
        self.assertIn("license: MIT", (ROOT / "SKILL.md").read_text(encoding="utf-8"))
        self.assertNotIn("Apache", text)


class Cli(unittest.TestCase):
    def test_symlinked_install_keeps_the_link_name_for_strict_install(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        checkout = tmp / "human-first-answers"
        checkout.mkdir()
        shutil.copy(ROOT / "SKILL.md", checkout / "SKILL.md")
        shutil.copytree(ROOT / "references", checkout / "references")
        link = tmp / "natural-voice"
        link.symlink_to(checkout, target_is_directory=True)
        report = V.validate(link.absolute(), strict_install=True, project_files=False)
        self.assertEqual(report.errors, [])
        self.assertNotEqual(V.validate(link.resolve(), strict_install=True, project_files=False).errors, [])

    def test_main_fails_on_a_broken_skill(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(V.main(["--root", str(tmp)]), 1)
        self.assertIn("ERROR:", out.getvalue())
        self.assertIn("Validation failed", out.getvalue())


if __name__ == "__main__":
    unittest.main()


class Portability(Fixture):
    def reference_errors(self, text):
        self.write("references/one.md", "# One\n" + text + "\n")
        return [e for e in self.validate().errors if "host-" in e]

    def test_host_conditional_rules_are_rejected(self):
        for text in ("In Claude Code, skip the headings.", "When running in Copilot, use bullets.",
                     "If the assistant is Codex, answer in one line.", "This is a Gemini CLI-only rule.",
                     "- On Windsurf: keep it short."):
            self.assertTrue(self.reference_errors(text), text)

    def test_host_owned_mechanisms_are_rejected(self):
        for text in ("Read CLAUDE.md first.", "Save it under .claude/skills.", "Call activate_skill.",
                     "Edit copilot-instructions.md.", "Set it in openai.yaml."):
            self.assertTrue(self.reference_errors(text), text)

    def test_legitimate_mentions_are_allowed(self):
        for text in ('The user says "Claude wrote this" and wants it rewritten.',
                     "Write a cover letter for an OpenAI recruiter.", "Openers like ChatGPT-style praise are a pattern.",
                     "Gemini is a constellation.", "A reviewer named Codex as an example of verbose output.",
                     "Cite Anthropic's published guidance if the user asks for sources."):
            self.assertEqual(self.reference_errors(text), [], text)

    def test_host_names_are_allowed_outside_the_contract(self):
        self.write("docs/notes.md", "In Claude Code, run /skills. Works in Copilot and Codex.\n")
        self.assertEqual(self.validate().errors, [])

    def test_install_section_commands_must_not_use_repository_relative_paths(self):
        bad = "## Supported AI Assistants\n\n```bash\npython3 scripts/validate_project.py --root x --strict-install\n```\n\n## Next\n"
        self.write("README.md", bad + "```bash\ngit clone u ~/.agents/skills/natural-voice\n```\n")
        report = V.Report()
        V.check_install_docs(self.root, report)
        self.assert_error(report, "relative to the repository")
        good = "## Supported AI Assistants\n\n```bash\nSKILL=~/x/natural-voice\npython3 -m pip install -r \"$SKILL/requirements-dev.txt\"\npython3 \"$SKILL/scripts/validate_project.py\" --root \"$SKILL\"\ngit clone u ~/.agents/skills/natural-voice\n```\n\n## Next\n"
        self.write("README.md", good)
        report = V.Report()
        V.check_install_docs(self.root, report)
        self.assertEqual(report.errors, [])

    def test_install_commands_must_target_the_skill_name(self):
        self.write("README.md", "```bash\ngit clone https://example.com/r.git ~/.agents/skills/natural-voice\n```\n")
        report = V.Report()
        V.check_install_docs(self.root, report)
        self.assertEqual(report.errors, [])
        self.write("README.md", "```bash\ngit clone https://example.com/r.git ~/.agents/skills/human-first-answers\n```\n")
        report = V.Report()
        V.check_install_docs(self.root, report)
        self.assert_error(report, "does not target a directory named 'natural-voice'")

    def test_symlink_commands_are_checked_and_missing_commands_are_reported(self):
        self.write("README.md", "```bash\nln -s ~/x ~/.claude/skills/wrong\n```\n")
        report = V.Report()
        V.check_install_docs(self.root, report)
        self.assert_error(report, "natural-voice")
        self.write("README.md", "no commands here\n")
        report = V.Report()
        V.check_install_docs(self.root, report)
        self.assert_error(report, "no install commands")

    def test_readme_documents_each_investigated_assistant_and_its_paths(self):
        text = (Path(V.__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")
        self.assertIn("## Supported AI Assistants", text)
        for fragment in ("GitHub Copilot", "Claude Code", "OpenAI Codex", "Gemini CLI", ".agents/skills", ".claude/skills",
                         ".github/skills", ".gemini/skills", "~/.copilot/skills", "Documented, untested"):
            self.assertIn(fragment, text, fragment)
        self.assertIn("not sharing a URL", text)
        self.assertNotIn("copilot-instructions", text.split("### Installing")[0])
