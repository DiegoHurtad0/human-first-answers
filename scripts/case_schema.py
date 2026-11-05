"""Load and validate the behavioral test-case files. Single owner of the case schema.

Needs PyYAML (`pip install -r requirements-dev.txt`). There is no fallback parser:
a hand-rolled one would silently accept files that real YAML tooling rejects.
"""
from __future__ import annotations

import re
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only on machines without PyYAML
    yaml = None

DIMENSIONS = [
    "naturalness",
    "clarity",
    "relevance",
    "contextual_fit",
    "factual_fidelity",
    "logical_coherence",
    "recommendation_quality",
    "decision_usefulness",
]
# Dimensions a judge may mark "n/a" when the prompt calls for no recommendation or action.
NA_ALLOWED = {"recommendation_quality", "decision_usefulness"}

# Every category must have at least one evaluation case (see check_coverage).
REQUIRED_CATEGORIES = [
    "factual_simple",
    "casual_conversation",
    "personal_advice",
    "professional_communication",
    "text_revision",
    "technical_explanation",
    "engineering_analysis",
    "strategic_decision",
    "evidence_recommendation",
    "ambiguous_question",
    "strict_format",
    "depth_request",
    "concise_request",
    "framework_inappropriate",
    "uncertainty_contradiction",
    "adhd_mode",
    "instruction_precedence",
    "conversation_continuity",
    "response_relevance",
    "implicit_intent",
    "feedback_adaptation",
]
REQUIRED_LANGUAGE_CATEGORIES = [("casual_conversation", "en"), ("casual_conversation", "es")]
MIN_SPANISH_CASES = 5
MULTI_TURN_LANGUAGES = ["en", "es"]  # each needs at least one scripted multi-turn (manual) evaluation case
TURN_ROLES = {"user", "assistant"}

ID_RE = re.compile(r"^[a-z0-9_]+$")
LANGUAGE_RE = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")


class CaseFileError(ValueError):
    """The case file is missing, unparsable, or not shaped as expected."""


def _require_yaml() -> None:
    if yaml is None:
        raise CaseFileError("PyYAML is required to read test cases: pip install -r requirements-dev.txt")


def read_yaml(path: Path) -> dict:
    _require_yaml()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CaseFileError(f"{path}: file not found") from exc
    except yaml.YAMLError as exc:
        raise CaseFileError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise CaseFileError(f"{path}: top level must be a mapping")
    return data


def _string_list(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(x, str) and x.strip() for x in value)


def check_case_input(case: dict, label: str, errors: list[str]) -> None:
    """A case supplies exactly one of `prompt` (single turn) or `turns` (scripted transcript).

    `turns` is the history before the response under test, so it must end on a user turn.
    The runner can only send one prompt and cannot replay scripted assistant turns, so a
    transcript is a manual case: it is reviewed by a person in a real stateful conversation.
    """
    if ("prompt" in case) == ("turns" in case):
        errors.append(f"{label}: give exactly one of 'prompt' or 'turns'")
    if "prompt" in case and (not isinstance(case["prompt"], str) or not case["prompt"].strip()):
        errors.append(f"{label}: 'prompt' must be a non-empty string")
    if "turns" not in case:
        return
    turns = case["turns"]
    if not isinstance(turns, list) or len(turns) < 2:
        errors.append(f"{label}: 'turns' must be a list of at least two turns (use 'prompt' for one)")
        return
    for number, turn in enumerate(turns, start=1):
        if (not isinstance(turn, dict) or set(turn) != {"role", "text"} or turn["role"] not in TURN_ROLES
                or not isinstance(turn["text"], str) or not turn["text"].strip()):
            errors.append(f"{label}: turn {number} must be {{role: user|assistant, text: <non-empty>}}")
    if isinstance(turns[-1], dict) and turns[-1].get("role") != "user":
        errors.append(f"{label}: the last turn must be a user turn; the response under test follows it")
    if case.get("manual") is not True:
        errors.append(f"{label}: cases with 'turns' must set 'manual: true' (the runner cannot replay scripted turns)")


def render_transcript(turns: list[dict]) -> str:
    """Plain-text transcript for a human reviewer replaying a manual case."""
    names = {"user": "User", "assistant": "Assistant"}
    return "\n".join(f"{names[t['role']]}: {t['text']}" for t in turns)


def validate_evaluation_file(data: dict) -> list[str]:
    """Return every problem found, so one run reports them all."""
    errors: list[str] = []
    if not isinstance(data.get("version"), int):
        errors.append("evaluation cases: 'version' must be an integer")
    if data.get("scoring_dimensions") != DIMENSIONS:
        errors.append("evaluation cases: 'scoring_dimensions' must equal case_schema.DIMENSIONS (same order)")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        return errors + ["evaluation cases: 'cases' must be a non-empty list"]
    seen: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"evaluation cases[{index}]: must be a mapping")
            continue
        cid = case.get("id")
        label = f"evaluation case '{cid}'" if isinstance(cid, str) else f"evaluation cases[{index}]"
        if not isinstance(cid, str) or not ID_RE.match(cid):
            errors.append(f"{label}: 'id' must match {ID_RE.pattern}")
        elif cid in seen:
            errors.append(f"{label}: duplicate id")
        else:
            seen.add(cid)
        if not isinstance(case.get("language"), str) or not LANGUAGE_RE.match(case["language"]):
            errors.append(f"{label}: 'language' must look like 'en' or 'es-MX'")
        if case.get("category") not in REQUIRED_CATEGORIES:
            errors.append(f"{label}: 'category' {case.get('category')!r} is not a known category")
        if not isinstance(case.get("intent"), str) or not case["intent"].strip():
            errors.append(f"{label}: 'intent' must be a non-empty string")
        check_case_input(case, label, errors)
        for field in ("expected", "failure_modes"):
            if not _string_list(case.get(field)):
                errors.append(f"{label}: '{field}' must be a non-empty list of strings")
        if "manual" in case and not isinstance(case["manual"], bool):
            errors.append(f"{label}: 'manual' must be true or false")
        unknown = set(case) - {"id", "language", "category", "intent", "prompt", "turns", "expected", "failure_modes", "manual"}
        if unknown:
            errors.append(f"{label}: unknown field(s) {sorted(unknown)}")
    errors += check_coverage([c for c in cases if isinstance(c, dict)])
    return errors


def check_coverage(cases: list[dict]) -> list[str]:
    errors = []
    present = {c.get("category") for c in cases}
    for category in REQUIRED_CATEGORIES:
        if category not in present:
            errors.append(f"coverage: no evaluation case in category '{category}'")
    for category, prefix in REQUIRED_LANGUAGE_CATEGORIES:
        if not any(c.get("category") == category and str(c.get("language", "")).startswith(prefix) for c in cases):
            errors.append(f"coverage: no '{category}' case in language '{prefix}'")
    for prefix in MULTI_TURN_LANGUAGES:
        if not any("turns" in c and str(c.get("language", "")).startswith(prefix) for c in cases):
            errors.append(f"coverage: no scripted multi-turn evaluation case in language '{prefix}'")
    spanish = sum(1 for c in cases if str(c.get("language", "")).startswith("es"))
    if spanish < MIN_SPANISH_CASES:
        errors.append(f"coverage: {spanish} Spanish case(s), need at least {MIN_SPANISH_CASES}")
    return errors


def validate_regression_file(data: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(data.get("version"), int):
        errors.append("regression cases: 'version' must be an integer")
    cases = data.get("regressions")
    if not isinstance(cases, list) or not cases:
        return errors + ["regression cases: 'regressions' must be a non-empty list"]
    seen: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"regressions[{index}]: must be a mapping")
            continue
        cid = case.get("id")
        label = f"regression '{cid}'" if isinstance(cid, str) else f"regressions[{index}]"
        if not isinstance(cid, str) or not ID_RE.match(cid):
            errors.append(f"{label}: 'id' must match {ID_RE.pattern}")
        elif cid in seen:
            errors.append(f"{label}: duplicate id")
        else:
            seen.add(cid)
        check_case_input(case, label, errors)
        for field in ("must", "must_not"):
            if not _string_list(case.get(field)):
                errors.append(f"{label}: '{field}' must be a non-empty list of strings")
        if "language" in case and (not isinstance(case["language"], str) or not LANGUAGE_RE.match(case["language"])):
            errors.append(f"{label}: 'language' must look like 'en' or 'es-MX'")
        if "manual" in case and not isinstance(case["manual"], bool):
            errors.append(f"{label}: 'manual' must be true or false")
        unknown = set(case) - {"id", "language", "prompt", "turns", "must", "must_not", "manual", "note"}
        if unknown:
            errors.append(f"{label}: unknown field(s) {sorted(unknown)}")
    return errors


def load_evaluation_cases(path: Path) -> dict[str, dict]:
    data = read_yaml(path)
    errors = validate_evaluation_file(data)
    if errors:
        raise CaseFileError(f"{path}: " + "; ".join(errors))
    return {c["id"]: {"prompt": None, "turns": None, **c, "manual": c.get("manual", False)} for c in data["cases"]}


def load_regression_cases(path: Path) -> dict[str, dict]:
    """Regression cases use the runner's shape: must -> expected, must_not -> failure_modes."""
    data = read_yaml(path)
    errors = validate_regression_file(data)
    if errors:
        raise CaseFileError(f"{path}: " + "; ".join(errors))
    return {
        c["id"]: {"id": c["id"], "language": c.get("language", "en"), "category": "regression", "intent": "regression",
                  "prompt": c.get("prompt"), "turns": c.get("turns"), "expected": c["must"],
                  "failure_modes": c["must_not"],
                  "manual": c.get("manual", False)}
        for c in data["regressions"]
    }


def load_all_cases(tests_dir: Path) -> dict[str, dict]:
    evaluation = load_evaluation_cases(tests_dir / "evaluation-cases.yaml")
    regression = load_regression_cases(tests_dir / "regression-cases.yaml")
    clash = sorted(set(evaluation) & set(regression))
    if clash:
        raise CaseFileError(f"ids used in both case files: {clash}")
    return {**evaluation, **regression}
