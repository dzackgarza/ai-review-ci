"""Behavioral tests for the shipped Ruff configuration."""

import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUFF_CONFIG = ROOT / "tool-configs" / "ruff-global.toml"
FIXTURE = pathlib.Path(__file__).resolve().parent / "fixtures" / "ruff" / "broad_exceptions.py"


def test_broad_exception_rules_preserve_handlers_that_raise() -> None:
    result = subprocess.run(
        [
            "uvx",
            "ruff",
            "check",
            "--config",
            str(RUFF_CONFIG),
            "--output-format=json",
            str(FIXTURE),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    findings = json.loads(result.stdout)
    actual = {(finding["code"], finding["location"]["row"]) for finding in findings}
    assert actual == {("BLE001", 7), ("E722", 14), ("BLE001", 21)}
