#!/usr/bin/env python3
"""Structural validation for Natural Voice. Deterministic; makes no model calls.

Checks the Agent Skills specification (https://agentskills.io/specification), file
references, test-case schemas, README accuracy, and common hygiene problems.
This is not a response-quality benchmark: passing it says nothing about how well
a model follows the skill.

Usage:
  python3 scripts/validate_project.py [--root PATH] [--strict-install]

--strict-install turns the directory-name warning into an error. Use it on an
installed copy, where the directory must be named after the skill.

Exit status: 0 valid, 1 invalid.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import case_schema  # noqa: E402

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "natural-voice"
SPEC_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")  # no leading, trailing, or consecutive hyphens
MAX_NAME, MAX_DESCRIPTION, MAX_COMPATIBILITY = 64, 1024, 500
SKILL_LINES_ERROR = 500      # agentskills.io limit
SKILL_LINES_WARN = 250       # this project's target (AGENTS.md)
SKILL_TOKENS_WARN = 5000     # agentskills.io recommendation; estimated at 4 characters per token

REQUIRED_FILES = [
    "SKILL.md", "README.md", "AGENTS.md", "LICENSE", "ATTRIBUTION.md", "CHANGELOG.md", "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md", "requirements-dev.txt", ".gitignore",
    "docs/ARCHITECTURE.md", "docs/EVALUATION.md",
    "examples/conversational-examples.md", "examples/consulting-examples.md", "examples/before-after.md",
    "tests/evaluation-cases.yaml", "tests/regression-cases.yaml",
    "scripts/validate_project.py", "scripts/run_evaluation.py", "scripts/evaluation_helpers.py",
    "scripts/case_schema.py",
    ".github/workflows/validate.yml", ".github/PULL_REQUEST_TEMPLATE.md",
]
REQUIRED_GITIGNORE = ["evaluation-results/", "__pycache__/", ".DS_Store", ".natural-voice/"]
LINK_PREFIXES = ("references/", "examples/", "scripts/", "docs/", "tests/", "assets/", ".github/")
SECRET_PATTERNS = {
    "Anthropic API key": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    "OpenAI-style API key": re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "AWS access key id": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}
SKIP_DIRS = {".git", "evaluation-results", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules"}
BACKTICK_RE = re.compile(r"`([A-Za-z0-9_./-]+\.(?:md|py|ya?ml|txt))`")
MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def read_text(path: Path, report: Report) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        report.error(f"{path.name}: file not found")
    except (UnicodeDecodeError, OSError) as exc:
        report.error(f"{path.name}: cannot read as UTF-8 text ({exc})")
    return None


def iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file() and not (set(path.relative_to(root).parts) & SKIP_DIRS):
            yield path


# --- SKILL.md -------------------------------------------------------------

def split_frontmatter(text: str) -> tuple[str, str] | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 3)
    if end < 0:
        return None
    return text[4:end], text[end + 5:]


def check_frontmatter(meta: object, root: Path, report: Report, strict_install: bool) -> None:
    if not isinstance(meta, dict):
        report.error("SKILL.md: frontmatter must be a YAML mapping")
        return
    unknown = sorted(set(meta) - SPEC_FIELDS)
    if unknown:
        report.error(f"SKILL.md: frontmatter fields {unknown} are not in the Agent Skills spec "
                     f"(allowed: {sorted(SPEC_FIELDS)}); hosts that validate strictly will reject the skill")
    name = meta.get("name")
    if not isinstance(name, str) or not name:
        report.error("SKILL.md: 'name' is required and must be a string")
    else:
        if len(name) > MAX_NAME or not NAME_RE.match(name):
            report.error(f"SKILL.md: invalid name {name!r} (1-{MAX_NAME} chars; lowercase letters, digits, "
                         "single hyphens; no leading or trailing hyphen)")
        if name != SKILL_NAME:
            report.error(f"SKILL.md: name {name!r} must be {SKILL_NAME!r}")
        if name != root.name:
            message = (f"checkout directory {root.name!r} differs from skill name {name!r}; the spec requires "
                       f"the installed directory to be named {name!r} (install by symlink or clone into that name)")
            (report.error if strict_install else report.warn)(f"SKILL.md: {message}")
    description = meta.get("description")
    if not isinstance(description, str) or not description.strip():
        report.error("SKILL.md: 'description' is required and must be a non-empty string")
    elif len(description.strip()) > MAX_DESCRIPTION:
        report.error(f"SKILL.md: description is {len(description.strip())} chars; the spec maximum is {MAX_DESCRIPTION}")
    if "license" in meta and (not isinstance(meta["license"], str) or not meta["license"].strip()):
        report.error("SKILL.md: 'license' must be a non-empty string")
    if "compatibility" in meta:
        c = meta["compatibility"]
        if not isinstance(c, str) or not 1 <= len(c) <= MAX_COMPATIBILITY:
            report.error(f"SKILL.md: 'compatibility' must be a string of 1-{MAX_COMPATIBILITY} chars")
    if "allowed-tools" in meta and not isinstance(meta["allowed-tools"], str):
        report.error("SKILL.md: 'allowed-tools' must be a space-separated string")
    if "metadata" in meta:
        m = meta["metadata"]
        if not isinstance(m, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in m.items()):
            report.error("SKILL.md: 'metadata' must map string keys to string values (quote versions: \"1.0\")")


def check_skill(root: Path, report: Report, strict_install: bool) -> str:
    text = read_text(root / "SKILL.md", report)
    if text is None:
        return ""
    parts = split_frontmatter(text)
    if parts is None:
        report.error("SKILL.md: must start with YAML frontmatter delimited by '---' lines")
        return text
    raw, body = parts
    try:
        meta = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        report.error(f"SKILL.md: frontmatter is not valid YAML: {exc}")
        return text
    check_frontmatter(meta, root, report, strict_install)
    lines = len(text.splitlines())
    if lines > SKILL_LINES_ERROR:
        report.error(f"SKILL.md has {lines} lines; the spec limit is {SKILL_LINES_ERROR}")
    elif lines > SKILL_LINES_WARN:
        report.warn(f"SKILL.md has {lines} lines; the project target is {SKILL_LINES_WARN}. Move detail to references/")
    if len(body) / 4 > SKILL_TOKENS_WARN:
        report.warn(f"SKILL.md body is about {len(body) // 4} tokens; the spec recommends under {SKILL_TOKENS_WARN}")
    if not re.search(r"(?m)^#\s+\S", body):
        report.error("SKILL.md: body needs a top-level heading")
    return text


# --- references and links --------------------------------------------------

def referenced_paths(text: str, source: Path, root: Path) -> list[tuple[str, Path | None]]:
    """(token, resolved path or None) for every relative file reference in a Markdown file."""
    found = []
    for target in MD_LINK_RE.findall(text):
        if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
            continue
        rel = target.split("#", 1)[0]
        if rel:
            found.append((target, (source.parent / rel).resolve()))
    for token in BACKTICK_RE.findall(text):
        in_references = source.parent.name == "references" and "/" not in token
        if not (token.startswith(LINK_PREFIXES) or in_references):
            continue
        candidates = [(source.parent / token).resolve(), (root / token).resolve()]
        found.append((token, next((c for c in candidates if c.is_file()), candidates[1])))
    return found


def check_links(root: Path, report: Report) -> None:
    for path in iter_files(root):
        if path.suffix != ".md":
            continue
        text = read_text(path, report)
        if text is None:
            continue
        for token, resolved in referenced_paths(text, path, root):
            if resolved is None or not resolved.exists():
                report.error(f"{path.relative_to(root)}: broken reference {token!r}")


def check_reachability(root: Path, skill_text: str, report: Report) -> None:
    mentioned = {t for t, _ in referenced_paths(skill_text, root / "SKILL.md", root)}
    refs = root / "references"
    if not refs.is_dir():
        report.error("references/ directory is missing")
        return
    for ref in sorted(refs.glob("*.md")):
        if f"references/{ref.name}" not in mentioned:
            report.error(f"references/{ref.name} is not referenced from SKILL.md, so progressive disclosure cannot reach it")
    for path in sorted(refs.rglob("*")):
        if path.is_dir() and path != refs:
            report.warn(f"{path.relative_to(root)}: nested directory; the spec asks for references one level deep")


def check_rubric(root: Path, report: Report) -> None:
    text = read_text(root / "references" / "evaluation-rubric.md", report)
    if text is None:
        return
    for dimension in case_schema.DIMENSIONS:
        label = dimension.replace("_", " ").capitalize()
        if not re.search(rf"(?m)^\|\s*{re.escape(label)}\s*\|", text):
            report.error(f"references/evaluation-rubric.md: no table row for dimension {label!r} ({dimension})")


# --- README layout ---------------------------------------------------------

def readme_layout_paths(text: str) -> list[str]:
    """Paths listed in the README's repository-layout code block (4 columns per nesting level)."""
    block = re.search(r"## Repository layout\s+```(?:text)?\n(.*?)```", text, re.S)
    if not block:
        return []
    paths, stack = [], []
    for line in block.group(1).splitlines():
        m = re.match(r"^((?:│   |    )*)(?:├── |└── )(\S+?)(\s+#.*)?$", line)
        if not m:
            continue
        depth = len(m.group(1)) // 4
        stack = stack[:depth] + [m.group(2).rstrip("/")]
        paths.append("/".join(stack))
    return paths


def check_readme(root: Path, report: Report) -> None:
    text = read_text(root / "README.md", report)
    if text is None:
        return
    listed = readme_layout_paths(text)
    if not listed:
        report.error("README.md: no parsable '## Repository layout' tree")
    for rel in listed:
        if not (root / rel).exists():
            report.error(f"README.md: repository layout lists {rel!r}, which does not exist")


# --- cases, hygiene --------------------------------------------------------

def check_cases(root: Path, report: Report) -> None:
    try:
        evaluation = case_schema.read_yaml(root / "tests" / "evaluation-cases.yaml")
        regression = case_schema.read_yaml(root / "tests" / "regression-cases.yaml")
    except case_schema.CaseFileError as exc:
        report.error(str(exc))
        return
    for error in case_schema.validate_evaluation_file(evaluation) + case_schema.validate_regression_file(regression):
        report.error(error)
    ids = [c.get("id") for c in evaluation.get("cases", []) if isinstance(c, dict)]
    ids += [c.get("id") for c in regression.get("regressions", []) if isinstance(c, dict)]
    for dup in sorted({i for i in ids if isinstance(i, str) and ids.count(i) > 1}):
        report.error(f"test cases: id {dup!r} is used more than once across the case files")


def check_hygiene(root: Path, report: Report) -> None:
    gitignore = read_text(root / ".gitignore", report) or ""
    patterns = {line.strip() for line in gitignore.splitlines()}
    for needed in REQUIRED_GITIGNORE:
        if needed not in patterns:
            report.error(f".gitignore: missing {needed!r}")
    for path in iter_files(root):
        rel = path.relative_to(root)
        if path.name == ".env" or path.suffix in {".pem", ".key"}:
            report.error(f"{rel}: looks like a credentials file; do not commit it")
            continue
        if path.suffix in {".png", ".jpg", ".gif", ".pdf", ".pyc", ".ico"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                report.error(f"{rel}: possible {label}")


def check_required_files(root: Path, report: Report) -> None:
    for rel in REQUIRED_FILES:
        path = root / rel
        if not path.is_file():
            report.error(f"missing required file: {rel}")
        elif not path.read_text(encoding="utf-8", errors="replace").strip():
            report.error(f"empty required file: {rel}")


def validate(root: Path, strict_install: bool = False, project_files: bool = True) -> Report:
    """Run every check against `root`. `project_files=False` validates an installed skill only."""
    report = Report()
    skill_text = check_skill(root, report, strict_install)
    if skill_text:
        check_reachability(root, skill_text, report)
    check_rubric(root, report)
    check_links(root, report)
    if project_files:
        check_required_files(root, report)
        check_readme(root, report)
        check_cases(root, report)
        check_hygiene(root, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="skill root (default: this repository)")
    parser.add_argument("--strict-install", action="store_true",
                        help="require the root directory to be named after the skill")
    args = parser.parse_args(argv)
    if yaml is None:
        print("ERROR: PyYAML is required for validation: pip install -r requirements-dev.txt", file=sys.stderr)
        return 1
    # absolute(), not resolve(): a symlinked install must keep the link's name, which is what the host reads.
    report = validate(args.root.expanduser().absolute(), args.strict_install)
    for warning in report.warnings:
        print(f"WARN: {warning}")
    for error in report.errors:
        print(f"ERROR: {error}")
    if report.errors:
        print(f"\nValidation failed with {len(report.errors)} error(s) and {len(report.warnings)} warning(s).")
        return 1
    print(f"PASS: structural validation ({len(report.warnings)} warning(s)).")
    print("NOTE: this checks structure, not response quality. See docs/EVALUATION.md for what is and is not measured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
