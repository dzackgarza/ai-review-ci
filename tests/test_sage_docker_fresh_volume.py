"""Exercise real Docker volume population without using the research container or volumes."""

import os
import shlex
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "ghcr.io/dzackgarza/sage:develop"
VOLUMES = ("sage-tree", "sage-repos", "sage-julia")
PRODUCTS = (".venv", "builddir", ".research-revisions", ".spinor-base-revision", ".spinor-source-revision")


def docker(*args: str, env: dict[str, str]) -> str:
    result = subprocess.run([env["FIXTURE_DOCKER"], *args], env=env, text=True, capture_output=True, check=True)
    return result.stdout.strip()


def namespaced_docker(args: list[str]) -> int:
    """Route the fixed namespace and registry response to a real disposable Docker image."""
    env = dict(os.environ)
    prefix = env["FIXTURE_PREFIX"]
    image = env["FIXTURE_IMAGE"]
    if args[:2] == ["volume", "ls"]:
        assert args == ["volume", "ls", "--format", "{{.Name}}"]
        names = docker(*args, env=env).splitlines()
        for name in names:
            if name.startswith(prefix + "-"):
                print(name.removeprefix(prefix + "-"))
        return 0
    if args[0] == "pull":
        assert args == ["pull", IMAGE]
        docker("image", "inspect", image, env=env)
        return 0
    if args[:2] == ["image", "inspect"] and any(".RepoDigests" in arg for arg in args):
        assert args[-1] == docker("image", "inspect", "--format", "{{.Id}}", image, env=env)
        print(f"{IMAGE.rsplit(':', 1)[0]}@{args[-1]}")
        return 0
    if args[0] == "image":
        assert args[1] in {"ls", "inspect"}, "the fixture image must not be refreshed"
    else:
        assert args[0] in {"ps", "inspect", "run", "create", "rm", "cp", "top", "start", "logs", "exec"}
    if args[0] == "ps":
        assert "name=^/sage-research$" in args
    mapped = [args[0]]
    if args[0] in {"run", "create"}:
        mapped.extend(["--label", f"sage-update-test={prefix}"])
    i = 1
    while i < len(args):
        arg = args[i]
        if arg == "--publish" or (arg == "--mount" and args[i + 1].startswith("type=bind,")):
            i += 2
            continue
        if arg == IMAGE:
            arg = image
        elif arg == f"reference={IMAGE}":
            arg = f"reference={image}"
        elif arg == "sage-research":
            arg = prefix
        elif arg == "name=^/sage-research$":
            arg = f"name=^/{prefix}$"
        elif arg.startswith("type=volume,src="):
            volume, destination = arg.removeprefix("type=volume,src=").split(",", 1)
            assert volume in VOLUMES
            arg = f"type=volume,src={prefix}-{volume},{destination}"
        mapped.append(arg)
        i += 1
    if mapped[0] in {"rm", "start", "logs", "top", "inspect"}:
        target = mapped[-1]
        assert docker("inspect", "--format", '{{index .Config.Labels "sage-update-test"}}', target, env=env) == prefix
    if mapped[0] == "cp":
        source = mapped[1].split(":", 1)[0]
        assert docker("inspect", "--format", '{{index .Config.Labels "sage-update-test"}}', source, env=env) == prefix
    if mapped[0] == "exec":
        assert prefix in mapped
    return subprocess.run([env["FIXTURE_DOCKER"], *mapped], env=env, check=False).returncode


def make_image(tmp_path: Path, env: dict[str, str]) -> str:
    rootfs = tmp_path / "rootfs"
    (rootfs / "bin").mkdir(parents=True)
    busybox = shutil.which("busybox")
    assert busybox is not None, "the Docker fixture requires a static BusyBox executable"
    shutil.copy(busybox, rootfs / "bin" / "busybox")
    for applet in ("sh", "sleep", "mkdir", "rm", "cp"):
        (rootfs / "bin" / applet).symlink_to("busybox")
    bash = rootfs / "bin" / "bash"
    bash.write_text('#!/bin/sh\nexec /bin/sh "$@"\n')
    bash.chmod(0o755)

    git_env = env | {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    origin = tmp_path / "origin"
    subprocess.run(["git", "init", "-q", str(origin)], env=git_env, check=True)
    (origin / "README").write_text("Sage source fixture\n")
    subprocess.run(["git", "-C", str(origin), "add", "README"], env=git_env, check=True)
    subprocess.run(["git", "-C", str(origin), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.com", "commit", "-qm", "source"], env=git_env, check=True)
    revision = subprocess.check_output(["git", "-C", str(origin), "rev-parse", "HEAD"], text=True, env=git_env).strip()
    tree = rootfs / "sage"
    subprocess.run(["git", "clone", "-q", "--no-hardlinks", str(origin), str(tree)], env=git_env, check=True)
    (tree / ".venv" / "bin").mkdir(parents=True)
    sage = tree / ".venv" / "bin" / "sage"
    sage.write_text("#!/bin/sh\necho 1\n")
    sage.chmod(0o755)
    (tree / "builddir").mkdir()
    (tree / "builddir" / "image-product").write_text("built\n")
    for record in PRODUCTS[2:]:
        (tree / record).write_text(revision + "\n")
    (rootfs / "repos" / "example").mkdir(parents=True)
    (rootfs / "repos" / "example" / "README").write_text("repo\n")
    (rootfs / "root" / ".julia").mkdir(parents=True)
    (rootfs / "opt" / "julia-depot" / "environments" / "fixture").mkdir(parents=True)
    archive = tmp_path / "image.tar"

    def root_owned(member: tarfile.TarInfo) -> tarfile.TarInfo:
        member.uid = member.gid = 0
        member.uname = member.gname = "root"
        return member

    with tarfile.open(archive, "w") as output:
        output.add(rootfs, arcname=".", filter=root_owned)
    docker(
        "import", "--change", f"LABEL org.opencontainers.image.revision={revision}", "--change", 'CMD ["/bin/sleep", "infinity"]', str(archive), env["FIXTURE_IMAGE"], env=env
    )
    return revision


def executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(0o755)


def test_fresh_volume_records_seeded_image_and_does_not_recopy(tmp_path: Path) -> None:
    host_home = Path.home()
    prefix = f"sage-update-test-{uuid4().hex}"
    home = tmp_path / "home"
    (home / "bin").mkdir(parents=True)
    (home / "gitclones").mkdir()
    env = dict(
        os.environ,
        DOCKER_HOST=f"unix:///run/user/{os.getuid()}/docker.sock",
        FIXTURE_DOCKER=str(host_home / "bin" / "docker"),
        FIXTURE_PREFIX=prefix,
        FIXTURE_IMAGE=f"{prefix}:test",
        HOME=str(home),
        PATH=f"{home / 'bin'}:{os.environ['PATH']}",
    )
    volumes = home / ".local" / "share" / "docker" / "volumes"
    volumes.mkdir(parents=True)
    actual_volumes = Path(docker("info", "--format", "{{.DockerRootDir}}", env=env)) / "volumes"
    for name in VOLUMES:
        (volumes / name).symlink_to(actual_volumes / f"{prefix}-{name}")
    executable(home / "bin" / "docker", f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(Path(__file__).resolve()))} "$@"\n')
    executable(
        home / "bin" / "curl",
        '#!/bin/sh\ncase "$*" in\n  *"/token?"*) printf \'{"token":"fixture"}\\n\';;\n'
        '  *"/manifests/"*) printf \'docker-content-digest: %s\\r\\n\' "$FIXTURE_DIGEST";;\n  *) exit 1;;\nesac\n',
    )
    executable(home / "bin" / "trash", '#!/bin/sh\nset -eu\nmkdir -p "$HOME/trash"\nmv "$1" "$HOME/trash/"\n')
    launcher = home / "sage-docker-update"
    launcher.symlink_to(ROOT / "scripts" / "sage-docker")
    try:
        revision = make_image(tmp_path, env)
        env["FIXTURE_DIGEST"] = docker("image", "inspect", "--format", "{{.Id}}", env["FIXTURE_IMAGE"], env=env)
        tree_volume = volumes / "sage-tree"
        assert f"{prefix}-sage-tree" not in docker("volume", "ls", "--format", "{{.Name}}", env=env).splitlines()
        marker = tree_volume / "image-revision"
        tree = tree_volume / "_data"

        def update() -> None:
            result = subprocess.run([str(launcher)], env=env, capture_output=True, text=True, check=False)
            assert result.returncode == 0, result.stdout + result.stderr
            assert result.stdout.splitlines()[-1] == "1"

        update()
        assert marker.read_text() == revision + "\n"
        assert (tree / "builddir" / "image-product").read_text() == "built\n"
        assert subprocess.check_output(["git", "-C", str(tree), "rev-parse", "HEAD"], env=env, text=True).strip() == revision
        first_container = docker("inspect", "--format", "{{.Id}}", prefix, env=env)
        sentinel = tree / ".venv" / "local-product"
        sentinel.write_text("existing product\n")
        update()
        assert sentinel.read_text() == "existing product\n"
        assert not (home / "trash").exists()
        assert docker("inspect", "--format", "{{.Id}}", prefix, env=env) == first_container
        assert marker.read_text() == revision + "\n"

        marker.unlink()
        docker("rm", "-f", prefix, env=env)
        update()
        assert marker.read_text() == revision + "\n"
        assert not sentinel.exists()
        assert (home / "trash" / ".venv" / "local-product").read_text() == "existing product\n"
        assert (tree / "builddir" / "image-product").read_text() == "built\n"
    finally:
        containers = docker("ps", "-aq", "--filter", f"label=sage-update-test={prefix}", env=env).splitlines()
        if containers:
            docker("rm", "-f", *containers, env=env)
        existing = set(docker("volume", "ls", "--format", "{{.Name}}", env=env).splitlines())
        for name in VOLUMES:
            if f"{prefix}-{name}" in existing:
                docker("volume", "rm", f"{prefix}-{name}", env=env)
        if env["FIXTURE_IMAGE"] in docker("image", "ls", "--format", "{{.Repository}}:{{.Tag}}", env=env).splitlines():
            docker("image", "rm", env["FIXTURE_IMAGE"], env=env)


if __name__ == "__main__":
    sys.exit(namespaced_docker(sys.argv[1:]))
