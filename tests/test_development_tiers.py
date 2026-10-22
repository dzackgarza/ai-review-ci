"""Regression checks for the development/publication versus CI-debt boundary."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "scripts" / "local-check.py"
TRIAGE = ROOT / "scripts" / "ci-triage.py"


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def test_local_gate_reads_index_not_worktree_and_checks_only_syntax(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q")
    source = tmp_path / "implementation.py"
    source.write_text("def untyped(x): return x\n")
    git(tmp_path, "add", "implementation.py")
    # The unstaged file is invalid; the candidate commit is syntactically valid.
    source.write_text("def broken(:\n")
    valid = subprocess.run([sys.executable, LOCAL], cwd=tmp_path, capture_output=True, text=True)
    assert valid.returncode == 0, valid.stderr
    assert "1 file(s)" in valid.stdout
    # The staged file now has an actual parse defect.
    git(tmp_path, "add", "implementation.py")
    invalid = subprocess.run([sys.executable, LOCAL], cwd=tmp_path, capture_output=True, text=True)
    assert invalid.returncode == 1
    assert "implementation.py" in invalid.stderr


def test_local_gate_catches_malformed_staged_config_not_typing_or_style(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q")
    (tmp_path / "code.py").write_text("def f( x ) :\n return {'unused': 1}\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'valid'\n")
    git(tmp_path, "add", ".")
    ok = subprocess.run([sys.executable, LOCAL], cwd=tmp_path, capture_output=True, text=True)
    assert ok.returncode == 0, ok.stderr
    (tmp_path / "pyproject.toml").write_text("[project\n")
    git(tmp_path, "add", "pyproject.toml")
    bad = subprocess.run([sys.executable, LOCAL], cwd=tmp_path, capture_output=True, text=True)
    assert bad.returncode == 1
    assert "pyproject.toml" in bad.stderr


@pytest.mark.parametrize(
    "profile", ["python", "sage", "rust", "bun", "bun-python", "lean", "docs-and-configs", "qc-tooling"]
)
@pytest.mark.parametrize("tier", ["test-commit", "test-push"])
def test_local_tiers_require_no_toolchain_or_suite(tmp_path: Path, profile: str, tier: str) -> None:
    git(tmp_path, "init", "-q")
    (tmp_path / "scratch.py").write_text("def f(a): return a\n")
    git(tmp_path, "add", "scratch.py")
    result = subprocess.run(
        ["just", "-f", str(ROOT / "justfiles" / f"{profile}.just"), "-d", str(tmp_path), tier],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Staged syntax: 1 file(s)" in result.stdout


def test_ci_collects_multiple_failures_without_stopping_and_opt_in_enforces(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_just = fake_bin / "just"
    fake_just.write_text(
        "#!/bin/sh\n"
        "case \" $* \" in\n"
        "  *' _pytest_with_coverage '*) echo 'assertion failed'; exit 7;;\n"
        "  *' _mypy '*) echo 'type debt'; exit 8;;\n"
        "  *) echo 'check ran'; exit 0;;\n"
        "esac\n"
    )
    fake_just.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = str(fake_bin) + os.pathsep + env["PATH"]
    report_dir = tmp_path / "diagnostics"
    args = [sys.executable, TRIAGE, "python", "--report-dir", str(report_dir)]
    result = subprocess.run(args, env=env, cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads((report_dir / "results.json").read_text())
    statuses = {record["id"]: record for record in payload["checks"]}
    assert statuses["python-tests"]["exit_code"] == 7
    assert statuses["python-types"]["exit_code"] == 8
    assert statuses["python-coverage"]["status"] == "passed"
    assert statuses["ai-slop"]["status"] == "passed"
    assert payload["failed_checks"] == 2
    assert "assertion failed" in (report_dir / "python-tests.log").read_text()
    assert "type debt" in (report_dir / "python-types.log").read_text()
    enforced = subprocess.run(args + ["--enforce"], env=env, cwd=tmp_path, capture_output=True, text=True)
    assert enforced.returncode == 1
    env["QC_ENFORCE"] = "true"
    stabilized = subprocess.run(args, env=env, cwd=tmp_path, capture_output=True, text=True)
    assert stabilized.returncode == 1


def test_development_ci_runs_full_suite_and_debt_independently() -> None:
    # A test-suite failure cannot hide later debt results, and local recipes
    # never mention suites, typing or formatting.
    from importlib.util import module_from_spec, spec_from_file_location
    import sys

    spec = spec_from_file_location("ci_triage", TRIAGE)
    assert spec and spec.loader
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    for profile in ("python", "sage", "bun", "rust", "lean"):
        checks = module.ci_checks(profile)
        assert any(x.category == "correctness" for x in checks)
        assert any(x.category == "debt" for x in checks)
        assert len({x.id for x in checks}) == len(checks)


def test_burndown_tracks_new_persistent_and_resolved_findings() -> None:
    from importlib.util import module_from_spec, spec_from_file_location
    import sys

    spec = spec_from_file_location("ci_triage_burndown", TRIAGE)
    assert spec and spec.loader
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    old = {
        "profile": "python", "tier": "ci", "generated_at": "previous-run",
        "checks": [{"id": name, "status": "failed"} for name in ("types", "tests")],
    }
    new = {
        "profile": "python", "tier": "ci",
        "checks": [{"id": "types", "status": "failed"}, {"id": "tests", "status": "passed"},
                   {"id": "format", "status": "failed"}],
    }
    assert module.compare_results(new, old) == {
        "baseline": "previous-run", "open": ["format", "types"],
        "new": ["format"], "persistent": ["types"], "resolved": ["tests"],
    }
    assert module.compare_results(new, None) == {
        "baseline": "unavailable", "open": ["format", "types"],
        "new": [], "persistent": [], "resolved": [],
    }
