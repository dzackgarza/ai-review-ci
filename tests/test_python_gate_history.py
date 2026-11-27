import json
from pathlib import Path

import pytest

from tests.test_justfiles import ROOT, commit_without_hooks, init_git_repo, run_git, run_just


@pytest.mark.parametrize("recipe", ["_pytest", "test-gh-boundary", "_pytest_with_coverage"])
def test_python_gate_records_each_case_at_the_tested_revision(tmp_path: Path, recipe: str) -> None:
    project = tmp_path / "consumer"
    package = project / "src" / "measure"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("def measure():\n    return 12\n")
    (project / "pyproject.toml").write_text(
        '[project]\nname="history-consumer"\nversion="0.1"\n'
        '[build-system]\nrequires=["setuptools"]\nbuild-backend="setuptools.build_meta"\n'
        '[tool.pytest.ini_options]\nmarkers=["gh_boundary: dependency boundary"]\n'
    )
    tests = project / "tests"
    tests.mkdir()
    (tests / "test_measure.py").write_text(
        "import pytest\nfrom measure import measure\n\n"
        "@pytest.mark.gh_boundary\ndef test_measure():\n    assert measure() == 12\n"
    )
    init_git_repo(project)
    assert run_git(project, "add", ".").returncode == 0
    commit_without_hooks(project, "Add the measured consumer test")
    revision = run_git(project, "rev-parse", "HEAD").stdout.strip()
    result = run_just(ROOT / "justfiles/python.just", project, recipe)
    assert result.returncode == 0, result.stdout + result.stderr
    history = project / ".ai-review-ci/python/pytest-history"
    runs = list(history.glob("*.jsonl"))
    assert len(runs) == 1, f"{recipe} ran pytest but produced {len(runs)} timing records"
    session, started, test, finish = map(json.loads, runs[0].read_text().splitlines())
    assert session["commit"] == revision
    assert started["nodeid"] == test["nodeid"] == "tests/test_measure.py::test_measure"
    assert test["outcome"] == "passed" and test["duration"] > 0
    assert finish["exitstatus"] == 0
    assert run_git(project, "check-ignore", str(runs[0])).returncode == 0
