"""Real-boundary proof for the sanctioned red-proof commit route (#222).

Every case drives the actual `ai-review-ci red-commit` CLI (via `-m
ai_review_ci.cli`) against a real on-disk git repo whose `just test-commit` gate
genuinely passes or fails from repo state. No internals are monkeypatched: the
CLI shells out to real `just` and real `git`, exactly as an agent would.

The gate keys on a staged `RED` marker file:
    test-commit:  fails iff a `RED` file exists in the working tree.
So an ordinary (green) commit passes the gate; a red proof (RED staged) fails it.
"""

import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

# `just test-commit` fails iff a RED marker file is present.
_GATE_JUSTFILE = 'test-commit:\n    @test ! -f RED || (echo "red proof present" && exit 1)\n'


def _git(repo: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "user.name=T", "-c", "user.email=t@e.x", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=True,
    )


@pytest.fixture
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """A real git repo with the state-keyed gate and the repo pre-commit hook."""
    repo = tmp_path / "downstream"
    repo.mkdir()
    _git(repo, "init", "-q")
    # Persist an identity so the CLI's own `git commit` works on identity-less
    # runners (CI has no global git user); real agents have one configured.
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "user.email", "t@e.x")
    (repo / "justfile").write_text(_GATE_JUSTFILE)
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    hook = hooks / "pre-commit"
    # Symlink the hook exactly as `install-repo-hooks` does: readlink -f then
    # resolves to the ai-review-ci checkout, so the hook's self-skip does NOT
    # misfire against the downstream repo and the gate genuinely runs. Copying
    # the file instead makes hook_repo resolve to the downstream .git and the
    # self-skip short-circuits the gate.
    hook.symlink_to(ROOT / "repo-hooks" / "pre-commit")
    # Pin hooks to this repo's own dir so the fixture hook is exercised
    # deterministically, regardless of any global core.hooksPath on the host
    # (install-global-hooks sets one; CI has none — this makes both behave alike).
    _git(repo, "config", "core.hooksPath", str(hooks))
    _git(repo, "add", "justfile")
    # The gate passes here (no RED file), so an ordinary initial commit is fine.
    _git(repo, "commit", "-q", "--no-verify", "-m", "init")
    return repo


def _red_commit(repo: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ai_review_ci.cli", "red-commit", "--target", str(repo), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def test_ordinary_pre_commit_hook_rejects_red_and_names_the_route(repo: pathlib.Path) -> None:
    """The plain hook blocks a red commit AND points at the sanctioned route."""
    (repo / "RED").write_text("reproduces the bug\n")
    _git(repo, "add", "RED")
    result = subprocess.run(
        ["git", "-c", "user.name=T", "-c", "user.email=t@e.x", "-C", str(repo), "commit", "-m", "red proof"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0, "hook must reject a commit whose gate fails"
    assert "ai-review-ci red-commit" in result.stderr
    assert "--issue" in result.stderr


def test_authorized_red_proof_is_accepted_through_the_route(repo: pathlib.Path) -> None:
    """A genuinely-red, issue-tagged commit lands via the sanctioned route."""
    (repo / "RED").write_text("reproduces the bug\n")
    _git(repo, "add", "RED")

    result = _red_commit(repo, "--issue", "222", "-m", "red proof for the parser bug")

    assert result.returncode == 0, result.stdout + result.stderr
    head = _git(repo, "log", "-1", "--pretty=%B").stdout
    assert "red proof for the parser bug" in head
    assert "Red-Proof: #222" in head
    # The committed tree really contains the red proof (gate would have blocked it).
    assert _git(repo, "show", "HEAD:RED").stdout == "reproduces the bug\n"


def test_passing_gate_is_rejected_as_not_a_red_proof(repo: pathlib.Path) -> None:
    """An ordinary (green) commit cannot use the route to bypass verification."""
    (repo / "feature.txt").write_text("ordinary change\n")
    _git(repo, "add", "feature.txt")

    before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    result = _red_commit(repo, "--issue", "222", "-m", "sneaking an ordinary commit through")

    assert result.returncode != 0
    assert "not a red proof" in result.stderr
    assert "ai-review-ci red-commit" in result.stderr  # remediation pointer
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == before, "no commit may be created"


def test_empty_message_is_rejected_with_remediation(repo: pathlib.Path) -> None:
    """An empty commit message is invalid authorization and is rejected."""
    (repo / "RED").write_text("reproduces the bug\n")
    _git(repo, "add", "RED")

    before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    result = _red_commit(repo, "--issue", "222", "-m", "   ")

    assert result.returncode != 0
    assert "commit message" in result.stderr
    assert "git-integration-workflow" in result.stderr
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == before


def test_missing_owning_issue_is_rejected_with_remediation(repo: pathlib.Path) -> None:
    """Invalid authorization data fails with the skill-directed pointer."""
    (repo / "RED").write_text("reproduces the bug\n")
    _git(repo, "add", "RED")

    before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    result = _red_commit(repo, "--issue", "0", "-m", "red proof")

    assert result.returncode != 0
    assert "positive owning-issue number" in result.stderr
    assert "git-integration-workflow" in result.stderr  # skill-directed remediation
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == before
