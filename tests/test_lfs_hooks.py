"""Exercise the installed global hooks with real Git LFS file transfers."""

import hashlib
import os
import pathlib
import stat
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture
def lfs_repo(tmp_path: pathlib.Path):
    home = tmp_path / "home"
    home.mkdir()
    hooks = home / "hooks"
    env = os.environ.copy()
    for key in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "GIT_PREFIX", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR"):
        env.pop(key, None)
    env.update(HOME=str(home), GIT_CONFIG_GLOBAL=str(home / "gitconfig"), GIT_CONFIG_NOSYSTEM="1", GIT_GLOBAL_HOOKS_DIR=str(hooks))
    subprocess.run(["just", "install-global-hooks"], cwd=ROOT, env=env, check=True)
    source = tmp_path / "source"
    source.mkdir()
    remote = tmp_path / "dzackgarza" / "remote.git"
    remote.parent.mkdir()
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], env=env, check=True)

    def git(*args: str, check: bool = True):
        result = subprocess.run(["git", *args], cwd=source, env=env, text=True, capture_output=True)
        if check:
            assert result.returncode == 0, result.stdout + result.stderr
        return result

    git("init", "-q", "-b", "main")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.invalid")
    git("config", "ai-review-ci.upstream-owner", "none")
    git("remote", "add", "origin", str(remote))
    git("lfs", "install", "--local", "--skip-repo")
    git("lfs", "track", "--lockable", "*.bin")
    central = ROOT / "justfiles" / "qc-tooling.just"
    (source / "justfile").write_text(
        "".join(f"{recipe}:\n    @just -f {central} -d . {recipe}\n\n" for recipe in ("test-commit", "test-push"))
    )
    return source, remote, git


def lfs_object(git_dir: pathlib.Path, content: bytes) -> pathlib.Path:
    oid = hashlib.sha256(content).hexdigest()
    return git_dir / "lfs" / "objects" / oid[:2] / oid[2:4] / oid


def test_global_hooks_upload_all_refs_and_preserve_qc(lfs_repo):
    source, remote, git = lfs_repo
    first = b"first real LFS payload"
    second = b"second real LFS payload"
    git("add", ".")
    git("commit", "-qm", "base")
    git("branch", "second")
    (source / "first.bin").write_bytes(first)
    (source / "module.py").write_text("answer = 42\n")
    git("add", ".")
    git("commit", "-qm", "first")
    git("checkout", "second")
    (source / "second.bin").write_bytes(second)
    (source / "second.py").write_text("second = True\n")
    git("add", "second.bin", "second.py")
    git("commit", "-qm", "second")
    pushed = git("push", "--all", "origin")
    assert "Push syntax: 2 file(s) checked" in pushed.stdout
    assert lfs_object(remote, first).read_bytes() == first
    assert lfs_object(remote, second).read_bytes() == second
    assert "refs/heads/main" in git("ls-remote", "origin").stdout
    assert "refs/heads/second" in git("ls-remote", "origin").stdout

    git("checkout", "-qb", "bad")
    (source / "module.py").write_text("def broken(:\n")
    bad = b"object that must not upload after a failed QC gate"
    (source / "bad.bin").write_bytes(bad)
    git("add", ".")
    git("-c", "core.hooksPath=/dev/null", "commit", "-qm", "invalid fixture")
    rejected = git("push", "origin", "bad", check=False)
    assert rejected.returncode != 0
    assert "push gate failed: just test-push" in rejected.stderr
    assert not lfs_object(remote, bad).exists()
    assert "refs/heads/bad" not in git("ls-remote", "origin").stdout


def test_global_post_hooks_restore_lockable_permissions(lfs_repo):
    source, _, git = lfs_repo
    git("add", ".")
    git("commit", "-qm", "initialize LFS tracking")
    locked = source / "first.bin"
    locked.write_bytes(b"lockable content")
    git("add", ".")
    locked.chmod(0o644)
    git("commit", "-qm", "base")
    assert not locked.stat().st_mode & stat.S_IWUSR

    locked.chmod(0o644)
    git("checkout", "--", "first.bin")
    assert not locked.stat().st_mode & stat.S_IWUSR

    git("checkout", "-qb", "feature")
    (source / "feature.py").write_text("feature = True\n")
    git("add", "feature.py")
    git("commit", "-qm", "feature")
    git("checkout", "main")
    locked.chmod(0o644)
    git("merge", "--ff-only", "feature")
    assert not locked.stat().st_mode & stat.S_IWUSR


def test_lfs_upload_failure_blocks_ref_update(lfs_repo):
    source, remote, git = lfs_repo
    payload = b"missing LFS payload"
    (source / "missing.bin").write_bytes(payload)
    git("add", ".")
    git("commit", "-qm", "missing object fixture")
    lfs_object(source / ".git", payload).unlink()
    rejected = git("push", "origin", "main", check=False)
    assert rejected.returncode != 0
    assert "Git LFS upload failed:" in rejected.stdout + rejected.stderr
    assert "missing.bin" in rejected.stdout + rejected.stderr
    assert not lfs_object(remote, payload).exists()
    assert "refs/heads/main" not in git("ls-remote", "origin").stdout


def test_qc_exempt_repo_still_uploads_lfs(lfs_repo):
    source, remote, git = lfs_repo
    foreign = remote.parent.parent / "foreign.git"
    remote.rename(foreign)
    git("remote", "set-url", "origin", str(foreign))
    payload = b"foreign LFS payload"
    (source / "foreign.bin").write_bytes(payload)
    git("add", ".")
    git("commit", "-qm", "foreign repository")
    pushed = git("push", "origin", "main")
    assert "QC not owned here" in pushed.stderr
    assert "Push syntax:" not in pushed.stdout
    assert lfs_object(foreign, payload).read_bytes() == payload
    assert "refs/heads/main" in git("ls-remote", "origin").stdout
