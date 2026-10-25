"""Explicit full inventories traverse native directories once without widening scope."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_unique_inventory_reuses_native_children_and_preserves_selection(tmp_path: Path) -> None:
    (tmp_path / "conftest.py").write_text(
        "from pathlib import Path\n"
        "import pytest\n"
        "@pytest.fixture\n"
        "def supplied(): return 37\n"
        "def pytest_collect_file(file_path, parent):\n"
        "    with Path('visits.txt').open('a') as stream:\n"
        "        stream.write(str(file_path) + '\\n')\n"
        "def pytest_collection_modifyitems(items):\n"
        "    Path('nodes.txt').write_text('\\n'.join(item.nodeid for item in items))\n"
    )
    paths = []
    for directory in ("plain", "package"):
        folder = tmp_path / directory
        folder.mkdir()
        if directory == "package":
            (folder / "__init__.py").write_text("")
        for index in range(12):
            path = folder / f"specimen_{index:02d}.py"
            path.write_text("def test_value(supplied):\n    assert supplied == 37\n")
            paths.append(str(path.relative_to(tmp_path)))
        (folder / "test_unselected.py").write_text("raise AssertionError('unselected sibling executed')\n")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "tool-artifacts" / "pytest_plugins")
    prefix = [sys.executable, "-m", "pytest", "-q"]
    baseline = subprocess.run([*prefix, *paths], cwd=tmp_path, env=env, text=True, capture_output=True, check=False)
    assert baseline.returncode == 0, baseline.stdout + baseline.stderr
    expected_nodes = (tmp_path / "nodes.txt").read_bytes()
    (tmp_path / "visits.txt").unlink()
    command = [*prefix, "-p", "qc_unique_inventory", *paths]
    result = subprocess.run(command, cwd=tmp_path, env=env, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "24 passed" in result.stdout
    assert (tmp_path / "nodes.txt").read_bytes() == expected_nodes
    visits = (tmp_path / "visits.txt").read_text().splitlines()
    assert len(visits) == len(set(visits)), "explicit inventory repeatedly scanned sibling files"


def test_unique_inventory_preserves_project_directory_collectors(tmp_path: Path) -> None:
    (tmp_path / "conftest.py").write_text(
        "from pathlib import Path\n"
        "import pytest\n"
        "class ProjectDirectory(pytest.Dir):\n"
        "    def collect(self):\n"
        "        Path('project-collector.txt').write_text('selected')\n"
        "        yield from super().collect()\n"
        "def pytest_collect_directory(path, parent):\n"
        "    if path.name == 'custom':\n"
        "        return ProjectDirectory.from_parent(parent, path=path)\n"
    )
    folder = tmp_path / "custom"
    folder.mkdir()
    (folder / "test_actual.py").write_text("def test_actual():\n    assert 13 * 3 == 39\n")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "tool-artifacts" / "pytest_plugins")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "qc_unique_inventory", "custom/test_actual.py"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout
    assert (tmp_path / "project-collector.txt").read_text() == "selected"
