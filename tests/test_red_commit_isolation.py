"""Exercise red-commit against real Git indexes and mutating Just recipes."""

from pathlib import Path
import subprocess
import sys

import pytest

from tests.test_red_commit import _git, _red_commit, repo


def _stage_mutating_gate(repo: Path, *, fails: bool = False) -> None:
    recipe = (
        'test-commit:\n'
        '    @echo "formatter ran"\n'
        '    @printf "formatted\\n" > source.txt\n'
        '    @git add source.txt\n'
        '    @touch formatter-output\n'
    )
    if fails:
        recipe += '    @false\n'
    (repo / "justfile").write_text(recipe)
    (repo / "source.txt").write_text("staged source\n")
    _git(repo, "add", "justfile", "source.txt")
    (repo / "source.txt").write_text("unstaged source\n")
    (repo / "untracked.txt").write_text("untracked source\n")


def _state(repo: Path) -> tuple[str, str, str, str, str, bytes, bytes, bool]:
    return (
        _git(repo, "rev-parse", "HEAD").stdout,
        _git(repo, "status", "--porcelain=v1").stdout,
        _git(repo, "diff", "--cached", "--binary").stdout,
        _git(repo, "diff", "--binary").stdout,
        _git(repo, "worktree", "list", "--porcelain").stdout,
        (repo / "source.txt").read_bytes(),
        (repo / "untracked.txt").read_bytes(),
        (repo / "formatter-output").exists(),
    )


def test_passing_mutating_gate_leaves_original_checkout_and_index_intact(
    repo: Path,
) -> None:
    _stage_mutating_gate(repo)
    before = _state(repo)
    result = _red_commit(repo, "--issue", "444", "-m", "green")
    assert result.returncode != 0
    assert "not a red proof" in result.stderr
    assert "formatter ran" in result.stdout
    assert _state(repo) == before


@pytest.mark.parametrize("fails", [False, True])
def test_exempt_fork_does_not_execute_mutating_gate(repo: Path, fails: bool) -> None:
    _git(repo, "remote", "add", "origin", "https://github.com/dzackgarza/fork.git")
    _git(repo, "config", "ai-review-ci.upstream-owner", "upstream")
    _stage_mutating_gate(repo, fails=fails)
    before = _state(repo)
    hook = _git(repo, "hook", "run", "pre-commit")
    assert "fork of upstream" in hook.stderr
    assert "formatter ran" not in hook.stdout
    assert _state(repo) == before
    result = _red_commit(repo, "--issue", "444", "-m", "exempt")
    assert result.returncode != 0
    assert "QC-exempt" in result.stderr
    assert "formatter ran" not in result.stdout
    assert _state(repo) == before


def test_mutating_red_gate_commits_only_original_staged_proof(repo: Path) -> None:
    _stage_mutating_gate(repo, fails=True)
    worktrees = _git(repo, "worktree", "list", "--porcelain").stdout
    result = _red_commit(repo, "--issue", "444", "-m", "red proof")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "formatter ran" in result.stdout
    assert _git(repo, "show", "HEAD:source.txt").stdout == "staged source\n"
    assert "Red-Proof: #444" in _git(repo, "log", "-1", "--pretty=%B").stdout
    assert (repo / "source.txt").read_text() == "unstaged source\n"
    assert (repo / "untracked.txt").read_text() == "untracked source\n"
    assert not (repo / "formatter-output").exists()
    assert _git(repo, "worktree", "list", "--porcelain").stdout.splitlines()[0] == worktrees.splitlines()[0]
    assert _git(repo, "worktree", "list", "--porcelain").stdout.count("worktree ") == 1


def test_unstaged_red_proof_does_not_authorize_green_index(repo: Path) -> None:
    (repo / "RED").write_text("not staged\n")
    (repo / "source.txt").write_text("green proof\n")
    _git(repo, "add", "source.txt")
    before = _git(repo, "rev-parse", "HEAD").stdout
    result = _red_commit(repo, "--issue", "444", "-m", "unstaged red")
    assert result.returncode != 0
    assert "not a red proof" in result.stderr
    assert _git(repo, "rev-parse", "HEAD").stdout == before
    assert (repo / "RED").read_text() == "not staged\n"
    assert _git(repo, "show", ":source.txt").stdout == "green proof\n"



def test_initial_red_commit_uses_empty_baseline_without_leaving_worktree(repo: Path) -> None:
    _git(repo, "switch", "--orphan", "initial-red")
    (repo / "justfile").write_text("test-commit:\n    @test ! -f RED\n")
    (repo / "RED").write_text("initial proof\n")
    _git(repo, "add", "justfile", "RED")
    result = _red_commit(repo, "--issue", "444", "-m", "initial red")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _git(repo, "rev-list", "--count", "HEAD").stdout.strip() == "1"
    assert _git(repo, "show", "HEAD:RED").stdout == "initial proof\n"
    assert _git(repo, "worktree", "list", "--porcelain").stdout.count("worktree ") == 1



def test_missing_candidate_gate_is_not_a_red_proof(repo: Path) -> None:
    _stage_mutating_gate(repo)
    recipe = repo / "justfile"
    recipe.write_text(recipe.read_text().replace("test-commit:", "other:"))
    _git(repo, "add", "justfile")
    before = _state(repo)
    result = _red_commit(repo, "--issue", "444", "-m", "missing gate")
    assert result.returncode != 0
    assert "no runnable test-commit recipe" in result.stderr
    assert "formatter ran" not in result.stdout
    assert _state(repo) == before


def test_missing_managed_hook_cannot_authorize_bypass(repo: Path) -> None:
    _git(repo, "config", "core.hooksPath", ".git/empty-hooks")
    _stage_mutating_gate(repo, fails=True)
    before = _state(repo)
    result = _red_commit(repo, "--issue", "444", "-m", "no hook")
    assert result.returncode != 0
    assert "no installed ai-review-ci pre-commit gate" in result.stderr
    assert "formatter ran" not in result.stdout
    assert _state(repo) == before


def _stage_local_runtime_gate(repo: Path, recipe: str) -> None:
    (repo / ".gitignore").write_text(".venv/\n")
    runtime = repo / ".venv" / "bin"
    runtime.mkdir(parents=True)
    (runtime / "python").symlink_to(sys.executable)
    (repo / "justfile").write_text(recipe)
    (repo / "example.py").write_text("x = 1\n")
    _git(repo, "add", ".gitignore", "justfile", "example.py")
    _git(repo, "commit", "--no-verify", "-m", "local runtime baseline")
    (repo / "example.py").write_text("x = 2\n")
    _git(repo, "add", "example.py")


@pytest.mark.parametrize("command", [
    "./.venv/bin/python -m py_compile example.py",
    "test -x .venv/bin/python",
])
def test_missing_ignored_runtime_cannot_authorize_green_candidate(
    repo: Path, command: str
) -> None:
    _stage_local_runtime_gate(repo, f"test-commit:\n    @{command}\n")
    ordinary = subprocess.run(["just", "test-commit"], cwd=repo, check=False)
    assert ordinary.returncode == 0
    head = _git(repo, "rev-parse", "HEAD").stdout
    index = _git(repo, "diff", "--cached", "--binary").stdout
    result = _red_commit(repo, "--issue", "444", "-m", "not a red proof")
    assert result.returncode != 0, result.stdout + result.stderr
    assert "runtime" in result.stderr or "unavailable" in result.stderr
    assert _git(repo, "rev-parse", "HEAD").stdout == head
    assert _git(repo, "diff", "--cached", "--binary").stdout == index
    assert (repo / ".venv" / "bin" / "python").is_symlink()
    assert (repo / "example.py").read_text() == "x = 2\n"
    assert _git(repo, "worktree", "list", "--porcelain").stdout.count("worktree ") == 1


@pytest.mark.parametrize("command", ["exit 126", "exit 127"])
def test_unavailable_gate_status_cannot_authorize_bypass(repo: Path, command: str) -> None:
    (repo / "justfile").write_text(f"test-commit:\n    @{command}\n")
    _git(repo, "add", "justfile")
    head = _git(repo, "rev-parse", "HEAD").stdout
    result = _red_commit(repo, "--issue", "444", "-m", "unavailable")
    assert result.returncode != 0, result.stdout + result.stderr
    assert "unavailable" in result.stderr
    assert _git(repo, "rev-parse", "HEAD").stdout == head
