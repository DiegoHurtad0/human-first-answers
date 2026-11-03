# Contributor guide for Natural Voice

This repository contains an Agent Skill and its supporting references, examples, and evaluation cases. Improve behavior through clear, testable rules rather than adding more style prohibitions.

## Before changing anything

1. Read `SKILL.md`, the reference file relevant to the issue, and `docs/ARCHITECTURE.md` for file ownership.
2. Identify whether the problem is naturalness, clarity, context selection, consultative structure, or factual fidelity.
3. Check whether an existing rule already covers the case. Avoid duplicates and contradictory requirements.

## Working principles

- Keep the root `SKILL.md` focused and preferably below 250 lines; detailed guidance belongs in `references/`.
- Use the standard Agent Skills frontmatter. `name` must match the skill directory name (`natural-voice`).
- Do not claim an instruction guarantees a behavior on every host or model.
- Do not optimize for AI-detector evasion or add deliberate errors, fake emotion, fake anecdotes, or invented first-person experience.
- Treat style patterns as context-dependent signals. Avoid universal bans on punctuation, list structures, contractions, or specific words unless the behavior is demonstrably harmful in all relevant contexts.
- Preserve factual scope, user intent, safety guidance, domain terminology, and meaningful uncertainty.
- Do not describe or imitate proprietary internal consulting methods. General frameworks such as answer-first communication, issue trees, trade-off analysis, Pyramid Principle, and SCQA may be explained as public concepts.
- Keep multilingual behavior intentional. Do not mix languages unless the user does or requests it. Drafted artifacts should follow the target audience's language and register.
- Do not collect or persist personal information in voice profiles without user authorization. Never store sensitive information for style matching.

## Test-driven iteration

For every substantive behavioral change:

1. Add an evaluation case or regression case in `tests/`.
2. Run `python scripts/validate_project.py` and `python -m pytest -q` (install `requirements-dev.txt` first).
3. Check the generated YAML and Markdown for accidental formatting issues.
4. Review at least one positive case and one possible regression.
5. Summarize the behavior changed and what has not been tested.

The tests are acceptance criteria for human/LLM evaluation; they are not a standalone benchmark that proves a quality increase.

## Commit style

Use focused commits, for example:
- `feat: add consultative recommendation mode`
- `fix: avoid forced list formatting in simple answers`
- `test: add regression case for unsupported certainty`
- `docs: clarify voice-profile persistence`

## Release and license rules

- Natural Voice is MIT licensed. Do not change `LICENSE` or the license wording in the skill, README, or attribution without an explicit maintainer decision. Third-party licenses in `ATTRIBUTION.md` describe other projects and must not be edited to match.
- Never run `scripts/run_evaluation.py` without `--dry-run` from inside a Claude Code session, and never bypass its isolation checks.
- Do not commit `evaluation-results/`, `.env`, or local voice profiles (`.natural-voice/`).
- Claims of behavioral improvement need a completed evaluation report; otherwise label them unverified.
