import pathlib
import subprocess
import sys

import pytest
import yaml

from ai_review_ci.gates import SUPPORTED_PROFILES
from ai_review_ci.install import (
    TEMPLATES,
    _prove_installation,
    _template_text,
    _write_manifest,
    _write_scaffold,
    _write_trigger_workflows,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]

# A job referencing a reusable workflow in this repo names it as
# `dzackgarza/ai-review-ci/.github/workflows/<file>@<ref>`.
_REUSABLE_PREFIX = "dzackgarza/ai-review-ci/.github/workflows/"
_WORKFLOWS_DIR = ROOT / ".github" / "workflows"


def _workflow_call_inputs(workflow_file: str) -> set[str]:
    """Declared `workflow_call` input names of a reusable workflow file."""
    data = yaml.safe_load((_WORKFLOWS_DIR / workflow_file).read_text())
    # PyYAML parses the bare `on:` key as the boolean True (YAML 1.1).
    on_block = data.get("on", data.get(True)) or {}
    return set((on_block.get("workflow_call") or {}).get("inputs") or {})


def _reusable_target(job: dict[str, object]) -> str | None:
    """The reusable-workflow filename a job calls, or None if not in-repo."""
    uses = job.get("uses")
    if not isinstance(uses, str) or not uses.startswith(_REUSABLE_PREFIX):
        return None
    return uses[len(_REUSABLE_PREFIX) :].split("@", 1)[0]


def _git_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    return repo


def _run_cli_install(
    repo: pathlib.Path,
    *,
    github_repo: str = "dzackgarza/ai-review-ci-install-target-does-not-exist",
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "ai_review_ci.cli",
            "install",
            "--target",
            str(repo),
            "--repo",
            github_repo,
            "--branch",
            "main",
            "--profile",
            "python",
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_install_writes_trigger_workflows(tmp_path: pathlib.Path) -> None:
    repo = _git_repo(tmp_path)
    _write_trigger_workflows(repo, "bun")
    wf = repo / ".github" / "workflows"
    assert sorted(p.name for p in wf.iterdir()) == sorted(TEMPLATES)
    for name in TEMPLATES:
        text = (wf / name).read_text()
        assert "uses: dzackgarza/ai-review-ci/.github/workflows/_review.yml@main" in text
    general = (wf / "review-general.yml").read_text()
    assert "report_type: general" in general
    assert "scope: repo" in general
    pr = (wf / "review-pr.yml").read_text()
    assert "scope: diff" in pr
    assert "gate: deterministic-diff" in pr
    assert "gate: delegation-conformance" in pr
    assert "gate: qc-doctor" in pr
    assert "gate: app-boot" not in pr
    assert "gate: thread-resolution" in pr
    assert "profile: 'bun'" in pr
    assert "fail_below" not in pr
    assert "pull_request" in pr


def test_install_writes_bun_playwright_app_boot_gate(tmp_path: pathlib.Path) -> None:
    repo = _git_repo(tmp_path)
    _write_trigger_workflows(repo, "bun-playwright")

    pr = (repo / ".github" / "workflows" / "review-pr.yml").read_text()
    assert "gate: app-boot" in pr
    assert "profile: 'bun-playwright'" in pr


def test_install_writes_manifest_contract(tmp_path: pathlib.Path) -> None:
    repo = _git_repo(tmp_path)

    _write_manifest(repo, "python", "main", "main", "main")

    manifest = (repo / ".ai-review-ci.toml").read_text()
    assert 'profile = "python"' in manifest
    assert 'installed_ref = "main"' in manifest
    assert 'release_channel = "main"' in manifest
    assert 'local_delegation = "global-justfile"' in manifest


def test_install_writes_profile_scaffold(tmp_path: pathlib.Path) -> None:
    repo = _git_repo(tmp_path)

    _write_scaffold(repo, "rust")

    assert (repo / "justfile").read_text() == (ROOT / "scaffolds" / "rust" / "justfile").read_text()


def test_install_local_files_finalize_with_doctor(tmp_path: pathlib.Path) -> None:
    repo = _git_repo(tmp_path)
    (repo / "pyproject.toml").write_text('[project]\nname = "target"\nversion = "0.1.0"\n')

    _write_scaffold(repo, "python")
    _write_trigger_workflows(repo, "python")
    _write_manifest(repo, "python", "main", "main", "main")
    _prove_installation(repo)

    assert (repo / "justfile").read_text() == (ROOT / "scaffolds" / "python" / "justfile").read_text()


def test_cli_install_uses_real_gh_and_fails_before_final_doctor_for_unavailable_branch_target(
    tmp_path: pathlib.Path,
) -> None:
    repo = _git_repo(tmp_path)
    (repo / "pyproject.toml").write_text('[project]\nname = "target"\nversion = "0.1.0"\n')

    result = _run_cli_install(repo)

    assert result.returncode == 1
    assert "FATAL: gh api --method PUT failed:" in result.stderr
    assert (repo / "justfile").read_text() == (ROOT / "scaffolds" / "python" / "justfile").read_text()
    assert (repo / ".github" / "workflows" / "review-pr.yml").exists()
    assert (repo / ".ai-review-ci.toml").exists()
    assert "doctor final proof" not in result.stdout
    assert "\nDone." not in result.stdout


def test_install_final_doctor_rejects_target_without_profile_shape(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _git_repo(tmp_path)
    _write_scaffold(repo, "python")
    _write_trigger_workflows(repo, "python")
    _write_manifest(repo, "python", "main", "main", "main")

    with pytest.raises(SystemExit):
        _prove_installation(repo)

    assert "FATAL: ai-review-ci doctor final proof failed with status misconfigured" in capsys.readouterr().err


def test_install_final_doctor_rejects_broken_local_delegation(tmp_path: pathlib.Path) -> None:
    repo = _git_repo(tmp_path)
    (repo / "pyproject.toml").write_text('[project]\nname = "target"\nversion = "0.1.0"\n')
    (repo / "justfile").write_text("test:\n    @true\n\ntest-ci:\n    @true\n")
    _write_trigger_workflows(repo, "python")
    _write_manifest(repo, "python", "main", "main", "main")

    with pytest.raises(SystemExit):
        _prove_installation(repo)


def test_install_refuses_non_git_dir(tmp_path: pathlib.Path) -> None:
    with pytest.raises(SystemExit):
        _write_trigger_workflows(tmp_path, "bun")


def test_install_refuses_overwriting_repo_owned_config(
    tmp_path: pathlib.Path,
) -> None:
    repo = _git_repo(tmp_path)
    _write_trigger_workflows(repo, "bun")
    customized = repo / ".github" / "workflows" / "review-general.yml"
    customized.write_text("# locally customized\n")
    with pytest.raises(SystemExit):
        _write_trigger_workflows(repo, "bun")
    assert customized.read_text() == "# locally customized\n"


@pytest.mark.parametrize("profile", SUPPORTED_PROFILES)
@pytest.mark.parametrize("template", TEMPLATES)
def test_trigger_inputs_are_declared_by_reusable_workflow(template: str, profile: str) -> None:
    """Every input an installed trigger passes must be declared by the
    reusable workflow it calls.

    Regression guard for #123: the installed triggers passed a `fail_below`
    input that `_review.yml` never declared, so GitHub rejected the run at
    startup (`startup_failure`) and the review silently never ran. An
    undeclared input is a workflow-file error for *any* input, so this checks
    the whole `with:` contract against the reusable workflow's declared inputs
    — across every profile-rendered trigger — rather than blocklisting one
    known-bad key.
    """
    rendered = _template_text(template, profile, "main")
    workflow = yaml.safe_load(rendered)

    checked_a_reusable_call = False
    for job_name, job in workflow["jobs"].items():
        target = _reusable_target(job)
        if target is None:
            continue
        checked_a_reusable_call = True
        declared = _workflow_call_inputs(target)
        passed = set((job.get("with") or {}))
        undeclared = passed - declared
        assert not undeclared, (
            f"{template} (profile={profile}) job {job_name!r} passes input(s) "
            f"{sorted(undeclared)} to {target}, which declares only {sorted(declared)}. "
            f"GitHub fails such a run at startup before any review step runs."
        )

    assert checked_a_reusable_call, f"{template} (profile={profile}) calls no in-repo reusable workflow"


def test_install_refuses_overwriting_repo_owned_scaffold(tmp_path: pathlib.Path) -> None:
    repo = _git_repo(tmp_path)
    customized = repo / "justfile"
    customized.write_text("test:\n    @true\n")

    with pytest.raises(SystemExit):
        _write_scaffold(repo, "python")

    assert customized.read_text() == "test:\n    @true\n"
