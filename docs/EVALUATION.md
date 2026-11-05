# Evaluation

Natural Voice is judged in five layers. Only the first four run without a model.

| Layer | What it checks | How to run | Needs a model |
|---|---|---|---|
| A. Structural validation | Agent Skills spec, metadata, links, reference reachability, case schemas, README accuracy, hygiene | `python scripts/validate_project.py` | No |
| B. Unit tests | Validator, case loading, budgets, blinding, judge parsing, isolation checks, report rendering | `python -m pytest -q` | No |
| C. Plan check | Which cases run, blinding assignment, system-prompt size, isolation capability | `python scripts/run_evaluation.py --dry-run --suite all --max-calls 400` | No |
| D. Regression review | Known failure patterns in `tests/regression-cases.yaml`, including manual multi-turn cases | A person reads responses against `must` and `must_not` | Optional |
| E. Behavioral evaluation | Baseline vs candidate responses, judged blind on eight dimensions | `python scripts/run_evaluation.py` from a separate terminal | Yes |

Layers A and B prove that files are well formed and the tooling behaves as designed. They say nothing about response quality.

## Dimensions

Each is judged on its own: naturalness, clarity, relevance, contextual fit, factual fidelity, logical coherence, recommendation quality, decision usefulness. `recommendation_quality` and `decision_usefulness` may be `n/a`. There is no combined score. The report lists, per case, which dimensions the candidate lost.

## Case coverage

`scripts/case_schema.py` requires at least one evaluation case in each of: simple facts, casual chat (English and Spanish), personal advice, professional writing, text revision, technical explanation, senior engineering analysis, strategic decisions, evidence-based recommendations, ambiguous questions, strict formats, requests for depth, requests for brevity, cases where a framework would be wrong, contradictory information, ADHD mode, instruction precedence, conversation continuity, response relevance, implicit intent, and feedback adaptation. It also requires at least five Spanish cases and one scripted multi-turn case in each of English and Spanish.

## Multi-turn and manual cases

Conversation continuity cannot be judged from one message: "Sí." means nothing without the question before it. Cases of this kind use `turns`, a scripted transcript that ends on a user turn; the response under test is the assistant's next turn.

- The runner sends a single prompt and cannot replay scripted assistant turns, so `turns` requires `manual: true`. The schema rejects anything else.
- A transcript flattened into one prompt is not a stateful conversation and is not used as a stand-in.
- `python scripts/run_evaluation.py --show-manual` prints every manual case with its transcript, acceptance properties, and failure modes. A reviewer replays the scripted turns in a real conversation with the host and model under test (for example through an API that accepts message history) and judges the next response against the listed properties.
- Cases with a single `prompt` that do not depend on earlier turns stay automated, including the continuity cases about emotional disclosure, requested summaries, and consequential confirmations.
- Continuity properties are judged under the existing dimensions (contextual fit, naturalness, clarity, factual fidelity). No new dimension was added.
- The goal is less unnecessary echoing, not less repetition. Cases for requested summaries and consequential confirmations penalize a response that drops the repetition.

## Runner guarantees

- Hard call cap and USD cap; every attempt counts, including failures.
- No automatic retries. Two consecutive failures stop the run.
- The judge sees both responses as A and B in a seeded random order; the mapping is stored separately and applied after judging. The judge prompt contains no condition names.
- Baseline and candidate share model, system prompt base, and flags. The only difference is the Natural Voice text in the candidate's system prompt. The rubric is excluded from the candidate prompt.
- Isolation is checked from the CLI's own startup event on every call. A contaminated call aborts the run.
- A Claude Code release without `--safe-mode` blocks live runs. The runner does not fall back to a weaker mode, does not unset `CLAUDECODE`, and does not use unsupported flags.

## Status of behavioral claims

**No behavioral result exists for this repository.** Everything below is unverified.

| Claim | Status |
|---|---|
| Natural Voice makes answers more natural than a baseline | Unverified |
| It improves clarity or decision usefulness | Unverified |
| It does not reduce factual fidelity | Unverified |
| It follows the precedence order | Unverified; acceptance cases exist |
| ADHD mode stays optional and keeps completeness | Unverified; acceptance cases exist |
| Responses echo the user less while keeping needed repetition | Unverified; acceptance cases exist, seven of them manual |
| The assistant infers implicit intent without mind-reading, stops when the need is met, scales depth to the task, and keeps task-scoped corrections | Unverified; acceptance cases exist, the multi-turn ones manual |
| The files are valid and tooling works | Verified by layers A and B |

### History of live attempts

Two live runs were attempted on 2026-10-26 and produced no judgments:

1. The first stopped because Claude Code refused to start inside another Claude Code session (two calls, no output).
2. The second aborted on the isolation check because the CLI loaded its bundled skills (one call).

The runner was then changed to require `--safe-mode`. The Claude Code release installed when this document was written (2.1.63) does not provide that flag, so live evaluation remains blocked until Claude Code is updated and the script is run from a normal terminal.

## Known limits of a live run

- One trial per case and one judge. The judge is the same model family as the generator and may prefer its own style or longer answers; word counts are reported to help notice that.
- The candidate receives every reference inline. A host that loads references on demand may behave differently.
- Sampling temperature is not controllable through `claude -p`, so reruns differ.
- Multi-turn and system-prompt cases are marked `manual: true` and are not run by the script.
- Cost figures under a subscription login are notional.

## Methodology review

**Measurable today (no model):** that files, links, schemas, and the runner behave as designed (layers A to C). Nothing here measures response quality.

**Measurable with a live run (layer E, currently blocked):** blind baseline-vs-candidate comparison on the eight dimensions for automated single-prompt cases. This is the only layer that can support a behavioral claim, and only for those cases.

**Manual only:** every case with `turns` (feedback persistence across revisions, closing signals, short answers that depend on a prior question). A reviewer replays the transcript in a real conversation and judges against `expected` or `must` and `must_not`.

**Are the eight dimensions enough?** Yes for now. Implicit intent and proportion map to relevance and contextual fit; restraint to naturalness and clarity; carryover and invented commitments to factual fidelity and relevance; feedback persistence to contextual fit and logical coherence. A new dimension would need a case where those eight cannot register the failure. None has been found, so none was added.

**Bias risks to keep in view**
- The judge is the same model family as the generator and may favor longer or more polished answers. Restraint cases are the most exposed: a judge can read a one-word "Perfecto." as low effort. Judge them against the listed properties, not overall impression.
- Cases are written by the same people who wrote the rules, so they can encode the rules' assumptions. Treat passing them as acceptance, not proof.
- Brevity cases need the paired cases that require detail (confirmations, amounts, deadlines, safety) so that "shorter" cannot win by dropping facts. Those pairs exist.
- One trial per case and no temperature control mean small differences are noise.
- AI-detector scores are not used as evidence of naturalness.

**Reproducing a live run:** update Claude Code to a release that provides `--safe-mode`; open a normal terminal outside any Claude Code session; run `python scripts/run_evaluation.py --dry-run --suite all --max-calls 400` to see the plan; then rerun without `--dry-run` with deliberate call and USD caps. Do not unset `CLAUDECODE`, use `--bare`, or bypass the isolation check.

## Adding a case

1. Pick the narrowest category. Write a realistic prompt with no personal data.
2. List `expected` properties and `failure_modes` as observable behaviors, not wording.
3. Run `python scripts/validate_project.py`.
4. For a new failure you observed, add the regression case first, then change the rule.
