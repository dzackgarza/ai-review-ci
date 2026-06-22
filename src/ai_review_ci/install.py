"""Installer for the complete ai-review-ci enforcement surface.

All review complexity lives upstream: the reusable workflow referenced by
these triggers clones this repository inside the CI runner at execution time.
Installing into a repo writes three minimally-correct trigger workflows —
plain configuration files (triggers, crons, thresholds) that the repo owns and
edits directly afterward:

- review-general.yml  — repo-wide general review (cron, push to main, dispatch)
- review-slop.yml     — repo-wide slop review   (cron, push to main, dispatch)
- review-pr.yml       — diff-scoped reviews on every pull request,
                        rendered for the declared curated project profile

Existing files are never overwritten: once installed they are repo-owned
configuration. Installation also applies the GitHub-side required-check
contract, because QC setup is incomplete if branch protection can be skipped.
"""

import pathlib
import sys
from importlib.resources import files

from ai_review_ci.gates import SUPPORTED_PROFILES, protect_branch

TEMPLATES = ("review-general.yml", "review-slop.yml", "review-pr.yml")


def _validate_profile(profile: str) -> None:
    if profile not in SUPPORTED_PROFILES:
        print(
            f"FATAL: unsupported project profile {profile!r}; "
            f"expected one of: {', '.join(SUPPORTED_PROFILES)}",
            file=sys.stderr,
        )
        sys.exit(1)


def _template_text(name: str, profile: str) -> str:
    source_name = "review-pr-bun-playwright.yml" if name == "review-pr.yml" and profile == "bun-playwright" else name
    text = (files("ai_review_ci") / "templates" / source_name).read_text()
    return text.replace("{{ profile }}", profile)


def _write_trigger_workflows(target: pathlib.Path, profile: str) -> None:
    """Write the repo-owned trigger workflow files."""
    _validate_profile(profile)
    target = target.resolve()
    if not (target / ".git").exists():
        print(f"FATAL: {target} is not a git repository root", file=sys.stderr)
        sys.exit(1)

    wf_dir = target / ".github" / "workflows"
    existing = [n for n in TEMPLATES if (wf_dir / n).exists()]
    if existing:
        print(
            f"FATAL: already installed in {target}: {', '.join(existing)} — these are repo-owned configuration; edit them directly, or remove them first to re-initialize.",
            file=sys.stderr,
        )
        sys.exit(1)

    wf_dir.mkdir(parents=True, exist_ok=True)
    for name in TEMPLATES:
        (wf_dir / name).write_text(_template_text(name, profile))
        print(f"installed .github/workflows/{name}")


def install(
    target: pathlib.Path = pathlib.Path("."),
    *,
    repo: str,
    branch: str,
    profile: str,
) -> None:
    """Install the review trigger workflows and required branch protection.

    Args:
        target: Target repository root (default: current directory).
        repo: GitHub repository in owner/name form.
        branch: Branch name protected by the required QC gates.
        profile: Curated project profile to enforce.
    """
    _write_trigger_workflows(target, profile)
    protect_branch(repo, branch, profile)

    print(
        "\nDone. Commit the three files; they are now repo-owned "
        "configuration — edit crons, branches, and upstream refs directly.\n"
        "Requirements: GitHub code scanning enabled and branch protection "
        f"requiring the ai-review-ci deterministic gates for {profile}."
    )
