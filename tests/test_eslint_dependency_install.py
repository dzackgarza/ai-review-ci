"""Concurrent downstream callers must serialize their shared Bun install."""

import fcntl
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_shared_eslint_install_is_serialized(tmp_path: Path) -> None:
    central = tmp_path / "central"
    configs = central / "tool-configs"
    configs.mkdir(parents=True)
    justfiles = central / "justfiles"
    justfiles.mkdir()
    shutil.copy(ROOT / "justfiles" / "bun.just", justfiles / "bun.just")

    package = central / "fixture-plugin"
    package.mkdir()
    (package / "package.json").write_text('{"name":"fixture-eslint-plugin","version":"1.0.0"}\n')
    (configs / "package.json").write_text(
        json.dumps(
            {
                "name": "shared-tool-config",
                "private": True,
                "devDependencies": {"fixture-eslint-plugin": "file:../fixture-plugin"},
                "scripts": {"postinstall": "bash install-probe.sh"},
            }
        )
    )
    (configs / "install-probe.sh").write_text(
        "set -eu\nmkdir installing\necho start >> events\nwhile [ ! -e release ]; do sleep 0.02; done\necho end >> events\nrmdir installing\ntest ! -e fail-install\n"
    )
    subprocess.run(
        ["bun", "install", "--ignore-scripts"],
        cwd=configs,
        check=True,
        capture_output=True,
        timeout=60,
    )
    shutil.rmtree(configs / "node_modules")

    callers = [tmp_path / "caller-a", tmp_path / "caller-b"]
    for caller in callers:
        caller.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=caller, check=True)

    command = ["just", "-f", str(justfiles / "bun.just"), "-d", ".", "_eslint-deps"]
    with subprocess.Popen(
        command,
        cwd=callers[0],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ) as first:
        try:
            deadline = time.monotonic() + 15
            while not (configs / "events").exists():
                assert first.poll() is None, "Bun exited before reaching its lifecycle script"
                assert time.monotonic() < deadline, "Bun did not reach its lifecycle script"
                time.sleep(0.02)

            fd = os.open(configs, os.O_RDONLY | os.O_DIRECTORY)
            try:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            finally:
                os.close(fd)

            with subprocess.Popen(
                command,
                cwd=callers[1],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            ) as second:
                (configs / "release").touch()
                second_output, _ = second.communicate(timeout=60)
                assert second.returncode == 0, second_output.decode()
        finally:
            (configs / "release").touch()
            first_output, _ = first.communicate(timeout=60)
        assert first.returncode == 0, first_output.decode()

    assert (configs / "events").read_text().splitlines() == ["start", "end", "start", "end"]
    assert (configs / "node_modules" / "fixture-eslint-plugin" / "package.json").is_file()

    (configs / "fail-install").touch()
    failed = subprocess.run(command, cwd=callers[0], capture_output=True, timeout=60)
    assert failed.returncode != 0
    (configs / "fail-install").unlink()
    recovered = subprocess.run(command, cwd=callers[1], capture_output=True, timeout=60)
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
