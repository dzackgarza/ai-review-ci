"""Real-boundary proof for the qc_xfail_issues collection gate.

Each case runs a real pytest subprocess with ``-p qc_xfail_issues`` in a real git repository
whose origin is this repository on GitHub, so issue states come from the live public API:
#188 (the work-tree ledger) is open and #1 is closed.
"""

import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "tool-artifacts" / "pytest_plugins"


@pytest.fixture
def project(tmp_path: pathlib.Path) -> pathlib.Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin", "https://github.com/dzackgarza/ai-review-ci.git"], check=True)
    return tmp_path


def _run(project: pathlib.Path, body: str) -> subprocess.CompletedProcess[str]:
    (project / "test_case.py").write_text("import pytest\n\n" + body)
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "qc_xfail_issues", "-p", "no:cacheprovider", "-q", str(project)],
        cwd=project,
        env={"PYTHONPATH": str(PLUGINS), "PATH": "/usr/bin:/bin"},
        text=True,
        capture_output=True,
        check=False,
    )


def test_strict_xfail_citing_an_open_issue_is_sanctioned(project: pathlib.Path) -> None:
    result = _run(project, '@pytest.mark.xfail(reason="capability owned by #188", strict=True)\ndef test_red():\n    assert False\n')

    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 xfailed" in result.stdout


def test_xfail_citing_a_closed_issue_fails_collection(project: pathlib.Path) -> None:
    result = _run(project, '@pytest.mark.xfail(reason="owned by #1", strict=True)\ndef test_red():\n    assert False\n')

    assert result.returncode != 0
    assert "#1 is closed" in result.stderr


def test_strict_xfail_that_passes_fails_the_run(project: pathlib.Path) -> None:
    result = _run(project, '@pytest.mark.xfail(reason="owned by #188", strict=True)\ndef test_now_green():\n    assert True\n')

    assert result.returncode != 0
    assert "XPASS(strict)" in result.stdout


def test_non_strict_xfail_is_rejected(project: pathlib.Path) -> None:
    result = _run(project, '@pytest.mark.xfail(reason="owned by #188")\ndef test_red():\n    assert False\n')

    assert result.returncode != 0
    assert "must be strict=True" in result.stderr


def test_xfail_without_an_issue_is_rejected(project: pathlib.Path) -> None:
    result = _run(project, '@pytest.mark.xfail(reason="broken sometimes", strict=True)\ndef test_red():\n    assert False\n')

    assert result.returncode != 0
    assert "must cite the owning issue" in result.stderr


def test_parametrized_case_marks_are_checked(project: pathlib.Path) -> None:
    body = '@pytest.mark.parametrize("x", [1, pytest.param(2, marks=pytest.mark.xfail(reason="owned by #1", strict=True))])\ndef test_cases(x):\n    assert x == 1\n'

    result = _run(project, body)

    assert result.returncode != 0
    assert "#1 is closed" in result.stderr


def test_skip_is_never_sanctioned(project: pathlib.Path) -> None:
    result = _run(project, '@pytest.mark.skip(reason="owned by #188")\ndef test_red():\n    assert False\n')

    assert result.returncode != 0
    assert "skip is never sanctioned" in result.stderr
