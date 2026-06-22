import os
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture
def hook_source_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    repo = tmp_path / "ai-review-ci"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "justfile").write_text("test:\n    @true\n\ntest-ci:\n    @true\n")
    subprocess.run(["git", "add", "justfile"], cwd=repo, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-q",
            "-m",
            "init",
        ],
        cwd=repo,
        check=True,
    )
    for hook_dir in ("global-hooks", "repo-hooks"):
        target_dir = repo / hook_dir
        target_dir.mkdir()
        for hook in ("pre-commit", "pre-push"):
            target = target_dir / hook
            shutil.copy(ROOT / hook_dir / hook, target)
            target.chmod(0o755)
    return repo


@pytest.mark.parametrize(
    ("hook_dir", "hook", "recipe"),
    [
        ("global-hooks", "pre-commit", "test"),
        ("global-hooks", "pre-push", "test-ci"),
        ("repo-hooks", "pre-commit", "test"),
        ("repo-hooks", "pre-push", "test-ci"),
    ],
)
def test_ai_review_ci_hooks_skip_linked_ai_review_ci_worktrees(
    hook_source_repo: pathlib.Path,
    tmp_path: pathlib.Path,
    hook_dir: str,
    hook: str,
    recipe: str,
) -> None:
    worktree = tmp_path / "ai-review-ci-worktree"
    subprocess.run(
        ["git", "-C", str(hook_source_repo), "worktree", "add", "-q", str(worktree)],
        check=True,
    )
    (worktree / "justfile").write_text(f"{recipe}:\n    @echo should-not-run\n")

    env = os.environ | {"PATH": path_with_only(tmp_path, "sh", "git", "readlink", "dirname")}
    result = subprocess.run(
        [str(hook_source_repo / hook_dir / hook)],
        cwd=worktree,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "should-not-run" not in result.stdout


@pytest.mark.parametrize(
    ("hook_dir", "hook", "recipe"),
    [
        ("global-hooks", "pre-commit", "test"),
        ("global-hooks", "pre-push", "test-ci"),
        ("repo-hooks", "pre-commit", "test"),
        ("repo-hooks", "pre-push", "test-ci"),
    ],
)
def test_ai_review_ci_hooks_still_run_in_downstream_repos(
    hook_source_repo: pathlib.Path,
    tmp_path: pathlib.Path,
    hook_dir: str,
    hook: str,
    recipe: str,
) -> None:
    downstream = tmp_path / "downstream"
    downstream.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=downstream, check=True)
    (downstream / "justfile").write_text(f"{recipe}:\n    @echo downstream-ran\n")

    result = subprocess.run(
        [str(hook_source_repo / hook_dir / hook)],
        cwd=downstream,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "downstream-ran"


def path_with_only(tmp_path: pathlib.Path, *commands: str) -> str:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for command in commands:
        target = shutil.which(command)
        assert target is not None, f"required command missing for test setup: {command}"
        (bin_dir / command).symlink_to(target)
    return str(bin_dir)
