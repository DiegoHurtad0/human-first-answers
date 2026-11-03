#!/usr/bin/env python3
"""Bounded baseline-vs-candidate pilot for Natural Voice using `claude -p`.

Baseline and candidate share one model, one minimal system prompt, and run under
`--safe-mode` (requires a Claude Code release that has it; subscription login is
kept) with no tools, no settings sources, bundled skills disabled, and an empty
working directory. The CLI's own startup event is checked on every call and the
run aborts on any skill, plugin, hook, MCP server, memory path, or API-key auth. The only
intended difference is that the candidate's system prompt also contains the
Natural Voice instructions (SKILL.md body plus the reference files), supplied
explicitly because `claude -p` does not load a root-level SKILL.md on its own.

Usage:
  python3 scripts/run_evaluation.py --dry-run                 # no model calls; works anywhere
  python3 scripts/run_evaluation.py                           # pilot: 8 cases, at most 24 calls
  python3 scripts/run_evaluation.py --suite evaluation --max-calls 120 --max-usd 15
  python3 scripts/run_evaluation.py --cases precedence_user_overrides_brevity

Suites: pilot (default), evaluation (every case in evaluation-cases.yaml),
regression (regression-cases.yaml), all. Cases marked `manual: true` need a
multi-turn transcript or a human and are never run automatically.

Generated output goes to evaluation-results/<run-id>/ (git-ignored).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import case_schema  # noqa: E402
import evaluation_helpers as H  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BASE_SYSTEM = "You are a helpful assistant."
JUDGE_SYSTEM = (
    "You are a careful evaluator of written responses. You judge only what is in front of you, "
    "cite evidence, allow ties, and reply with exactly the JSON the user requests."
)
DEFAULT_MAX_CALLS = 24
DEFAULT_MAX_USD = 5.0
PILOT_CASES = [
    "direct_simple_question",
    "spanish_personal_advice",
    "consultative_metrics",
    "copy_ready_message",
    "technical_detail",
    "uncertain_vendor_choice",
    "strict_format",
    "user_requests_depth",
]
# Reference files supplied to the candidate. evaluation-rubric.md is excluded on
# purpose: it is the judge's rubric and the candidate should not be tuned to it.
EXCLUDED_REFERENCES = {"evaluation-rubric.md"}


@dataclass
class CallResult:
    text: str
    cost: float | None = None
    usage: dict = field(default_factory=dict)
    model: str | None = None
    init: dict = field(default_factory=dict)
    error: str | None = None
    isolation_error: str | None = None


class IsolationError(RuntimeError):
    pass


# --- prompts --------------------------------------------------------------

def strip_frontmatter(text: str) -> str:
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end >= 0:
            return text[end + 5 :].lstrip("\n")
    return text


def build_candidate_system(root: Path = ROOT) -> str:
    parts = [BASE_SYSTEM, "", "Follow the Natural Voice skill below. Its reference files are included after it.", "",
             "# SKILL.md", strip_frontmatter((root / "SKILL.md").read_text(encoding="utf-8"))]
    for ref in sorted((root / "references").glob("*.md")):
        if ref.name in EXCLUDED_REFERENCES:
            continue
        parts += ["", f"# references/{ref.name}", (root / "references" / ref.name).read_text(encoding="utf-8")]
    return "\n".join(parts)


def claude_version() -> str:
    if os.environ.get("NV_EVAL_NO_VERSION"):
        return "n/a"
    try:
        return subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# --- claude -p client -----------------------------------------------------

# Billing credentials that would silently move the run off the subscription.
API_KEY_SOURCES = {"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "apiKeyHelper"}


def clean_env() -> dict[str, str]:
    """Drop inherited Claude Code session and API variables so the child is a fresh, standalone run.

    CLAUDE_CODE_DISABLE_BUNDLED_SKILLS removes the skills that ship inside Claude Code
    (debug, simplify, ...), which --safe-mode alone leaves loaded.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE_") and not k.startswith("ANTHROPIC_")}
    env["CLAUDE_CODE_DISABLE_BUNDLED_SKILLS"] = "1"
    return env


def build_command(model: str, system: str, max_usd: float) -> list[str]:
    """The exact argv for every model-backed step (baseline, candidate, judge)."""
    return [
        "claude", "-p", "--safe-mode", "--output-format", "stream-json", "--verbose",
        "--model", model, "--system-prompt", system,
        "--tools", "", "--setting-sources", "", "--disable-slash-commands",
        "--strict-mcp-config", "--no-session-persistence",
        "--max-budget-usd", f"{max_usd:.2f}",
    ]


def supports_safe_mode(help_text: str) -> bool:
    return "--safe-mode" in help_text


def require_safe_mode(run=None) -> None:
    """Zero-model-call capability check. Fails closed; never falls back to a weaker mode."""
    run = run or subprocess.run
    try:
        proc = run(["claude", "--help"], capture_output=True, text=True, timeout=30, env=clean_env())
    except (OSError, subprocess.SubprocessError) as exc:
        raise IsolationError(f"could not run `claude --help`: {exc}") from exc
    if not supports_safe_mode((proc.stdout or "") + (proc.stderr or "")):
        version = ""
        try:
            version = run(["claude", "--version"], capture_output=True, text=True, timeout=30,
                          env=clean_env()).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
        raise IsolationError(
            f"the installed Claude Code ({version or 'unknown version'}) has no --safe-mode flag, so the "
            "evaluation cannot be isolated while keeping subscription login. Update Claude Code "
            "(`claude update` or `npm install -g @anthropic-ai/claude-code@latest`) and rerun. "
            "--bare is not used because it ignores OAuth/subscription login."
        )


def find_project_instructions(path: str) -> list[str]:
    """CLAUDE.md / .claude entries in the working directory or any parent (zero model calls)."""
    found = []
    here = Path(path).resolve()
    for d in [here, *here.parents]:
        for name in ("CLAUDE.md", "CLAUDE.local.md", ".claude"):
            if (d / name).exists():
                found.append(str(d / name))
    return found


def check_isolation(init: dict, events: list[dict] | None = None, requested_model: str | None = None) -> None:
    """Fail closed on any sign of contamination, using the CLI's own startup event."""
    if not init:
        raise IsolationError("no startup (init) event was emitted, so isolation cannot be verified")
    problems = []
    for key in ("tools", "mcp_servers", "skills", "plugins", "plugin_errors", "mcp_server_errors"):
        if init.get(key):
            problems.append(f"{key}: {init[key]}")
    if init.get("memory_paths"):
        problems.append(f"memory_paths: {init['memory_paths']}")
    if init.get("apiKeySource") in API_KEY_SOURCES:
        problems.append(f"apiKeySource: {init['apiKeySource']} (would not use the subscription login)")
    hooks = [e.get("hook_event") or e.get("hook_name") or e.get("subtype")
             for e in (events or []) if e.get("type") == "system" and str(e.get("subtype", "")).startswith("hook")]
    if hooks:
        problems.append(f"hooks fired: {hooks}")
    model = init.get("model")
    if requested_model and model and requested_model not in model and model not in requested_model:
        problems.append(f"model: requested {requested_model}, got {model}")
    if problems:
        raise IsolationError("; ".join(problems))


INIT_KEYS = ("model", "tools", "mcp_servers", "skills", "plugins", "agents", "permissionMode",
             "apiKeySource", "claude_code_version", "output_style", "memory_paths")


def evaluate_stream(stdout: str, returncode: int, stderr: str, requested_model: str | None = None) -> CallResult:
    """Turn one `claude -p --output-format stream-json` run into a CallResult.

    A failed process is a plain error. A successful process without clean startup
    evidence carries `isolation_error`, so its cost is still recorded before the run aborts.
    """
    events = []
    for line in stdout.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
    final = next((e for e in reversed(events) if e.get("type") == "result"), {})
    cost = final.get("total_cost_usd") if final else None
    if returncode != 0 or not final or final.get("is_error"):
        detail = (final.get("result") if final else None) or stderr.strip()[:300] or f"exit {returncode}"
        return CallResult("", cost=cost, error=str(detail))
    summary = {k: init.get(k) for k in INIT_KEYS if k in init}
    try:
        check_isolation(init, events, requested_model)
    except IsolationError as exc:
        return CallResult("", cost=cost, init=summary, isolation_error=str(exc))
    return CallResult(text=(final.get("result") or "").strip(), cost=cost, usage=final.get("usage") or {},
                      model=init.get("model"), init=summary)


def claude_client(model: str, timeout: int, per_call_usd: float, budget: H.Budget, run=subprocess.run):
    workdir = tempfile.mkdtemp(prefix="nv-eval-")  # empty: no project files
    contaminated = find_project_instructions(workdir)
    if contaminated:
        raise IsolationError(f"project instructions found at or above the working directory: {contaminated}")

    def call(system: str, prompt: str) -> CallResult:
        cap = min(per_call_usd, budget.remaining_usd())
        cmd = build_command(model, system, cap)
        try:
            proc = run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout,
                       cwd=workdir, env=clean_env())
        except subprocess.TimeoutExpired:
            return CallResult("", error=f"timeout after {timeout}s")
        except OSError as exc:
            return CallResult("", error=f"could not start claude: {exc}")
        return evaluate_stream(proc.stdout, proc.returncode, proc.stderr, model)

    return call


# --- orchestration --------------------------------------------------------

def run_pilot(client, budget: H.Budget, cases: dict[str, dict], case_ids: list[str], seed: int,
              out_dir: Path, candidate_system: str, rubric: str, model: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    blinding = H.assign_blinding(case_ids, seed)
    (out_dir / "blinding.json").write_text(json.dumps(blinding, indent=2))  # never shown to the judge
    systems = {"baseline": BASE_SYSTEM, "candidate": candidate_system}
    config = {
        "model_requested": model, "seed": seed, "case_ids": case_ids,
        "max_calls": budget.max_calls, "max_usd": budget.max_usd,
        "system_prompt_sha256_16": {k: sha(v) for k, v in systems.items()},
        "judge_system_sha256_16": sha(JUDGE_SYSTEM),
        "claude_version": claude_version(),
        "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    (out_dir / "config.json").write_text(json.dumps(config, indent=2))
    (out_dir / "system_candidate.txt").write_text(candidate_system)

    errors: list[dict] = []
    responses: dict[str, dict[str, str]] = {}
    judgments: dict[str, dict] = {}
    consecutive_failures = 0
    models_seen: set[str] = set()
    aborted: str | None = None

    def record(path: str, row: dict) -> None:
        with (out_dir / path).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    def attempt(kind: str, case_id: str, system: str, prompt: str) -> CallResult | None:
        nonlocal consecutive_failures, aborted
        budget.start_call()
        result = client(system, prompt)
        budget.record_cost(result.cost)
        if result.isolation_error:
            raise IsolationError(result.isolation_error)
        if result.model:
            models_seen.add(result.model)
        if result.error or not result.text:
            consecutive_failures += 1
            err = {"case": case_id, "stage": kind, "error": result.error or "empty response"}
            errors.append(err)
            record("errors.jsonl", err)
            if consecutive_failures >= 2:
                aborted = "two consecutive failed calls; stopping instead of spending more"
            return None
        consecutive_failures = 0
        return result

    try:
        for case_id in case_ids:
            if aborted:
                break
            case = cases[case_id]
            pair: dict[str, str] = {}
            for condition in ("baseline", "candidate"):
                res = attempt("generate:" + condition, case_id, systems[condition], case["prompt"])
                if res is None:
                    break
                pair[condition] = res.text
                record("responses.jsonl", {"case": case_id, "condition": condition, "text": res.text,
                                           "words": H.word_count(res.text), "cost": res.cost,
                                           "usage": res.usage, "init": res.init})
            if len(pair) == 2:
                responses[case_id] = pair
        for case_id, pair in responses.items():
            if aborted:
                break
            mapping = blinding[case_id]
            a, b = pair[mapping["A"]], pair[mapping["B"]]
            prompt = H.build_judge_prompt(cases[case_id], rubric, a, b)
            record("judge_inputs.jsonl", {"case": case_id, "prompt": prompt})
            res = attempt("judge", case_id, JUDGE_SYSTEM, prompt)
            if res is None:
                continue
            try:
                parsed = H.parse_judge_output(res.text)
            except H.JudgeParseError as exc:
                err = {"case": case_id, "stage": "judge_parse", "error": str(exc), "raw": res.text[:2000]}
                errors.append(err)
                record("errors.jsonl", err)
                continue
            judgments[case_id] = parsed
            record("judgments.jsonl", {"case": case_id, "parsed": parsed, "raw": res.text})
    except H.BudgetExceeded as exc:
        aborted = f"budget: {exc}"
    except IsolationError as exc:
        aborted = f"isolation failure, no further calls: {exc}"

    summary = H.summarize(judgments, blinding)
    result = {
        "aborted": aborted, "calls": budget.calls, "usd_reported": round(budget.usd, 4),
        "calls_without_cost": budget.unmetered_calls, "models_seen": sorted(models_seen),
        "errors": errors, "responses": responses, "judgments": judgments, "summary": summary,
        "blinding": blinding,
    }
    (out_dir / "report.md").write_text(render_report(result, config, cases, case_ids))
    return result


VERDICT_SYMBOL = {"candidate": "C", "baseline": "B", "tie": "=", "n/a": "-"}


def render_report(result: dict, config: dict, cases: dict[str, dict], case_ids: list[str]) -> str:
    s: H.Summary = result["summary"]
    n = len(result["judgments"])
    lines = ["# Natural Voice evaluation", "",
             f"Cases judged: {n} of {len(case_ids)} planned. Screening result, not evidence of general improvement.", "",
             f"- Model requested: `{config['model_requested']}`; observed: {', '.join(result['models_seen']) or 'none'}",
             f"- Seed: {config['seed']}; calls used: {result['calls']}/{config['max_calls']}",
             f"- Reported cost: ${result['usd_reported']:.4f} (cap ${config['max_usd']:.2f}); "
             f"{result['calls_without_cost']} call(s) returned no cost figure",
             f"- Stopped early: {result['aborted'] or 'no'}", "",
             "## By dimension (unblinded after judging)", "",
             "Dimensions are reported separately on purpose. There is no combined score.", "",
             "| Dimension | Candidate | Baseline | Tie | n/a |", "|---|---|---|---|---|"]
    for d in H.DIMENSIONS:
        t = s.dimensions[d]
        lines.append(f"| {d} | {t.candidate} | {t.baseline} | {t.tie} | {t.na} |")
    lines += ["", f"Gate failures reported by the judge: candidate {s.gate_failures['candidate']}, "
                  f"baseline {s.gate_failures['baseline']}.", "",
              "## Where the candidate lost", ""]
    losses = []
    for cid, judged in result["judgments"].items():
        mapping = result["blinding"][cid]
        lost = [d for d in H.DIMENSIONS
                if H.unblind(judged["dimensions"][d]["verdict"], mapping) == "baseline"]
        if lost:
            losses.append(f"- **{cid}**: {', '.join(lost)}")
    lines += losses or ["- No dimension in any judged case went to the baseline."]
    lines += ["", "## Per case", "",
              "Cells: C candidate, B baseline, = tie, - not applicable. Words are baseline / candidate.", "",
              "| Case | Overall | " + " | ".join(H.DIMENSIONS) + " | Words |",
              "|---|---|" + "---|" * len(H.DIMENSIONS) + "---|"]
    for cid in case_ids:
        pair = result["responses"].get(cid)
        words = f"{H.word_count(pair['baseline'])} / {H.word_count(pair['candidate'])}" if pair else "-"
        if cid in result["judgments"]:
            judged, mapping = result["judgments"][cid], result["blinding"][cid]
            overall = H.unblind(judged["overall"], mapping)
            cells = [VERDICT_SYMBOL[H.unblind(judged["dimensions"][d]["verdict"], mapping)] for d in H.DIMENSIONS]
        else:
            overall, cells = "not judged", ["-"] * len(H.DIMENSIONS)
        lines.append(f"| {cid} | {overall} | " + " | ".join(cells) + f" | {words} |")
    lines += ["", f"Holistic preference across cases (secondary, not a score): candidate {s.overall.candidate}, "
                  f"baseline {s.overall.baseline}, tie {s.overall.tie}.", "", "## Judge summaries", ""]
    for cid, judged in result["judgments"].items():
        outcome = H.unblind(judged["overall"], result["blinding"][cid])
        lines.append(f"- **{cid}** ({outcome}): {judged.get('summary', '').strip()}")
    if result["errors"]:
        lines += ["", "## Errors", ""] + [f"- {e['case']} / {e['stage']}: {e['error']}" for e in result["errors"]]
    lines += ["", "## Limitations", "",
              "- One trial per case and one automated judge: a screening result only.",
              "- The judge is the same model family as the generator and may favor its own style or longer answers; word counts are reported to help spot that.",
              "- The candidate receives SKILL.md and all references inline, which is an upper bound on a host that loads references on demand.",
              "- Cost is whatever `claude -p` reports; under a subscription login it is notional, not a bill.",
              "- Sampling temperature cannot be set through `claude -p`, so outputs are not exactly repeatable."]
    return "\n".join(lines) + "\n"


def select_cases(args, cases: dict[str, dict]) -> list[str]:
    """Resolve --cases / --suite to ids. Manual cases are never part of a suite."""
    if args.cases:
        return args.cases
    if args.suite == "pilot":
        return PILOT_CASES
    categories = {"evaluation": lambda c: c["category"] != "regression",
                  "regression": lambda c: c["category"] == "regression",
                  "all": lambda c: True}[args.suite]
    return [cid for cid, c in cases.items() if categories(c) and not c["manual"]]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", default="claude-sonnet-4-6", help="pinned for all three roles")
    p.add_argument("--seed", type=int, default=20261026)
    p.add_argument("--suite", choices=["pilot", "evaluation", "regression", "all"], default="pilot")
    p.add_argument("--cases", nargs="+", help="explicit case ids; overrides --suite")
    p.add_argument("--max-calls", type=int, default=DEFAULT_MAX_CALLS)
    p.add_argument("--max-usd", type=float, default=DEFAULT_MAX_USD)
    p.add_argument("--per-call-usd", type=float, default=0.5)
    p.add_argument("--timeout", type=int, default=240)
    p.add_argument("--output-dir", type=Path, default=ROOT / "evaluation-results")
    p.add_argument("--dry-run", action="store_true", help="build and print the plan; make no model calls")
    args = p.parse_args(argv)

    try:
        cases = case_schema.load_all_cases(ROOT / "tests")
    except case_schema.CaseFileError as exc:
        print(f"Invalid test cases: {exc}", file=sys.stderr)
        return 2
    case_ids = select_cases(args, cases)
    missing = [c for c in case_ids if c not in cases]
    manual = [c for c in case_ids if c in cases and cases[c]["manual"]]
    if missing or manual:
        if missing:
            print(f"Unknown case ids: {missing}", file=sys.stderr)
        if manual:
            print(f"Manual cases cannot be run automatically: {manual}", file=sys.stderr)
        return 2
    candidate_system = build_candidate_system()
    rubric = (ROOT / "references" / "evaluation-rubric.md").read_text(encoding="utf-8")
    planned = len(case_ids) * 3
    print(f"Plan: {len(case_ids)} cases -> up to {planned} calls (cap {args.max_calls}); model {args.model}; seed {args.seed}")
    print(f"Candidate system prompt: {len(candidate_system.split())} words, sha {sha(candidate_system)}")
    if planned > args.max_calls:
        print(f"Refusing: plan needs {planned} calls but cap is {args.max_calls}. "
              f"Raise --max-calls (and --max-usd) deliberately.", file=sys.stderr)
        return 2
    try:
        require_safe_mode()
        print("Isolation: --safe-mode is supported by the installed Claude Code.")
    except IsolationError as exc:
        if not args.dry_run:
            print(f"Blocked: {exc}\nNo model calls were made.", file=sys.stderr)
            return 4
        print(f"Isolation: NOT available, so a live run would be blocked. {exc}")
    if args.dry_run:
        print("Dry run: no model calls made.")
        for cid, m in H.assign_blinding(case_ids, args.seed).items():
            print(f"  {cid}: A={m['A']} B={m['B']}")
        return 0

    if os.environ.get("CLAUDECODE"):
        # Claude Code blocks nested sessions because they can crash the parent. Do not bypass it.
        print("Blocked: running inside a Claude Code session. Run this script from a separate terminal "
              "(where CLAUDECODE is not set). No model calls were made.", file=sys.stderr)
        return 3

    run_id = time.strftime("%Y%m%d-%H%M%S")
    budget = H.Budget(args.max_calls, args.max_usd)
    try:
        client = claude_client(args.model, args.timeout, args.per_call_usd, budget)
    except IsolationError as exc:
        print(f"Blocked: {exc}\nNo model calls were made.", file=sys.stderr)
        return 4
    result = run_pilot(client, budget, cases, case_ids, args.seed, args.output_dir / run_id,
                       candidate_system, rubric, args.model)
    print((args.output_dir / run_id / "report.md").read_text())
    print(f"Saved to {args.output_dir / run_id}")
    return 1 if result["aborted"] or result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
