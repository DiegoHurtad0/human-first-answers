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

## Install

The specification requires the skill directory to be named after the skill (`natural-voice`). This repository is named `human-first-answers`, so clone it into a directory with the skill name.

### Claude Code

Personal skill (all projects), per the [Claude Code skills documentation](https://code.claude.com/docs/en/skills):

```bash
git clone https://github.com/DiegoHurtad0/human-first-answers.git ~/.claude/skills/natural-voice
```

For one repository, clone into `.claude/skills/natural-voice` inside it. Claude Code also accepts a symlink to a checkout elsewhere:

```bash
ln -s /path/to/your/checkout ~/.claude/skills/natural-voice
```

Claude Code loads the skill when its description matches the task, and exposes it as `/natural-voice`. Start a new session if it does not appear.

### Codex

Per the [Codex skills documentation](https://learn.chatgpt.com/docs/build-skills), user-level skills live in `$HOME/.agents/skills` and repository skills in `.agents/skills`:

```bash
git clone https://github.com/DiegoHurtad0/human-first-answers.git ~/.agents/skills/natural-voice
```

Codex follows symlinked skill folders and detects changes automatically; restart it if an update does not appear.

### Other hosts

Any host that implements the Agent Skills specification should accept the folder in its skills location. Other hosts have not been tested. Check that host's documentation for the path.

### Verify the install

```bash
python3 -m pip install -r requirements-dev.txt
python3 scripts/validate_project.py --root ~/.claude/skills/natural-voice --strict-install
```

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

The license is defined by the [`LICENSE`](LICENSE) file in this repository. Attribution for the projects that informed the design is in [`ATTRIBUTION.md`](ATTRIBUTION.md).
