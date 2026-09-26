"""Policy tests for the shared Ruff configuration."""

import pathlib
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_sage_monodict_unsafe_fixes_are_unfixable() -> None:
    config = tomllib.loads((ROOT / "tool-configs" / "ruff-global.toml").read_text())
    assert set(config["lint"]["unfixable"]) >= {"SIM401", "PERF102"}
