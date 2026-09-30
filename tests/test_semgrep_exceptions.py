"""An owner-granted semgrep exception drops exactly its rule, path and repository while its issue
is open (#450). The issue states are read from the public GitHub API."""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "tool-artifacts" / "scripts" / "semgrep_exceptions.py"
RULE = "yaml.github-actions.security.pull-request-target-code-checkout.pull-request-target-code-checkout"
PATH = ".github/workflows/custodian-review.yml"
OPEN_ISSUE = 450
CLOSED_ISSUE = 447


def _gate(tmp_path: Path, origin: str, issue: int, path: str) -> tuple[int, list[dict[str, str]]]:
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(["git", "remote", "add", "origin", origin], cwd=project, check=True)
    exceptions = tmp_path / "semgrep-exceptions.toml"
    exceptions.write_text(
        f'[[exception]]\nrepository = "dzackgarza/lean-cas-dsl"\npath = "{PATH}"\n'
        f'rule = "{RULE}"\nissue = {issue}\n'
    )
    findings = tmp_path / "semgrep.json"
    findings.write_text(json.dumps({"results": [{"check_id": RULE, "path": path, "start": {"line": 27}}]}))
    proc = subprocess.run([str(SCRIPT), str(exceptions), str(findings)], cwd=project, capture_output=True, text=True)
    return proc.returncode, json.loads(findings.read_text())["results"]


def test_open_issue_drops_the_excepted_finding(tmp_path: Path) -> None:
    assert _gate(tmp_path, "git@github.com:dzackgarza/lean-cas-dsl.git", OPEN_ISSUE, PATH) == (0, [])


@pytest.mark.parametrize(
    ("origin", "issue", "path"),
    [
        ("git@github.com:dzackgarza/lean-cas-dsl.git", CLOSED_ISSUE, PATH),
        ("git@github.com:dzackgarza/lean-cas-dsl.git", OPEN_ISSUE, ".github/workflows/other.yml"),
        ("https://github.com/someone/lean-cas-dsl", OPEN_ISSUE, PATH),
    ],
    ids=["closed-issue", "other-path", "other-repository"],
)
def test_the_finding_stays_otherwise(tmp_path: Path, origin: str, issue: int, path: str) -> None:
    rc, results = _gate(tmp_path, origin, issue, path)
    assert rc == 1
    assert [r["path"] for r in results] == [path]
