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
    config.write_text(yaml.safe_dump({"rules": [r for r in rules if r["id"] in
                                              ("lean-shim-suffix-decl", "lean-no-axiom")]}))
    project = tmp_path / "caller"
    project.mkdir()
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    source = project / "packet.lean"
    source.write_bytes((ROOT / "tests/fixtures/semgrep/engineering_packet.lean").read_bytes())
    report = project / "scan.json"
    base = project / "base.json"
    base.write_text('{"results":[]}')

    def scan() -> dict:
        result = subprocess.run(
            ["uvx", "--from", "semgrep", "semgrep", "scan", "--config", str(config),
             "--scan-unknown-extensions", "--no-git-ignore", "--json", str(source)],
            cwd=project, capture_output=True, text=True, check=True)
        report.write_text(result.stdout)
        return json.loads(result.stdout)

    def full_gate() -> subprocess.CompletedProcess:
        return subprocess.run(
            ["python3", str(ROOT / "tool-artifacts/scripts/semgrep_exceptions.py"),
             str(ROOT / "tool-configs/semgrep-exceptions.toml"), str(report)],
            cwd=project, capture_output=True, text=True)

    def diff_gate() -> subprocess.CompletedProcess:
        return subprocess.run(
            ["python3", str(ROOT / "tool-artifacts/scripts/semgrep_diff_gate.py"),
             "--base-json", str(base), "--head-json", str(report)],
            cwd=project, capture_output=True, text=True)

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
    exceptions = tmp_path / 'exceptions.toml'
    exceptions.write_text('exception = []\n')
    report = tmp_path / 'scan.json'
    malformed = [
        {'results': {}},
        {'results': ''},
        {'results': [{'extra': {'severity': 'WARNING'}}]},
    ]
    for payload in malformed:
        original = json.dumps(payload)
        report.write_text(original)
        result = subprocess.run(
            ['python3', str(ROOT / 'tool-artifacts/scripts/semgrep_exceptions.py'),
             str(exceptions), str(report)], cwd=tmp_path, capture_output=True, text=True)
        assert result.returncode != 0, result.stdout
        assert report.read_text() == original


def test_real_caller_retains_exact_revision_warning_report(tmp_path: Path) -> None:
    project = tmp_path / 'caller'
    project.mkdir()
    subprocess.run(['git', 'init', '-q', str(project)], check=True)
    (project / 'packet.lean').write_text('structure ComputationData where\n  encoded : String\n')
    subprocess.run(['git', 'add', '.'], cwd=project, check=True)
    subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false',
                    '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                    'commit', '-qm', 'caller'], cwd=project, check=True)
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=project, text=True).strip()
    result = subprocess.run(['just', '-f', str(ROOT / 'justfiles/shared.just'), '-d', '.',
                             '_semgrep'], cwd=project, capture_output=True, text=True,
                            env={k: v for k, v in os.environ.items() if k != 'DIFF_COVER_BASE'})
    assert result.returncode == 0, result.stdout + result.stderr
    report = project / '.git/ai-review-ci/semgrep' / revision / 'head.json'
    payload = json.loads(report.read_text())
    finding = next(r for r in payload['results'] if r['check_id'].endswith('lean-shim-suffix-decl'))
    assert finding['path'] == 'packet.lean'
    assert finding['extra']['severity'] == 'WARNING'
    assert subprocess.check_output(['git', 'status', '--porcelain'], cwd=project, text=True) == ''


def test_real_caller_without_commit_still_scans(tmp_path: Path) -> None:
    for initialize_git in (False, True):
        project = tmp_path / str(initialize_git)
        project.mkdir()
        if initialize_git:
            subprocess.run(['git', 'init', '-q', str(project)], check=True)
        (project / 'unsafe.lean').write_text('axiom fabricated : True\n')
        result = subprocess.run(['just', '-f', str(ROOT / 'justfiles/shared.just'), '-d', '.',
                                 '_semgrep'], cwd=project, capture_output=True, text=True,
                                env={k: v for k, v in os.environ.items() if k != 'DIFF_COVER_BASE'})
        assert 'lean-no-axiom' in result.stdout + result.stderr
        assert result.returncode != 0
