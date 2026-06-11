"""Installer for the ai-review-ci trigger workflows.

All review complexity lives upstream: the reusable workflow referenced by
these triggers clones this repository inside the CI runner at execution time.
Installing into a repo means writing three minimally-correct trigger
workflows — plain configuration files (triggers, crons, thresholds) that the
repo owns and edits directly afterward:

- review-general.yml  — repo-wide general review (cron, push to main, dispatch)
- review-slop.yml     — repo-wide slop review   (cron, push to main, dispatch)
- review-pr.yml       — diff-scoped reviews on every pull request

Existing files are never overwritten: once installed they are repo-owned
configuration.

This module is a pure file-copier: no process execution, no network
(enforced by the import-linter contract in pyproject.toml).
"""

import pathlib
import sys
from importlib.resources import files

TEMPLATES = ["review-general.yml", "review-slop.yml", "review-pr.yml"]


def install(target: pathlib.Path = pathlib.Path(".")) -> None:
    """Install the review trigger workflows into a repo.

    Args:
        target: Target repository root (default: current directory).
    """
    target = target.resolve()
    if not (target / ".git").exists():
        print(f"FATAL: {target} is not a git repository root", file=sys.stderr)
        sys.exit(1)

    wf_dir = target / ".github" / "workflows"
    existing = [n for n in TEMPLATES if (wf_dir / n).exists()]
    if existing:
        print(
            f"FATAL: already installed in {target}: {', '.join(existing)} — "
            "these are repo-owned configuration; edit them directly, or "
            "remove them first to re-initialize.",
            file=sys.stderr,
        )
        sys.exit(1)

    wf_dir.mkdir(parents=True, exist_ok=True)
    for name in TEMPLATES:
        (wf_dir / name).write_text(
            (files("ai_review_ci") / "templates" / name).read_text()
        )
        print(f"installed .github/workflows/{name}")

    print(
        "\nDone. Commit the three files; they are now repo-owned "
        "configuration — edit crons, branches, and thresholds directly.\n"
        "Requirements: GitHub code scanning enabled; optional Actions vars "
        "GENERAL_FAIL_BELOW / SLOP_FAIL_BELOW for health-score gating."
    )
