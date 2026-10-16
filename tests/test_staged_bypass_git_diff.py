"""Exercise the bypass gate on patches produced by Git from damaged text."""

import subprocess
from contextlib import chdir
from pathlib import Path

import pytest

from ai_review_ci.gates import check_staged_bypass


def git(project: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(project), *args], check=True, capture_output=True).stdout


@pytest.fixture(params=[b"\r", b"\v", b"\f", b"\x1c", b"\x1d", b"\x1e", "\x85".encode(), "\u2028".encode(), "\u2029".encode(), b"\xff"])
def damaged_repository(tmp_path: Path, request: pytest.FixtureRequest) -> Path:
    git(tmp_path, "init", "--quiet")
    source = tmp_path / "app.py"
    source.write_bytes(b"# damaged " + request.param + b" payload\npass\n")
    (tmp_path / "binary.dat").write_bytes(b"before\0")
    git(tmp_path, "add", "app.py", "binary.dat")
    tree = git(tmp_path, "write-tree").decode().strip()
    commit = git(tmp_path, "-c", "user.name=QC test", "-c", "user.email=qc@example.test", "commit-tree", tree, "-m", "baseline").decode().strip()
    git(tmp_path, "update-ref", "HEAD", commit)
    (tmp_path / "binary.dat").write_bytes(b"after\0")
    git(tmp_path, "add", "binary.dat")
    return tmp_path


def test_staged_bypass_accepts_repairing_control_byte_damage(damaged_repository: Path) -> None:
    (damaged_repository / "app.py").write_text("# repaired\npass\n")
    git(damaged_repository, "add", "app.py")

    with chdir(damaged_repository):
        check_staged_bypass()


def test_damaged_removed_text_does_not_silence_added_bypass(damaged_repository: Path, capsys: pytest.CaptureFixture[str]) -> None:
    marker = "# pragma: no cov" + "er"
    (damaged_repository / "app.py").write_text(f"# repaired\npass  {marker}\n")
    git(damaged_repository, "add", "app.py")

    with chdir(damaged_repository):
        with pytest.raises(SystemExit) as error:
            check_staged_bypass()
    assert error.value.code == 1
    assert "app.py:2: no-coverage-pragma:" in capsys.readouterr().err
