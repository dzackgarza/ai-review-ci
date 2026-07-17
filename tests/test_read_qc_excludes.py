"""Proof that enclosing QC does not inspect nested repository ownership."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "tool-artifacts" / "scripts" / "read_qc_excludes.py"
SAGE_JUSTFILE = ROOT / "justfiles" / "sage.just"


def _git(project: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    )


def test_runtime_excludes_include_gitlinks_and_nested_repositories(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _git(project, "init")
    _git(project, "config", "user.name", "QC Test")
    _git(project, "config", "user.email", "qc@example.invalid")
    (project / "owned.py").write_text("OWNED = True\n")
    _git(project, "add", "owned.py")
    tree = _git(project, "write-tree").stdout.strip()
    commit = subprocess.run(
        ["git", "commit-tree", tree],
        cwd=project,
        input="fixture\n",
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    linked = project / "linked"
    linked.mkdir()
    (linked / "foreign.py").write_text("FOREIGN = True\n")
    _git(project, "update-index", "--add", "--cacheinfo", f"160000,{commit},linked")

    nested = project / "nested"
    nested.mkdir()
    _git(nested, "init")
    (nested / "foreign.py").write_text("FOREIGN = True\n")

    config = tmp_path / "qc-excludes.toml"
    config.write_text('directories = ["vendor"]\n')
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(config)],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.splitlines() == ["vendor", "linked", "nested"]


def test_sage_test_discovery_excludes_gitlink_tests(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _git(project, "init")
    _git(project, "config", "user.name", "QC Test")
    _git(project, "config", "user.email", "qc@example.invalid")

    owned_test = project / "tests" / "test_owned.sage"
    owned_test.parent.mkdir()
    owned_test.write_text("assert 2 + 2 == 4\n")
    _git(project, "add", "tests/test_owned.sage")
    tree = _git(project, "write-tree").stdout.strip()
    commit = subprocess.run(
        ["git", "commit-tree", tree],
        cwd=project,
        input="fixture\n",
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    linked_test = project / "linked" / "tests" / "test_foreign.sage"
    linked_test.parent.mkdir(parents=True)
    linked_test.write_text("assert 3 + 3 == 6\n")
    _git(project, "update-index", "--add", "--cacheinfo", f"160000,{commit},linked")

    result = subprocess.run(
        ["just", "--justfile", str(SAGE_JUSTFILE), "-d", str(project), "_sage-test-files"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.splitlines() == ["tests/test_owned.sage"]
