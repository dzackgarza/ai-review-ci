"""Real scanner output keeps heuristic findings visible without declaring a defect."""

import json
import os
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_real_suffix_tripwire_and_hard_errors(tmp_path: Path) -> None:
    rules = yaml.safe_load((ROOT / "tool-configs/semgrep.yml").read_text())["rules"]
    config = tmp_path / "rules.yml"
    config.write_text(yaml.safe_dump({"rules": [r for r in rules if r["id"] in ("lean-shim-suffix-decl", "lean-no-axiom")]}))
    project = tmp_path / "caller"
    project.mkdir()
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    source = project / "packet.lean"
    source.write_bytes((ROOT / "tests/fixtures/semgrep/engineering_packet.lean").read_bytes())
    report = project / "scan.json"
    base = project / "base.json"
    base.write_text('{"results":[],"errors":[]}')

    def scan() -> dict:
        result = subprocess.run(
            ["uvx", "--from", "semgrep", "semgrep", "scan", "--config", str(config), "--scan-unknown-extensions", "--no-git-ignore", "--json", str(source)],
            cwd=project,
            capture_output=True,
            text=True,
            check=True,
        )
        report.write_text(result.stdout)
        return json.loads(result.stdout)

    def full_gate() -> subprocess.CompletedProcess:
        return subprocess.run(
            ["python3", str(ROOT / "tool-artifacts/scripts/semgrep_exceptions.py"), str(ROOT / "tool-configs/semgrep-exceptions.toml"), str(report)],
            cwd=project,
            capture_output=True,
            text=True,
        )

    def diff_gate() -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                "python3",
                str(ROOT / "tool-artifacts/scripts/semgrep_diff_gate.py"),
                "--base-json",
                str(base),
                "--head-json",
                str(report),
                "--base-root",
                str(project),
                "--head-root",
                str(project),
            ],
            cwd=project,
            capture_output=True,
            text=True,
        )

    engineering = scan()
    assert len(engineering["results"]) == 1
    assert engineering["results"][0]["extra"]["severity"] == "WARNING"
    assert full_gate().returncode == 0
    assert json.loads(report.read_text())["results"] == engineering["results"]
    assert diff_gate().returncode == 0

    source.write_text("structure DiscrepancyData where\n  coefficient : Nat\n")
    mathematical = scan()
    assert len(mathematical["results"]) == 1
    assert mathematical["results"][0]["extra"]["severity"] == "WARNING"
    assert full_gate().returncode == 0
    assert json.loads(report.read_text())["results"] == mathematical["results"]

    source.write_text("axiom inventedLaw : True\n")
    hard_error = scan()
    assert len(hard_error["results"]) == 1
    assert hard_error["results"][0]["extra"]["severity"] == "ERROR"
    assert full_gate().returncode == 1
    assert diff_gate().returncode == 1

    # Malformed scanner metadata cannot turn a required finding into success.
    del hard_error["results"][0]["extra"]["severity"]
    report.write_text(json.dumps(hard_error))
    assert full_gate().returncode != 0
    assert diff_gate().returncode != 0


def test_full_consumer_rejects_malformed_reports_without_rewriting(tmp_path: Path) -> None:
    exceptions = tmp_path / "exceptions.toml"
    exceptions.write_text("exception = []\n")
    report = tmp_path / "scan.json"
    malformed = [
        {"results": {}},
        {"results": ""},
        {"results": [{"extra": {"severity": "WARNING"}}]},
    ]
    for payload in malformed:
        original = json.dumps(payload)
        report.write_text(original)
        result = subprocess.run(
            ["python3", str(ROOT / "tool-artifacts/scripts/semgrep_exceptions.py"), str(exceptions), str(report)], cwd=tmp_path, capture_output=True, text=True
        )
        assert result.returncode != 0, result.stdout
        assert report.read_text() == original


def test_real_caller_retains_exact_revision_warning_report(tmp_path: Path) -> None:
    project = tmp_path / "caller"
    project.mkdir()
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    (project / "packet.lean").write_text("structure ComputationData where\n  encoded : String\n")
    subprocess.run(["git", "add", "."], cwd=project, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "caller",
        ],
        cwd=project,
        check=True,
    )
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=project, text=True).strip()
    result = subprocess.run(
        ["just", "-f", str(ROOT / "justfiles/shared.just"), "-d", ".", "_semgrep"],
        cwd=project,
        capture_output=True,
        text=True,
        env={k: v for k, v in os.environ.items() if k != "DIFF_COVER_BASE"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = project / ".git/ai-review-ci/semgrep" / revision / "head.json"
    payload = json.loads(report.read_text())
    finding = next(r for r in payload["results"] if r["check_id"].endswith("lean-shim-suffix-decl"))
    assert finding["path"] == "packet.lean"
    assert finding["extra"]["severity"] == "WARNING"
    assert subprocess.check_output(["git", "status", "--porcelain"], cwd=project, text=True) == ""


def test_real_caller_without_commit_still_scans(tmp_path: Path) -> None:
    for initialize_git in (False, True):
        project = tmp_path / str(initialize_git)
        project.mkdir()
        if initialize_git:
            subprocess.run(["git", "init", "-q", str(project)], check=True)
        (project / "unsafe.lean").write_text("axiom fabricated : True\n")
        result = subprocess.run(
            ["just", "-f", str(ROOT / "justfiles/shared.just"), "-d", ".", "_semgrep"],
            cwd=project,
            capture_output=True,
            text=True,
            env={k: v for k, v in os.environ.items() if k != "DIFF_COVER_BASE"},
        )
        assert "lean-no-axiom" in result.stdout + result.stderr
        assert result.returncode != 0


def _committed_caller(project: Path) -> str:
    project.mkdir()
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    (project / "README.md").write_text("Caller fixture\n")
    subprocess.run(["git", "add", "."], cwd=project, check=True)
    subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "base"],
        cwd=project,
        check=True,
    )
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=project, text=True).strip()


def _commit_fixture(project: Path) -> str:
    subprocess.run(["git", "add", "."], cwd=project, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "change",
        ],
        cwd=project,
        check=True,
    )
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=project, text=True).strip()


def test_ci_diff_recipe_respects_warning_and_error(tmp_path: Path) -> None:
    project = tmp_path / "caller"
    base = _committed_caller(project)
    subprocess.run(["git", "update-ref", "refs/remotes/origin/main", base], cwd=project, check=True)
    for source, blocked in [("structure DiscrepancyData where\n  coefficient : Nat\n", False), ("axiom fabricated : True\n", True)]:
        (project / "example.lean").write_text(source)
        revision = _commit_fixture(project)
        result = subprocess.run(
            ["just", "-f", str(ROOT / "ci/runner.just"), "-d", ".", "check-semantic-diff", "main"],
            cwd=project,
            env={**os.environ, "GITHUB_WORKSPACE": str(project)},
            capture_output=True,
            text=True,
        )
        assert (result.returncode != 0) == blocked, result.stdout + result.stderr
        report = project / ".git/ai-review-ci/semgrep" / revision / "head.json"
        payload = json.loads(report.read_text())
        expected = "lean-no-axiom" if blocked else "lean-shim-suffix-decl"
        assert any(r["check_id"].endswith(expected) for r in payload["results"])
        assert payload["errors"] == []


def test_empty_diff_scan_has_report_but_invalid_base_fails(tmp_path: Path) -> None:
    project = tmp_path / "caller"
    base = _committed_caller(project)
    (project / "justfile").write_text("hello:\n    echo hello\n")
    revision = _commit_fixture(project)
    command = ["just", "-f", str(ROOT / "justfiles/shared.just"), "-d", ".", "_semgrep"]
    result = subprocess.run(command, cwd=project, env={**os.environ, "DIFF_COVER_BASE": base}, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    report = project / ".git/ai-review-ci/semgrep" / revision / "head.json"
    payload = json.loads(report.read_text())
    assert payload["results"] == []
    assert payload["errors"] == []
    assert payload["ai_review_ci"]["evaluation"] == "empty-domain"
    assert payload["ai_review_ci"]["targets"] == []
    assert payload["ai_review_ci"]["base"] == base
    result = subprocess.run(command, cwd=project, env={**os.environ, "DIFF_COVER_BASE": "nonexistent-revision"}, capture_output=True, text=True)
    assert result.returncode != 0
    assert not report.exists()


def test_consumers_reject_failed_scan_even_without_findings(tmp_path: Path) -> None:
    report = tmp_path / "failed.json"
    report.write_text(json.dumps({"results": [], "errors": [{"level": "error", "message": "scan failed"}]}))
    base = tmp_path / "base.json"
    base.write_text('{"results": [], "errors": []}')
    commands = [
        ["python3", str(ROOT / "tool-artifacts/scripts/semgrep_exceptions.py"), str(ROOT / "tool-configs/semgrep-exceptions.toml"), str(report)],
        [
            "python3",
            str(ROOT / "tool-artifacts/scripts/semgrep_diff_gate.py"),
            "--base-json",
            str(base),
            "--head-json",
            str(report),
            "--base-root",
            str(tmp_path),
            "--head-root",
            str(tmp_path),
        ],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
        assert result.returncode != 0


def test_diff_without_merge_base_is_failed_evaluation(tmp_path: Path) -> None:
    project = tmp_path / "caller"
    original = _committed_caller(project)
    subprocess.run(["git", "checkout", "--orphan", "disconnected"], cwd=project, check=True, capture_output=True)
    (project / "README.md").write_text("Unrelated history\n")
    base = _commit_fixture(project)
    subprocess.run(["git", "checkout", "--detach", original], cwd=project, check=True, capture_output=True)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=project, text=True).strip()
    result = subprocess.run(
        ["just", "-f", str(ROOT / "justfiles/shared.just"), "-d", ".", "_semgrep"], cwd=project, env={**os.environ, "DIFF_COVER_BASE": base}, capture_output=True, text=True
    )
    assert result.returncode != 0, result.stdout + result.stderr
    assert not (project / ".git/ai-review-ci/semgrep" / revision / "head.json").exists()


def test_native_partial_parsing_diagnostics_reach_review(tmp_path: Path) -> None:
    project = tmp_path / "caller"
    _committed_caller(project)
    workflow = project / ".github/workflows/interpolation.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("""name: native diagnostic fixture
on: push
jobs:
  inspect:
    runs-on: ubuntu-latest
    steps:
      - run: |
          if git clone "https://x-access-token:${{ github.token }}@github.com/${{ github.repository }}" rejections; then :
          else
            git init --quiet rejections
          fi
""")
    revision = _commit_fixture(project)
    result = subprocess.run(
        ["just", "-f", str(ROOT / "justfiles/shared.just"), "-d", ".", "_semgrep"],
        cwd=project,
        env={k: v for k, v in os.environ.items() if k != "DIFF_COVER_BASE"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    reports = project / ".git/ai-review-ci/semgrep" / revision
    raw = json.loads((reports / "head.raw.json").read_text())
    reviewed = json.loads((reports / "head.json").read_text())
    assert raw["errors"]
    assert all(d["level"] == "warn" for d in raw["errors"])
    assert reviewed["errors"] == raw["errors"]
    for diagnostic in reviewed["errors"]:
        assert json.dumps(diagnostic, sort_keys=True) in result.stdout


def test_ci_diff_distinguishes_replaced_hard_error_with_equal_counts(tmp_path: Path) -> None:
    project = tmp_path / "caller"
    _committed_caller(project)
    source = project / "law.lean"
    source.write_text("axiom existing : True\n")
    base = _commit_fixture(project)
    subprocess.run(["git", "update-ref", "refs/remotes/origin/main", base], cwd=project, check=True)
    command = ["just", "-f", str(ROOT / "ci/runner.just"), "-d", ".", "check-semantic-diff", "main"]
    environment = {**os.environ, "GITHUB_WORKSPACE": str(project), "QC_TIER": "test-ci"}
    source.write_text("-- Shift unchanged source\naxiom existing : True\n")
    _commit_fixture(project)
    unchanged = subprocess.run(command, cwd=project, env=environment, capture_output=True, text=True)
    assert unchanged.returncode == 0, unchanged.stdout + unchanged.stderr
    source.write_text("-- Shift unchanged source\naxiom newlyInvented : False\n")
    revision = _commit_fixture(project)
    replaced = subprocess.run(command, cwd=project, env=environment, capture_output=True, text=True)
    reports = project / ".git/ai-review-ci/semgrep" / revision
    old = json.loads((reports / "base.raw.json").read_text())["results"]
    new = json.loads((reports / "head.raw.json").read_text())["results"]
    assert len(old) == len(new) == 1
    assert old[0]["check_id"] == new[0]["check_id"]
    assert old[0]["path"] == new[0]["path"] == "law.lean"
    assert old[0]["extra"]["message"] == new[0]["extra"]["message"]
    assert replaced.returncode != 0, replaced.stdout + replaced.stderr
