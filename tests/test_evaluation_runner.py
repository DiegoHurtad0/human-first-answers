"""Unit tests for the evaluation runner. No model calls are made.

Run: python3 -m pytest -q   (needs PyYAML; see requirements-dev.txt)
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import subprocess
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
os.environ["NV_EVAL_NO_VERSION"] = "1"

import case_schema  # noqa: E402
import evaluation_helpers as H  # noqa: E402
import run_evaluation as R  # noqa: E402

CASES = case_schema.load_all_cases(ROOT / "tests")


def good_judge(overall="A", verdict="A"):
    dims = {d: {"verdict": verdict, "evidence": "quote"} for d in H.DIMENSIONS}
    return json.dumps({"dimensions": dims, "gate_failures": {"A": [], "B": []}, "overall": overall, "summary": "s"})


class FakeClient:
    """Judge answers come from `judge_replies`; generations echo the system prompt role."""

    def __init__(self, judge_replies=None, fail_on=None, cost=0.01):
        self.calls = []
        self.judge_replies = list(judge_replies or [])
        self.fail_on = fail_on or set()
        self.cost = cost

    def __call__(self, system, prompt):
        n = len(self.calls)
        self.calls.append((system, prompt))
        if n in self.fail_on:
            return R.CallResult("", error="boom")
        if system == R.JUDGE_SYSTEM:
            return R.CallResult(self.judge_replies.pop(0) if self.judge_replies else good_judge(), cost=self.cost)
        role = "candidate" if system != R.BASE_SYSTEM else "baseline"
        return R.CallResult(f"{role} answer", cost=self.cost, model="m")


class CaseLoading(unittest.TestCase):
    def test_pilot_cases_exist_and_have_fields(self):
        for cid in R.PILOT_CASES:
            self.assertIn(cid, CASES)
            self.assertTrue(CASES[cid]["prompt"])
            self.assertTrue(CASES[cid]["expected"])

    def test_loaded_cases_keep_prompt_and_expectations(self):
        raw = case_schema.read_yaml(ROOT / "tests" / "evaluation-cases.yaml")
        for case in raw["cases"]:
            loaded = CASES[case["id"]]
            self.assertEqual(loaded["prompt"], case.get("prompt"))
            self.assertEqual(loaded["turns"], case.get("turns"))
            self.assertEqual(loaded["expected"], case["expected"])
            self.assertEqual(loaded["failure_modes"], case["failure_modes"])

    def test_regression_cases_use_the_runner_shape(self):
        raw = case_schema.read_yaml(ROOT / "tests" / "regression-cases.yaml")
        for case in raw["regressions"]:
            loaded = CASES[case["id"]]
            self.assertEqual(loaded["expected"], case["must"])
            self.assertEqual(loaded["failure_modes"], case["must_not"])
            self.assertEqual(loaded["category"], "regression")

    def test_manual_cases_are_flagged_and_never_selected_by_a_suite(self):
        manual = [cid for cid, c in CASES.items() if c["manual"]]
        self.assertTrue(manual)
        for suite in ("evaluation", "regression", "all"):
            args = type("A", (), {"cases": None, "suite": suite})()
            self.assertFalse(set(manual) & set(R.select_cases(args, CASES)))

    def test_explicit_cases_override_the_suite(self):
        args = type("A", (), {"cases": ["strict_format"], "suite": "all"})()
        self.assertEqual(R.select_cases(args, CASES), ["strict_format"])

    def test_scripted_multi_turn_cases_are_manual_and_have_no_single_prompt(self):
        scripted = [c for c in CASES.values() if c["turns"]]
        self.assertGreaterEqual(len(scripted), 10)
        for case in scripted:
            self.assertTrue(case["manual"], case["id"])
            self.assertIsNone(case["prompt"], case["id"])

    def test_show_manual_prints_transcripts_and_makes_no_calls(self):
        out = io.StringIO()
        fake = Fake(stdout="irrelevant")
        with mock.patch.object(R.subprocess, "run", fake), contextlib.redirect_stdout(out):
            self.assertEqual(R.main(["--show-manual"]), 0)
        text = out.getvalue()
        self.assertIn("Assistant: ¿Te bañaste hoy?\nUser: Sí.", text)
        self.assertIn("Failure modes:", text)
        self.assertIn("never runs them", text)
        self.assertEqual(fake.invocations, [])

    def test_explicitly_requesting_a_scripted_case_is_refused(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(R.main(["--dry-run", "--cases", "echo_spanish_yes_no_answer"]), 2)

    def test_pilot_cases_are_not_manual(self):
        self.assertFalse([c for c in R.PILOT_CASES if CASES[c]["manual"]])


class Blinding(unittest.TestCase):
    def test_reproducible_and_balanced_enough(self):
        ids = list(CASES)
        self.assertEqual(H.assign_blinding(ids, 1), H.assign_blinding(ids, 1))
        self.assertNotEqual(H.assign_blinding(ids, 1), H.assign_blinding(ids, 2))
        flips = {m["A"] for m in H.assign_blinding(ids, 1).values()}
        self.assertEqual(flips, {"baseline", "candidate"})

    def test_judge_prompt_leaks_nothing(self):
        prompt = H.build_judge_prompt(CASES["direct_simple_question"], "rubric text", "resp one", "resp two")
        for word in ("baseline", "candidate", "natural voice", "natural-voice", "skill"):
            self.assertNotIn(word, prompt.lower())

    def test_unblind_and_summarize(self):
        blinding = {"c1": {"A": "candidate", "B": "baseline"}, "c2": {"A": "baseline", "B": "candidate"}}
        judgments = {"c1": json.loads(good_judge("A", "A")), "c2": json.loads(good_judge("A", "A"))}
        s = H.summarize(judgments, blinding)
        self.assertEqual((s.overall.candidate, s.overall.baseline), (1, 1))
        self.assertEqual(s.dimensions["clarity"].candidate, 1)


class JudgeParsing(unittest.TestCase):
    def test_accepts_plain_and_fenced(self):
        self.assertEqual(H.parse_judge_output(good_judge())["overall"], "A")
        self.assertEqual(H.parse_judge_output("```json\n" + good_judge() + "\n```")["overall"], "A")
        self.assertEqual(H.parse_judge_output("Here you go: " + good_judge() + " done")["overall"], "A")

    def test_rejects_bad_output(self):
        bad = [
            "not json",
            "{}",
            json.dumps({"dimensions": {}, "overall": "A"}),
            good_judge(verdict="C"),
            good_judge(overall="C"),
        ]
        for text in bad:
            with self.assertRaises(H.JudgeParseError, msg=text):
                H.parse_judge_output(text)

    def test_na_only_for_recommendation_and_decision_dimensions(self):
        allowed = {"recommendation_quality", "decision_usefulness"}  # spelled out on purpose; not read from the code under test
        for name in H.DIMENSIONS:
            data = json.loads(good_judge())
            data["dimensions"][name]["verdict"] = "n/a"
            if name in allowed:
                H.parse_judge_output(json.dumps(data))
            else:
                with self.assertRaises(H.JudgeParseError, msg=name):
                    H.parse_judge_output(json.dumps(data))

    def test_every_dimension_is_required(self):
        for name in H.DIMENSIONS:
            data = json.loads(good_judge())
            del data["dimensions"][name]
            with self.assertRaises(H.JudgeParseError, msg=name):
                H.parse_judge_output(json.dumps(data))

    def test_there_are_eight_independent_dimensions(self):
        self.assertEqual(len(H.DIMENSIONS), 8)
        self.assertEqual(len(set(H.DIMENSIONS)), 8)

    def test_requires_evidence(self):
        data = json.loads(good_judge())
        data["dimensions"]["clarity"]["evidence"] = " "
        with self.assertRaises(H.JudgeParseError):
            H.parse_judge_output(json.dumps(data))


class Budget(unittest.TestCase):
    def test_call_cap(self):
        b = H.Budget(max_calls=2, max_usd=5)
        b.start_call(); b.start_call()
        with self.assertRaises(H.BudgetExceeded):
            b.start_call()

    def test_usd_cap(self):
        b = H.Budget(max_calls=10, max_usd=0.05)
        b.start_call(); b.record_cost(0.06)
        with self.assertRaises(H.BudgetExceeded):
            b.start_call()

    def test_missing_cost_is_counted_not_assumed_free(self):
        b = H.Budget(10, 5)
        b.start_call(); b.record_cost(None)
        self.assertEqual(b.unmetered_calls, 1)


class Pipeline(unittest.TestCase):
    def run_pilot(self, client, ids, budget=None, seed=7):
        out = Path(tempfile.mkdtemp())
        budget = budget or H.Budget(24, 5.0)
        res = R.run_pilot(client, budget, CASES, ids, seed, out, "CANDIDATE SYSTEM", "rubric", "m")
        return res, out, budget

    def test_happy_path_and_blinding_audit(self):
        ids = R.PILOT_CASES
        client = FakeClient()
        res, out, budget = self.run_pilot(client, ids)
        self.assertEqual(budget.calls, 24)
        self.assertEqual(len(res["judgments"]), 8)
        mapping = json.loads((out / "blinding.json").read_text())
        judge_inputs = [json.loads(l) for l in (out / "judge_inputs.jsonl").read_text().splitlines()]
        for row in judge_inputs:
            m = mapping[row["case"]]
            self.assertIn(f"{m['A']} answer", row["prompt"].split("<response_a>")[1].split("</response_a>")[0])
            self.assertIn(f"{m['B']} answer", row["prompt"].split("<response_b>")[1].split("</response_b>")[0])
        self.assertTrue((out / "report.md").is_file())
        self.assertNotIn("blinding", (out / "judge_inputs.jsonl").read_text())

    def test_baseline_never_gets_candidate_instructions(self):
        client = FakeClient()
        self.run_pilot(client, ["direct_simple_question"])
        systems = [s for s, _ in client.calls]
        self.assertEqual(systems[0], R.BASE_SYSTEM)
        self.assertEqual(systems[1], "CANDIDATE SYSTEM")
        self.assertNotIn("Natural Voice", R.BASE_SYSTEM)

    def test_call_cap_stops_run(self):
        client = FakeClient()
        res, _, budget = self.run_pilot(client, R.PILOT_CASES, budget=H.Budget(5, 5.0))
        self.assertEqual(budget.calls, 5)
        self.assertIn("budget", res["aborted"])
        self.assertEqual(len(client.calls), 5)

    def test_usd_cap_stops_run(self):
        client = FakeClient(cost=1.0)
        res, _, budget = self.run_pilot(client, R.PILOT_CASES, budget=H.Budget(24, 2.5))
        self.assertLessEqual(budget.calls, 3)
        self.assertIn("budget", res["aborted"])

    def test_failed_generation_skips_case_without_retry(self):
        client = FakeClient(fail_on={1})  # candidate generation of first case fails
        res, _, budget = self.run_pilot(client, ["direct_simple_question", "consultative_metrics"])
        self.assertEqual(len(res["errors"]), 1)
        self.assertEqual(list(res["judgments"]), ["consultative_metrics"])
        self.assertEqual(budget.calls, 2 + 2 + 1 + 0)  # c1 baseline+failed, c2 two gens, one judge

    def test_two_consecutive_failures_abort(self):
        client = FakeClient(fail_on={0, 1, 2, 3, 4, 5})
        res, _, budget = self.run_pilot(client, R.PILOT_CASES)
        self.assertIn("consecutive", res["aborted"])
        self.assertEqual(budget.calls, 2)

    def test_judge_parse_error_is_recorded_not_fatal(self):
        client = FakeClient(judge_replies=["garbage", good_judge()])
        res, out, _ = self.run_pilot(client, ["direct_simple_question", "consultative_metrics"])
        self.assertEqual([e["stage"] for e in res["errors"]], ["judge_parse"])
        self.assertEqual(len(res["judgments"]), 1)
        self.assertIn("judge_parse", (out / "errors.jsonl").read_text())

    def test_isolation_failure_aborts(self):
        def client(system, prompt):
            raise R.IsolationError("tools were available")

        res, _, budget = self.run_pilot(client, ["direct_simple_question"])
        self.assertIn("isolation", res["aborted"])
        self.assertEqual(budget.calls, 1)


class ReportRendering(unittest.TestCase):
    def test_report_lists_every_dimension_and_where_the_candidate_lost(self):
        out = Path(tempfile.mkdtemp())
        ids = ["direct_simple_question"]
        blinding = H.assign_blinding(ids, 1)
        baseline_letter = "A" if blinding[ids[0]]["A"] == "baseline" else "B"
        dims = {d: {"verdict": "tie", "evidence": "e"} for d in H.DIMENSIONS}
        dims["clarity"]["verdict"] = baseline_letter  # the baseline wins one dimension
        dims["decision_usefulness"]["verdict"] = "n/a"
        judge = json.dumps({"dimensions": dims, "gate_failures": {"A": [], "B": []}, "overall": "tie", "summary": "s"})
        client = FakeClient(judge_replies=[judge])
        res = R.run_pilot(client, H.Budget(10, 5), CASES, ids, 1, out, "candidate system", "rubric", "m")
        report = (out / "report.md").read_text()
        for dimension in H.DIMENSIONS:
            self.assertIn(f"| {dimension} |", report)
        self.assertIn("**direct_simple_question**: clarity", report)
        self.assertIn("There is no combined score", report)
        self.assertEqual(res["summary"].dimensions["clarity"].baseline, 1)
        self.assertEqual(res["summary"].dimensions["decision_usefulness"].na, 1)

    def test_report_without_losses_says_so(self):
        out = Path(tempfile.mkdtemp())
        judge = good_judge(overall="tie", verdict="tie")
        R.run_pilot(FakeClient(judge_replies=[judge]), H.Budget(10, 5), CASES, ["direct_simple_question"],
                    1, out, "candidate system", "rubric", "m")
        self.assertIn("No dimension in any judged case went to the baseline", (out / "report.md").read_text())


class NestedSession(unittest.TestCase):
    def test_refuses_inside_claude_code_without_calls(self):
        old = os.environ.get("CLAUDECODE")
        os.environ["CLAUDECODE"] = "1"
        try:
            with mock.patch.object(R, "require_safe_mode"):
                self.assertEqual(R.main(["--output-dir", tempfile.mkdtemp()]), 3)
        finally:
            if old is None:
                del os.environ["CLAUDECODE"]
            else:
                os.environ["CLAUDECODE"] = old


CLEAN_INIT = {"type": "system", "subtype": "init", "model": "claude-sonnet-4-6", "tools": [], "mcp_servers": [],
              "skills": [], "plugins": [], "agents": ["general-purpose"], "apiKeySource": "none",
              "slash_commands": ["compact"], "claude_code_version": "2.1.311"}
RESULT = {"type": "result", "result": "hello", "is_error": False, "total_cost_usd": 0.02, "usage": {"output_tokens": 3}}


def stream(*events):
    return "\n".join(json.dumps(e) for e in events)


class Fake:
    """Stands in for subprocess.run; records every argv/env/cwd."""

    def __init__(self, stdout="", returncode=0, stderr="", raises=None):
        self.stdout, self.returncode, self.stderr, self.raises = stdout, returncode, stderr, raises
        self.invocations = []

    def __call__(self, cmd, **kwargs):
        self.invocations.append((cmd, kwargs))
        if self.raises:
            raise self.raises
        return subprocess.CompletedProcess(cmd, self.returncode, self.stdout, self.stderr)


class SafeModeInvocation(unittest.TestCase):
    def test_command_has_safe_mode_and_pinned_flags_but_not_bare(self):
        cmd = R.build_command("claude-sonnet-4-6", "SYS", 0.5)
        self.assertIn("--safe-mode", cmd)
        self.assertNotIn("--bare", cmd)
        self.assertEqual(cmd[cmd.index("--model") + 1], "claude-sonnet-4-6")
        self.assertEqual(cmd[cmd.index("--system-prompt") + 1], "SYS")
        self.assertEqual(cmd[cmd.index("--tools") + 1], "")
        self.assertEqual(cmd[cmd.index("--max-budget-usd") + 1], "0.50")
        for flag in ("--no-session-persistence", "--strict-mcp-config", "--disable-slash-commands"):
            self.assertIn(flag, cmd)

    def test_every_model_role_uses_the_same_isolation_flags(self):
        fake = Fake(stdout=stream(CLEAN_INIT, RESULT))
        budget = H.Budget(24, 5.0)
        client = R.claude_client("claude-sonnet-4-6", 10, 0.5, budget, run=fake)
        for system in (R.BASE_SYSTEM, "CANDIDATE", R.JUDGE_SYSTEM):
            client(system, "prompt")
        self.assertEqual(len(fake.invocations), 3)
        for cmd, kwargs in fake.invocations:
            self.assertIn("--safe-mode", cmd)
            self.assertNotIn("--bare", cmd)
            self.assertEqual(kwargs["env"]["CLAUDE_CODE_DISABLE_BUNDLED_SKILLS"], "1")
            self.assertEqual(kwargs["input"], "prompt")
        self.assertEqual([c[0][c[0].index("--system-prompt") + 1] for c in fake.invocations],
                         [R.BASE_SYSTEM, "CANDIDATE", R.JUDGE_SYSTEM])

    def test_per_call_cap_shrinks_with_remaining_budget(self):
        fake = Fake(stdout=stream(CLEAN_INIT, RESULT))
        budget = H.Budget(24, 5.0)
        budget.usd = 4.8
        R.claude_client("m", 10, 0.5, budget, run=fake)("s", "p")
        cmd = fake.invocations[0][0]
        self.assertEqual(cmd[cmd.index("--max-budget-usd") + 1], "0.20")

    def test_claudecode_env_is_never_unset_by_the_runner(self):
        os.environ["CLAUDECODE"] = "1"
        try:
            self.assertEqual(R.clean_env().get("CLAUDECODE"), "1")
        finally:
            del os.environ["CLAUDECODE"]


class Capability(unittest.TestCase):
    def test_supported(self):
        R.require_safe_mode(run=Fake(stdout="  --safe-mode   Start with all customizations disabled"))

    def test_unsupported_fails_closed_with_upgrade_hint(self):
        fake = Fake(stdout="Usage: claude [options]\n  --bare ...")
        with self.assertRaises(R.IsolationError) as ctx:
            R.require_safe_mode(run=fake)
        self.assertIn("no --safe-mode", str(ctx.exception))
        self.assertIn("claude update", str(ctx.exception))

    def test_help_failure_fails_closed(self):
        with self.assertRaises(R.IsolationError):
            R.require_safe_mode(run=Fake(raises=FileNotFoundError("claude")))

    def test_live_run_stops_with_no_model_call_when_unsupported(self):
        fake = Fake(stdout="no flag here")
        with mock.patch.object(R.subprocess, "run", fake):
            self.assertEqual(R.main(["--output-dir", tempfile.mkdtemp()]), 4)
        for cmd, _ in fake.invocations:
            self.assertNotIn("-p", cmd)  # only --help / --version, never a model call

    def test_dry_run_succeeds_without_safe_mode_and_says_a_live_run_is_blocked(self):
        fake = Fake(stdout="no flag here")
        out = io.StringIO()
        with mock.patch.object(R.subprocess, "run", fake), contextlib.redirect_stdout(out):
            self.assertEqual(R.main(["--dry-run", "--suite", "all", "--max-calls", "300", "--output-dir", tempfile.mkdtemp()]), 0)
        self.assertIn("would be blocked", out.getvalue())
        for cmd, _ in fake.invocations:
            self.assertNotIn("-p", cmd)

    def test_dry_run_survives_a_missing_claude_binary(self):
        out = io.StringIO()
        with mock.patch.object(R.subprocess, "run", Fake(raises=FileNotFoundError("claude"))), \
                contextlib.redirect_stdout(out):
            self.assertEqual(R.main(["--dry-run", "--output-dir", tempfile.mkdtemp()]), 0)

    def test_oversized_plan_is_refused_before_any_call(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(R.main(["--dry-run", "--suite", "all", "--max-calls", "3"]), 2)
        self.assertIn("Refusing", err.getvalue())

    def test_manual_and_unknown_cases_are_refused(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(R.main(["--dry-run", "--cases", "one_correction_is_not_a_personality"]), 2)
            self.assertEqual(R.main(["--dry-run", "--cases", "nope"]), 2)


class IsolationFailures(unittest.TestCase):
    def evaluate(self, init_overrides=None, extra_events=(), drop_init=False):
        init = {**CLEAN_INIT, **(init_overrides or {})}
        events = ([] if drop_init else [init]) + list(extra_events) + [RESULT]
        return R.evaluate_stream(stream(*events), 0, "", "claude-sonnet-4-6")

    def test_clean_run_passes(self):
        res = self.evaluate()
        self.assertEqual((res.text, res.error, res.isolation_error), ("hello", None, None))

    def test_each_contamination_is_caught_and_cost_is_kept(self):
        cases = {
            "skill": {"skills": ["debug"]},
            "plugin": {"plugins": [{"name": "x"}]},
            "plugin error": {"plugin_errors": [{"m": 1}]},
            "mcp": {"mcp_servers": [{"name": "m"}]},
            "tool": {"tools": ["Bash"]},
            "memory": {"memory_paths": {"auto": "/x"}},
            "api key": {"apiKeySource": "ANTHROPIC_API_KEY"},
            "wrong model": {"model": "claude-opus-4-8"},
        }
        for label, override in cases.items():
            res = self.evaluate(override)
            self.assertTrue(res.isolation_error, label)
            self.assertEqual(res.text, "", label)
            self.assertEqual(res.cost, 0.02, label)

    def test_hook_event_is_caught(self):
        res = self.evaluate(extra_events=[{"type": "system", "subtype": "hook_started", "hook_event": "SessionStart"}])
        self.assertIn("hooks fired", res.isolation_error)

    def test_missing_init_fails_closed(self):
        res = self.evaluate(drop_init=True)
        self.assertIn("no startup", res.isolation_error)

    def test_isolation_failure_aborts_pilot_counts_one_call_and_records_cost(self):
        fake = Fake(stdout=stream({**CLEAN_INIT, "skills": ["debug"]}, RESULT))
        budget = H.Budget(24, 5.0)
        client = R.claude_client("claude-sonnet-4-6", 10, 0.5, budget, run=fake)
        out = Path(tempfile.mkdtemp())
        res = R.run_pilot(client, budget, CASES, R.PILOT_CASES, 1, out, "CANDIDATE", "rubric", "claude-sonnet-4-6")
        self.assertIn("isolation failure", res["aborted"])
        self.assertEqual((budget.calls, len(fake.invocations)), (1, 1))
        self.assertAlmostEqual(budget.usd, 0.02)
        self.assertEqual(res["responses"], {})

    def test_contaminated_workdir_is_refused_before_any_call(self):
        parent = Path(tempfile.mkdtemp())
        (parent / "CLAUDE.md").write_text("x")
        child = parent / "sub"
        child.mkdir()
        self.assertIn(str((parent / "CLAUDE.md").resolve()), R.find_project_instructions(str(child)))
        with mock.patch.object(R.tempfile, "mkdtemp", return_value=str(child)):
            with self.assertRaises(R.IsolationError):
                R.claude_client("m", 10, 0.5, H.Budget(24, 5.0), run=Fake())


class FailedSubprocess(unittest.TestCase):
    def test_nonzero_exit_is_a_plain_error(self):
        res = R.evaluate_stream("", 2, "unknown option '--safe-mode'", "m")
        self.assertIn("unknown option", res.error)
        self.assertIsNone(res.isolation_error)

    def test_error_result_event(self):
        res = R.evaluate_stream(stream(CLEAN_INIT, {**RESULT, "is_error": True, "result": "limit reached"}), 0, "", "m")
        self.assertEqual(res.error, "limit reached")

    def test_timeout_and_oserror_are_errors_not_crashes(self):
        for exc, text in ((subprocess.TimeoutExpired("claude", 1), "timeout"), (FileNotFoundError("x"), "could not start")):
            client = R.claude_client("m", 1, 0.5, H.Budget(24, 5.0), run=Fake(raises=exc))
            self.assertIn(text, client("s", "p").error)

    def test_each_failed_attempt_counts_and_two_in_a_row_stop_the_run(self):
        fake = Fake(stdout="", returncode=1, stderr="boom")
        budget = H.Budget(24, 5.0)
        client = R.claude_client("m", 10, 0.5, budget, run=fake)
        res = R.run_pilot(client, budget, CASES, R.PILOT_CASES, 1, Path(tempfile.mkdtemp()), "C", "r", "m")
        self.assertEqual((budget.calls, len(fake.invocations)), (2, 2))
        self.assertIn("consecutive", res["aborted"])
        self.assertEqual(budget.usd, 0)

    def test_hard_caps_unchanged(self):
        self.assertEqual((R.DEFAULT_MAX_CALLS, R.DEFAULT_MAX_USD), (24, 5.0))
        self.assertEqual(len(R.PILOT_CASES), 8)
        extra = next(c for c in CASES if c not in R.PILOT_CASES)
        with mock.patch.object(R, "require_safe_mode"):  # plan of 27 calls must be refused against the 24 cap
            self.assertEqual(R.main(["--dry-run", "--cases", *R.PILOT_CASES, extra]), 2)


class Isolation(unittest.TestCase):
    def test_check_isolation(self):
        R.check_isolation({"tools": [], "mcp_servers": []})
        for bad in ({"tools": ["Bash"]}, {"mcp_servers": [{"name": "x"}]}, {"skills": ["a"]}):
            with self.assertRaises(R.IsolationError):
                R.check_isolation(bad)

    def test_clean_env_drops_session_vars(self):
        os.environ["CLAUDE_CODE_SESSION_ID"] = "x"
        os.environ["ANTHROPIC_API_KEY"] = "secret"
        env = R.clean_env()
        self.assertNotIn("CLAUDE_CODE_SESSION_ID", env)
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        del os.environ["CLAUDE_CODE_SESSION_ID"], os.environ["ANTHROPIC_API_KEY"]

    def test_candidate_prompt_includes_skill_not_rubric(self):
        text = R.build_candidate_system()
        self.assertIn("# Natural Voice", text)
        self.assertIn("# references/natural-conversation.md", text)
        self.assertNotIn("# references/evaluation-rubric.md", text)
        self.assertFalse(text.count("name: natural-voice"))


if __name__ == "__main__":
    unittest.main()
