"""Pre-push closure-claim confrontation (#244): keyword lever, ack lifecycle, guidance shape."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

import pytest

_SCRIPT = Path(__file__).parent.parent / "global-hooks" / "confront_closes.py"

_spec = importlib.util.spec_from_file_location("confront_closes", _SCRIPT)
assert _spec is not None and _spec.loader is not None
_confront_closes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_confront_closes)


def test_closing_numbers_matches_githubs_keyword_lever() -> None:
    text = "feat: x\n\nCloses #100, fixes #7, Resolved: #3.\nRefs #25 and see #26."
    assert _confront_closes.closing_numbers(text) == [3, 7, 100]
    assert _confront_closes.closing_numbers("chore: nothing claimed") == []


class PushRepo(NamedTuple):
    repo: Path
    sha: str
    env: dict[str, str]
    bin: Path


@pytest.fixture
def push_repo(tmp_path: Path) -> PushRepo:
    """A tmp repo with one closing-keyword commit on main and a PATH-faked gh."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    # The machine-wide core.hooksPath must not fire inside the fixture repo.
    subprocess.run(["git", "-C", str(repo), "config", "core.hooksPath", str(repo / ".git" / "hooks")], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "--allow-empty", "-q", "-m", "feat: partial work\n\nCloses #7"],
        check=True,
    )
    sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    issue = {"title": "Do all four sites", "state": "OPEN", "body": "Each of the four sites must be re-sited."}
    gh = bin_dir / "gh"
    gh.write_text(f"#!/bin/sh\necho '{json.dumps(issue)}'\n", encoding="utf-8")
    gh.chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    return PushRepo(repo=repo, sha=sha, env=env, bin=bin_dir)


def _run(ctx: PushRepo, stdin_line: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "origin"],
        input=stdin_line,
        cwd=ctx.repo,
        env=ctx.env,
        capture_output=True,
        text=True,
    )


def test_default_branch_closure_claim_blocks_once_with_verbatim_asks(push_repo: PushRepo) -> None:
    line = f"refs/heads/main {push_repo.sha} refs/heads/main {'0' * 40}\n"

    first = _run(push_repo, line)
    assert first.returncode == 1
    # The confrontation carries the issue's own text and the three options,
    # with the reword option framed as a false-claim correction, not progress.
    assert "Each of the four sites must be re-sited." in first.stderr
    assert "#7" in first.stderr
    assert "finish the remaining asks" in first.stderr
    assert "accomplishes nothing" in first.stderr

    ack = push_repo.repo / ".git" / "ai-review-ack-closes"
    ack.write_text("7\n", encoding="utf-8")
    second = _run(push_repo, line)
    assert second.returncode == 0
    assert not ack.exists(), "acknowledgment must be one-shot"


def test_non_default_branch_and_keyword_free_pushes_pass(push_repo: PushRepo) -> None:
    feature = f"refs/heads/f {push_repo.sha} refs/heads/feature {'0' * 40}\n"
    assert _run(push_repo, feature).returncode == 0

    subprocess.run(
        ["git", "-C", str(push_repo.repo), "commit", "--allow-empty", "-q", "-m", "chore: no claims"],
        check=True,
    )
    sha = subprocess.run(["git", "-C", str(push_repo.repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    keyword_free = f"refs/heads/main {sha} refs/heads/main {push_repo.sha}\n"
    assert _run(push_repo, keyword_free).returncode == 0


def test_already_closed_issue_does_not_confront(push_repo: PushRepo) -> None:
    issue = {"title": "Done long ago", "state": "CLOSED", "body": "x"}
    gh = push_repo.bin / "gh"
    gh.write_text(f"#!/bin/sh\necho '{json.dumps(issue)}'\n", encoding="utf-8")

    line = f"refs/heads/main {push_repo.sha} refs/heads/main {'0' * 40}\n"
    assert _run(push_repo, line).returncode == 0


def test_unfetchable_issue_blocks_loudly(push_repo: PushRepo) -> None:
    gh = push_repo.bin / "gh"
    gh.write_text("#!/bin/sh\necho 'boom' >&2\nexit 1\n", encoding="utf-8")

    line = f"refs/heads/main {push_repo.sha} refs/heads/main {'0' * 40}\n"
    result = _run(push_repo, line)
    assert result.returncode == 1
    assert "could not fetch issue #7" in result.stderr
