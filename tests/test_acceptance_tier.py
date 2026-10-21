"""The Sage push and CI test recipes leave tests/acceptance/ to the acceptance workflow (#478).

Each case runs the real central recipe against a target repository built on disk. The
suite cases record that they ran, so the proof is which files pytest actually executed,
not which paths a recipe printed.

Sage itself is not installed where this suite runs. The recipes reach Sage through two
seams: the interpreter (``SAGE_PYTHON_BIN``) and the startup import ``import sage.all``.
Here the interpreter is a real Python with pytest and coverage, and ``sage.all`` is an
empty module. Which test files the recipe hands to pytest does not depend on either.
"""

import os
import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SAGE_JUSTFILE = ROOT / "justfiles" / "sage.just"

PYPROJECT = '[project]\nname = "acceptance-target"\nversion = "0.1.0"\n\n[tool.pytest.ini_options]\npythonpath = ["."]\n'
# The target's one product module; each suite case records through it that it ran.
RECORD = 'from pathlib import Path\n\n\ndef record(name):\n    Path(f"ran-{name}").touch()\n'
UNIT_CASE = 'from record import record\n\n\ndef test_unit():\n    record("unit")\n'
ACCEPTANCE_CASE = 'from record import record\n\n\ndef test_family():\n    record("acceptance")\n'


def run(command: list[str], cwd: pathlib.Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, check=False)


def target_repository(root: pathlib.Path, files: dict[str, str]) -> pathlib.Path:
    project = root / "target"
    project.mkdir()
    assert run(["git", "init", "-q"], project).returncode == 0
    (project / "pyproject.toml").write_text(PYPROJECT)
    (project / "record.py").write_text(RECORD)
    for relative_path, contents in files.items():
        path = project / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
    # The suite recipes record each run against the target's HEAD commit.
    assert run(["git", "add", "."], project).returncode == 0
    committed = run(
        ["git", "-c", "user.name=QC Test", "-c", "user.email=qc@example.invalid", "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "fixture"],
        project,
    )
    assert committed.returncode == 0, committed.stdout + committed.stderr
    return project


@pytest.fixture(scope="module")
def interpreter(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """Environment naming a Python with pytest and coverage, and a ``sage.all`` to import."""
    root = tmp_path_factory.mktemp("interpreter")
    venv = root / "venv"
    created = run(["uv", "venv", "--quiet", "--python", "3.14", str(venv)], root)
    assert created.returncode == 0, created.stdout + created.stderr
    installed = run(["uv", "pip", "install", "--quiet", "--python", str(venv / "bin" / "python"), "pytest", "coverage"], root)
    assert installed.returncode == 0, installed.stdout + installed.stderr
    startup = root / "startup" / "sage"
    startup.mkdir(parents=True)
    (startup / "__init__.py").write_text("")
    (startup / "all.py").write_text("")
    return {"SAGE_PYTHON_BIN": str(venv / "bin" / "python"), "PYTHONPATH": str(startup.parent)}


@pytest.mark.parametrize("recipe", ["_sage-pytest", "_sage-pytest-coverage"])
def test_sage_suite_recipes_run_every_test_except_the_acceptance_suite(
    tmp_path: pathlib.Path,
    interpreter: dict[str, str],
    recipe: str,
) -> None:
    project = target_repository(
        tmp_path,
        {"tests/test_unit.py": UNIT_CASE, "tests/acceptance/test_family.py": ACCEPTANCE_CASE},
    )
    env = os.environ | interpreter
    env["AI_REVIEW_CI_HEAVY_GATE_LOCK_DIR"] = str(tmp_path / "lock")
    env["XDG_CACHE_HOME"] = str(tmp_path / "cache")

    result = run(["just", "--justfile", str(SAGE_JUSTFILE), "-d", str(project), recipe], project, env)

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert (project / "ran-unit").exists(), output
    assert not (project / "ran-acceptance").exists(), output


def test_sage_test_discovery_leaves_acceptance_sage_files_to_the_acceptance_workflow(tmp_path: pathlib.Path) -> None:
    project = target_repository(
        tmp_path,
        {"tests/test_unit.sage": "assert 1 + 1 == 2\n", "tests/acceptance/test_family.sage": "assert 2 + 2 == 4\n"},
    )

    result = run(["just", "--justfile", str(SAGE_JUSTFILE), "-d", str(project), "_sage-test-files"], project)

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines() == ["tests/test_unit.sage"]
