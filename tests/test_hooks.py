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
    target_dir = repo / "repo-hooks"
    target_dir.mkdir()
    for hook in ("pre-commit", "pre-push"):
        target = target_dir / hook
        shutil.copy(ROOT / "repo-hooks" / hook, target)
        target.chmod(0o755)
    # The hooks source their shared exemption logic next to themselves.
    shutil.copy(ROOT / "repo-hooks" / "qc-exempt.sh", target_dir / "qc-exempt.sh")
    # pre-push resolves the closure-claim confrontation script (#244) relative
    # to the hook repo, so the copied layout must carry it too.
    (repo / "global-hooks").mkdir()
    shutil.copy(ROOT / "global-hooks" / "confront_closes.py", repo / "global-hooks" / "confront_closes.py")
    return repo


@pytest.mark.parametrize(
    ("hook_dir", "hook", "recipe"),
    [
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


def _cache_upstream_owner(repo: pathlib.Path, owner: str) -> None:
    """Record the resolved fork origin the way the hook itself caches it."""
    subprocess.run(
        ["git", "config", "--local", "ai-review-ci.upstream-owner", owner],
        cwd=repo,
        env=git_test_env(),
        check=True,
    )


@pytest.mark.parametrize(("hook_dir", "hook", "recipe"), BYPASS_HOOKS)
def test_hooks_skip_forks_of_third_party_upstreams(hook_source_repo: pathlib.Path, tmp_path: pathlib.Path, hook_dir: str, hook: str, recipe: str) -> None:
    # A fork under the account carries upstream's layout and will never be QC-wired
    # (#372). The hook must skip before invoking the recipe — proven by omitting `just`
    # from PATH, so a non-skipping hook would fail command-not-found.
    fork = _init_downstream(tmp_path / "sage", recipe, "@echo should-not-run", remote="https://github.com/dzackgarza/sage.git")
    _cache_upstream_owner(fork, "sagemath")
    env = git_test_env(PATH=path_with_only(tmp_path, "sh", "git", "readlink", "dirname", "sed"))

    result = subprocess.run([str(hook_source_repo / hook_dir / hook)], cwd=fork, env=env, text=True, capture_output=True, check=False)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "should-not-run" not in result.stdout
    assert "fork of sagemath" in result.stderr


@pytest.mark.parametrize(("hook_dir", "hook", "recipe"), BYPASS_HOOKS)
def test_hooks_gate_a_repo_that_is_not_a_fork(hook_source_repo: pathlib.Path, tmp_path: pathlib.Path, hook_dir: str, hook: str, recipe: str) -> None:
    # The cached not-a-fork answer must not read as an exemption.
    owned = _init_downstream(tmp_path / "owned", recipe, "@echo owned-ran", remote="https://github.com/dzackgarza/foo.git")
    _cache_upstream_owner(owned, "none")

    result = subprocess.run([str(hook_source_repo / hook_dir / hook)], cwd=owned, env=git_test_env(), text=True, capture_output=True, check=False)

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "owned-ran"


@pytest.mark.parametrize(("hook_dir", "hook", "recipe"), BYPASS_HOOKS)
def test_hooks_gate_a_fork_of_another_repo_in_the_account(hook_source_repo: pathlib.Path, tmp_path: pathlib.Path, hook_dir: str, hook: str, recipe: str) -> None:
    # Forking within the account leaves it our own code, so it stays gated. The
    # exemption is about whose code it is, not about the repo being a fork.
    fork = _init_downstream(tmp_path / "own-fork", recipe, "@echo owned-ran", remote="https://github.com/dzackgarza/own-fork.git")
    _cache_upstream_owner(fork, "dzackgarza")

    result = subprocess.run([str(hook_source_repo / hook_dir / hook)], cwd=fork, env=git_test_env(), text=True, capture_output=True, check=False)

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "owned-ran"
