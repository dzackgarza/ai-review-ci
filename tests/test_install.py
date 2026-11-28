import datetime
import os
import pathlib
import subprocess
import sys
from typing import Any

import pytest
import yaml

from ai_review_ci.gates import POLICY_GATE_MARKER, SUPPORTED_PROFILES
from ai_review_ci.install import (
    AISLOP_CONFIG,
    AMBIENT_WORKFLOW,
    PR_TEMPLATE,
    PR_WORKFLOW,
    _prove_installation,
    _template_text,
    _write_aislop_config,
    _write_pr_template,
    _write_scaffold,
    _write_trigger_workflows,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]

_WORKFLOWS_DIR = ROOT / ".github" / "workflows"


def _workflow_jobs(workflow_file: str) -> dict[str, dict[str, Any]]:
    data = yaml.safe_load((_WORKFLOWS_DIR / workflow_file).read_text())
    jobs = data.get("jobs")
    assert isinstance(jobs, dict)
    assert all(isinstance(job, dict) for job in jobs.values())
    return jobs


def _git_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    return repo


def _run_cli_install(
    repo: pathlib.Path,
    *,
    github_repo: str = "dzackgarza/ai-review-ci-install-target-does-not-exist",
    skip_scaffold: bool = False,
    phase: str = "development",
) -> subprocess.CompletedProcess[str]:
    args = [
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
        "--phase",
        phase,
    ]
    if skip_scaffold:
        args.append("--skip-scaffold")
    return subprocess.run(
        args,
        text=True,
        capture_output=True,
        check=False,
    )


def test_install_writes_pr_template_with_gate_marker(tmp_path: pathlib.Path) -> None:
    repo = _git_repo(tmp_path)
    _write_pr_template(repo)
    dest = repo / ".github" / PR_TEMPLATE
    assert dest.is_file()
    text = dest.read_text(encoding="utf-8")
    assert POLICY_GATE_MARKER in text
    assert "## Issue-scoped lifecycle gate — required" in text
    assert "Linked triaged issue(s)" in text
    assert "started as a draft" in text
    assert "Ready-for-review was requested only after" in text
    assert "every resolved substantive item carries its own evidenced disposition" in text


def test_install_writes_canonical_aislop_config(tmp_path: pathlib.Path) -> None:
    repo = _git_repo(tmp_path)
    _write_aislop_config(repo)
    dest = repo / AISLOP_CONFIG
    assert dest.is_file()
    config = yaml.safe_load(dest.read_text())
    assert config["rules"]["ai-slop/python-print-debug"] == "off"
    assert "failBelow" not in (config.get("ci") or {})


def test_distributed_aislop_config_matches_repo_own_config() -> None:
    packaged = (ROOT / "src" / "ai_review_ci" / "data" / "aislop-config.yml").read_text()
    repo_own = (ROOT / ".aislop" / "config.yml").read_text()
    assert repo_own == packaged
    assert "NOT distributed" not in packaged


def test_install_aislop_config_refuses_overwrite(tmp_path: pathlib.Path) -> None:
    repo = _git_repo(tmp_path)
    dest = repo / AISLOP_CONFIG
    dest.parent.mkdir(parents=True)
    dest.write_text("rules: {}\n")
    with pytest.raises(SystemExit):
        _write_aislop_config(repo)
    assert dest.read_text() == "rules: {}\n"


def test_install_pr_template_refuses_overwrite(tmp_path: pathlib.Path) -> None:
    repo = _git_repo(tmp_path)
    dest = repo / ".github" / PR_TEMPLATE
    dest.parent.mkdir(parents=True)
    dest.write_text("existing repo-owned template\n")
    with pytest.raises(SystemExit):
        _write_pr_template(repo)
    assert dest.read_text() == "existing repo-owned template\n"


def test_install_writes_trigger_workflows(tmp_path: pathlib.Path) -> None:
    repo = _git_repo(tmp_path)
    _write_trigger_workflows(repo, "bun")
    wf = repo / ".github" / "workflows"
    assert sorted(p.name for p in wf.iterdir()) == sorted([PR_WORKFLOW, AMBIENT_WORKFLOW])
    pr = (wf / PR_WORKFLOW).read_text()
    jobs = yaml.safe_load(pr)["jobs"]
    assert set(jobs) == {"qc-ci", "deterministic-diff", "delegation-conformance", "qc-doctor", "pr-description-checklist"}
    assert all(job["uses"].startswith("dzackgarza/ai-review-ci/.github/workflows/") for job in jobs.values())
    assert all("needs" not in job for job in jobs.values())
    assert "uses: dzackgarza/ai-review-ci/.github/workflows/_qc.yml@main" in pr
    assert "tier: test-ci" in pr
    assert "enforcement: all" in pr
    assert "gate: deterministic-diff" in pr
    assert "gate: delegation-conformance" in pr
    assert "gate: qc-doctor" in pr
    assert "gate: app-boot" not in pr
    assert "profile: 'bun'" in pr
    assert "fail_below" not in pr
    assert "pull_request" in pr


@pytest.mark.parametrize("profile", ["python", "bun", "bun-playwright", "bun-python", "rust", "sage"])
def test_install_writes_scheduled_ambient_workflow(tmp_path: pathlib.Path, profile: str) -> None:
    repo = _git_repo(tmp_path)
    _write_trigger_workflows(repo, profile)

    ambient = yaml.safe_load((repo / ".github" / "workflows" / AMBIENT_WORKFLOW).read_text())
    triggers = ambient[True]
    assert [entry["cron"] for entry in triggers["schedule"]]
    assert "pull_request" not in triggers and "push" not in triggers
    (job,) = ambient["jobs"].values()
    assert job["uses"] == "dzackgarza/ai-review-ci/.github/workflows/_qc.yml@main"
    assert job["with"] == {"tier": "ambient", "profile": profile, "infra_ref": "main"}


def test_install_writes_no_ambient_workflow_for_docs_and_configs(tmp_path: pathlib.Path) -> None:
    repo = _git_repo(tmp_path)
    _write_trigger_workflows(repo, "docs-and-configs")

    assert [p.name for p in (repo / ".github" / "workflows").iterdir()] == [PR_WORKFLOW]


@pytest.mark.parametrize("profile", ["python", "bun", "bun-playwright", "bun-python", "rust", "sage"])
def test_repo_and_packaged_scaffolds_are_identical(profile: str) -> None:
    repo_scaffold = (ROOT / "scaffolds" / profile / "justfile").read_text()
    packaged_scaffold = (ROOT / "src" / "ai_review_ci" / "scaffolds" / profile / "justfile").read_text()

    assert repo_scaffold == packaged_scaffold


def test_install_writes_bun_playwright_app_boot_gate(tmp_path: pathlib.Path) -> None:
    repo = _git_repo(tmp_path)
    _write_trigger_workflows(repo, "bun-playwright")

    pr = (repo / ".github" / "workflows" / "review-pr.yml").read_text()
    assert "gate: app-boot" in pr
    assert "profile: 'bun-playwright'" in pr


def test_install_writes_justfile_contract_variables(tmp_path: pathlib.Path) -> None:
    repo = _git_repo(tmp_path)

    _write_scaffold(repo, "python", branch="trunk", ref="release/v1", release_channel="stable")

    justfile = (repo / "justfile").read_text()
    assert 'ai_review_ci_schema_version := "1"' in justfile
    assert 'ai_review_ci_profile := "python"' in justfile
    assert 'ai_review_ci_ref := "release/v1"' in justfile
    assert 'ai_review_ci_release_channel := "stable"' in justfile
    assert 'ai_review_ci_workflow_template_version := "1"' in justfile
    assert 'ai_review_ci_local_delegation := "global-justfile"' in justfile
    assert 'ai_review_ci_default_branch := "trunk"' in justfile


def test_install_writes_profile_scaffold(tmp_path: pathlib.Path) -> None:
    repo = _git_repo(tmp_path)

    _write_scaffold(repo, "rust")

    assert (repo / "justfile").read_text() == (ROOT / "scaffolds" / "rust" / "justfile").read_text()


def test_install_local_files_finalize_with_doctor(tmp_path: pathlib.Path) -> None:
    repo = _git_repo(tmp_path)
    (repo / "pyproject.toml").write_text('[project]\nname = "target"\nversion = "0.1.0"\n')
    _write_scaffold(repo, "python")
    _write_trigger_workflows(repo, "python")
    _prove_installation(repo)

    assert (repo / "justfile").read_text() == (ROOT / "scaffolds" / "python" / "justfile").read_text()


def test_default_install_is_push_diagnostics_without_pr_protection(tmp_path: pathlib.Path) -> None:
    repo = _git_repo(tmp_path)
    (repo / "pyproject.toml").write_text('[project]\\nname = "target"\\nversion = "0.1.0"\\n')

    result = _run_cli_install(repo)

    assert result.returncode == 0, result.stdout + result.stderr
    workflows = repo / ".github" / "workflows"
    assert (workflows / "development.yml").is_file()
    assert not (workflows / "review-pr.yml").exists()
    assert not (repo / ".github" / PR_TEMPLATE).exists()
    assert "No PR review or branch protection installed." in result.stdout
    data = yaml.safe_load((workflows / "development.yml").read_text())
    assert "push" in data[True] and "pull_request" not in data[True]
    assert list(data["jobs"]) == ["qc-ci"]
    from ai_review_ci.doctor import doctor_report
    report = doctor_report(repo)
    assert report.global_status == "current"
    assert report.branch_protection.observed_state == "not_applicable"
    assert report.label_alignment.observed_state == "not_applicable"


def test_cli_install_uses_real_gh_and_fails_before_final_doctor_for_unavailable_branch_target(
    tmp_path: pathlib.Path,
) -> None:
    repo = _git_repo(tmp_path)
    (repo / "pyproject.toml").write_text('[project]\nname = "target"\nversion = "0.1.0"\n')

    result = _run_cli_install(repo, phase="stabilized")

    assert result.returncode == 1
    assert "FATAL: gh api --method PUT failed:" in result.stderr
    assert (repo / "justfile").read_text() == (ROOT / "scaffolds" / "python" / "justfile").read_text()
    assert (repo / ".github" / "workflows" / "review-pr.yml").exists()
    assert not (repo / ".ai-review-ci.toml").exists()
    assert "doctor final proof" not in result.stdout
    assert "\nDone." not in result.stdout


def test_install_final_doctor_rejects_target_without_profile_shape(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _git_repo(tmp_path)
    _write_scaffold(repo, "python")
    _write_trigger_workflows(repo, "python")

    with pytest.raises(SystemExit):
        _prove_installation(repo)

    assert "FATAL: ai-review-ci doctor final proof failed with status misconfigured" in capsys.readouterr().err


def test_install_final_doctor_rejects_broken_local_delegation(
    tmp_path: pathlib.Path,
) -> None:
    repo = _git_repo(tmp_path)
    (repo / "pyproject.toml").write_text('[project]\nname = "target"\nversion = "0.1.0"\n')
    (repo / "justfile").write_text(
        "\n".join(
            [
                "# broken local delegation.",
                'ai_review_ci_schema_version := "1"',
                'ai_review_ci_profile := "python"',
                'ai_review_ci_ref := "main"',
                'ai_review_ci_release_channel := "main"',
                'ai_review_ci_workflow_template_version := "1"',
                'ai_review_ci_local_delegation := "global-justfile"',
                'ai_review_ci_default_branch := "main"',
                "",
                "# Broken commit gate.",
                "test-commit:",
                "    @true",
                "",
                "# Broken push gate.",
                "test-push:",
                "    @true",
                "",
                "# Broken CI gate.",
                "test-ci:",
                "    @true",
                "",
            ]
        )
    )
    _write_trigger_workflows(repo, "python")

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
    customized = repo / ".github" / "workflows" / PR_WORKFLOW
    customized.write_text("# locally customized\n")
    with pytest.raises(SystemExit):
        _write_trigger_workflows(repo, "bun")
    assert customized.read_text() == "# locally customized\n"


@pytest.mark.parametrize("workflow_file", ["_qc.yml", "_gates.yml"])
def test_reusable_workflows_use_maintained_just_installer(workflow_file: str) -> None:
    """Regression guard for #129.

    The reusable workflows must not use the old anonymous
    `releases/latest | tar` installer. The maintained setup action exposes an
    explicit token input; wiring it in the workflow keeps the install path
    authenticated instead of relying on unauthenticated GitHub API calls.
    """
    text = (_WORKFLOWS_DIR / workflow_file).read_text()
    assert "https://api.github.com/repos/casey/just/releases/latest" not in text
    assert "tar -xzf" not in text
    assert "VERSION=$(curl -sL" not in text


@pytest.mark.parametrize(
    "workflow_file,job_name",
    [(wf, job) for wf in ("_qc.yml", "_gates.yml") for job in _workflow_jobs(wf)],
)
def test_reusable_workflow_just_installs_via_setup_action(workflow_file: str, job_name: str) -> None:
    """Every job's Install just step uses extractions/setup-just@v4 with a token."""
    job = _workflow_jobs(workflow_file)[job_name]
    steps = job.get("steps")
    assert isinstance(steps, list), f"{workflow_file} job {job_name!r} has no steps"
    install_steps = [step for step in steps if isinstance(step, dict) and step.get("name") == "Install just"]
    assert install_steps, f"{workflow_file} job {job_name!r} has no Install just step"
    for step in install_steps:
        assert step.get("uses") == "extractions/setup-just@v4"
        assert step.get("with", {}).get("github-token") == "${{ github.token }}"
        assert "env" not in step


def test_gates_qc_doctor_grants_labels_read_scope() -> None:
    """Regression guard for #224.

    doctor's REQUIRED label-alignment check reads the repo's live labels with
    `gh label list` -> GET /repos/{owner}/{repo}/labels. Per GitHub's
    fine-grained-PAT permissions reference that endpoint requires the "Issues"
    repository permission (read). The Actions GITHUB_TOKEN defaults unset scopes
    to none, so without `issues: read` the check cannot read labels on a
    correctly-labeled repo, resolves `unverifiable`, and fails the qc-doctor
    gate — a false-RED. The callee job that runs the gate must grant the scope.
    """
    perms = _workflow_jobs("_gates.yml")["qc-doctor"].get("permissions")
    assert isinstance(perms, dict), "qc-doctor job must declare least-privilege permissions"
    assert perms.get("issues") == "read", f"qc-doctor job must grant issues: read so the label-alignment check's `gh label list` call is verifiable; got permissions={perms!r}"
    assert "write" not in perms.values()


@pytest.mark.parametrize("profile", SUPPORTED_PROFILES)
def test_rendered_pr_qc_doctor_grants_labels_read_scope(profile: str) -> None:
    """Regression guard for #224 (caller side).

    A reusable-workflow token is capped by the caller job's `permissions`, so
    `issues: read` on the callee (_gates.yml) alone is not enough — every
    rendered `review-pr.yml` caller must also grant it, or the intersection
    strips the scope and the qc-doctor label check false-REDs.
    """
    workflow = yaml.safe_load(_template_text(profile, "main"))
    perms = workflow["jobs"]["qc-doctor"].get("permissions")
    assert isinstance(perms, dict), f"review-pr.yml (profile={profile}) qc-doctor job must declare permissions"
    assert perms.get("issues") == "read", f"review-pr.yml (profile={profile}) qc-doctor caller must grant issues: read; got {perms!r}"
    assert "write" not in perms.values()


def test_install_refuses_overwriting_repo_owned_scaffold(
    tmp_path: pathlib.Path,
) -> None:
    repo = _git_repo(tmp_path)
    customized = repo / "justfile"
    customized.write_text("test:\n    @true\n")

    with pytest.raises(SystemExit):
        _write_scaffold(repo, "python")

    assert customized.read_text() == "test:\n    @true\n"


def test_skip_scaffold_final_proof_adopts_brownfield_non_delegating_justfile(
    tmp_path: pathlib.Path,
) -> None:
    repo = _git_repo(tmp_path)
    (repo / "pyproject.toml").write_text('[project]\nname = "target"\nversion = "0.1.0"\n')
    existing = repo / "justfile"
    brownfield_justfile = "# pre-existing brownfield justfile\ntest:\n    @true\n"
    existing.write_text(brownfield_justfile)
    _write_trigger_workflows(repo, "python")
    _write_pr_template(repo)
    _prove_installation(repo, skip_scaffold=True)

    assert existing.read_text() == brownfield_justfile
    assert not (repo / ".ai-review-ci.toml").exists()
    assert (repo / ".github" / "workflows" / PR_WORKFLOW).is_file()


def test_skip_scaffold_final_proof_still_aborts_on_non_justfile_fault(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _git_repo(tmp_path)
    (repo / "pyproject.toml").write_text('[project]\nname = "target"\nversion = "0.1.0"\n')
    (repo / "justfile").write_text("# pre-existing brownfield justfile\ntest:\n    @true\n")

    with pytest.raises(SystemExit):
        _prove_installation(repo, skip_scaffold=True)

    err = capsys.readouterr().err
    assert "FATAL: ai-review-ci doctor final proof failed" in err
    assert "workflow" in err


def test_cli_install_skip_scaffold_bypasses_scaffold_overwrite_guard(
    tmp_path: pathlib.Path,
) -> None:
    repo = _git_repo(tmp_path)
    (repo / "pyproject.toml").write_text('[project]\nname = "target"\nversion = "0.1.0"\n')
    existing = repo / "justfile"
    existing.write_text("# pre-existing brownfield justfile\ntest-commit:\n    @true\n")

    result = _run_cli_install(repo, skip_scaffold=True, phase="stabilized")

    combined = result.stdout + result.stderr
    assert "refusing to overwrite existing scaffold" not in combined, combined
    assert result.returncode == 1, combined
    assert "FATAL: gh api --method PUT failed:" in result.stderr, combined
    assert existing.read_text() == "# pre-existing brownfield justfile\ntest-commit:\n    @true\n"
    assert not (repo / ".ai-review-ci.toml").exists()
    assert (repo / ".github" / "workflows" / "review-pr.yml").exists()


def test_cli_install_without_skip_scaffold_still_refuses_existing_justfile(
    tmp_path: pathlib.Path,
) -> None:
    repo = _git_repo(tmp_path)
    (repo / "justfile").write_text("test-commit:\n    @true\n")

    result = _run_cli_install(repo)

    assert result.returncode == 1
    assert "refusing to overwrite existing scaffold" in result.stderr
    assert not (repo / ".ai-review-ci.toml").exists()


def test_qc_workflow_declares_gh_boundary_opt_in_disabled_by_default() -> None:
    data = yaml.safe_load((_WORKFLOWS_DIR / "_qc.yml").read_text())
    on_block = data.get("on", data.get(True)) or {}
    boundary_input = on_block["workflow_call"]["inputs"]["run_gh_boundary"]

    assert boundary_input == {
        "description": "Run this repository's real GitHub API tests marked pytest.mark.gh_boundary in an isolated token-scoped step",
        "required": False,
        "type": "boolean",
        "default": False,
    }


def test_qc_tier_step_does_not_export_gh_token_tier_wide() -> None:
    data = yaml.safe_load((_WORKFLOWS_DIR / "_qc.yml").read_text())
    job = data["jobs"]["qc"]
    assert "GH_TOKEN" not in (job.get("env") or {})
    tier = next(step for step in job["steps"] if isinstance(step, dict) and step.get("name") == "Run QC tier")
    assert "GH_TOKEN" not in (tier.get("env") or {})


def test_qc_workflow_installs_flowmark_runtime_dependencies() -> None:
    job = _workflow_jobs("_qc.yml")["qc"]
    install_index = next(index for index, step in enumerate(job["steps"]) if isinstance(step, dict) and step.get("name") == "Install QC system packages")
    install = job["steps"][install_index]
    run_index = next(index for index, step in enumerate(job["steps"]) if isinstance(step, dict) and step.get("name") == "Run QC tier")

    assert install_index < run_index
    assert isinstance(install, dict)
    assert "sudo apt-get update && sudo apt-get install -y pandoc ripgrep" in install["run"]


def test_qc_workflow_installs_project_profile_before_running_acceptance() -> None:
    job = _workflow_jobs("_qc.yml")["qc"]
    install_index = next(index for index, step in enumerate(job["steps"]) if isinstance(step, dict) and step.get("name") == "Install project dependencies")
    run_index = next(index for index, step in enumerate(job["steps"]) if isinstance(step, dict) and step.get("name") == "Run QC tier")
    install = job["steps"][install_index]["run"]

    assert install_index < run_index
    assert install == ('just -f "$HOME/ai-review-ci/ci/runner.just" setup-profile "$QC_PROFILE"')


def test_sage_ci_runs_the_setup_recipe_in_the_published_runtime() -> None:
    job = _workflow_jobs("_qc.yml")["qc"]
    assert job["container"] == "${{ inputs.profile == 'sage' && inputs.tier == 'test-ci' && 'ghcr.io/dzackgarza/sage:develop' || '' }}"
    assert job["defaults"]["run"]["shell"] == "bash"

    names = [step.get("name") for step in job["steps"]]
    node = job["steps"][names.index("Install node in the job container")]
    assert node["uses"].startswith("actions/setup-node@")
    assert node["if"] == "job.container.id != ''"
    assert names.index("Install bun") < names.index("Provision project CI environment")
    assert names.index("Install node in the job container") < names.index("Provision project CI environment")


def test_sage_ambient_does_not_require_project_dependencies() -> None:
    job = _workflow_jobs("_qc.yml")["qc"]
    install = next(step for step in job["steps"] if step.get("name") == "Install project dependencies")
    assert install["if"] == "inputs.tier != 'ambient' || inputs.profile != 'sage'"
    tier = next(step for step in job["steps"] if step.get("name") == "Run QC tier")
    assert "if" not in tier


def test_qc_workflow_runs_validated_project_setup_before_acceptance() -> None:
    data = yaml.safe_load((_WORKFLOWS_DIR / "_qc.yml").read_text())
    on_block = data.get("on", data.get(True)) or {}
    setup_input = on_block["workflow_call"]["inputs"]["setup_recipe"]
    job = data["jobs"]["qc"]
    validation = next(step for step in job["steps"] if step.get("name") == "Validate inputs")
    setup_index = next(index for index, step in enumerate(job["steps"]) if step.get("name") == "Provision project CI environment")
    run_index = next(index for index, step in enumerate(job["steps"]) if step.get("name") == "Run QC tier")
    setup = job["steps"][setup_index]

    assert setup_input == {
        "description": "Optional caller-owned just recipe that provisions domain-specific CI dependencies",
        "required": False,
        "type": "string",
        "default": "",
    }
    assert "[^A-Za-z0-9_-]" in validation["run"]
    assert setup_index < run_index
    assert setup["if"] == "inputs.setup_recipe != ''"
    assert setup["run"] == 'just "$QC_SETUP_RECIPE"'


def test_qc_workflow_caches_project_setup_around_the_recipe(tmp_path: pathlib.Path) -> None:
    job = _workflow_jobs("_qc.yml")["qc"]
    names = [step.get("name") for step in job["steps"]]
    key_step = job["steps"][names.index("Key the project CI environment cache")]
    restore = job["steps"][names.index("Restore the project CI environment")]
    save = job["steps"][names.index("Save the project CI environment")]

    assert names.index("Restore the project CI environment") < names.index("Provision project CI environment")
    assert names.index("Provision project CI environment") < names.index("Save the project CI environment")
    assert names.index("Save the project CI environment") < names.index("Run QC tier")
    for step in (key_step, restore):
        assert step["if"] == "inputs.setup_cache_paths != ''"
    assert save["if"] == "inputs.setup_cache_paths != '' && steps.setup-cache.outputs.cache-hit != 'true'"
    assert restore["with"] == save["with"]

    (tmp_path / "setup.sh").write_text("install v1\n")
    (tmp_path / "pins.json").write_text("{}\n")

    def cache_key() -> str:
        output = tmp_path / "github-output"
        output.write_text("")
        env = {
            "PATH": "/usr/bin:/bin",
            "RUNNER_OS": "Linux",
            "QC_SETUP_RECIPE": "setup-ci",
            "QC_SETUP_CACHE_KEY_FILES": "setup.sh\npins.json\n",
            "QC_SETUP_CACHE_PERIOD": "",
            "GITHUB_OUTPUT": str(output),
        }
        subprocess.run(["bash", "-euo", "pipefail", "-c", key_step["run"]], cwd=tmp_path, env=env, check=True)
        return output.read_text().removeprefix("key=").strip()

    first = cache_key()
    assert first.startswith("qc-setup-Linux-setup-ci-")
    assert cache_key() == first
    (tmp_path / "setup.sh").write_text("install v2\n")
    assert cache_key() != first


def test_qc_workflow_setup_cache_follows_the_period_of_a_rolling_source(tmp_path: pathlib.Path) -> None:
    job = _workflow_jobs("_qc.yml")["qc"]
    key_step = next(step for step in job["steps"] if step.get("name") == "Key the project CI environment cache")
    validation = next(step for step in job["steps"] if step.get("name") == "Validate inputs")
    (tmp_path / "setup.sh").write_text("install v1\n")

    def run_step(script: str, period: str) -> subprocess.CompletedProcess[str]:
        output = tmp_path / "github-output"
        output.write_text("")
        env = {
            "PATH": "/usr/bin:/bin",
            "RUNNER_OS": "Linux",
            "QC_TIER": "test-ci",
            "QC_PROFILE": "bun",
            "QC_ENFORCEMENT": "none",
            "QC_INFRA_REF": "main",
            "QC_SETUP_RECIPE": "setup-ci",
            "QC_SETUP_CACHE_PATHS": "~/texlive\n",
            "QC_SETUP_CACHE_KEY_FILES": "setup.sh\n",
            "QC_SETUP_CACHE_PERIOD": period,
            "GITHUB_OUTPUT": str(output),
        }
        return subprocess.run(["bash", "-euo", "pipefail", "-c", script], cwd=tmp_path, env=env, capture_output=True, text=True)

    def cache_key(period: str) -> str:
        run_step(key_step["run"], period).check_returncode()
        return (tmp_path / "github-output").read_text().removeprefix("key=").strip()

    year, week, _ = datetime.datetime.now(datetime.UTC).isocalendar()
    without_period = cache_key("")
    weekly = cache_key("iso-week")
    assert weekly == without_period.replace("-setup-ci-", f"-setup-ci-{year}-W{week:02d}-", 1)
    assert run_step(validation["run"], "iso-week").returncode == 0
    refused = run_step(validation["run"], "daily")
    assert refused.returncode == 1
    assert "invalid setup_cache_period: daily" in refused.stderr


def test_qc_workflow_accepts_only_remote_acceptance_tiers() -> None:
    job = _workflow_jobs("_qc.yml")["qc"]
    validation = next(step for step in job["steps"] if isinstance(step, dict) and step.get("name") == "Validate inputs")

    assert "test-ci|ambient" in validation["run"]
    assert "test|test-ci|ambient" not in validation["run"]


def test_qc_scopes_gh_token_to_explicitly_opted_in_gh_boundary_step() -> None:
    job = _workflow_jobs("_qc.yml")["qc"]
    token_steps = [step for step in job["steps"] if isinstance(step, dict) and (step.get("env") or {}).get("GH_TOKEN") == "${{ github.token }}"]
    assert len(token_steps) == 1, token_steps
    step = token_steps[0]
    run = step.get("run", "")
    assert 'just -f "$HOME/ai-review-ci/justfiles/python.just" -d . test-gh-boundary' == run
    assert '"$QC_TIER"' not in run
    assert step["if"] == "inputs.run_gh_boundary"


def test_qc_tier_provisions_the_scratch_directory_declared_by_the_consumer(tmp_path: pathlib.Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    scratch = consumer / "scratch"
    (consumer / ".envrc").write_text('source_up\nexport TMPDIR="$PWD/scratch"\n')
    (consumer / "justfile").write_text("ambient:\n    mktemp > created-path\n")
    job = _workflow_jobs("_qc.yml")["qc"]
    step = next(step for step in job["steps"] if step.get("name") == "Run QC tier")
    result = subprocess.run(["bash", "-e", "-c", step["run"]], cwd=consumer, env=os.environ | {"HOME": str(home), "QC_TIER": "ambient"}, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    created = pathlib.Path((consumer / "created-path").read_text().strip())
    assert created.parent == scratch
    assert created.is_file()


@pytest.mark.parametrize("workflow", ["_qc.yml", "_gates.yml", "_acceptance.yml"])
def test_reusable_workflows_pin_the_just_release(workflow: str) -> None:
    """An empty version specifier can make setup-just fail before CI runs."""
    jobs = _workflow_jobs(workflow)
    installers = [
        step for job in jobs.values() for step in job.get("steps", [])
        if step.get("uses") == "extractions/setup-just@v4"
    ]
    assert installers
    assert all(step["with"]["just-version"] == "1.59.0" for step in installers)



def test_qc_push_diff_uses_previous_commit_and_branch_scoped_debt(tmp_path: pathlib.Path) -> None:
    workflow = yaml.safe_load((_WORKFLOWS_DIR / "_qc.yml").read_text())
    job = workflow["jobs"]["qc"]
    assert "github.event.before" in job["env"]["DIFF_COVER_BASE"]
    steps = job["steps"]
    restore = next(step for step in steps if step.get("name") == "Restore prior branch diagnostic snapshot")
    save = next(step for step in steps if step.get("name") == "Cache branch diagnostic snapshot")
    assert "github.ref" in restore["with"]["key"]
    assert "github.ref" in restore["with"]["restore-keys"]
    assert restore["with"]["key"] == save["with"]["key"]
    resolver = next(step for step in steps if step.get("name") == "Resolve diff base on first branch push")
    script = resolver["run"].replace("${{ github.event.repository.default_branch }}", "main")

    repo = tmp_path / "repository"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    (repo / "tracked").write_text("base")
    subprocess.run(["git", "add", "tracked"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                    "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "base"],
                   cwd=repo, check=True)
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    subprocess.run(["git", "remote", "add", "origin", str(origin)], cwd=repo, check=True)
    subprocess.run(["git", "push", "-q", "origin", "main"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "feature"], cwd=repo, check=True)
    (repo / "tracked").write_text("feature")
    subprocess.run(["git", "add", "tracked"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                    "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "feature"],
                   cwd=repo, check=True)
    output = tmp_path / "github-env"
    output.write_text("")
    env = os.environ | {
        "DIFF_COVER_BASE": "0" * 40,
        "GITHUB_ENV": str(output),
        "GITHUB_WORKSPACE": str(repo),
        "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig"),
    }
    result = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", script],
                            cwd=repo, env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert output.read_text().strip() == f"DIFF_COVER_BASE={base}"
    output.write_text("")
    env["DIFF_COVER_BASE"] = base
    result = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", script],
                            cwd=repo, env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert output.read_text() == ""


@pytest.mark.parametrize("profile", ["python", "sage"])
def test_qc_retains_pytest_history_after_all_test_steps(profile: str) -> None:
    steps = _workflow_jobs("_qc.yml")["qc"]["steps"]
    upload = next(step for step in steps if step.get("name") == f"Retain {profile} pytest history")
    assert steps.index(upload) > next(i for i, step in enumerate(steps) if step.get("name") == "Run gh-boundary tests")
    assert upload["if"] == "always()"
    assert upload["uses"].startswith("actions/upload-artifact@")
    assert upload["with"] == {
        "name": "${{ github.run_id }}-${{ github.run_attempt }}-${{ inputs.tier }}-${{ inputs.profile }}-" + profile + "-pytest-history",
        "path": f".ai-review-ci/{profile}/pytest-history/*.jsonl",
        "include-hidden-files": True,
        "if-no-files-found": "ignore",
        "retention-days": 90,
    }


def test_acceptance_retains_each_shards_pytest_history_separately() -> None:
    jobs = _workflow_jobs("_acceptance.yml")
    steps = jobs["shard"]["steps"]
    upload = next(step for step in steps if step.get("name") == "Retain Sage pytest history")
    assert steps.index(upload) > next(i for i, step in enumerate(steps) if step.get("name") == "Run the shard")
    assert upload["if"] == "always()"
    assert upload["uses"].startswith("actions/upload-artifact@")
    assert upload["with"] == {
        "name": "${{ github.run_id }}-${{ github.run_attempt }}-sage-pytest-history-${{ matrix.name }}-${{ matrix.shard }}",
        "path": ".ai-review-ci/sage/pytest-history/*.jsonl",
        "include-hidden-files": True,
        "if-no-files-found": "ignore",
        "retention-days": 90,
    }
    download = next(step for step in jobs["summary"]["steps"] if step.get("uses", "").startswith("actions/download-artifact@"))
    assert download["with"]["pattern"] == "acceptance-*"
