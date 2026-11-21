"""Terminating the launcher stops the command it started in the container."""

import os
from pathlib import Path
import signal
import subprocess
import time
import uuid

import pytest
import tempfile


ROOT = Path(__file__).resolve().parents[1]
DOCKER = Path.home() / "bin" / "docker"
CONTAINER = "sage-research"


def _docker_env() -> dict[str, str]:
    return dict(os.environ, DOCKER_HOST=f"unix:///run/user/{os.getuid()}/docker.sock")


def _container_processes(marker: str) -> list[str]:
    result = subprocess.run(
        [str(DOCKER), "exec", CONTAINER, "ps", "-eo", "pid,args"],
        env=_docker_env(), text=True, capture_output=True, check=True,
    )
    return [line for line in result.stdout.splitlines() if marker in line]


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT, signal.SIGHUP])
def test_signal_to_launcher_stops_container_command(sig: signal.Signals) -> None:
    # The container mounts only the home directory, so the work directory lives there.
    cache = Path.home() / ".cache" / "sage-docker-tmp"
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache) as directory:
        _run_and_signal(Path(directory), sig)


def _run_and_signal(tmp_path: Path, sig: signal.Signals) -> None:
    launcher = tmp_path / "sage-docker-python"
    launcher.symlink_to(ROOT / "scripts" / "sage-docker")
    script = tmp_path / "sleeper.py"
    marker = f"sleeper-{uuid.uuid4().hex}"
    script.write_text(f"import time\n# {marker}\ntime.sleep(300)\n")
    marked = tmp_path / f"{marker}.py"
    script.rename(marked)

    process = subprocess.Popen([str(launcher), str(marked)], cwd=tmp_path)
    deadline = time.monotonic() + 30
    while not _container_processes(marker):
        assert time.monotonic() < deadline, "the command never started in the container"
        time.sleep(0.5)

    process.send_signal(sig)
    process.wait(timeout=15)
    time.sleep(3)
    assert _container_processes(marker) == []
