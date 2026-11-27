"""sage-docker-update moves a sage-tree checkout that holds the previous image's build records to the new image."""

import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
DOCKER = Path.home() / "bin" / "docker"
IMAGE = "ghcr.io/dzackgarza/sage:develop"
SAGE_SOURCE = Path.home() / "gitclones" / "sage-develop"
PREVIOUS_IMAGE_REVISION = "648dbc4921d731547fb86a7780d7cae2676cbbeb"
IMAGE_RECORDS = (".research-revisions", ".spinor-base-revision", ".spinor-source-revision")


def _docker(*args: str) -> str:
    environment = dict(os.environ, DOCKER_HOST=f"unix:///run/user/{os.getuid()}/docker.sock")
    result = subprocess.run(
        [str(DOCKER), *args], env=environment, text=True, capture_output=True, check=True,
    )
    return result.stdout


def test_update_replaces_the_previous_image_build_records(tmp_path: Path) -> None:
    image_revision = _docker(
        "image", "inspect", "--format",
        '{{index .Config.Labels "org.opencontainers.image.revision"}}', IMAGE,
    ).strip()
    home = tmp_path / "home"
    (home / "bin").mkdir(parents=True)
    (home / "bin" / "docker").symlink_to(DOCKER)
    (home / "gitclones").mkdir()
    volume = home / ".local" / "share" / "docker" / "volumes" / "sage-tree"
    tree = volume / "_data"
    subprocess.run(
        ["git", "clone", "--quiet", "--shared", "--no-checkout", str(SAGE_SOURCE), str(tree)],
        check=True,
    )
    subprocess.run(["git", "-C", str(tree), "checkout", "--quiet", PREVIOUS_IMAGE_REVISION], check=True)
    (tree / ".research-revisions").write_text("research 605806b3b73b92caea3f4735e0b0d96db0f297df\n")
    (tree / ".spinor-base-revision").write_text(f"{PREVIOUS_IMAGE_REVISION}\n")
    (tree / ".spinor-source-revision").write_text(f"{PREVIOUS_IMAGE_REVISION}\n")
    (volume / "image-revision").write_text(f"{PREVIOUS_IMAGE_REVISION}\n")
    launcher = home / "sage-docker-update"
    launcher.symlink_to(ROOT / "scripts" / "sage-docker")

    try:
        result = subprocess.run(
            [str(launcher)], env=dict(os.environ, HOME=str(home)),
            text=True, capture_output=True, check=False,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        head = subprocess.run(
            ["git", "-C", str(tree), "rev-parse", "HEAD"], text=True, capture_output=True, check=True,
        ).stdout.strip()
        assert head == image_revision
        for record in IMAGE_RECORDS:
            image_record = _docker("run", "--rm", "--entrypoint", "cat", IMAGE, f"/sage/{record}")
            assert (tree / record).read_text() == image_record, record
    finally:
        shutil.rmtree(tmp_path)
