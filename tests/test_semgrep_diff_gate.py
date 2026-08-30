"""Behavioral tests for the CI-tier semgrep diff gate (#366).

The gate compares Semgrep JSON between the base and head trees and fails on new
finding signatures. Semgrep emits a result per *file* for a rule it could not
evaluate — Rust is a Pro-engine language, so the shipped ``rs-*`` rules degrade
to a "requires login" placeholder whenever no SEMGREP_APP_TOKEN is present.

Those placeholders say nothing about the code. Counting them as findings makes
any PR that adds a new file fail for a reason unrelated to its content, which is
what #366 reports.
"""

import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
GATE = ROOT / "tool-artifacts" / "scripts" / "semgrep_diff_gate.py"


def _write(path: pathlib.Path, results: list[dict[str, object]]) -> pathlib.Path:
    path.write_text(json.dumps({"results": results}))
    return path


def _finding(check_id: str, path: str, message: str, lines: str) -> dict[str, object]:
    return {"check_id": check_id, "path": path, "extra": {"message": message, "lines": lines}}


def _run(base: pathlib.Path, head: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", str(GATE), "--base-json", str(base), "--head-json", str(head)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_unevaluated_pro_rules_do_not_fail_a_new_file(tmp_path: pathlib.Path) -> None:
    """A new file that only draws 'requires login' placeholders is not a finding (#366)."""
    base = _write(tmp_path / "base.json", [])
    head = _write(
        tmp_path / "head.json",
        [
            _finding("tool-configs.rs-no-allow-attr", ".envrc", "requires login", "requires login"),
            _finding("tool-configs.rs-no-result-ok", "systemd/unit.service", "requires login", "requires login"),
        ],
    )

    result = _run(base, head)

    assert result.returncode == 0, result.stdout + result.stderr


def test_unevaluated_rules_are_still_reported_as_a_coverage_gap(tmp_path: pathlib.Path) -> None:
    """Dropping them silently would hide that the rs-* rules never ran at all."""
    base = _write(tmp_path / "base.json", [])
    head = _write(
        tmp_path / "head.json",
        [_finding("tool-configs.rs-no-allow-attr", ".envrc", "requires login", "requires login")],
    )

    result = _run(base, head)

    assert "rs-no-allow-attr" in result.stdout, result.stdout


def test_a_real_new_finding_still_fails(tmp_path: pathlib.Path) -> None:
    """The gate must keep failing on findings that describe actual code."""
    base = _write(tmp_path / "base.json", [])
    head = _write(
        tmp_path / "head.json",
        [
            _finding("tool-configs.py-no-dict-get-default", "src/app.py", "POLICY.RUNTIME_DEFAULT", 'cfg.get("k", 1)'),
            _finding("tool-configs.rs-no-allow-attr", ".envrc", "requires login", "requires login"),
        ],
    )

    result = _run(base, head)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "py-no-dict-get-default" in result.stdout, result.stdout


def test_a_finding_present_in_base_is_not_new(tmp_path: pathlib.Path) -> None:
    """Pre-existing findings stay out of the gate; only regressions fail it."""
    existing = _finding(
        "tool-configs.py-no-dict-get-default", "src/app.py", "POLICY.RUNTIME_DEFAULT", 'cfg.get("k", 1)'
    )
    base = _write(tmp_path / "base.json", [existing])
    head = _write(tmp_path / "head.json", [existing])

    result = _run(base, head)

    assert result.returncode == 0, result.stdout + result.stderr
