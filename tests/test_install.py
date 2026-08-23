import pathlib
import subprocess
import sys
from typing import Any

import pytest
import yaml
from automated_reviews.publication import WORKFLOW_NAMES

from ai_review_ci.doctor import _review_guidelines_findings
from ai_review_ci.gates import POLICY_GATE_MARKER, SUPPORTED_PROFILES
from ai_review_ci.install import (
    AISLOP_CONFIG,
    PR_TEMPLATE,
    _prove_installation,
    _template_text,
    _write_aislop_config,
    _write_pr_template,
    _write_review_guidelines,
    _write_scaffold,
    _write_trigger_workflows,
)
from ai_review_ci.review_guidelines import (
    classify_review_guidelines,
    extract_review_guidelines_sections,
    load_canonical_review_guidelines,
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
    # The distributed template carries the marker, which is what opts the target
    # repo into check_pr_description marker enforcement (#154).
    text = dest.read_text(encoding="utf-8")
    assert POLICY_GATE_MARKER in text
    assert "## Issue-scoped lifecycle gate — required" in text
    assert "Linked triaged issue(s)" in text
    assert "started as a draft" in text
    assert "Ready-for-review was requested only after" in text
    assert "every resolved substantive item carries its own evidenced disposition" in text


def test_install_writes_canonical_aislop_config(tmp_path: pathlib.Path) -> None:
    # #228: aislop has no --config flag — it reads .aislop/config.yml from the
    # scanned directory root — so the uniform central policy governs a repo only
    # if install physically lands this file in it. Run the real writer against a
    # real tmp target and assert the config lands with python-print-debug
    # disabled (the owner-policy payload). Real file boundary, no mock.
    repo = _git_repo(tmp_path)
    _write_aislop_config(repo)
    dest = repo / AISLOP_CONFIG
    assert dest.is_file()
    config = yaml.safe_load(dest.read_text())
    assert config["rules"]["ai-slop/python-print-debug"] == "off"
    # No per-repo threshold / opt-in: it is the uniform central standard.
    assert "failBelow" not in (config.get("ci") or {})


def test_distributed_aislop_config_matches_repo_own_config() -> None:
    # #228: the config install distributes MUST be identical to the one governing
    # ai-review-ci's own scan — otherwise the fleet standard and the head repo's
    # own gate silently diverge (the false-green class the review-guidelines gate
    # guards against). The packaged canonical is the single source; the repo-root
    # copy that aislop reads for the self-scan must stay byte-identical to it.
    packaged = (ROOT / "src" / "ai_review_ci" / "data" / "aislop-config.yml").read_text()
    repo_own = (ROOT / ".aislop" / "config.yml").read_text()
    assert repo_own == packaged
    # And the comment must not still claim the config is undistributed (#205 was
    # reversed by #228); the stale claim would be an outright false statement.
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
    assert sorted(p.name for p in wf.iterdir()) == sorted(WORKFLOW_NAMES)
    for name in WORKFLOW_NAMES:
        text = (wf / name).read_text()
        assert "uses: dzackgarza/automated-reviews/.github/workflows/_review.yml@main" in text
    sweep = (wf / "review-slop.yml").read_text()
    assert "report_type: slop" in sweep
    assert "scope: repo" in sweep
    pr = (wf / "review-pr.yml").read_text()
    assert "uses: dzackgarza/ai-review-ci/.github/workflows/_qc.yml@main" in pr
    assert "tier: test-ci" in pr
    assert "scope: diff" in pr
    assert "gate: deterministic-diff" in pr
    assert "gate: delegation-conformance" in pr
    assert "gate: qc-doctor" in pr
    assert "gate: app-boot" not in pr
    assert "gate: thread-resolution" in pr
    assert "profile: 'bun'" in pr
    assert "fail_below" not in pr
    assert "pull_request" in pr


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


def test_install_review_guidelines_creates_passing_section_without_existing_agents_md(
    tmp_path: pathlib.Path,
) -> None:
    # #232: a repo with no AGENTS.md must not fail its own review-guidelines gate after
    # install. The writer creates the file; the REAL doctor gate must then pass.
    repo = _git_repo(tmp_path)
    assert not (repo / "AGENTS.md").exists()

    _write_review_guidelines(repo)

    assert _review_guidelines_findings(repo) == []
    assert len(extract_review_guidelines_sections((repo / "AGENTS.md").read_text())) == 1


def test_install_review_guidelines_upserts_into_existing_agents_md_without_clobbering(
    tmp_path: pathlib.Path,
) -> None:
    # #232: an existing AGENTS.md (here carrying unrelated content plus a STALE section)
    # must keep its other content and get the section refreshed to current — proven at the
    # real doctor boundary, not by string-matching the writer's own output.
    repo = _git_repo(tmp_path)
    (repo / "AGENTS.md").write_text("# Project\n\nKeep me.\n\n# Review Guidelines\n\nold stale guidance\n\n# Conventions\n\nAlso keep me.\n")

    _write_review_guidelines(repo)

    text = (repo / "AGENTS.md").read_text()
    assert "Keep me." in text
    assert "Also keep me." in text
    assert "old stale guidance" not in text
    assert len(extract_review_guidelines_sections(text)) == 1
    assert _review_guidelines_findings(repo) == []


def test_install_review_guidelines_is_idempotent(tmp_path: pathlib.Path) -> None:
    # #232 acceptance: re-running install neither duplicates nor drifts the section.
    repo = _git_repo(tmp_path)
    _write_review_guidelines(repo)
    first = (repo / "AGENTS.md").read_text()

    _write_review_guidelines(repo)
    second = (repo / "AGENTS.md").read_text()

    assert first == second
    assert len(extract_review_guidelines_sections(second)) == 1
    assert classify_review_guidelines(second, load_canonical_review_guidelines()).state == "current"
    assert _review_guidelines_findings(repo) == []


def test_install_local_files_finalize_with_doctor(tmp_path: pathlib.Path) -> None:
    repo = _git_repo(tmp_path)
    (repo / "pyproject.toml").write_text('[project]\nname = "target"\nversion = "0.1.0"\n')
    # The final doctor proof now requires a current review-guidelines section, so a
    # conformant target carries one before finalize (the gate the doctor enforces).
    (repo / "AGENTS.md").write_text(f"# target\n\nIntro.\n\n{load_canonical_review_guidelines()}\n")

    _write_scaffold(repo, "python")
    _write_trigger_workflows(repo, "python")
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
    customized = repo / ".github" / "workflows" / "review-slop.yml"
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


def test_thread_resolution_checks_out_target_repository() -> None:
    job = _workflow_jobs("_gates.yml")["thread-resolution"]
    steps = job.get("steps")

    assert isinstance(steps, list)
    assert any(
        isinstance(step, dict) and step.get("uses") == "actions/checkout@v4"
        for step in steps
    )


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
    # Least privilege: read scope only, never widened to write.
    assert "write" not in perms.values()


@pytest.mark.parametrize("profile", SUPPORTED_PROFILES)
def test_rendered_pr_qc_doctor_grants_labels_read_scope(profile: str) -> None:
    """Regression guard for #224 (caller side).

    A reusable-workflow token is capped by the caller job's `permissions`, so
    `issues: read` on the callee (_gates.yml) alone is not enough — every
    rendered `review-pr.yml` caller must also grant it, or the intersection
    strips the scope and the qc-doctor label check false-REDs.
    """
    workflow = yaml.safe_load(_template_text("review-pr.yml", profile, "main"))
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
    # Brownfield adoption (#202): a repo that predates ai-review-ci owns a
    # substantive, non-delegating top-level justfile. Under --skip-scaffold the
    # installer writes the triggers and PR template and leaves the
    # justfile untouched — justfile delegation/conformance convergence is
    # deferred to a `doctor` finding by design. The final proof step must
    # therefore reach SUCCESS on exactly this intended-success state: everything
    # ai-review-ci installs is present, and the ONLY outstanding doctor findings
    # are the deferred justfile delegation/conformance ones.
    #
    # Regression guard: before the fix the proof step ran doctor and hard-exited
    # on doctor's (by-design) `misconfigured` status, so a fully-adopted repo
    # reported install failure on the very case --skip-scaffold exists to serve.
    # This exercises the real proof boundary (a real `doctor` run against the
    # installed file state) and reds if that abort regresses. It does NOT pass
    # via an earlier-boundary failure: it runs the proof step directly and
    # asserts it *returns*, then asserts the success end state.
    repo = _git_repo(tmp_path)
    (repo / "pyproject.toml").write_text('[project]\nname = "target"\nversion = "0.1.0"\n')
    existing = repo / "justfile"
    brownfield_justfile = "# pre-existing brownfield justfile\ntest:\n    @true\n"
    existing.write_text(brownfield_justfile)
    # Everything install writes under --skip-scaffold (the scaffold itself is skipped):
    _write_trigger_workflows(repo, "python")
    _write_pr_template(repo)
    # A conformant adopted repo carries the current review-guidelines section
    # (the doctor gate requires it; #232 tracks install writing it). Only the
    # justfile delegation/conformance findings then remain, deferred by design.
    (repo / "AGENTS.md").write_text(f"# target\n\nIntro.\n\n{load_canonical_review_guidelines()}\n")

    # Must NOT abort: the only outstanding doctor findings are the deferred
    # justfile delegation/conformance ones. A regressed (strict) proof step
    # raises SystemExit here.
    _prove_installation(repo, skip_scaffold=True)

    # Success end state: adoption completed and the brownfield justfile is intact.
    assert existing.read_text() == brownfield_justfile
    assert not (repo / ".ai-review-ci.toml").exists()
    for name in WORKFLOW_NAMES:
        assert (repo / ".github" / "workflows" / name).is_file()


def test_skip_scaffold_final_proof_still_aborts_on_non_justfile_fault(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Narrowness invariant (#202): --skip-scaffold defers ONLY justfile
    # delegation/conformance convergence. Every other doctor misconfiguration
    # must still make the final proof fail loud — the tolerance is not a blanket
    # "ignore doctor findings". Here the brownfield repo is missing the installed
    # trigger workflows (a `workflow`-surface fault, non-deferred), so even under
    # skip_scaffold the proof step must abort. A blanket-suppression regression
    # would let this pass; pytest.raises(SystemExit) reds on it.
    repo = _git_repo(tmp_path)
    (repo / "pyproject.toml").write_text('[project]\nname = "target"\nversion = "0.1.0"\n')
    (repo / "justfile").write_text("# pre-existing brownfield justfile\ntest:\n    @true\n")
    # Triggers deliberately NOT written: a genuine non-deferred fault remains.

    with pytest.raises(SystemExit):
        _prove_installation(repo, skip_scaffold=True)

    err = capsys.readouterr().err
    assert "FATAL: ai-review-ci doctor final proof failed" in err
    # The non-deferred fault is surfaced, not suppressed.
    assert "workflow" in err


def test_cli_install_skip_scaffold_bypasses_scaffold_overwrite_guard(
    tmp_path: pathlib.Path,
) -> None:
    # Brownfield guard-bypass (#202): --skip-scaffold is the explicit opt-in that
    # lets install proceed on a repo that already owns a top-level justfile
    # instead of hard-exiting at the scaffold-overwrite guard. This proves the
    # CLI threads the flag end to end: the scaffold guard does NOT fire, the
    # existing justfile is left untouched, and the triggers are written.
    # Full adoption completion is proven at the proof-step boundary by
    # test_skip_scaffold_final_proof_adopts_brownfield_non_delegating_justfile;
    # here execution reaches the real gh branch-protection boundary and fails
    # there only because the gh target repo is unavailable.
    repo = _git_repo(tmp_path)
    (repo / "pyproject.toml").write_text('[project]\nname = "target"\nversion = "0.1.0"\n')
    existing = repo / "justfile"
    existing.write_text("# pre-existing brownfield justfile\ntest-commit:\n    @true\n")

    result = _run_cli_install(repo, skip_scaffold=True)

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
    # Adoption is opt-in: the genuine unsafe-overwrite guard stays live. Without
    # --skip-scaffold a pre-existing justfile still hard-exits and nothing is
    # written (#202 keeps the honest refusal for the accidental case).
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
    # #218: GH_TOKEN must not sit on the whole "Run QC tier" step (nor the job
    # env it inherits), where every QC recipe and every npx/uvx tool runner
    # (semgrep, ai-slop, aislop) would execute with the token in its environment.
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
    assert install["run"] == "sudo apt-get update && sudo apt-get install -y pandoc ripgrep"


def test_qc_workflow_installs_project_profile_before_running_acceptance() -> None:
    job = _workflow_jobs("_qc.yml")["qc"]
    install_index = next(index for index, step in enumerate(job["steps"]) if isinstance(step, dict) and step.get("name") == "Install project dependencies")
    run_index = next(index for index, step in enumerate(job["steps"]) if isinstance(step, dict) and step.get("name") == "Run QC tier")
    install = job["steps"][install_index]["run"]

    assert install_index < run_index
    assert install == ('just -f "$HOME/ai-review-ci/ci/runner.just" setup-profile "$QC_PROFILE"')


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


def test_qc_workflow_accepts_only_remote_acceptance_tiers() -> None:
    job = _workflow_jobs("_qc.yml")["qc"]
    validation = next(step for step in job["steps"] if isinstance(step, dict) and step.get("name") == "Validate inputs")

    assert "test-ci|ambient" in validation["run"]
    assert "test|test-ci|ambient" not in validation["run"]


@pytest.mark.parametrize("profile", ["python", "bun-playwright"])
def test_pr_qc_and_reviews_start_in_parallel(profile: str) -> None:
    workflow = yaml.safe_load(_template_text("review-pr.yml", profile, "main"))
    jobs = workflow["jobs"]

    assert jobs["qc-ci"]["with"]["tier"] == "test-ci"
    assert "needs" not in jobs["qc-ci"]
    assert "needs" not in jobs["slop"]


def test_qc_scopes_gh_token_to_explicitly_opted_in_gh_boundary_step() -> None:
    # #218: only an explicit caller opt-in permits real-boundary GitHub tests to
    # receive the token, in their own step running the canonical Python profile
    # recipe — never the tier-wide `just "$QC_TIER"` run that drives third-party
    # tool runners.
    job = _workflow_jobs("_qc.yml")["qc"]
    token_steps = [step for step in job["steps"] if isinstance(step, dict) and (step.get("env") or {}).get("GH_TOKEN") == "${{ github.token }}"]
    assert len(token_steps) == 1, token_steps
    step = token_steps[0]
    run = step.get("run", "")
    assert 'just -f "$HOME/ai-review-ci/justfiles/python.just" -d . test-gh-boundary' == run
    assert '"$QC_TIER"' not in run
    assert step["if"] == "inputs.run_gh_boundary"
