"""The host's jupyter command serves the research container's kernels on 127.0.0.1."""

import json
from pathlib import Path
import secrets
import subprocess
import time
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
PORT = 8888


def _kernelspecs(token: str) -> dict[str, dict[str, str]] | None:
    url = f"http://127.0.0.1:{PORT}/api/kernelspecs?token={token}"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return json.load(response)["kernelspecs"]
    except (urllib.error.URLError, ConnectionError, TimeoutError):
        return None


def test_jupyter_server_lists_container_kernels(tmp_path: Path) -> None:
    jupyter = tmp_path / "jupyter"
    jupyter.symlink_to(ROOT / "scripts" / "sage-docker")
    token = secrets.token_hex(16)

    server = subprocess.Popen(
        [str(jupyter), "server", f"--IdentityProvider.token={token}"],
        cwd=Path.home(), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        specs = None
        deadline = time.monotonic() + 120
        while specs is None and server.poll() is None and time.monotonic() < deadline:
            time.sleep(1)
            specs = _kernelspecs(token)
    finally:
        server.terminate()
        output, _ = server.communicate(timeout=30)

    assert specs is not None, output
    assert {"sagemath", "julia"} <= set(specs), sorted(specs)
    assert specs["sagemath"]["spec"]["argv"][0].startswith("/sage/.venv/"), specs["sagemath"]
    assert specs["julia"]["spec"]["argv"][0].startswith("/opt/julia/"), specs["julia"]
