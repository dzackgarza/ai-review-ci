"""Proof that enclosing QC does not inspect nested repository ownership."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "tool-artifacts" / "scripts" / "read_qc_excludes.py"


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
