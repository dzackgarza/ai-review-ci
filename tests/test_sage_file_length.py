"""The native file-length recipe checks Git scope beyond the exec argument limit."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_file_length_checks_all_git_paths_beyond_arg_max(tmp_path: Path) -> None:
    target = tmp_path / "consumer"
    target.mkdir()
    subprocess.run(["git", "init", "--quiet", str(target)], check=True)
    tracked = target / "tracked"
    untracked = target / "untracked"
    tracked.mkdir()
    untracked.mkdir()
    seed = tracked / "000 first file.py"
    seed.write_text("pass\n")
    argument_bytes = 0
    index = 0
    while argument_bytes <= os.sysconf("SC_ARG_MAX") + 131072:
        directory = (tracked, untracked)[index % 2]
        path = directory / f"{index:06d} {'long name ' * 20}.py"
        path.hardlink_to(seed)
        argument_bytes += len(os.fsencode(path.relative_to(target))) + 1
        index += 1
    (untracked / "embedded\nnewline.py").hardlink_to(seed)
    subprocess.run(["git", "add", "tracked"], cwd=target, check=True)
    (target / ".gitignore").write_text("ignored/\n")
    ignored = target / "ignored"
    ignored.mkdir()
    (ignored / "not in Git scope.py").write_text("pass\n" * 701)
    command = ["just", "-f", str(ROOT / "justfiles" / "sage.just"), "-d", str(target), "_sage-file-length"]
    valid = subprocess.run(command, text=True, capture_output=True, check=False)
    assert valid.returncode == 0, valid.stdout + valid.stderr

    # Distinct files in the first and last batches must both be diagnosed.
    first = untracked / "000 first failure with spaces.py"
    first.write_text("pass\n" * 701)
    last = tracked / "zzzz last file with spaces.py"
    last.write_text("pass\n" * 701)
    subprocess.run(["git", "add", str(last.relative_to(target))], cwd=target, check=True)
    invalid = subprocess.run(command, text=True, capture_output=True, check=False)
    assert invalid.returncode != 0
    assert str(first.relative_to(target)) in invalid.stdout, invalid.stdout + invalid.stderr
    assert str(last.relative_to(target)) in invalid.stdout, invalid.stdout + invalid.stderr
    assert "not in Git scope.py" not in invalid.stdout


def test_file_length_limits_source_not_stored_documents(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    for name in ("certificates.yaml", "gram-index.json", "lattices/card.md", "sources/table.html", "sources/table.txt"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("stored data\n" * 701)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    command = ["just", "-f", str(ROOT / "justfiles" / "sage.just"), "-d", str(tmp_path), "_sage-file-length"]
    documents = subprocess.run(command, text=True, capture_output=True, check=False)
    assert documents.returncode == 0, documents.stdout + documents.stderr
    for name in (
        "module.py",
        "module.sage",
        "module.pyx",
        "worker.jl",
        "worker.sh",
        "client.ts",
        "styles.css",
        "partial.j2",
        "page.vue",
        "tasks.just",
        "nested/Makefile",
        "Dockerfile",
        "nested/justfile",
        "runner",
    ):
        source = tmp_path / name
        source.parent.mkdir(parents=True, exist_ok=True)
        first_line = "#!/usr/bin/env python3\n" if name == "runner" else "source\n"
        source.write_text(first_line + "source\n" * 700)
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        assert result.returncode != 0, name
        assert name in result.stdout, result.stdout + result.stderr
        source.write_text(first_line + "source\n" * 699)
        boundary = subprocess.run(command, text=True, capture_output=True, check=False)
        assert boundary.returncode == 0, boundary.stdout + boundary.stderr
