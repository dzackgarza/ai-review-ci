"""A Lean checkout reached through its ~/gitclones link builds against the image's shared Mathlib."""

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
CHECKOUT = Path.home() / "gitclones" / "lean-cas-dsl"


def test_lake_from_host_link_imports_shared_mathlib(tmp_path: Path) -> None:
    lake = tmp_path / "lake"
    lake.symlink_to(ROOT / "scripts" / "sage-docker")

    result = subprocess.run(
        [str(lake), "env", "lean", "--stdin"],
        cwd=CHECKOUT,
        input="import Mathlib.Data.Nat.Basic\n#eval (2 + 2 : Nat)\n",
        text=True, capture_output=True, check=False, timeout=600,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "4"
