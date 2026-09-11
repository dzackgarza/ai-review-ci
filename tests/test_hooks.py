import os
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GIT_HOOK_ENV_KEYS = (
    "GIT_DIR",
    "GIT_INDEX_FILE",
    "GIT_WORK_TREE",
    "GIT_PREFIX",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
)


def git_test_env(**updates: str) -> dict[str, str]:
    env = os.environ.copy()
    for key in GIT_HOOK_ENV_KEYS:
        env.pop(key, None)
    env.update(updates)
    return env


@pytest.fixture
def hook_source_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    repo = tmp_path / "ai-review-ci"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, env=git_test_env(), check=True)
    (repo / "justfile").write_text("test-commit:\n    @true\n\ntest-push:\n    @true\n\ntest-ci:\n    @true\n")
    subprocess.run(["git", "add", "justfile"], cwd=repo, env=git_test_env(), check=True)
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
        env=git_test_env(),
        check=True,
    )
    for hook_dir in ("global-hooks", "repo-hooks"):
        target_dir = repo / hook_dir
        target_dir.mkdir()
        for hook in ("pre-commit", "pre-push"):
            target = target_dir / hook
            shutil.copy(ROOT / hook_dir / hook, target)
            target.chmod(0o755)
    # pre-push resolves the closure-claim confrontation script (#244) relative
    # to the hook repo, so the copied layout must carry it too.
    shutil.copy(ROOT / "global-hooks" / "confront_closes.py", repo / "global-hooks" / "confront_closes.py")
    return repo


@pytest.mark.parametrize(
    ("hook_dir", "hook", "recipe"),
    [
        ("global-hooks", "pre-commit", "test-commit"),
        ("global-hooks", "pre-push", "test-push"),
        ("repo-hooks", "pre-commit", "test-commit"),
        ("repo-hooks", "pre-push", "test-push"),
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
        env=git_test_env(),
        check=True,
    )
    (worktree / "justfile").write_text(f"{recipe}:\n    @echo should-not-run\n")

    env = git_test_env(PATH=path_with_only(tmp_path, "sh", "git", "readlink", "dirname"))
    result = subprocess.run(
        [str(hook_source_repo / hook_dir / hook)],
        cwd=worktree,
        input="",
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
        ("global-hooks", "pre-commit", "test-commit"),
        ("global-hooks", "pre-push", "test-push"),
        ("repo-hooks", "pre-commit", "test-commit"),
        ("repo-hooks", "pre-push", "test-push"),
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
    subprocess.run(["git", "init", "-q"], cwd=downstream, env=git_test_env(), check=True)
    (downstream / "justfile").write_text(f"{recipe}:\n    @echo downstream-ran\n")

    result = subprocess.run(
        [str(hook_source_repo / hook_dir / hook)],
        cwd=downstream,
        input="",
        env=git_test_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "downstream-ran"


@pytest.mark.parametrize("hook_dir", ["global-hooks", "repo-hooks"])
def test_pre_commit_preserves_pathspec_temporary_index(
    hook_source_repo: pathlib.Path, tmp_path: pathlib.Path, hook_dir: str
) -> None:
    downstream = tmp_path / "pathspec-downstream"
    downstream.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=downstream, env=git_test_env(), check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=downstream, env=git_test_env(), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=downstream, env=git_test_env(), check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=downstream, env=git_test_env(), check=True)
    (downstream / "corpus").mkdir()
    (downstream / "queues").mkdir()
    (downstream / "corpus" / "sibling.md").write_text("base\n")
    (downstream / "corpus" / "mine.md").write_text("base\n")
    (downstream / "queues" / "C.md").write_text("base\n")
    (downstream / "justfile").write_text(
        "test-commit:\n"
        "    #!/usr/bin/env sh\n"
        "    set -eu\n"
        "    if git diff --cached --quiet -- corpus; then\n"
        "        echo no-corpus-change\n"
        "    else\n"
        "        printf 'generated\\n' >> queues/C.md\n"
        "        git add queues/C.md\n"
        "    fi\n"
        "\n"
        "test-push:\n    @true\n\n"
        "test-ci:\n    @true\n"
    )
    subprocess.run(["git", "add", "."], cwd=downstream, env=git_test_env(), check=True)
    subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "base"],
        cwd=downstream,
        env=git_test_env(),
        check=True,
    )
    subprocess.run(
        ["git", "config", "core.hooksPath", str(hook_source_repo / hook_dir)],
        cwd=downstream,
        env=git_test_env(),
        check=True,
    )

    # Another stream has corpus work staged in the shared index. A pathspec
    # commit that touches only the queue must see its temporary commit index,
    # not that shared staged corpus path.
    with (downstream / "corpus" / "sibling.md").open("a") as handle:
        handle.write("sibling staged\n")
    subprocess.run(["git", "add", "corpus/sibling.md"], cwd=downstream, env=git_test_env(), check=True)
    with (downstream / "queues" / "C.md").open("a") as handle:
        handle.write("mine\n")
    result = subprocess.run(
        ["git", "commit", "--only", "queues/C.md", "-m", "pathspec queue update"],
        cwd=downstream,
        env=git_test_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert subprocess.run(
        ["git", "show", "HEAD:queues/C.md"], cwd=downstream, env=git_test_env(), text=True, capture_output=True, check=True
    ).stdout == "base\nmine\n"
    assert subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=downstream, env=git_test_env(), text=True, capture_output=True, check=True
    ).stdout.splitlines() == ["corpus/sibling.md"]

    # A corpus pathspec commit must take the other branch: regenerate/stage the
    # queue into Git's temporary commit index, while the sibling's staged corpus
    # path remains outside the commit.
    with (downstream / "corpus" / "mine.md").open("a") as handle:
        handle.write("mine corpus change\n")
    result = subprocess.run(
        ["git", "commit", "--only", "corpus/mine.md", "-m", "pathspec corpus update"],
        cwd=downstream,
        env=git_test_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert subprocess.run(
        ["git", "show", "HEAD:queues/C.md"], cwd=downstream, env=git_test_env(), text=True, capture_output=True, check=True
    ).stdout == "base\nmine\ngenerated\n"
    assert subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
        cwd=downstream,
        env=git_test_env(),
        text=True,
        capture_output=True,
        check=True,
    ).stdout.splitlines() == ["corpus/mine.md", "queues/C.md"]
    assert "corpus/sibling.md" in subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=downstream, env=git_test_env(), text=True, capture_output=True, check=True
    ).stdout.splitlines()


def path_with_only(tmp_path: pathlib.Path, *commands: str) -> str:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for command in commands:
        target = shutil.which(command)
        assert target is not None, f"required command missing for test setup: {command}"
        (bin_dir / command).symlink_to(target)
    return str(bin_dir)


def _init_downstream(path: pathlib.Path, recipe: str, body: str, remote: str | None = None) -> pathlib.Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, env=git_test_env(), check=True)
    if remote is not None:
        subprocess.run(["git", "remote", "add", "origin", remote], cwd=path, env=git_test_env(), check=True)
    (path / "justfile").write_text(f"{recipe}:\n    {body}\n")
    return path


BYPASS_HOOKS = [
    ("global-hooks", "pre-commit", "test-commit"),
    ("global-hooks", "pre-push", "test-push"),
    ("repo-hooks", "pre-commit", "test-commit"),
    ("repo-hooks", "pre-push", "test-push"),
]


@pytest.mark.parametrize(("hook_dir", "hook", "recipe"), BYPASS_HOOKS)
def test_hooks_skip_wiki_repositories(hook_source_repo: pathlib.Path, tmp_path: pathlib.Path, hook_dir: str, hook: str, recipe: str) -> None:
    # A .wiki repository is categorically outside the QC regime. The hook must
    # skip (exit 0) before ever invoking the recipe — proven by omitting `just`
    # from PATH: a non-skipping hook would fail command-not-found.
    wiki = _init_downstream(tmp_path / "research.wiki", recipe, "@echo should-not-run")
    env = git_test_env(PATH=path_with_only(tmp_path, "sh", "git", "readlink", "dirname"))
    result = subprocess.run([str(hook_source_repo / hook_dir / hook)], cwd=wiki, env=env, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "should-not-run" not in result.stdout
    assert "wiki repository" in result.stderr


@pytest.mark.parametrize(("hook_dir", "hook", "recipe"), BYPASS_HOOKS)
def test_hooks_skip_repos_not_under_dzackgarza(hook_source_repo: pathlib.Path, tmp_path: pathlib.Path, hook_dir: str, hook: str, recipe: str) -> None:
    foreign = _init_downstream(tmp_path / "foreign", recipe, "@echo should-not-run", remote="https://github.com/someoneelse/foo.git")
    env = git_test_env(PATH=path_with_only(tmp_path, "sh", "git", "readlink", "dirname"))
    result = subprocess.run([str(hook_source_repo / hook_dir / hook)], cwd=foreign, env=env, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "should-not-run" not in result.stdout
    assert "not under the dzackgarza account" in result.stderr


@pytest.mark.parametrize(("hook_dir", "hook", "recipe"), BYPASS_HOOKS)
def test_hooks_still_gate_dzackgarza_repos(hook_source_repo: pathlib.Path, tmp_path: pathlib.Path, hook_dir: str, hook: str, recipe: str) -> None:
    # A repository under the dzackgarza account is gated normally: the recipe runs.
    owned = _init_downstream(tmp_path / "owned", recipe, "@echo owned-ran", remote="https://github.com/dzackgarza/foo.git")
    result = subprocess.run([str(hook_source_repo / hook_dir / hook)], cwd=owned, env=git_test_env(), text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "owned-ran"


@pytest.mark.parametrize(("hook_dir", "hook", "recipe"), BYPASS_HOOKS)
def test_hooks_print_red_proof_sanction_on_gated_failure(hook_source_repo: pathlib.Path, tmp_path: pathlib.Path, hook_dir: str, hook: str, recipe: str) -> None:
    # A genuine QC failure in a gated repo blocks (exit 1) and names the only
    # bypass reachable here — the TDD red-proof --no-verify route.
    gated = _init_downstream(tmp_path / "gated", recipe, "@exit 1", remote="https://github.com/dzackgarza/foo.git")
    result = subprocess.run([str(hook_source_repo / hook_dir / hook)], cwd=gated, env=git_test_env(), text=True, capture_output=True, check=False)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "--no-verify" in result.stderr
    assert "red-proof" in result.stderr
