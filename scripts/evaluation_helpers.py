"""Pure helpers for the Natural Voice pilot evaluation (no model calls here)."""
from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field

from case_schema import DIMENSIONS, NA_ALLOWED  # single source of truth for the dimensions

VERDICTS = {"A", "B", "tie", "n/a"}  # "n/a" is only valid for the dimensions in NA_ALLOWED


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class Budget:
    """Hard call cap plus a USD cap on reported (possibly notional) cost.

    Every attempt counts, including failed ones. Nothing retries.
    """

    max_calls: int
    max_usd: float
    calls: int = 0
    usd: float = 0.0
    unmetered_calls: int = 0  # calls that returned no cost figure

    def check(self) -> None:
        if self.calls >= self.max_calls:
            raise BudgetExceeded(f"call cap reached ({self.calls}/{self.max_calls})")
        if self.usd >= self.max_usd:
            raise BudgetExceeded(f"cost cap reached (${self.usd:.4f}/${self.max_usd:.2f})")

    def remaining_usd(self) -> float:
        return max(self.max_usd - self.usd, 0.0)

    def start_call(self) -> None:
        self.check()
        self.calls += 1

    def record_cost(self, cost: float | None) -> None:
        if cost is None:
            self.unmetered_calls += 1
        else:
            self.usd += cost


# --- blinding -------------------------------------------------------------

def assign_blinding(case_ids: list[str], seed: int) -> dict[str, dict[str, str]]:
    """Return {case_id: {"A": condition, "B": condition}}, reproducible from seed."""
    mapping = {}
    for case_id in case_ids:
        flip = random.Random(f"{seed}:{case_id}").random() < 0.5
        mapping[case_id] = {"A": "candidate", "B": "baseline"} if flip else {"A": "baseline", "B": "candidate"}
    return mapping


def word_count(text: str) -> int:
    return len(text.split())


def build_judge_prompt(case: dict, rubric: str, response_a: str, response_b: str) -> str:
    """Everything here is judge-visible. It must not name conditions or skills."""
    expected = "\n".join(f"- {x}" for x in case.get("expected", []))
    failures = "\n".join(f"- {x}" for x in case.get("failure_modes", []))
    dims = ", ".join(DIMENSIONS)
    return f"""Compare two assistant responses to the same user prompt.

<user_prompt>
{case['prompt']}
</user_prompt>

Acceptance properties for this prompt (guides, not a checklist to score mechanically):
{expected}

Known failure modes for this prompt:
{failures}

<rubric>
{rubric}
</rubric>

<response_a>
{response_a}
</response_a>

<response_b>
{response_b}
</response_b>

Judge each dimension independently: {dims}.
Rules:
- For each dimension choose "A", "B", or "tie". Use "n/a" only for recommendation_quality or decision_usefulness when the prompt calls for no recommendation or action.
- Keep the dimensions independent: a strong result on one must not raise or lower another.
- Quote or closely cite evidence from the responses for every verdict. Do not reward length for its own sake.
- List any rubric non-negotiable gate failures per response (fabricated evidence, changed meaning, removed safety caveat, violated format, exposed reasoning), or an empty list.
- Do not guess which system produced either response.

Reply with only a JSON object, no Markdown fences, in exactly this shape:
{{"dimensions": {{"<dimension>": {{"verdict": "A|B|tie|n/a", "evidence": "..."}}}}, "gate_failures": {{"A": [], "B": []}}, "overall": "A|B|tie", "summary": "one or two sentences"}}"""


class JudgeParseError(ValueError):
    pass


def parse_judge_output(text: str) -> dict:
    """Extract and validate the judge JSON. Raises JudgeParseError on any problem."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    elif not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise JudgeParseError("no JSON object found")
        text = text[start : end + 1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise JudgeParseError(f"invalid JSON: {exc}") from exc
    dims = data.get("dimensions")
    if not isinstance(dims, dict):
        raise JudgeParseError("missing 'dimensions' object")
    for name in DIMENSIONS:
        entry = dims.get(name)
        if not isinstance(entry, dict) or entry.get("verdict") not in VERDICTS:
            raise JudgeParseError(f"dimension '{name}' missing or has an invalid verdict")
        if entry["verdict"] == "n/a" and name not in NA_ALLOWED:
            raise JudgeParseError(f"'n/a' is only allowed for {sorted(NA_ALLOWED)}, not '{name}'")
        if not str(entry.get("evidence", "")).strip():
            raise JudgeParseError(f"dimension '{name}' has no evidence")
    if data.get("overall") not in {"A", "B", "tie"}:
        raise JudgeParseError("'overall' must be A, B, or tie")
    gates = data.get("gate_failures", {})
    if not isinstance(gates, dict):
        raise JudgeParseError("'gate_failures' must be an object")
    return data


# --- aggregation ----------------------------------------------------------

def unblind(verdict: str, mapping: dict[str, str]) -> str:
    """Map a judge verdict (A/B/tie/n/a) to candidate/baseline/tie/n/a."""
    return mapping[verdict] if verdict in ("A", "B") else verdict


@dataclass
class Tally:
    candidate: int = 0
    baseline: int = 0
    tie: int = 0
    na: int = 0

    def add(self, outcome: str) -> None:
        if outcome == "candidate":
            self.candidate += 1
        elif outcome == "baseline":
            self.baseline += 1
        elif outcome == "tie":
            self.tie += 1
        else:
            self.na += 1


@dataclass
class Summary:
    overall: Tally = field(default_factory=Tally)
    dimensions: dict[str, Tally] = field(default_factory=lambda: {d: Tally() for d in DIMENSIONS})
    gate_failures: dict[str, int] = field(default_factory=lambda: {"candidate": 0, "baseline": 0})


def summarize(judgments: dict[str, dict], blinding: dict[str, dict[str, str]]) -> Summary:
    """judgments: case_id -> parsed judge output. blinding: case_id -> {"A":cond,"B":cond}."""
    summary = Summary()
    for case_id, judged in judgments.items():
        mapping = blinding[case_id]
        summary.overall.add(unblind(judged["overall"], mapping))
        for name in DIMENSIONS:
            summary.dimensions[name].add(unblind(judged["dimensions"][name]["verdict"], mapping))
        for label, items in (judged.get("gate_failures") or {}).items():
            if label in mapping and items:
                summary.gate_failures[mapping[label]] += len(items)
    return summary
