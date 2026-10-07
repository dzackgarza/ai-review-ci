"""Real-boundary proof for the sanctioned red-gate push route.

Every case drives the actual `ai-review-ci red-push` CLI against a real git clone of a
real bare remote, whose `just test-push` gate genuinely passes or fails from repo state:
    test-push:  fails iff a `RED` file exists in the working tree.
"""

import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

_GATE_JUSTFILE = 'test-push:\n    @test ! -f RED || (echo "gate is red" && exit 1)\n'


def _git(repo: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "user.name=T", "-c", "user.email=t@e.x", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=True,
    )


@pytest.fixture
def clone(tmp_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    """A bare remote and a clone tracking it, with the state-keyed gate and the repo pre-push hook."""
    # The hook gates only repositories whose origin is under the dzackgarza account.
    remote = tmp_path / "dzackgarza" / "remote.git"
    remote.parent.mkdir()
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    repo = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(remote), str(repo)], check=True, capture_output=True)
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "user.email", "t@e.x")
    # Not a fork: recorded so the hook does not ask GitHub.
    _git(repo, "config", "ai-review-ci.upstream-owner", "none")
    _git(repo, "checkout", "-q", "-b", "main")
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    (hooks / "pre-push").symlink_to(ROOT / "repo-hooks" / "pre-push")
    _git(repo, "config", "core.hooksPath", str(hooks))
    (repo / "justfile").write_text(_GATE_JUSTFILE)
    _git(repo, "add", "justfile")
    _git(repo, "commit", "-q", "--no-verify", "-m", "init")
    _git(repo, "push", "-q", "--no-verify", "-u", "origin", "main")
    return remote, repo


def _red_push(repo: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ai_review_ci.cli", "red-push", "--target", str(repo), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def _commit_red(repo: pathlib.Path) -> str:
    (repo / "RED").write_text("acceptance suite red until its work units land\n")
    _git(repo, "add", "RED")
    _git(repo, "commit", "-q", "--no-verify", "-m", "red work")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def test_red_gate_push_lands_with_an_auditable_note(clone: tuple[pathlib.Path, pathlib.Path]) -> None:
    remote, repo = clone
    head = _commit_red(repo)

    result = _red_push(repo, "--issue", "33")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _git(remote, "rev-parse", "main").stdout.strip() == head
    note = _git(remote, "notes", "--ref=red-push", "show", head).stdout
    assert "Red-Push: #33" in note


def test_passing_gate_is_rejected_and_nothing_is_pushed(clone: tuple[pathlib.Path, pathlib.Path]) -> None:
    remote, repo = clone
    before = _git(remote, "rev-parse", "main").stdout.strip()
    (repo / "feature.txt").write_text("ordinary change\n")
    _git(repo, "add", "feature.txt")
    _git(repo, "commit", "-q", "--no-verify", "-m", "ordinary")

    result = _red_push(repo, "--issue", "33")

    assert result.returncode != 0
    assert "nothing to bypass" in result.stderr
    assert "ai-review-ci red-push" in result.stderr
    assert _git(remote, "rev-parse", "main").stdout.strip() == before


def test_non_positive_issue_is_rejected_before_the_gate_runs(clone: tuple[pathlib.Path, pathlib.Path]) -> None:
    remote, repo = clone
    before = _git(remote, "rev-parse", "main").stdout.strip()
    _commit_red(repo)

    result = _red_push(repo, "--issue", "0")

    assert result.returncode != 0
    assert "positive owning-issue number" in result.stderr
    assert _git(remote, "rev-parse", "main").stdout.strip() == before


def test_ordinary_pre_push_hook_rejects_red_and_names_the_route(clone: tuple[pathlib.Path, pathlib.Path]) -> None:
    remote, repo = clone
    before = _git(remote, "rev-parse", "main").stdout.strip()
    _commit_red(repo)

    result = subprocess.run(["git", "-C", str(repo), "push"], text=True, capture_output=True, check=False)

    assert result.returncode != 0
    assert "ai-review-ci red-push --issue" in result.stderr
    assert _git(remote, "rev-parse", "main").stdout.strip() == before
