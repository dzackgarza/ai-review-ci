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


@pytest.mark.parametrize(
    ("hook_dir", "hook", "recipe"),
    [
        ("global-hooks", "pre-commit", "test"),
        ("global-hooks", "pre-push", "test-ci"),
        ("repo-hooks", "pre-commit", "test"),
        ("repo-hooks", "pre-push", "test-ci"),
    ],
)
def test_ai_review_ci_hooks_load_target_direnv_before_running_gate(
    hook_source_repo: pathlib.Path,
    tmp_path: pathlib.Path,
    hook_dir: str,
    hook: str,
    recipe: str,
) -> None:
    downstream = tmp_path / "downstream"
    downstream.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=downstream, check=True)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    direnv_log = tmp_path / "direnv-argv"
    just_log = tmp_path / "just-argv"
    write_fake_direnv(bin_dir / "direnv", direnv_log)
    write_fake_just(bin_dir / "just", just_log)
    for command in ("sh", "git", "readlink", "dirname"):
        target = shutil.which(command)
        assert target is not None, f"required command missing for test setup: {command}"
        (bin_dir / command).symlink_to(target)

    env = os.environ | {"PATH": str(bin_dir)}
    result = subprocess.run(
        [str(hook_source_repo / hook_dir / hook)],
        cwd=downstream,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert direnv_log.read_text() == f"exec . just {recipe}\n"
    assert just_log.read_text() == f"{recipe}\n"


def path_with_only(tmp_path: pathlib.Path, *commands: str) -> str:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for command in commands:
        target = shutil.which(command)
        assert target is not None, f"required command missing for test setup: {command}"
        (bin_dir / command).symlink_to(target)
    return str(bin_dir)


def write_fake_direnv(path: pathlib.Path, log_path: pathlib.Path) -> None:
    path.write_text(
        f'#!/usr/bin/env sh\nset -e\nprintf \'%s\\n\' "$*" > {log_path}\nif [ "$1" != "exec" ] || [ "$2" != "." ]; then\n  exit 64\nfi\nshift 2\nexec "$@"\n',
    )
    path.chmod(0o755)


def write_fake_just(path: pathlib.Path, log_path: pathlib.Path) -> None:
    path.write_text(f"#!/usr/bin/env sh\nset -e\nprintf '%s\\n' \"$*\" > {log_path}\n")
    path.chmod(0o755)
