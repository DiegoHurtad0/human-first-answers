# Changelog

All notable changes are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Conversation continuity without echoing: new `references/conversation-continuity.md`, a core-contract rule in `SKILL.md`, and short pointers in `natural-conversation.md` and `context-adaptation.md`. Repetition stays where it protects the user (safety, consequential confirmations, corrections, requested summaries).
- Case schema: optional `turns` (a scripted transcript ending on a user turn) as an alternative to `prompt`. Such cases must be `manual: true`; the runner cannot replay scripted assistant turns. `run_evaluation.py --show-manual` prints them for human review.
- Eight evaluation cases (4 automated, 4 manual) and ten regression cases (3 automated, 7 manual) for echoing, short replies, corrections, topic changes, and useful repetition. New required category `conversation_continuity`, and a coverage rule of one scripted multi-turn case per language (en, es).

- Response relevance and information economy for drafted replies: new `references/response-relevance.md`, core-contract rule 9, and pointers from `context-adaptation.md`, `conversation-continuity.md`, and `revising-text.md`. Unneeded commitments, redundant acknowledgments, and repeated thanks are left out; confirmations, obligations, and requested summaries stay. Eight evaluation cases and eight regression cases (English and Spanish), all single-prompt and automated, and a new required category `response_relevance`.
- Implicit-intent recognition, closing-signal restraint, and task-scoped corrections: sections in `conversation-continuity.md` and `voice-profile.md`, a proportion table in `clear-communication.md`, a register and boilerplate section in `response-relevance.md`, and two clauses in `SKILL.md`. 14 evaluation cases and 14 regression cases (English and Spanish; 4 evaluation and 5 regression cases are manual multi-turn). New required categories `implicit_intent` and `feedback_adaptation`. `docs/EVALUATION.md` gained a methodology review. CI dry-run cap raised to 400.
- README section "Supported AI Assistants": a documentation-verified matrix (GitHub Copilot, Claude Code, OpenAI Codex, Gemini CLI), personal and project install paths, activation and verification steps, the repository-versus-skill naming rule, and the difference between installing, sharing a URL, and repository custom instructions. One `~/.agents/skills/natural-voice` clone serves Copilot, Codex, and Gemini CLI; a symlink adds Claude Code. No platform adapter files were added.
- Validator checks: host-conditional rules and host-owned mechanisms are rejected in `SKILL.md` and `references/` (product names alone are allowed); README install commands must target a directory named `natural-voice`, and install-section commands must work from any directory.

### Fixed
- CI: the Python 3.9 job failed before running any project code because `actions/setup-python` has no Python 3.9 build for Ubuntu 26.04. The workflow now pins explicit pairs: Python 3.9 on `ubuntu-24.04`, Python 3.12 on `ubuntu-26.04`.

### Added
- Repository policy against AI-tool attribution (`AGENTS.md`, `CONTRIBUTING.md`).
- Tests that guard the workflow matrix and the presence of the policy.

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
- The maintainer decided on the MIT License. `LICENSE` now contains the MIT text (previously the repository's initial commit carried Apache-2.0), copyright holder Diego Hurtado, 2026.
- `SKILL.md` (`license: MIT`), `README.md`, `ATTRIBUTION.md`, `CONTRIBUTING.md`, and `AGENTS.md` state MIT. Third-party licenses in `ATTRIBUTION.md` are unchanged.
- The validator now checks that the `license` field matches the `LICENSE` file.
