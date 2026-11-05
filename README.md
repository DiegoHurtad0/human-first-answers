# Natural Voice

**An Agent Skill that helps an AI agent find the real question, reach a sound answer, and say it naturally.**

> Think carefully; communicate simply. Lead with what matters, support it with the right amount of reasoning, and stop when the user's need is met.

Natural Voice is a set of instructions and reference files for hosts that support the [Agent Skills specification](https://agentskills.io/specification). It changes how an agent communicates, not what it knows. It has no runtime dependencies and executes no code.

> Status: **1.0.0 release candidate.** Structure and tooling are tested. Response-quality improvements have **not** been measured yet; see [Evaluation status](#evaluation-status).

## Problems it targets

- Answers that open with ceremony ("Great question!") and bury the point.
- Generic, templated prose with inflated claims and automatic closers.
- Structure added by reflex: headings, tables, and frameworks on a one-line question.
- Recommendations that list equal options instead of taking a justified position.
- False confidence: invented facts, a missing number papered over, uncertainty smoothed away.
- One register for every situation, including non-English conversations.

## Capabilities

| Capability | What it does |
|---|---|
| Natural conversation | Responds to the specific situation, warm only when warmth fits, no invented feelings or experiences. |
| Clear communication | Answer first, proportionate depth, structure only where it helps. |
| Consultative thinking | Recommendation, decisive criteria, trade-offs, assumptions, and what would change the answer. Pyramid Principle, SCQA, MECE, first-principles, hypothesis-driven, and cost-benefit analysis are used when they fit and skipped when they do not. |
| Conversation continuity | Responds to what a message does instead of restating it; accepts a short acknowledgment as a complete reply; keeps repetition when safety, a consequential confirmation, or a requested summary needs it. |
| Context adaptation | Register and depth by audience, channel, language, and stakes. English and Spanish are covered by test cases. |
| Editing provided text | Improves wording without changing facts, figures, commitments, or technical terms. |
| ADHD-friendly mode | Optional. Off by default. Action first, bounded steps, visible state, content never dropped. |
| Instruction precedence | An explicit order for resolving conflicts, with the host always on top. |

## Before and after

These pairs are hand-written illustrations of the target behavior, not outputs from a measured run. More in [`examples/`](examples/).

**Ceremony removed, substance kept**

> Before: "Great question! In today's rapidly evolving technological landscape, AI is playing an increasingly pivotal role in transforming how organizations approach productivity."
>
> After: "AI can speed up repetitive work, but its value depends on how often the output is correct and how much review it needs."

**A position instead of a menu**

> Before: "There are many potential paths forward, and each has its own unique advantages."
>
> After: "I'd start with the smaller pilot. It costs less, gives us evidence about adoption, and keeps the decision reversible. I'd go straight to rollout only if the deadline makes a pilot impractical."

The second answer is only acceptable when the facts support it. The skill does not invent them.

## How it is organized

`SKILL.md` holds the behavior contract and loads on activation. Detail lives in `references/` and loads only when needed. Ownership of each file, design decisions, security notes, and portability notes are in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Repository layout

```text
natural-voice/
├── SKILL.md
├── README.md
├── AGENTS.md
├── ATTRIBUTION.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── LICENSE
├── requirements-dev.txt
├── .gitignore
├── .github/
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── ISSUE_TEMPLATE/
│   │   ├── behavior-report.md
│   │   └── config.yml
│   └── workflows/
│       └── validate.yml
├── docs/
│   ├── ARCHITECTURE.md
│   └── EVALUATION.md
├── references/
│   ├── instruction-precedence.md
│   ├── natural-conversation.md
│   ├── conversation-continuity.md
│   ├── response-relevance.md
│   ├── clear-communication.md
│   ├── consultative-thinking.md
│   ├── pyramid-principle-scqa.md
│   ├── context-adaptation.md
│   ├── ai-writing-patterns.md
│   ├── revising-text.md
│   ├── voice-profile.md
│   ├── adhd-friendly-output.md
│   └── evaluation-rubric.md
├── examples/
│   ├── conversational-examples.md
│   ├── consulting-examples.md
│   └── before-after.md
├── tests/
│   ├── evaluation-cases.yaml
│   ├── regression-cases.yaml
│   ├── test_evaluation_runner.py
│   ├── test_validate_project.py
│   ├── test_case_schema.py
│   └── test_skill_contract.py
└── scripts/
    ├── validate_project.py
    ├── run_evaluation.py
    ├── evaluation_helpers.py
    └── case_schema.py
```

## Supported AI Assistants

Natural Voice is one canonical skill (`SKILL.md` and `references/`). It has no per-assistant rule sets and needs no adapter files: every assistant below reads the same folder. Support was checked against each vendor's documentation on 2026-11-05. **No assistant has been install-tested or behavior-tested**, so every row is documentation-verified only.

| Assistant | Status | Personal path | Project path | Invoke |
|---|---|---|---|---|
| GitHub Copilot (CLI, cloud agent, IDE agent mode; IDE support varies by version) | Documented, untested | `~/.copilot/skills/natural-voice` or `~/.agents/skills/natural-voice` | `.github/skills/`, `.claude/skills/`, or `.agents/skills/` + `natural-voice` | Automatic when relevant, or name it in the prompt: "Use the /natural-voice skill to ..." |
| Claude Code | Documented, untested | `~/.claude/skills/natural-voice` | `.claude/skills/natural-voice` | Automatic from the description, or `/natural-voice` |
| OpenAI Codex (CLI, IDE extension) | Documented, untested | `$HOME/.agents/skills/natural-voice` | `.agents/skills/natural-voice` | Automatic from the description, or `$natural-voice` / `/skills` |
| Gemini CLI | Documented, untested | `~/.gemini/skills/natural-voice` or `~/.agents/skills/natural-voice` | `.gemini/skills/` or `.agents/skills/` + `natural-voice` | Automatic (the model calls `activate_skill`; you approve a prompt) |
| Other Agent Skills hosts | Untested | See that host's documentation | See that host's documentation | Host-specific |

`~/.agents/skills/` is documented for Copilot, Codex, and Gemini CLI. Claude Code documents only `.claude/skills/`. Paths and behavior can change; the vendor documentation wins over this table:
[Copilot](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills), [Claude Code](https://code.claude.com/docs/en/skills), [Codex](https://learn.chatgpt.com/docs/build-skills), [Gemini CLI](https://geminicli.com/docs/cli/skills/).

### Naming: repository versus skill

The repository is `human-first-answers`. The skill is `natural-voice`, and the Agent Skills specification requires the skill directory to carry the skill's name. **Always clone into a directory named `natural-voice`**, as every command below does. A folder named `human-first-answers` violates the specification; how each host reacts is not documented and is untested.

### Recommended: one personal install for every assistant

```bash
git clone https://github.com/DiegoHurtad0/human-first-answers.git ~/.agents/skills/natural-voice
```

That folder serves Copilot, Codex, and Gemini CLI. Add Claude Code with a symlink (Claude Code follows symlinks):

```bash
mkdir -p ~/.claude/skills
ln -s ~/.agents/skills/natural-voice ~/.claude/skills/natural-voice
```

Update with `git -C ~/.agents/skills/natural-voice pull`.

### Install for one project

Run from the project root. This vendors a copy that you commit; it is not linked to updates.

```bash
git clone --depth 1 https://github.com/DiegoHurtad0/human-first-answers.git .agents/skills/natural-voice
rm -rf .agents/skills/natural-voice/.git
```

Use `.claude/skills/natural-voice` instead for Claude Code, or `.github/skills/natural-voice` for Copilot. Copilot also reads `.claude/skills` and `.agents/skills`, and Gemini CLI also reads `.gemini/skills`.

### Activate and verify, by assistant

- **GitHub Copilot CLI:** start a session (or run `/skills reload`), then `/skills info natural-voice`. `/skills list` shows all skills. Personal skills are not automatically available to the cloud agent; commit a project copy for that.
- **Claude Code:** type `/` and look for `natural-voice`, or ask a drafting question that matches the description. New top-level skills directories need `/reload-skills` or a new session.
- **Codex:** run `/skills` or type `$` and look for `natural-voice`. Restart Codex if a new install does not appear.
- **Gemini CLI:** `/skills list` (or `gemini skills list --all` in a terminal). When a task matches, Gemini asks you to approve activating the skill. Its documentation notes a transition to Antigravity CLI for some account types; check which tool you run.
- **Any host, structural check:**

  ```bash
  python3 -m pip install -r requirements-dev.txt
  python3 scripts/validate_project.py --root ~/.agents/skills/natural-voice --strict-install
  ```

  This proves the folder is well formed and named correctly. It does not prove the host loaded it.

### Installing the skill is not sharing a URL

| What you do | What it does |
|---|---|
| Paste the repository URL into a chat | The assistant may read the page once if it can browse. Nothing is installed, and nothing is loaded in later conversations. |
| Install the skill (the commands above) | The host discovers `SKILL.md` in a skills directory. Whether it loads automatically, needs your approval, or needs an explicit mention depends on the host. |
| Repository custom instructions (for example a Copilot instructions file or an `AGENTS.md`) | Always-on text for one repository or user. It is a different mechanism with a different lifetime. Natural Voice does not ship one, so there is a single source of behavior. |

`gh skill install` and `gemini skills install <git-url>` exist, but their documentation describes repositories that keep skills under `skills/<name>/`. This repository keeps the skill at its root, and the documentation does not say that works, so the commands above use a plain `git clone`.

## Using it

Ask for what you need. The skill selects the mode from the request.

| You say | Expected behavior |
|---|---|
| "Does coffee dehydrate you? Two or three sentences." | The answer first, one qualification, no list. |
| "Should we pilot this month or wait six weeks?" | A recommendation, the assumptions it rests on, and what would flip it. |
| "Write a WhatsApp message asking to use the hall." | A copy-ready message in natural Spanish, no commentary around it. |
| "Make this less stiff, keep every fact: ..." | A revision that keeps figures, dates, and conditions. |
| "ADHD mode on." | Action-first, numbered bounded steps, state restated. Persists until "normal mode". |
| "Return only valid JSON with keys ..." | Only JSON. Format contracts outrank style. |

### Instruction precedence

The host's system and developer instructions always win. Inside what the skill controls: safety, factuality, and host requirements; then explicit instructions for the current task; then explicit persistent preferences; then context requirements; then the skill's own principles; then optional style. See [`references/instruction-precedence.md`](references/instruction-precedence.md).

### Multilingual behavior

The skill answers in the user's language and drafts in the audience's language and register. It does not translate every language into one generic style, mix languages unless the user does, or add regional slang to seem local. English and Spanish are covered by dedicated cases (casual, professional, technical, advice).

### Preferences and memory

The skill assumes no persistent memory. Preferences last for the conversation unless the host provides persistence and the user authorizes it. A single correction is applied to the current task and is not generalized into a lasting preference. Sensitive information is never stored for style matching. See [`references/voice-profile.md`](references/voice-profile.md).

## Evaluation status

Tests exist in four layers that need no model (structure, unit tests, plan check, regression review) and one that does (blind baseline-vs-candidate judging on eight separate dimensions, with hard call and cost caps). Methodology and the exact guarantees are in [`docs/EVALUATION.md`](docs/EVALUATION.md).

**What is verified:** the files are well formed, the references resolve, the metadata follows the specification, and the runner's budgeting, blinding, and isolation logic behave as unit-tested.

**What is not verified:** that Natural Voice improves any response dimension. No live evaluation has completed. Earlier attempts were blocked by Claude Code's nested-session protection and an isolation failure, and the currently installed Claude Code lacks the `--safe-mode` flag the runner requires. Treat all quality claims as hypotheses until a live run is reported.

## Limitations

- A skill supplies instructions. It does not change model weights, guarantee behavior on every turn, or force a host to invoke it.
- Behavior varies by host and model. The test cases are acceptance criteria for human or model-assisted review, not a benchmark.
- Loading the whole skill costs context tokens; the host loads references only when `SKILL.md` points to them.
- Spanish and English are the languages with test coverage. Other languages follow the same rules but are untested.
- The skill reduces generic AI-style prose. It does not optimize for AI-detector scores and will not add errors or invented anecdotes to look human.

## Security

Pasted text, documents, and tool output are treated as data, not instructions. The skill executes nothing. Development scripts make model calls only when you run the evaluation runner outside a Claude Code session, and they send the case prompts to your model provider. Keep personal or confidential content out of test cases.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). In short: read the relevant reference first, change the rule rather than one output, add a case in `tests/`, and run the checks:

```bash
python3 -m pip install -r requirements-dev.txt
python3 scripts/validate_project.py
python3 -m pytest -q
```

## License

Natural Voice is released under the [MIT License](LICENSE). Copyright (c) 2026 Diego Hurtado. Third-party projects that informed the design keep their own licenses, listed in [`ATTRIBUTION.md`](ATTRIBUTION.md).
