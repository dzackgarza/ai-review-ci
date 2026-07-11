"""Review harness: assembles the reviewer prompt and loops opencode until a
validated report artifact exists.

Prompt assembly order: reviewer context (existing tracked findings), scope
instructions (repo-wide sweep or PR diff), focus prompt (repo-declared review
focus), manifest documents (skills and guides, statically declared per review
type), policy documents (repo-declared, explicit paths), review context packet
(repo-assembled tar exploded into .review-context/ by the runner), repo docs,
task template.

For PR-diff scope, the staged unified diff is inlined into the prompt and
repo README/AGENTS docs are not auto-injected. Diff reviewers need the changed
surface and the central review contract, not broad repository instructions that
compete with the diff. Explicitly-declared policy documents and the focus
prompt are repo-owned configuration and are inlined in every scope.

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
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, NonNegativeFloat, PositiveInt

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
CONTEXT_PACKET_DIR = Path(".review-context")
CONTEXT_PACKET_PROMPT = "PROMPT.md"
SUBMIT_CANDIDATE_BIN = Path("/home/reviewer/bin/submit-candidate")
SUBMITTED_CANDIDATE = "submitted.json"


class OpencodeConfig(BaseModel):
    """External-process seams for the retry loop: the opencode binary, per-attempt
    timeout, retry count, and inter-attempt backoff. Required config, not defaults —
    the CI wiring (``ci/runner.just``) supplies every value and a missing (KeyError),
    malformed (ValueError), or out-of-range (ValidationError) one crashes at the
    boundary rather than silently falling back to a baked-in guess. The value ranges
    are enforced on the model surface: a non-positive timeout or max_attempts, or a
    negative backoff, is a degenerate run (an empty ``range(1, max_attempts + 1)``
    never invokes opencode), so those are rejected at construction, not accepted. A
    non-finite backoff (``inf``/``nan``) is rejected too (``allow_inf_nan=False``) — an
    infinite backoff would hang/crash in ``time.sleep`` mid-loop, not at the boundary.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    binary: Path
    timeout: PositiveInt
    max_attempts: PositiveInt
    backoff: NonNegativeFloat

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> OpencodeConfig:
        """Build from required environment variables; fail loud on any missing/malformed value.

        Missing key -> KeyError; non-numeric or out-of-range timeout/attempts/backoff ->
        ValueError (pydantic ValidationError subclasses ValueError). The model enforces
        the field types, value ranges, and frozen-ness on the parsed values.
        """
        source = os.environ if environ is None else environ
        return cls(
            binary=Path(source["AI_REVIEW_OPENCODE_BIN"]),
            timeout=int(source["AI_REVIEW_OPENCODE_TIMEOUT"]),
            max_attempts=int(source["AI_REVIEW_MAX_ATTEMPTS"]),
            backoff=float(source["AI_REVIEW_BACKOFF"]),
        )


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


def focus_prompt_section(focus_prompt: str) -> str:
    """Render the repo-declared review focus as a prompt section; empty if unset."""
    text = focus_prompt.strip()
    if not text:
        return ""
    return "## Repository Review Focus\n\n" + text


def policy_docs_section(policy_paths: str, repo_root: Path) -> str:
    """Inline the repo-declared policy documents; a missing entry is fatal.

    One repo-relative path per line; blank lines and ``#`` comments are
    skipped. These are explicit repo-owned configuration, so unlike the
    auto-collected README/AGENTS docs they are inlined in every scope and a
    dangling path fails the run instead of being silently dropped.
    """
    sections: list[str] = []
    for raw in policy_paths.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        p = repo_root / line
        if not p.is_file():
            print(f"FATAL: policy document not found: {line}", file=sys.stderr)
            sys.exit(1)
        sections.append(f"### Policy document: {line}\n\n{p.read_text()}")
    if not sections:
        return ""
    return "## Repository Policy Documents\n\n" + "\n\n---\n\n".join(sections)


def context_packet_section(repo_root: Path) -> str:
    """Inline the exploded review context packet, if one was staged.

    The packet is repo-owned: a tar archive assembled by the consumer repo
    (prompt + reference documents, in whatever directory organization the
    repo chose) and exploded into ``.review-context/`` by the runner. A
    top-level ``PROMPT.md`` leads the section; every other Markdown file is
    inlined in sorted path order. Non-Markdown files are listed by path so
    the reviewer knows they exist and can read them from disk.
    """
    packet_root = repo_root / CONTEXT_PACKET_DIR
    if not packet_root.is_dir():
        return ""
    files = sorted(p for p in packet_root.rglob("*") if p.is_file())
    if not files:
        print(f"FATAL: staged review context packet is empty: {CONTEXT_PACKET_DIR}", file=sys.stderr)
        sys.exit(1)
    lead: list[str] = []
    docs: list[str] = []
    listed: list[str] = []
    for p in files:
        rel = p.relative_to(packet_root)
        if str(rel) == CONTEXT_PACKET_PROMPT:
            lead.append(p.read_text())
        elif p.suffix == ".md":
            docs.append(f"### Review packet document: {rel}\n\n{p.read_text()}")
        else:
            listed.append(f"- {CONTEXT_PACKET_DIR}/{rel}")
    sections = ["## Repository Review Packet", *lead, *docs]
    if listed:
        sections.append("### Additional packet files (read from disk as needed)\n\n" + "\n".join(listed))
    return "\n\n".join(sections)


def is_diff_scope(scope_path: Path) -> bool:
    """True when the current review is a PR diff review."""
    return scope_path.name == "scope-diff.md"


def diff_prompt_section(repo_root: Path) -> str:
    """Inline the staged PR diff; diff scope is invalid without it."""
    diff_path = repo_root / DIFF_PATH
    if not diff_path.is_file() or diff_path.stat().st_size == 0:
        print(f"FATAL: diff-scope review requires non-empty {DIFF_PATH}", file=sys.stderr)
        sys.exit(1)
    return "## Pull Request Unified Diff\n\n```diff\n" + diff_path.read_text() + "\n```"


def build_initial_prompt(
    template_path: Path,
    scope_path: Path,
    manifest_path: Path,
    ctx_path: Path,
    repo_root: Path,
    policy_paths: str = "",
    focus_prompt: str = "",
) -> str:
    """Assemble the full reviewer prompt in the documented order."""
    diff_scope = is_diff_scope(scope_path)
    sections = [
        ctx_path.read_text(),
        scope_path.read_text(),
    ]
    if focus := focus_prompt_section(focus_prompt):
        sections.append(focus)
    if diff_scope:
        sections.append(diff_prompt_section(repo_root))
    sections.append(load_manifest(manifest_path))
    if policy_docs := policy_docs_section(policy_paths, repo_root):
        sections.append(policy_docs)
    if packet := context_packet_section(repo_root):
        sections.append(packet)
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


def opencode_command(config: OpencodeConfig, attempt: int) -> list[str]:
    """opencode invocation for an attempt; retries continue the session."""
    cmd = [str(config.binary), "run"]
    if attempt > 1:
        cmd.append("-c")
    return cmd


def ensure_blocking_stdio() -> None:
    """Restore blocking mode on the harness's own stdout/stderr.

    The CI recipe runs ``opencode --version`` in the same shell before this
    harness, and Node sets O_NONBLOCK on inherited stdio file descriptions
    without restoring it. A non-blocking stdout makes Python's writes and
    exit-time flush of the large captured opencode transcript fail with
    EAGAIN (BlockingIOError), which CPython reports as exit code 120 —
    failing the CI run *after* a report was successfully submitted.
    """
    for stream in (sys.stdout, sys.stderr):
        os.set_blocking(stream.fileno(), True)


def run_opencode(config: OpencodeConfig, task_path: Path, attempt: int) -> int:
    """Run opencode with the task prompt on stdin; returns the exit code."""
    env = {
        **os.environ,
        "OPENCODE_PURE": "1",
        "RUNNER_TEMP": str(task_path.parent.parent),
    }
    with open(task_path) as f:
        res = subprocess.run(
            opencode_command(config, attempt),
            stdin=f,
            capture_output=True,
            text=True,
            check=False,
            timeout=config.timeout,
            env=env,
        )

    ensure_blocking_stdio()
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
    template: Path,
    scope: Path,
    manifest: Path,
    reviewer_context: Path,
    policy_paths: str = "",
    focus_prompt: str = "",
) -> None:
    """Assemble the reviewer prompt and loop opencode until an artifact exists.

    Args:
        template: Path to the review task template markdown.
        scope: Path to scope instructions markdown (repo sweep or PR diff).
        manifest: Path to the prompt manifest listing guide documents.
        reviewer_context: Path to reviewer context file (existing tracked findings).
        policy_paths: Newline-delimited repo-relative policy documents to
            inline into the prompt; a missing entry is fatal.
        focus_prompt: Short repo-specific review-focus instructions inlined
            into the prompt.
    """
    config = OpencodeConfig.from_env()
    _require_files(template, scope, manifest, reviewer_context)

    run_dir = Path(".agents/review-runner").resolve()
    candidates_dir = run_dir / "candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    task_path = run_dir / "task.md"

    initial_prompt = build_initial_prompt(
        template,
        scope,
        manifest,
        reviewer_context,
        Path.cwd(),
        policy_paths=policy_paths,
        focus_prompt=focus_prompt,
    )

    submitted_path = candidates_dir / SUBMITTED_CANDIDATE

    last_timeout: subprocess.TimeoutExpired | None = None
    for attempt in range(1, config.max_attempts + 1):
        last_timeout = None
        if attempt > 1:
            time.sleep(config.backoff)
            prompt = retry_prompt(submitted_path)
        else:
            prompt = initial_prompt

        task_path.write_text(prompt)
        print(f"--- opencode run attempt {attempt}/{config.max_attempts} ---", file=sys.stderr)
        submitted_path.unlink(missing_ok=True)
        ARTIFACT_PATH.unlink(missing_ok=True)
        try:
            run_opencode(config, task_path, attempt)
        except subprocess.TimeoutExpired as error:
            last_timeout = error
            print(f"--- opencode timed out: {error} ---", file=sys.stderr)
        except FileNotFoundError:
            print(
                "FATAL: 'opencode' executable not found in PATH. This is a non-transient failure — exiting immediately.",
                file=sys.stderr,
            )
            sys.exit(1)

        if ARTIFACT_PATH.exists():
            print("--- Report artifact submitted ---", file=sys.stderr)
            ensure_blocking_stdio()
            sys.exit(0)

    if last_timeout is not None:
        print(
            f"FATAL: No report artifact after {config.max_attempts} attempts; last attempt timed out after {last_timeout.timeout}s",
            file=sys.stderr,
        )
    else:
        print(f"FATAL: No report artifact after {config.max_attempts} attempts", file=sys.stderr)
    sys.exit(1)
