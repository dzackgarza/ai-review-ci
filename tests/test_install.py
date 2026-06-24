import os
import pathlib
import subprocess
import sys

import pytest

from ai_review_ci.install import TEMPLATES, _prove_installation, _write_manifest, _write_scaffold, _write_trigger_workflows

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _git_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    return repo


def _write_gh_cli_fixture(tmp_path: pathlib.Path) -> pathlib.Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json",
                "import sys",
                "",
                "if sys.argv[1:4] == ['api', '--method', 'PUT']:",
                "    json.load(sys.stdin)",
                "    print('{}')",
                "else:",
                "    raise SystemExit(f'unsupported gh invocation: {sys.argv[1:]}')",
                "",
            ]
        )
    )
    gh.chmod(0o755)
    return bin_dir


def _run_cli_install(tmp_path: pathlib.Path, repo: pathlib.Path) -> subprocess.CompletedProcess[str]:
    env = os.environ | {"PATH": f"{_write_gh_cli_fixture(tmp_path)}:{os.environ['PATH']}"}
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "ai_review_ci.cli",
            "install",
            "--target",
            str(repo),
            "--repo",
            "owner/repo",
            "--branch",
            "main",
            "--profile",
            "python",
        ],
        text=True,
        capture_output=True,
        check=False,
        env=env,
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


def test_cli_install_writes_scaffold_and_finalizes_with_doctor(tmp_path: pathlib.Path) -> None:
    repo = _git_repo(tmp_path)
    (repo / "pyproject.toml").write_text('[project]\nname = "target"\nversion = "0.1.0"\n')

    result = _run_cli_install(tmp_path, repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (repo / "justfile").read_text() == (ROOT / "scaffolds" / "python" / "justfile").read_text()
    assert "doctor final proof: current" in result.stdout


def test_cli_install_fails_when_final_doctor_rejects_target(tmp_path: pathlib.Path) -> None:
    repo = _git_repo(tmp_path)

    result = _run_cli_install(tmp_path, repo)

    assert result.returncode == 1
    assert "FATAL: ai-review-ci doctor final proof failed with status misconfigured" in result.stderr
    assert "\nDone." not in result.stdout


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


def test_install_refuses_overwriting_repo_owned_scaffold(tmp_path: pathlib.Path) -> None:
    repo = _git_repo(tmp_path)
    customized = repo / "justfile"
    customized.write_text("test:\n    @true\n")

    with pytest.raises(SystemExit):
        _write_scaffold(repo, "python")

    assert customized.read_text() == "test:\n    @true\n"
