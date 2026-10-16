import grp
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_group_exec_preserves_large_argument_vector_and_stdin() -> None:
    # Proves the launcher's real sg transport, including quoting and empty argv.
    arguments = ["", "spaces and 'quotes'", "line\nbreak", "$(exit 9)", *[f"{i}:" + "x" * 100 for i in range(3000)]]
    code = "import json,sys; print(json.dumps([sys.argv[1:],sys.stdin.read()])); sys.exit(7)"
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/group-exec"), grp.getgrgid(os.getgid()).gr_name, sys.executable, "-c", code, *arguments],
        input="caller input\n",
        text=True,
        capture_output=True,
    )
    assert result.returncode == 7, result.stdout + result.stderr
    assert json.loads(result.stdout) == [arguments, "caller input\n"]
