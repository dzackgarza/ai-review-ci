"""Review harness: assembles the reviewer prompt and loops opencode until a
validated report artifact exists.

Prompt assembly order: reviewer context (existing tracked findings), scope
instructions (repo-wide sweep or PR diff), manifest documents (skills and
guides, statically declared per review type), repo docs, task template.

For PR-diff scope, the staged unified diff is inlined into the prompt and
repo README/AGENTS docs are not auto-injected. Diff reviewers need the changed
surface and the central review contract, not broad repository instructions that
compete with the diff.

The agent writes a candidate report to a fixed path, then calls the reviewer
submission command (no arguments) to validate and submit. submit-candidate
copies the validated report to .review-report-artifact.json. This harness
only checks for that artifact's existence after each opencode invocation;
on timeout or a missing artifact it continues the session with
``opencode run -c``.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

IGNORE_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "__pycache__",
    "dist",
    "build",
    ".next",
    "coverage",
}

ARTIFACT_PATH = Path(".review-report-artifact.json")
DIFF_PATH = Path(".reviewer-diff.patch")
MAX_ATTEMPTS = 5
OPENCODE_TIMEOUT = 600
OPENCODE_BIN = Path("/usr/local/bin/opencode")
SUBMIT_CANDIDATE_BIN = Path("/home/reviewer/bin/submit-candidate")
SUBMITTED_CANDIDATE = "submitted.json"


def _doc_section(p: Path, repo_root: Path) -> str | None:
    """Render one repo doc as a prompt section; None if it must be skipped."""
    rel = p.relative_to(repo_root)
    if any(part in IGNORE_DIRS for part in p.parts):
        return None
    if not p.is_file() or p.stat().st_size > 500_000:
        return None
    return f"### Repo doc: {rel}\n\n{p.read_text()}"


def collect_repo_docs(repo_root: Path) -> str:
    """Inline every README/AGENTS doc in the repo into one prompt section."""
    sections = []
    for pattern in ("*README.md", "*AGENTS.md", "*AGENTS*.md"):
        for p in repo_root.rglob(pattern):
            section = _doc_section(p, repo_root)
            if section is not None:
                sections.append(section)
    if not sections:
        return ""
    return "## Repo Documentation\n\n" + "\n\n---\n\n".join(sections)


def _manifest_entry_sections(p: Path) -> list[str]:
    """Sections for one manifest entry: a file, or a directory of *.md files."""
    if p.is_dir():
        files = sorted(p.glob("*.md"))
        if not files:
            print(f"FATAL: manifest dir has no .md files: {p}", file=sys.stderr)
            sys.exit(1)
        return [f.read_text() for f in files]
    if p.is_file():
        return [p.read_text()]
    print(f"FATAL: manifest entry not found: {p}", file=sys.stderr)
    sys.exit(1)


def load_manifest(manifest_path: Path) -> str:
    """Inline every document listed in the manifest, in order.

    One path per line, relative to the reviews/ directory (the manifest's
    parent's parent). A directory entry inlines all of its top-level *.md
    files, sorted by name. Missing entries are fatal.
    """
    reviews_root = manifest_path.resolve().parent.parent
    sections: list[str] = []
    for raw in manifest_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        sections.extend(_manifest_entry_sections(reviews_root / line))
    if not sections:
        print(f"FATAL: manifest is empty: {manifest_path}", file=sys.stderr)
        sys.exit(1)
    return "\n\n---\n\n".join(sections)


def is_diff_scope(scope_path: Path) -> bool:
    """True when the current review is a PR diff review."""
    return scope_path.name == "scope-diff.md"


def diff_prompt_section(repo_root: Path) -> str:
    """Inline the staged PR diff; diff scope is invalid without it."""
    diff_path = repo_root / DIFF_PATH
    if not diff_path.is_file() or diff_path.stat().st_size == 0:
        print(
            f"FATAL: diff-scope review requires non-empty {DIFF_PATH}", file=sys.stderr
        )
        sys.exit(1)
    return "## Pull Request Unified Diff\n\n```diff\n" + diff_path.read_text() + "\n```"


def build_initial_prompt(
    template_path: Path,
    scope_path: Path,
    manifest_path: Path,
    ctx_path: Path,
    repo_root: Path,
) -> str:
    """Assemble the full reviewer prompt in the documented order."""
    diff_scope = is_diff_scope(scope_path)
    sections = [
        ctx_path.read_text(),
        scope_path.read_text(),
    ]
    if diff_scope:
        sections.append(diff_prompt_section(repo_root))
    sections.append(load_manifest(manifest_path))
    if not diff_scope and (repo_docs := collect_repo_docs(repo_root)):
        sections.append(repo_docs)
    sections.append(template_path.read_text())
    return "\n\n".join(sections)


def retry_prompt(submitted_path: Path) -> str:
    """Continuation prompt used when an attempt produced no valid artifact."""
    return (
        f"The previous invocation in this opencode session ended without "
        f"a valid report at {ARTIFACT_PATH}. Continue the existing session. "
        f"Write the report to {submitted_path}, then run "
        f"{SUBMIT_CANDIDATE_BIN} with no arguments."
    )


def opencode_command(attempt: int) -> list[str]:
    """opencode invocation for an attempt; retries continue the session."""
    cmd = [str(OPENCODE_BIN), "run"]
    if attempt > 1:
        cmd.append("-c")
    return cmd


def run_opencode(task_path: Path, attempt: int) -> int:
    """Run opencode with the task prompt on stdin; returns the exit code."""
    env = {
        **os.environ,
        "OPENCODE_PURE": "1",
        "RUNNER_TEMP": str(task_path.parent.parent),
    }
    with open(task_path) as f:
        res = subprocess.run(
            opencode_command(attempt),
            stdin=f,
            capture_output=True,
            text=True,
            check=False,
            timeout=OPENCODE_TIMEOUT,
            env=env,
        )

    sys.stdout.write(res.stdout)
    sys.stderr.write(res.stderr)
    return res.returncode


def _require_files(*paths: Path) -> None:
    """Every harness input must exist before any opencode attempt starts."""
    for p in paths:
        if not p.is_file():
            print(f"FATAL: required input not found: {p}", file=sys.stderr)
            sys.exit(1)


def run_review(
    template: Path, scope: Path, manifest: Path, reviewer_context: Path
) -> None:
    """Assemble the reviewer prompt and loop opencode until an artifact exists.

    Args:
        template: Path to the review task template markdown.
        scope: Path to scope instructions markdown (repo sweep or PR diff).
        manifest: Path to the prompt manifest listing guide documents.
        reviewer_context: Path to reviewer context file (existing tracked findings).
    """
    _require_files(template, scope, manifest, reviewer_context)

    run_dir = Path(".agents/review-runner").resolve()
    candidates_dir = run_dir / "candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    task_path = run_dir / "task.md"

    initial_prompt = build_initial_prompt(
        template, scope, manifest, reviewer_context, Path.cwd()
    )

    submitted_path = candidates_dir / SUBMITTED_CANDIDATE

    for attempt in range(1, MAX_ATTEMPTS + 1):
        if attempt > 1:
            time.sleep(5)
            prompt = retry_prompt(submitted_path)
        else:
            prompt = initial_prompt

        task_path.write_text(prompt)
        print(f"--- opencode run attempt {attempt}/{MAX_ATTEMPTS} ---", file=sys.stderr)
        submitted_path.unlink(missing_ok=True)
        ARTIFACT_PATH.unlink(missing_ok=True)
        try:
            run_opencode(task_path, attempt)
        except subprocess.TimeoutExpired:
            print("--- opencode timed out ---", file=sys.stderr)
        except FileNotFoundError:
            print(
                "FATAL: 'opencode' executable not found in PATH. This is a non-transient failure — exiting immediately.",
                file=sys.stderr,
            )
            sys.exit(1)

        if ARTIFACT_PATH.exists():
            print("--- Report artifact submitted ---", file=sys.stderr)
            sys.exit(0)

    print(f"FATAL: No report artifact after {MAX_ATTEMPTS} attempts", file=sys.stderr)
    sys.exit(1)
