"""The host launcher must never treat container-only Python paths as host paths."""

import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("recipe", "target"),
    [
        ("_sage-python", "sage-docker-python"),
        ("_sage-preparse-bin", "sage-docker-preparse"),
    ],
)
def test_host_sage_uses_host_side_executable(
    tmp_path: Path, recipe: str, target: str
) -> None:
    fake_home = tmp_path / "home"
    scripts = fake_home / "ai-review-ci" / "scripts"
    scripts.mkdir(parents=True)
    launcher = scripts / "sage-docker"
    shutil.copy2(ROOT / "scripts" / "sage-docker", launcher)
    bindir = fake_home / ".local" / "bin"
    bindir.mkdir(parents=True)
    for name in ("sage", "sage-docker-python", "sage-docker-preparse"):
        (bindir / name).symlink_to(launcher)

    environment = dict(os.environ, HOME=str(fake_home), SAGE_BIN=str(bindir / "sage"))
    environment.pop("SAGE_PYTHON_BIN", None)
    environment.pop("SAGE_PREPARSE_BIN", None)
    result = subprocess.run(
        ["just", "-f", str(ROOT / "justfiles" / "sage.just"), "-d", str(tmp_path), recipe],
        cwd=tmp_path, env=environment, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == str(bindir / target)
