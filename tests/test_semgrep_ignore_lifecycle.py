"""Exercise overlapping invocations of the real ignore-file wrapper."""

import select
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "tool-artifacts/scripts/semgrep-with-qc-ignores.sh"
READER = ROOT / "tool-artifacts/scripts/read_qc_excludes.py"
CONFIG = ROOT / "tool-configs/qc-excludes.toml"
CHILD = """
import sys
from pathlib import Path
ignore = Path('.semgrepignore')
Path(sys.argv[1]).write_bytes(ignore.read_bytes())
print('entered', flush=True)
assert sys.stdin.readline() == 'release\\n'
Path(sys.argv[2]).write_bytes(ignore.read_bytes())
"""


def enter(proc: subprocess.Popen[str], timeout: float) -> bool:
    assert proc.stdout is not None
    ready, _, _ = select.select([proc.stdout], [], [], timeout)
    if not ready:
        return False
    assert proc.stdout.readline() == "entered\n"
    return True


def release(proc: subprocess.Popen[str]) -> None:
    assert proc.stdin is not None
    proc.stdin.write("release\n")
    proc.stdin.flush()
    stdout, stderr = proc.communicate(timeout=30)
    assert proc.returncode == 0, stdout + stderr


@pytest.mark.parametrize("original_kind", ["regular", "symlink", "absent"])
def test_overlapping_ignore_lifecycles_preserve_scan_and_owner_entry(
    tmp_path: Path, original_kind: str
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    ignore = project / ".semgrepignore"
    sentinel = b"OWNER-SENTINEL\n"
    target = tmp_path / "owner-ignore"
    if original_kind == "regular":
        ignore.write_bytes(sentinel)
    elif original_kind == "symlink":
        target.write_bytes(sentinel)
        ignore.symlink_to(target)
    expected = subprocess.check_output(["uv", "run", str(READER), str(CONFIG)], cwd=project)
    expected += b"*.html\n**/*.html\n.pnp.cjs\n.pnp.loader.mjs\n"
    processes: list[subprocess.Popen[str]] = []

    def start(name: str) -> subprocess.Popen[str]:
        proc = subprocess.Popen(
            [str(WRAPPER), str(READER), str(CONFIG), "--", sys.executable, "-c", CHILD,
             str(tmp_path / f"{name}-before"), str(tmp_path / f"{name}-after")],
            cwd=project, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
        )
        processes.append(proc)
        return proc

    try:
        first = start("first")
        assert enter(first, 30)
        second = start("second")
        second_entered_early = enter(second, 3)
        release(first)
        if not second_entered_early:
            assert enter(second, 30)
        release(second)
        for name in ("first", "second"):
            assert (tmp_path / f"{name}-before").read_bytes() == expected
            assert (tmp_path / f"{name}-after").read_bytes() == expected
        assert not second_entered_early
        if original_kind == "regular":
            assert not ignore.is_symlink()
            assert ignore.read_bytes() == sentinel
        elif original_kind == "symlink":
            assert ignore.is_symlink()
            assert ignore.readlink() == target
            assert target.read_bytes() == sentinel
        else:
            assert not ignore.exists() and not ignore.is_symlink()
    finally:
        for proc in processes:
            if proc.poll() is None:
                release(proc)
