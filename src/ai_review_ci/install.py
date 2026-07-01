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
SCAFFOLD_FILES = ("justfile",)
PR_TEMPLATE = "pull_request_template.md"
DEFAULT_INFRA_REF = "main"
SUCCESSFUL_DOCTOR_STATUSES = ("current", "intentional_exception")


def _validate_profile(profile: str) -> None:
    if profile not in SUPPORTED_PROFILES:
        print(
            f"FATAL: unsupported project profile {profile!r}; expected one of: {', '.join(SUPPORTED_PROFILES)}",
            file=sys.stderr,
        )
        sys.exit(1)


def _git_repo_root(target: pathlib.Path) -> pathlib.Path:
    target = target.resolve()
    if not (target / ".git").exists():
        print(f"FATAL: {target} is not a git repository root", file=sys.stderr)
        sys.exit(1)
    return target


def _template_text(name: str, profile: str, ref: str = DEFAULT_INFRA_REF) -> str:
    source_name = "review-pr-bun-playwright.yml" if name == "review-pr.yml" and profile == "bun-playwright" else name
    text = (files("ai_review_ci") / "templates" / source_name).read_text()
    return text.replace("{{ profile }}", profile).replace("{{ ref }}", ref)


def _scaffold_text(profile: str, name: str) -> str:
    _validate_profile(profile)
    return (files("ai_review_ci") / "scaffolds" / profile / name).read_text()


def _write_scaffold(target: pathlib.Path, profile: str) -> None:
    """Write the profile-local QC delegation scaffold."""
    _validate_profile(profile)
    target = _git_repo_root(target)
    existing = [name for name in SCAFFOLD_FILES if (target / name).exists()]
    if existing:
        print(
            f"FATAL: refusing to overwrite existing scaffold target(s) in {target}: {', '.join(existing)}",
            file=sys.stderr,
        )
        sys.exit(1)
    for name in SCAFFOLD_FILES:
        (target / name).write_text(_scaffold_text(profile, name))
        print(f"installed {name}")


def _write_trigger_workflows(target: pathlib.Path, profile: str, ref: str = DEFAULT_INFRA_REF) -> None:
    """Write the repo-owned trigger workflow files."""
    _validate_profile(profile)
    target = _git_repo_root(target)

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
        (wf_dir / name).write_text(_template_text(name, profile, ref))
        print(f"installed .github/workflows/{name}")


def _write_pr_template(target: pathlib.Path) -> None:
    """Write the policy-alignment PR template.

    Installing this template opts the repo into gate enforcement: the marker it
    carries is what `check_pr_description` requires in every PR body, so the
    affirmation section cannot be deleted to bypass the gate.
    """
    target = _git_repo_root(target)
    dest = target / ".github" / PR_TEMPLATE
    if dest.exists():
        print(
            f"FATAL: {dest} already exists — this PR template is repo-owned configuration; edit it directly, or remove it first to re-initialize.",
            file=sys.stderr,
        )
        sys.exit(1)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text((files("ai_review_ci") / "templates" / PR_TEMPLATE).read_text())
    print(f"installed .github/{PR_TEMPLATE}")


def _write_manifest(target: pathlib.Path, profile: str, branch: str, ref: str, release_channel: str) -> None:
    from ai_review_ci.doctor import LOCAL_DELEGATION_MODE, WORKFLOW_TEMPLATE_VERSION, manifest_text

    manifest = target / ".ai-review-ci.toml"
    if manifest.exists():
        print(
            f"FATAL: {manifest} already exists — this manifest is repo-owned configuration; edit it directly, or remove it first to re-initialize.",
            file=sys.stderr,
        )
        sys.exit(1)
    manifest.write_text(
        manifest_text(
            profile=profile,
            installed_ref=ref,
            release_channel=release_channel,
            workflow_template_version=WORKFLOW_TEMPLATE_VERSION,
            local_delegation=LOCAL_DELEGATION_MODE,
            default_branch=branch,
            exceptions=(),
        )
    )
    print(f"installed {manifest.name}")


def _prove_installation(target: pathlib.Path) -> None:
    """Run doctor as the final install proof."""
    from ai_review_ci.doctor import doctor_report

    report = doctor_report(target)
    if report.global_status not in SUCCESSFUL_DOCTOR_STATUSES:
        print(
            f"FATAL: ai-review-ci doctor final proof failed with status {report.global_status}",
            file=sys.stderr,
        )
        for finding in report.findings:
            print(f"- {finding.surface}: {finding.evidence}", file=sys.stderr)
        sys.exit(1)
    print(f"doctor final proof: {report.global_status}")


def install(
    target: pathlib.Path = pathlib.Path("."),
    *,
    repo: str,
    branch: str,
    profile: str,
    ref: str = DEFAULT_INFRA_REF,
    release_channel: str = DEFAULT_INFRA_REF,
) -> None:
    """Install the review trigger workflows and required branch protection.

    Args:
        target: Target repository root (default: current directory).
        repo: GitHub repository in owner/name form.
        branch: Branch name protected by the required QC gates.
        profile: Curated project profile to enforce.
        ref: ai-review-ci git ref used by installed workflows.
        release_channel: Human-readable ai-review-ci release channel recorded in the manifest.
    """
    target = target.resolve()
    _write_scaffold(target, profile)
    _write_trigger_workflows(target, profile, ref)
    _write_pr_template(target)
    _write_manifest(target, profile, branch, ref, release_channel)
    protect_branch(repo, branch, profile)
    _prove_installation(target)

    print(
        "\nDone. Commit the installed files; they are now repo-owned "
        "configuration — edit crons, branches, and upstream refs directly.\n"
        "Requirements: GitHub code scanning enabled and branch protection "
        f"requiring the ai-review-ci deterministic gates for {profile}."
    )
