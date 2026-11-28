"""Exercise the actual Sage preparser at the public Git syntax-gate boundary."""

import os
import subprocess
from pathlib import Path

import pytest

SAGE_JUSTFILE = Path(__file__).resolve().parents[1] / "justfiles" / "sage.just"
VALID = "R.<x,y> = QQ[]\nraise RuntimeError('syntax check must not execute code')\n"
INVALID = "from sage.all import (\n    ZZ,\n"


def git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), "-c", "user.name=Test", "-c",
         "user.email=test@example.com", "-c", "core.hooksPath=/dev/null", *args],
        env=env, text=True,
    ).strip()


@pytest.mark.sage_boundary
@pytest.mark.parametrize("mode", ["staged", "temporary-index", "outgoing"])
def test_sage_gate_checks_candidate_not_worktree(tmp_path: Path, mode: str) -> None:
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "commit", "--allow-empty", "-qm", "base")
    base = git(tmp_path, "rev-parse", "HEAD")
    env = os.environ.copy()
    env.pop("AI_REVIEW_CI_PRE_PUSH_REMOTE", None)
    env.pop("GIT_INDEX_FILE", None)
    if mode == "temporary-index":
        env["GIT_INDEX_FILE"] = str(tmp_path / ".git" / "candidate-index")
        git(tmp_path, "read-tree", "HEAD", env=env)
    if mode == "outgoing":
        env["AI_REVIEW_CI_PRE_PUSH_REMOTE"] = "origin"
    tier = "test-push" if mode == "outgoing" else "test-commit"
    source = tmp_path / "witness with spaces.sage"
    other = tmp_path / "other.sage"
    other.write_text(VALID)

    def check(candidate: str, worktree: str) -> subprocess.CompletedProcess[str]:
        source.write_text(candidate)
        git(tmp_path, "add", source.name, other.name, env=env)
        refs = ""
        if mode == "outgoing":
            git(tmp_path, "commit", "-qm", "candidate", env=env)
            head = git(tmp_path, "rev-parse", "HEAD")
            refs = f"refs/heads/main {head} refs/heads/main {base}\n"
        source.write_text(worktree)
        return subprocess.run(
            ["just", "-f", str(SAGE_JUSTFILE), "-d", ".", tier],
            cwd=tmp_path, env=env, input=refs, capture_output=True, text=True,
        )

    bad = check(INVALID, VALID)
    assert bad.returncode == 1, bad.stdout + bad.stderr
    assert source.name in bad.stderr
    good = check(VALID, INVALID)
    assert good.returncode == 0, good.stdout + good.stderr
    assert "2 file(s) checked" in good.stdout


def test_sage_gate_fails_if_configured_runtime_missing(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q")
    (tmp_path / "test.sage").write_text(VALID)
    git(tmp_path, "add", "test.sage")
    result = subprocess.run(
        ["just", "-f", str(SAGE_JUSTFILE), "-d", ".", "test-commit"],
        cwd=tmp_path, env=os.environ | {"SAGE_BIN": str(tmp_path / "missing-sage")},
        capture_output=True, text=True,
    )
    assert result.returncode != 0, result.stdout
    assert "SAGE_BIN" in result.stderr
