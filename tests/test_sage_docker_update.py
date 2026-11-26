"""sage-docker-update starts the research container from an image that is already pulled."""

import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
DOCKER = Path.home() / "bin" / "docker"
IMAGE = "ghcr.io/dzackgarza/sage:develop"
CONTAINER = "sage-research"


def _docker(*args: str) -> str:
    environment = dict(os.environ, DOCKER_HOST=f"unix:///run/user/{os.getuid()}/docker.sock")
    result = subprocess.run(
        [str(DOCKER), *args], env=environment, text=True, capture_output=True, check=True,
    )
    return result.stdout.strip()


def test_update_with_pulled_image_runs_container_on_the_tag(tmp_path: Path) -> None:
    _docker("image", "inspect", "--format", "{{.Id}}", IMAGE)
    home = tmp_path / "home"
    (home / "bin").mkdir(parents=True)
    (home / "bin" / "docker").symlink_to(DOCKER)
    (home / "gitclones").mkdir()
    launcher = home / "sage-docker-update"
    launcher.symlink_to(ROOT / "scripts" / "sage-docker")

    result = subprocess.run(
        [str(launcher)], env=dict(os.environ, HOME=str(home)),
        text=True, capture_output=True, check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines()[-1] == "1"
    tag_image = _docker("image", "inspect", "--format", "{{.Id}}", IMAGE)
    assert _docker("inspect", "--format", "{{.Image}}", CONTAINER) == tag_image
    assert _docker("inspect", "--format", "{{.State.Running}}", CONTAINER) == "true"
