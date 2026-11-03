## What changed and why

<!-- One behavior problem per PR where possible. Name the failure this fixes. -->

## Category

- [ ] naturalness  - [ ] clarity  - [ ] context selection  - [ ] consultative structure  - [ ] factual fidelity  - [ ] tooling/docs

## Checklist

- [ ] I checked that no existing rule already covers this (no duplicate or contradictory rule).
- [ ] I added or updated a case in `tests/evaluation-cases.yaml` or `tests/regression-cases.yaml`.
- [ ] `python scripts/validate_project.py` passes.
- [ ] `python -m pytest -q` passes.
- [ ] I did not add universal bans on punctuation, words, or formats, or detector-evasion tricks.
- [ ] I did not change `LICENSE` or attribution without discussion.

## What was not tested

<!-- Be specific. Test cases are acceptance criteria, not proof of improvement. -->
