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
    expected = "Push syntax: 0 file(s)" if tier == "test-push" else "Staged syntax: 1 file(s)"
    assert expected in result.stdout


def test_push_does_not_inspect_unpublished_staged_edits(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "valid.py").write_text("value = 1\n")
    git(tmp_path, "add", "valid.py")
    git(tmp_path, "-c", "user.name=Test", "-c", "user.email=test@example.com",
        "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "valid")
    (tmp_path / "not_in_push.py").write_text("def broken(:\n")
    git(tmp_path, "add", "not_in_push.py")

    push = subprocess.run([sys.executable, LOCAL, "--mode", "push"],
                          cwd=tmp_path, capture_output=True, text=True)
    assert push.returncode == 0, push.stdout + push.stderr
    # Initial publication checks its committed tree, never its staged overlay.
    assert "Push syntax: 1 file(s)" in push.stdout
    assert "not_in_push.py" not in push.stderr
    assert push.stderr == ""

    commit = subprocess.run([sys.executable, LOCAL],
                            cwd=tmp_path, capture_output=True, text=True)
    assert commit.returncode == 1
    assert "not_in_push.py" in commit.stderr


def test_ci_collects_multiple_failures_without_stopping_and_opt_in_enforces(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_just = fake_bin / "just"
    fake_just.write_text(
        "#!/bin/sh\n"
        "test \"$AI_REVIEW_CI_FAILURE_MODE\" = triage || exit 21\n"
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


@pytest.mark.parametrize("mode", ("direct", "triage"))
@pytest.mark.parametrize(
    "script", ("emit-triage-directive.sh", "emit-test-writing-directive.sh"),
)
def test_qc_diagnostic_notices_never_redirect_implementation(mode: str, script: str) -> None:
    result = subprocess.run(
        [str(ROOT / "tool-artifacts" / "scripts" / script)],
        env={**os.environ, "AI_REVIEW_CI_FAILURE_MODE": mode},
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "QC FAILURE" in result.stdout
    assert "subagent" not in result.stdout.lower()
    assert "TRIAGE REQUIRED" not in result.stdout
    assert "DIRECT REPAIR REQUIRED" not in result.stdout
    assert "MUST" not in result.stdout
    assert "pause only" not in result.stdout
    assert "policy exception" not in result.stdout.lower()


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



def test_ci_retains_hidden_diagnostics_and_fails_if_report_absent() -> None:
    # A success status without the promised triage evidence is infrastructure
    # failure, distinct from the deliberately nonblocking project findings.
    import yaml

    workflow = yaml.safe_load((ROOT / ".github/workflows/_qc.yml").read_text())
    steps = workflow["jobs"]["qc"]["steps"]
    (upload,) = (step for step in steps if step.get("name") == "Retain development diagnostic triage")
    assert upload["with"]["include-hidden-files"] is True
    assert upload["with"]["if-no-files-found"] == "error"


def test_ci_cancels_superseded_same_branch_runs() -> None:
    # Older revisions in a hosted-runner backlog must not consume runner
    # capacity ahead of the current branch revision. Different branches stay
    # independent and reusable workflows do not accidentally cancel callers.
    import yaml

    ci = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    assert ci["concurrency"] == {
        "group": "development-ci-${{ github.ref }}",
        "cancel-in-progress": True,
    }
    reusable = yaml.safe_load((ROOT / ".github/workflows/_qc.yml").read_text())
    assert "concurrency" not in reusable


def test_ci_retains_individual_location_and_test_failures(tmp_path: Path) -> None:
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location("ci_triage_findings", TRIAGE)
    assert spec and spec.loader
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    logfile = tmp_path / "types-and-tests.log"
    logfile.write_text(
        "src/algebra/module.py:17: error: incompatible assignment [assignment]\n"
        "src/algebra/module.py:18: error: another error [no-untyped-def]\n"
        "FAILED tests/test_module.py::test_consistency - AssertionError\n"
    )
    check = module.Check("quality", "debt", "python", "_mypy")
    findings = module.extract_findings(check, logfile, 1)
    assert len(findings) == 3
    assert {(item["location"], item["rule"]) for item in findings} == {
        ("src/algebra/module.py", "assignment"),
        ("src/algebra/module.py", "no-untyped-def"),
        ("tests/test_module.py::test_consistency", ""),
    }
    assert all(item["log"] == logfile.name for item in findings)

    old = {"profile": "sage", "tier": "ci", "generated_at": "old",
           "findings": [findings[0], findings[1]]}
    current = {"profile": "sage", "tier": "ci", "findings": [findings[1], findings[2]]}
    delta = module.compare_findings(current, old)
    assert delta["new"] == [findings[2]["id"]]
    assert delta["persistent"] == [findings[1]["id"]]
    assert delta["resolved"] == [findings[0]["id"]]
    assert module.compare_findings(current, {"profile": "sage", "tier": "ci", "checks": []})["baseline"] == "unavailable"
    assert module.extract_findings(check, logfile, 0) == []
    logfile.write_text("unrecognized tool failure")
    fallback = module.extract_findings(check, logfile, 127)
    assert len(fallback) == 1
    assert fallback[0]["rule"] == "CHECK_FAILED"


def test_manual_push_check_respects_published_branch_baseline(tmp_path: Path) -> None:
    # A branch that is already at its tracked remote must not be compared
    # against origin/main and re-gate old implementation work.
    git(tmp_path, "init", "-q", "-b", "feature")
    (tmp_path / "legacy.py").write_text("def broken(:\n")
    git(tmp_path, "add", "legacy.py")
    subprocess.run(
        ["git", "-C", str(tmp_path), "-c", "user.name=Test",
         "-c", "user.email=test@example.com", "-c", "core.hooksPath=/dev/null",
         "commit", "-q", "-m", "historical source"],
        check=True,
    )
    commit = git(tmp_path, "rev-parse", "HEAD").stdout.decode().strip()
    git(tmp_path, "remote", "add", "origin", str(tmp_path / "unreachable.git"))
    git(tmp_path, "update-ref", "refs/remotes/origin/feature", commit)
    git(tmp_path, "branch", "--set-upstream-to=origin/feature", "feature")

    published = subprocess.run(
        [sys.executable, LOCAL, "--mode", "push"],
        cwd=tmp_path, text=True, capture_output=True,
    )
    assert published.returncode == 0, published.stdout + published.stderr
    assert "Push syntax: 0 file(s)" in published.stdout

    # A new outgoing committed defect is still inspected.
    (tmp_path / "new.py").write_text("def also_broken(:\n")
    git(tmp_path, "add", "new.py")
    subprocess.run(
        ["git", "-C", str(tmp_path), "-c", "user.name=Test",
         "-c", "user.email=test@example.com", "-c", "core.hooksPath=/dev/null",
         "commit", "-q", "-m", "new regression"],
        check=True,
    )
    failed = subprocess.run(
        [sys.executable, LOCAL, "--mode", "push"],
        cwd=tmp_path, text=True, capture_output=True,
    )
    assert failed.returncode == 1
    assert "new.py" in failed.stderr
    assert "legacy.py" not in failed.stderr
