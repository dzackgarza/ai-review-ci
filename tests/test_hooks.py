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
    (repo / "scripts").mkdir()
    shutil.copy(ROOT / "scripts" / "local-check.py", repo / "scripts" / "local-check.py")
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
    assert f'{"Push" if hook == "pre-push" else "Staged"} syntax: 0 file(s)' in result.stdout


@pytest.mark.parametrize("installation", ["global", "repo"])
def test_pre_commit_preserves_pathspec_temporary_index(
    hook_source_repo: pathlib.Path, tmp_path: pathlib.Path, installation: str
) -> None:
    """The checker reads Git's temporary --only index without mutating other work."""
    hooks_path = hook_source_repo / "repo-hooks"
    if installation == "global":
        hooks_path = tmp_path / "global-hooks-dir"
        hooks_path.mkdir()
        for hook in ("pre-commit", "pre-push"):
            (hooks_path / hook).symlink_to(hook_source_repo / "repo-hooks" / hook)
    downstream = tmp_path / "pathspec-downstream"
    downstream.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=downstream, env=git_test_env(), check=True)
    for key, value in (("user.name", "Test"), ("user.email", "test@example.invalid"), ("commit.gpgsign", "false")):
        subprocess.run(["git", "config", key, value], cwd=downstream, env=git_test_env(), check=True)
    for name in ("sibling.py", "mine.py"):
        (downstream / name).write_text("def f(x): return x\\n".replace("\\n", "\n"))
    subprocess.run(["git", "add", "."], cwd=downstream, env=git_test_env(), check=True)
    subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "base"],
        cwd=downstream, env=git_test_env(), check=True,
    )
    subprocess.run(["git", "config", "core.hooksPath", str(hooks_path)], cwd=downstream, env=git_test_env(), check=True)

    # Invalid staged sibling is outside the temporary --only index.
    (downstream / "sibling.py").write_text("def broken(:\\n".replace("\\n", "\n"))
    subprocess.run(["git", "add", "sibling.py"], cwd=downstream, env=git_test_env(), check=True)
    (downstream / "mine.py").write_text("def f(x): return x + 1\\n".replace("\\n", "\n"))
    result = subprocess.run(
        ["git", "commit", "--only", "mine.py", "-m", "pathspec commit"],
        cwd=downstream, env=git_test_env(), text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Staged syntax: 1 file(s)" in result.stderr
    assert subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=downstream, env=git_test_env(),
        text=True, capture_output=True, check=True,
    ).stdout.splitlines() == ["sibling.py"]

    # An invalid candidate for --only must be rejected, while the unrelated
    # staged sibling remains precisely as it was.
    (downstream / "mine.py").write_text("def broken(:\\n".replace("\\n", "\n"))
    rejected = subprocess.run(
        ["git", "commit", "--only", "mine.py", "-m", "invalid candidate"],
        cwd=downstream, env=git_test_env(), text=True, capture_output=True,
    )
    assert rejected.returncode == 1, rejected.stdout + rejected.stderr
    assert "mine.py" in rejected.stderr
    assert subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=downstream, env=git_test_env(),
        text=True, capture_output=True, check=True,
    ).stdout.splitlines() == ["sibling.py"]


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
    assert f'{"Push" if hook == "pre-push" else "Staged"} syntax: 0 file(s)' in result.stdout


def test_hooks_pass_exact_candidate_blobs_to_project_validator(
    hook_source_repo: pathlib.Path, tmp_path: pathlib.Path,
) -> None:
    project = _init_downstream(
        tmp_path / "owned", "test-commit", "@true",
        remote="https://github.com/dzackgarza/example.git",
    )
    (project / "scripts").mkdir()
    validator = project / "scripts" / "local-validate.py"
    validator.write_text(
        "#!/usr/bin/env python3\n"
        "import argparse, json, subprocess, sys\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--mode', required=True)\n"
        "args = parser.parse_args()\n"
        "records = [json.loads(line) for line in sys.stdin]\n"
        "print(f'Project {args.mode}: {len(records)} candidate(s)')\n"
        "for record in records:\n"
        "    if record['path'].endswith('.md'):\n"
        "        revision = ':' if record['version'] == 'index' else record['version'] + ':'\n"
        "        blob = subprocess.run(['git', 'show', revision + record['path']], check=True, capture_output=True, text=True).stdout\n"
        "        if 'BROKEN' in blob:\n"
        "            sys.exit(1)\n"
    )
    validator.chmod(0o755)
    card = project / "card.md"
    card.write_text("valid\n")
    subprocess.run(["git", "add", "."], cwd=project, env=git_test_env(), check=True)
    card.write_text("BROKEN in worktree only\n")
    staged = subprocess.run(
        [str(hook_source_repo / "repo-hooks" / "pre-commit")], cwd=project,
        env=git_test_env(), capture_output=True, text=True,
    )
    assert staged.returncode == 0, staged.stdout + staged.stderr
    assert "Project staged: 3 candidate(s)" in staged.stdout

    subprocess.run(["git", "add", "card.md"], cwd=project, env=git_test_env(), check=True)
    rejected = subprocess.run(
        [str(hook_source_repo / "repo-hooks" / "pre-commit")], cwd=project,
        env=git_test_env(), capture_output=True, text=True,
    )
    assert rejected.returncode == 1, rejected.stdout + rejected.stderr

    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
         "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "candidate"],
        cwd=project, env=git_test_env(), check=True,
    )
    oid = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=project, text=True).strip()
    card.write_text("repaired\n")
    subprocess.run(["git", "add", "card.md"], cwd=project, env=git_test_env(), check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
         "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "repaired"],
        cwd=project, env=git_test_env(), check=True,
    )
    repaired_oid = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=project, text=True).strip()
    push = subprocess.run(
        [str(hook_source_repo / "repo-hooks" / "pre-push")], cwd=project,
        env=git_test_env(), input=(
            f"refs/heads/repaired {repaired_oid} refs/heads/repaired {'0' * 40}\n"
            f"refs/heads/broken {oid} refs/heads/broken {'0' * 40}\n"
        ),
        capture_output=True, text=True,
    )
    assert push.returncode == 1, push.stdout + push.stderr
    assert "Project push: 4 candidate(s)" in push.stdout


@pytest.mark.parametrize(("hook_dir", "hook", "recipe"), BYPASS_HOOKS)
def test_hooks_report_only_local_syntax_failure(
    hook_source_repo: pathlib.Path, tmp_path: pathlib.Path, hook_dir: str, hook: str, recipe: str
) -> None:
    gated = _init_downstream(tmp_path / "gated", recipe, "@exit 1", remote="https://github.com/dzackgarza/foo.git")
    (gated / "broken.py").write_text("def broken(:\\n".replace("\\n", "\n"))
    subprocess.run(["git", "add", "broken.py"], cwd=gated, env=git_test_env(), check=True)
    stdin = ""
    if hook == "pre-push":
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
             "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "invalid outgoing tree"],
            cwd=gated, env=git_test_env(), check=True,
        )
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=gated, text=True).strip()
        stdin = f"refs/heads/main {sha} refs/heads/main {'0' * 40}\n"
    result = subprocess.run(
        [str(hook_source_repo / hook_dir / hook)], cwd=gated, env=git_test_env(),
        input=stdin, text=True, capture_output=True,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("outgoing-commit syntax" if hook == "pre-push" else "staged-source syntax") in result.stderr
    assert "red-commit" not in result.stderr
    assert "xfail" not in result.stderr


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
    assert f'{"Push" if hook == "pre-push" else "Staged"} syntax: 0 file(s)' in result.stdout


@pytest.mark.parametrize(("hook_dir", "hook", "recipe"), BYPASS_HOOKS)
def test_hooks_gate_a_fork_of_another_repo_in_the_account(hook_source_repo: pathlib.Path, tmp_path: pathlib.Path, hook_dir: str, hook: str, recipe: str) -> None:
    # Forking within the account leaves it our own code, so it stays gated. The
    # exemption is about whose code it is, not about the repo being a fork.
    fork = _init_downstream(tmp_path / "own-fork", recipe, "@echo owned-ran", remote="https://github.com/dzackgarza/own-fork.git")
    _cache_upstream_owner(fork, "dzackgarza")

    result = subprocess.run([str(hook_source_repo / hook_dir / hook)], cwd=fork, env=git_test_env(), text=True, capture_output=True, check=False)

    assert result.returncode == 0, result.stdout + result.stderr
    assert f'{"Push" if hook == "pre-push" else "Staged"} syntax: 0 file(s)' in result.stdout


def test_pre_push_checks_committed_tree_and_not_empty_index(
    hook_source_repo: pathlib.Path, tmp_path: pathlib.Path,
) -> None:
    """A prior commit's syntax defect cannot disappear at the next push."""
    source = tmp_path / "source"
    destination = tmp_path / "remote.git"
    source.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=source, env=git_test_env(), check=True)
    subprocess.run(["git", "init", "--bare", "-q", str(destination)], env=git_test_env(), check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/dzackgarza/example.git"],
        cwd=source, env=git_test_env(), check=True,
    )
    subprocess.run(
        ["git", "config", "core.hooksPath", str(hook_source_repo / "repo-hooks")],
        cwd=source, env=git_test_env(), check=True,
    )
    subprocess.run(
        ["git", "config", "ai-review-ci.upstream-owner", "none"],
        cwd=source, env=git_test_env(), check=True,
    )

    def commit(content: str) -> str:
        (source / "module.py").write_text(content)
        subprocess.run(["git", "add", "module.py"], cwd=source, env=git_test_env(), check=True)
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
             "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "candidate"],
            cwd=source, env=git_test_env(), check=True,
        )
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()

    original = commit("def f(x): return x\n")
    initial = subprocess.run(
        ["git", "push", str(destination), "HEAD:refs/heads/main"],
        cwd=source, env=git_test_env(), capture_output=True, text=True,
    )
    assert initial.returncode == 0, initial.stdout + initial.stderr

    commit("def broken(:\n")
    assert subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=source, env=git_test_env(),
    ).returncode == 0

    rejected = subprocess.run(
        ["git", "push", str(destination), "HEAD:refs/heads/main"],
        cwd=source, env=git_test_env(), capture_output=True, text=True,
    )
    assert rejected.returncode != 0, rejected.stdout + rejected.stderr
    assert "module.py" in rejected.stderr
    assert "outgoing-commit syntax check failed" in rejected.stderr
    assert subprocess.check_output(
        ["git", "--git-dir", str(destination), "rev-parse", "refs/heads/main"],
        text=True,
    ).strip() == original

    commit("def f(x): return x + 1\n")
    accepted = subprocess.run(
        ["git", "push", str(destination), "HEAD:refs/heads/main"],
        cwd=source, env=git_test_env(), capture_output=True, text=True,
    )
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
