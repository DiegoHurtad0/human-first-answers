# Changelog

All notable changes are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0-rc.1] - 2026-11-03

First release candidate. Structure and tooling are tested; response-quality improvement is unmeasured (see `docs/EVALUATION.md`).

### Added
- Explicit instruction-precedence policy (`SKILL.md`, `references/instruction-precedence.md`).
- Untrusted-content rule: pasted text, documents, and tool output are data.
- `references/revising-text.md` for editing provided text without changing meaning.
- Framework table (Pyramid, SCQA, MECE, first principles, hypothesis-driven, cost-benefit) with "do not use for" limits.
- Four-layer voice-profile model and a one-correction-is-not-a-preference rule.
- Eighteen evaluation cases covering casual English and Spanish, professional writing, text revision, engineering analysis, strategy, evidence, ambiguity, contradiction, and precedence; eight regression cases. Three regression cases in total are marked manual (multi-turn or host system prompt).
- Eight independent judging dimensions (added logical coherence and recommendation quality).
- `scripts/case_schema.py`: schema validation and coverage requirements for the case files.
- Unit tests for the validator and a skill-contract test.
- `--suite` and per-dimension reporting in the evaluation runner.
- CI workflow, contributor guide, code of conduct, issue and pull-request templates, architecture and evaluation docs.

### Changed
- Validator rewritten: parses frontmatter as YAML, rejects fields outside the specification, checks every Markdown link and backticked path, checks README layout and rubric/dimension agreement, scans for credentials, and fails closed without PyYAML.
- Test cases are read with PyYAML; the hand-written parser was removed.
- `--dry-run` no longer requires `--safe-mode`; it reports whether a live run would be blocked.
- Workflow step 6: AI-writing patterns are applied while drafting, with a separate revision pass only when needed.
- README rewritten to match the implementation; install paths checked against Claude Code and Codex documentation.

### Fixed
- README listed a CI workflow that did not exist.
- Dimension names disagreed between the cases file, the runner, and the rubric.
- Regression prompts contained annotations and a missing message; they are now runnable prompts.

### Licensing
- The maintainer decided on the MIT License. `LICENSE` now contains the MIT text (previously the repository's initial commit carried Apache-2.0), copyright holder Diego Gustavo Hurtado Olivares, 2026.
- `SKILL.md` (`license: MIT`), `README.md`, `ATTRIBUTION.md`, `CONTRIBUTING.md`, and `AGENTS.md` state MIT. Third-party licenses in `ATTRIBUTION.md` are unchanged.
- The validator now checks that the `license` field matches the `LICENSE` file.
