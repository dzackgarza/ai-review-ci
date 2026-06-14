# /// script
# requires-python = ">=3.11"
# ///
"""
Review runner: manages the agent loop, harvesting, and finalization.

The agent writes a candidate report to a fixed path, then calls
quality-control/ci/submit-candidate (no arguments) to validate and submit.
The script copies the validated report to .review-report-artifact.json
on success. The harness only checks for existence of that artifact after
the opencode session ends — the script owns validation and submission.
On timeout or missing artifact, the harness re-prompts and loops.
"""

import argparse
import os
import pathlib
import re
import subprocess
import sys
import time

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

HERE = pathlib.Path(__file__).parent.resolve()

ARTIFACT_PATH = pathlib.Path(".review-report-artifact.json")
COMMENT_PATH = pathlib.Path(".review-report-comment.md")
SCORE_PATH = pathlib.Path(".review-report-score.txt")
MAX_ATTEMPTS = 5
OPENCODE_TIMEOUT = 600


REPO_DOC_PATTERNS = ("*README.md", "*AGENTS.md", "*AGENTS*.md")
SCORE_RE = re.compile(r"\*\*Score: (\d+)/100\*\*")
REPO_SWEEP_HEADER = """
# INSTRUCTIONS: Repository-wide sweep, not PR-diff review

You are performing a FRESH, COMPREHENSIVE REPOSITORY AUDIT.
Scan the ENTIRE repository source tree - do NOT limit analysis to recent commits or diffs.
Analyze all files as if this were a day-zero audit of a new codebase.

HOWEVER: The context above lists existing review issues on this PR (from the thread index).
Do NOT re-raise these issues unless you have new evidence, the problem reappears in a
materially different form, or the previous resolution is directly contradicted by the
current code. The index is maintained by a separate gardener agent - respect it.
"""


def _repo_doc_candidates(repo_root: pathlib.Path) -> list[pathlib.Path]:
    return [path for pattern in REPO_DOC_PATTERNS for path in repo_root.rglob(pattern)]


def _is_repo_doc(repo_root: pathlib.Path, path: pathlib.Path) -> bool:
    rel_parts = path.relative_to(repo_root).parts
    return not any(part in IGNORE_DIRS for part in rel_parts) and path.is_file() and path.stat().st_size <= 500_000


def _render_repo_doc(repo_root: pathlib.Path, path: pathlib.Path) -> str:
    rel = path.relative_to(repo_root)
    return f"### Repo doc: {rel}\n\n{path.read_text()}"


def _join_repo_doc_sections(sections: list[str]) -> str:
    if not sections:
        return ""
    return "## Repo Documentation\n\n" + "\n\n---\n\n".join(sections)


def collect_repo_docs(repo_root: pathlib.Path) -> str:
    sections = [_render_repo_doc(repo_root, path) for path in _repo_doc_candidates(repo_root) if _is_repo_doc(repo_root, path)]
    return _join_repo_doc_sections(sections)


def collect_shared_guides(skills_dir: pathlib.Path) -> list[str]:
    skills_repo = pathlib.Path("opencode/skills").resolve()
    guides = []
    for fname in ["common.md", "source-coverage.md", "decay-risks.md"]:
        p = skills_dir / "_shared" / fname
        if p.exists():
            guides.append(p.read_text())

    ci_protocol = pathlib.Path("opencode/skills/_shared/ci-sweep-protocol.md").resolve()
    if ci_protocol.exists():
        guides.append(ci_protocol.read_text())

    for skill_name in [
        "policy-index",
        "bespoke-software-policy",
        "test-guidelines",
        "tool-provisioning-and-environment-hygiene",
    ]:
        p = skills_repo / skill_name / "SKILL.md"
        if p.exists():
            guides.append(p.read_text())

    return guides


def collect_slop_guides() -> list[str]:
    skills_repo = pathlib.Path("opencode/skills").resolve()
    guides = []
    for skill_name in ["anti-slop", "reviewing-llm-code", "fixing-slop"]:
        p = skills_repo / skill_name / "SKILL.md"
        if p.exists():
            guides.append(p.read_text())
    for ref_dir in [
        skills_repo / "reviewing-llm-code" / "references",
        skills_repo / "anti-slop" / "references",
    ]:
        if ref_dir.exists():
            for f in sorted(ref_dir.iterdir()):
                if f.suffix == ".md":
                    guides.append(f.read_text())
    return guides


def collect_review_context_guides(skills_dir: pathlib.Path) -> list[str]:
    guides = []
    p = skills_dir / "brooks-review" / "pr-review-guide.md"
    if p.exists():
        guides.append(p.read_text())

    repo_docs = collect_repo_docs(pathlib.Path.cwd())
    if repo_docs:
        guides.append(repo_docs)
    return guides


def load_review_skills(skills_dir: pathlib.Path) -> str:
    guides = collect_shared_guides(skills_dir)
    guides.extend(collect_review_context_guides(skills_dir))
    return "\n\n---\n\n".join(guides)


def load_slop_review_skills(skills_dir: pathlib.Path) -> str:
    guides = collect_shared_guides(skills_dir)
    guides.extend(collect_slop_guides())
    guides.extend(collect_review_context_guides(skills_dir))
    return "\n\n---\n\n".join(guides)


def substitute(template: str, **kwargs: str) -> str:
    for k, v in kwargs.items():
        template = template.replace(f"{{{{{k}}}}}", v)
    return template


SUBMITTED_CANDIDATE = "submitted.json"


def run_opencode(task_path: pathlib.Path) -> int:
    cmd = ["opencode", "run", "--model", "opencode/deepseek-v4-flash-free"]

    env = {
        **os.environ,
        "OPENCODE_PURE": "1",
        "RUNNER_TEMP": str(task_path.parent.parent),
    }
    with open(task_path) as f:
        res = subprocess.run(
            cmd,
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="review")
    parser.add_argument("--skills-dir", default="opencode/skills")
    parser.add_argument("--base-ref")
    parser.add_argument(
        "--template",
        default=str(HERE / "reviews" / "general" / "template.md"),
    )
    parser.add_argument("--pr-number", default="0")
    parser.add_argument(
        "--reviewer-context",
        default=None,
        help="Path to reviewer context file (existing issues on this PR)",
    )
    return parser.parse_args()


def _runner_inputs(args: argparse.Namespace) -> tuple[pathlib.Path, pathlib.Path]:
    skills_dir = pathlib.Path(args.skills_dir)
    template_path = pathlib.Path(args.template)
    if not skills_dir.is_dir() or not template_path.is_file():
        print("FATAL: Missing dependencies", file=sys.stderr)
        sys.exit(1)
    return skills_dir, template_path


def _prepare_run_paths() -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    run_dir = pathlib.Path(".agents/review-runner").resolve()
    candidates_dir = run_dir / "candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    return run_dir, candidates_dir, run_dir / "task.md"


def _repo_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def _review_system(mode: str, skills_dir: pathlib.Path) -> str:
    if mode == "slop":
        return load_slop_review_skills(skills_dir)
    return load_review_skills(skills_dir)


def _initial_prompt(args: argparse.Namespace, skills_dir: pathlib.Path, template_path: pathlib.Path) -> str:
    body = substitute(template_path.read_text(), REPO_SHA=_repo_sha())
    system = _review_system(args.mode, skills_dir)
    return f"{REPO_SWEEP_HEADER}\n\n{system}\n\n{body}"


def _inject_reviewer_context(prompt: str, reviewer_context: str | None) -> str:
    if reviewer_context is None:
        return prompt
    ctx_path = pathlib.Path(reviewer_context)
    if not ctx_path.is_file():
        print(f"FATAL: --reviewer-context file not found: {ctx_path}", file=sys.stderr)
        sys.exit(1)
    return f"{ctx_path.read_text()}\n\n{prompt}"


def _clear_submission_files(submitted_path: pathlib.Path) -> None:
    submitted_path.unlink(missing_ok=True)
    ARTIFACT_PATH.unlink(missing_ok=True)


def _run_opencode_attempt(task_path: pathlib.Path, attempt: int) -> None:
    print(f"--- opencode run attempt {attempt}/{MAX_ATTEMPTS} ---", file=sys.stderr)
    try:
        run_opencode(task_path)
    except subprocess.TimeoutExpired:
        print("--- opencode timed out ---", file=sys.stderr)
    except FileNotFoundError:
        print(
            "FATAL: 'opencode' executable not found in PATH. This is a non-transient failure - exiting immediately.",
            file=sys.stderr,
        )
        sys.exit(1)


def _record_artifact_score() -> None:
    comment = COMMENT_PATH.read_text()
    match = SCORE_RE.search(comment)
    if match is None:
        print("FATAL: rendered comment did not contain a machine-parseable score", file=sys.stderr)
        sys.exit(1)
    SCORE_PATH.write_text(match.group(1))


def _finalize_artifact_if_present() -> bool:
    if not ARTIFACT_PATH.exists():
        return False
    print("--- Report artifact submitted ---", file=sys.stderr)
    _record_artifact_score()
    return True


def _continuation_prompt(current_prompt: str, attempt: int, submitted_path: pathlib.Path) -> str:
    return (
        f"{current_prompt}\n\n## Continuation Context (Attempt {attempt})\n\n"
        f"Your session ended without a valid report at {ARTIFACT_PATH}.\n"
        f"Run quality-control/ci/submit-candidate (no arguments) after writing your "
        f"report to {submitted_path}."
    )


def _review_retry_loop(task_path: pathlib.Path, submitted_path: pathlib.Path, prompt: str) -> None:
    current_prompt = prompt
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if attempt > 1:
            time.sleep(5)
        task_path.write_text(current_prompt)
        _clear_submission_files(submitted_path)
        _run_opencode_attempt(task_path, attempt)
        if _finalize_artifact_if_present():
            sys.exit(0)
        current_prompt = _continuation_prompt(current_prompt, attempt, submitted_path)
    print(f"FATAL: No report artifact after {MAX_ATTEMPTS} attempts", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    args = _parse_args()
    skills_dir, template_path = _runner_inputs(args)
    _, candidates_dir, task_path = _prepare_run_paths()
    prompt = _inject_reviewer_context(_initial_prompt(args, skills_dir, template_path), args.reviewer_context)
    _review_retry_loop(task_path, candidates_dir / SUBMITTED_CANDIDATE, prompt)


if __name__ == "__main__":
    main()
