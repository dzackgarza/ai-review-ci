"""Real-boundary tests for per-repository hook timing.

Each test drives the real global hooks through a real repository and reads the
durable log the hooks write into that repository's Git directory. Nothing is
mocked: the record is produced by the hook that ``git commit`` or ``git push``
actually ran.
"""

import json
import os
import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
HOOKS_DIR = ROOT / "repo-hooks"
GIT_HOOK_ENV_KEYS = (
    "GIT_DIR",
    "GIT_INDEX_FILE",
    "GIT_WORK_TREE",
    "GIT_PREFIX",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
)


def git_env(**updates: str) -> dict[str, str]:
    env = os.environ.copy()
    for key in GIT_HOOK_ENV_KEYS:
        env.pop(key, None)
    env.update(updates)
    return env


def run_git(
    args: list[str],
    cwd: pathlib.Path,
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["git", *args], cwd=cwd, env=git_env(), text=True, capture_output=True)
    if check and result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stdout}{result.stderr}")
    return result


def init_repo(path: pathlib.Path, remote: str = "https://github.com/dzackgarza/example.git") -> pathlib.Path:
    path.mkdir(parents=True)
    run_git(["init", "-q", "-b", "main"], path)
    for key, value in (
        ("user.name", "Test"),
        ("user.email", "test@example.com"),
        ("commit.gpgsign", "false"),
        ("core.hooksPath", str(HOOKS_DIR)),
    ):
        run_git(["config", key, value], path)
    if remote is not None:
        run_git(["remote", "add", "origin", remote], path)
    central = ROOT / "justfiles" / "qc-tooling.just"
    (path / "justfile").write_text(
        "".join(f"{recipe}:\n    @just -f {central} -d . {recipe}\n\n" for recipe in ("test-commit", "test-push"))
    )
    return path


def records(repo: pathlib.Path) -> list[dict[str, object]]:
    path = repo / ".git" / "ai-review-ci" / "timing" / "hooks.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_commit_records_pre_commit_duration(tmp_path: pathlib.Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "module.py").write_text("x = 1\n")
    run_git(["add", "module.py"], repo)

    result = run_git(["commit", "-q", "-m", "add module"], repo, check=False)

    assert result.returncode == 0, result.stdout + result.stderr
    hooks = records(repo)
    assert [record["hook"] for record in hooks] == ["pre-commit"]
    record = hooks[0]
    assert record["schema"] == 1
    assert record["exit_code"] == 0
    assert record["duration_ms"] >= 0
    assert isinstance(record["started_at"], str) and "T" in str(record["started_at"])
    assert pathlib.Path(str(record["worktree"])).resolve() == repo.resolve()


def test_failing_gate_records_nonzero_exit(tmp_path: pathlib.Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "broken.py").write_text("def broken(:\n")
    run_git(["add", "broken.py"], repo)

    result = run_git(["commit", "-q", "-m", "broken"], repo, check=False)

    assert result.returncode != 0, result.stdout + result.stderr
    hooks = records(repo)
    assert hooks[-1]["hook"] == "pre-commit"
    assert hooks[-1]["exit_code"] != 0
    assert hooks[-1]["duration_ms"] >= 0


def test_push_records_pre_push_duration(tmp_path: pathlib.Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "module.py").write_text("x = 1\n")
    run_git(["add", "module.py"], repo)
    run_git(["-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "add module"], repo)
    destination = tmp_path / "dzackgarza" / "remote.git"
    destination.parent.mkdir()
    run_git(["init", "--bare", "-q", str(destination)], tmp_path)
    run_git(["remote", "set-url", "origin", str(destination)], repo)

    result = run_git(["push", str(destination), "main"], repo, check=False)

    assert result.returncode == 0, result.stdout + result.stderr
    hooks = records(repo)
    assert [record["hook"] for record in hooks] == ["pre-push"]
    assert hooks[0]["exit_code"] == 0
    assert hooks[0]["duration_ms"] >= 0


def test_exempt_repository_still_records_timing(tmp_path: pathlib.Path) -> None:
    repo = init_repo(tmp_path / "repo", remote="https://github.com/someoneelse/foo.git")
    (repo / "module.py").write_text("x = 1\n")
    run_git(["add", "module.py"], repo)

    result = run_git(["commit", "-q", "-m", "foreign"], repo, check=False)

    assert result.returncode == 0, result.stdout + result.stderr
    assert [record["hook"] for record in records(repo)] == ["pre-commit"]


def test_linked_worktree_records_into_shared_log(tmp_path: pathlib.Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "module.py").write_text("x = 0\n")
    run_git(["add", "module.py", "justfile"], repo)
    run_git(["-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "base"], repo)
    worktree = tmp_path / "worktree"
    run_git(["worktree", "add", "-q", str(worktree), "-b", "feature"], repo)
    (worktree / "module.py").write_text("x = 1\n")
    run_git(["add", "module.py"], worktree)

    result = run_git(["commit", "-q", "-m", "worktree"], worktree, check=False)

    assert result.returncode == 0, result.stdout + result.stderr
    hooks = records(repo)
    assert [record["hook"] for record in hooks] == ["pre-commit"]
    assert pathlib.Path(str(hooks[0]["worktree"])).resolve() == worktree.resolve()


def test_commit_prints_the_duration_it_logged(tmp_path: pathlib.Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "module.py").write_text("x = 1\n")
    run_git(["add", "module.py"], repo)

    result = run_git(["commit", "-q", "-m", "first"], repo, check=False)

    assert result.returncode == 0, result.stdout + result.stderr
    logged_seconds = records(repo)[0]["duration_ms"] / 1000
    assert f"pre-commit: checks took {logged_seconds:.1f}s" in result.stderr


def test_push_prints_the_duration_it_logged(tmp_path: pathlib.Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "module.py").write_text("x = 1\n")
    run_git(["add", "module.py"], repo)
    run_git(["-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "add module"], repo)
    destination = tmp_path / "dzackgarza" / "remote.git"
    destination.parent.mkdir()
    run_git(["init", "--bare", "-q", str(destination)], tmp_path)
    run_git(["remote", "set-url", "origin", str(destination)], repo)

    result = run_git(["push", str(destination), "main"], repo, check=False)

    assert result.returncode == 0, result.stdout + result.stderr
    logged_seconds = records(repo)[0]["duration_ms"] / 1000
    assert f"pre-push: checks took {logged_seconds:.1f}s" in result.stderr


def test_unwritable_timing_log_fails_the_hook_loudly(tmp_path: pathlib.Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / ".git" / "ai-review-ci" / "timing" / "hooks.jsonl").mkdir(parents=True)
    (repo / "module.py").write_text("x = 1\n")
    run_git(["add", "module.py"], repo)

    result = run_git(["commit", "-q", "-m", "blocked"], repo, check=False)

    assert result.returncode != 0, result.stdout + result.stderr
    assert "hooks.jsonl" in result.stderr
