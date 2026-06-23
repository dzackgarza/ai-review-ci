import pathlib
import subprocess

import pytest

from ai_review_ci.install import TEMPLATES, _write_manifest, _write_trigger_workflows


def _git_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    return repo


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
