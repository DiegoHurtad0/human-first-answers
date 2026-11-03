# Evaluation rubric

Use this rubric for human review, pairwise comparisons, or model-assisted evaluation. It is a guide for finding defects, not a single score to optimize blindly.

## Dimensions

Score each dimension from 1 to 5, or judge it pairwise. Dimensions are independent: do not average them into one score, and do not let a strong dimension hide a weak one.

| Dimension | 1 — Weak | 3 — Adequate | 5 — Strong |
|---|---|---|---|
| Naturalness | Templated, stiff, or performative | Generally readable, some formulaic phrasing | Appropriate voice, fluid but not artificially casual |
| Clarity | Hard to follow or buried answer | Understandable, minor friction | Main point and supporting logic are immediately clear |
| Relevance | Misses the actual request | Answers the main request with some noise | Directly solves the user's actual need |
| Contextual fit | Wrong register, depth, language, or format | Acceptable fit | Voice, depth, language, and format match the situation |
| Factual fidelity | Invents, distorts, or overstates | Mostly accurate, minor qualification gaps | Preserves facts, intent, uncertainty, and technical precision |
| Logical coherence | Contradictory, unsupported, or poorly ordered | Mostly sound, limited prioritization | Conclusion follows from the stated evidence and criteria |
| Recommendation quality | Evasive, arbitrary, or overconfident | Gives a view with partial support | Takes a justified position, names assumptions and what would change it. Not applicable when no recommendation is called for |
| Decision usefulness | Leaves the user unable to act | Somewhat useful | Makes the next decision or action clear. Not applicable when none is called for |

## Non-negotiable gates

A response fails regardless of its style score if it materially:

- Fabricates evidence, citations, quotations, calculations, or personal experience.
- Changes a user's meaning, commitments, or requested deliverable.
- Removes a safety-critical qualification or important uncertainty.
- Violates a required format or output schema.
- Exposes private internal reasoning rather than a concise rationale.

## Pairwise evaluation

When comparing two outputs for the same prompt, ask:

1. Which answers the request more directly?
2. Which one sounds more natural for this context without becoming performative?
3. Which makes its reasoning easier to evaluate?
4. Which preserves more important facts, caveats, and intent?
5. Would a real reader prefer one, and why?

Randomize which candidate is called A or B during blind evaluations. Include a tie option. Judge task success and factuality alongside style.

## Regression checks

Style improvement is not a win if it makes responses less accurate, less useful, overly short, too informal, or unnecessarily structured. Specifically, these are regressions:

- Prose that is shorter but has lost essential context.
- A more casual tone that reduces professionalism where the audience expects it.
- Headings or a consulting structure added to a simple question.
- A rewrite that changes the meaning of the message.

Compare against existing regression cases after changing rules.

Do not rely on AI detectors as a proxy for quality. Detector scores do not establish naturalness, usefulness, or factual fidelity.
