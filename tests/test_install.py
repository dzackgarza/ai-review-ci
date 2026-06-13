import pathlib
import subprocess

import pytest

from ai_review_ci.install import TEMPLATES, install


def _git_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    return repo


def test_install_writes_trigger_workflows(tmp_path: pathlib.Path) -> None:
    repo = _git_repo(tmp_path)
    install(repo)
    wf = repo / ".github" / "workflows"
    assert sorted(p.name for p in wf.iterdir()) == sorted(TEMPLATES)
    for name in TEMPLATES:
        text = (wf / name).read_text()
        assert (
            "uses: dzackgarza/ai-review-ci/.github/workflows/_review.yml@main" in text
        )
    general = (wf / "review-general.yml").read_text()
    assert "report_type: general" in general
    assert "scope: repo" in general
    pr = (wf / "review-pr.yml").read_text()
    assert "scope: diff" in pr
    assert "pull_request" in pr
    assert "fail_below: ${{ vars.GENERAL_FAIL_BELOW }}" in pr
    assert "fail_below: ${{ vars.SLOP_FAIL_BELOW }}" in pr


def test_install_refuses_non_git_dir(tmp_path: pathlib.Path) -> None:
    with pytest.raises(SystemExit):
        install(tmp_path)


def test_install_refuses_overwriting_repo_owned_config(
    tmp_path: pathlib.Path,
) -> None:
    repo = _git_repo(tmp_path)
    install(repo)
    customized = repo / ".github" / "workflows" / "review-general.yml"
    customized.write_text("# locally customized\n")
    with pytest.raises(SystemExit):
        install(repo)
    assert customized.read_text() == "# locally customized\n"
