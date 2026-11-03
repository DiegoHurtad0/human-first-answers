# Contributing

Thank you for helping improve Natural Voice. Contributions are judged by whether they make responses better without trading away accuracy, so every behavior change comes with a test case.

## Setup

```bash
python3 -m pip install -r requirements-dev.txt
python3 scripts/validate_project.py
python3 -m pytest -q
```

Python 3.9 or newer. The skill itself has no dependencies; PyYAML and pytest are for development.

## Before you change anything

1. Read `SKILL.md` and the reference file that owns the topic (see `docs/ARCHITECTURE.md`).
2. Name the problem: naturalness, clarity, context selection, consultative structure, or factual fidelity.
3. Check whether an existing rule already covers it. Avoid duplicate or contradictory rules.

## Making a change

1. Write the failing case first: a prompt, the properties a good answer has (`expected`), and what a bad one does (`failure_modes`, or `must` / `must_not` for regressions).
2. Change the rule, not one output. Keep `SKILL.md` under 250 lines; detail goes in `references/`.
3. Run the validator and the tests.
4. Review one positive and one possible regression case by hand.
5. In the pull request, say what changed and what was **not** tested.

## Rules for rules

- No universal bans on a punctuation mark, word, list, or format unless it is harmful in every relevant context.
- No detector-evasion tricks, deliberate errors, fake emotion, invented anecdotes, or invented first-person experience.
- No claim that an instruction guarantees behavior on every host or model.
- Preserve factual scope, user intent, safety guidance, domain terms, and real uncertainty.
- Do not describe or imitate proprietary internal consulting methods. General frameworks may be explained as public concepts.
- Do not mix languages unless the user does.
- Voice profiles need user authorization. Never store sensitive information for style matching.

## Evaluation runs

`scripts/run_evaluation.py` makes model calls. Run it only from a separate terminal, never inside a Claude Code session, and keep the call and cost caps. Do not bypass its isolation checks. Generated output in `evaluation-results/` is git-ignored; do not commit it.

## Attribution and license

If you adapt material from another project, copy only what its license allows, keep its notice, and update `ATTRIBUTION.md`. Do not change `LICENSE` in a feature pull request; open an issue instead. By contributing you agree your work is provided under the repository's license.

## Commits

Use focused commits:

- `feat: add consultative recommendation mode`
- `fix: avoid forced list formatting in simple answers`
- `test: add regression case for unsupported certainty`
- `docs: clarify voice-profile persistence`
