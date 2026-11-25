import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(("filename", "code", "comment"), [
    ("a.py", 's = "#"', "# note"),
    ("a.sage", 's = "#"', "# note"),
    ("a.pyx", "cdef int x", "# note"),
    ("a.lean", 'def s := "/-"', "/- outer /- inner -/ end -/"),
    ("a.M2", 's = "--"', "-- note"),
    ("a.jl", 's = "#="', "#= note =#"),
    ("a.rs", 'const S: &str = "//";', "/* note */"),
    ("a.cpp", '#include <cstdio>', "// note"),
    ("a.ts", 'const s = "//";', "/* note */"),
    ("a.tsx", 'const e = <div>text</div>;', "// note"),
    ("a.js", 'const s = "/*";', "// note"),
    ("a.sh", 'echo "#"', "# note"),
    ("a.lua", 's = "--"', "--[[note]]"),
    ("a.tex", r"10\%", "% note"),
    ("a.tikz", r"\draw (0,0) -- (1,1);", "% note"),
    ("a.g", 's := "#";', "# note"),
    ("a.css", 'p { color: #fff; }', "/* note */"),
    ("a.toml", 's = "#"', "# note"),
    ("a.yaml", 's: "#"', "# note"),
])
def test_staged_language_comments(tmp_path: Path, filename: str, code: str, comment: str) -> None:
    checker = Path(__file__).resolve().parents[1] / "scripts/check_staged_comments.py"
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    path = tmp_path / filename
    for source, expected in [(code, 0), (code + "\n" + comment, 1)]:
        path.write_text(source + "\n")
        subprocess.run(["git", "add", "-f", "--", filename], cwd=tmp_path, check=True)
        result = subprocess.run([sys.executable, checker], cwd=tmp_path, capture_output=True, text=True)
        assert result.returncode == expected, result.stderr
        if expected:
            assert f"{filename}:2: remove code comment" in result.stderr


def test_merge_does_not_reject_files_taken_unchanged_from_the_merged_branch(tmp_path: Path) -> None:
    checker = Path(__file__).resolve().parents[1] / "scripts/check_staged_comments.py"

    def git(*args: str) -> None:
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.hooksPath=/dev/null", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q", "-b", "main")
    (tmp_path / "base.txt").write_text("base\n")
    git("add", "base.txt")
    git("commit", "-q", "-m", "base")
    git("checkout", "-q", "-b", "other")
    (tmp_path / "taken.py").write_text("x = 1\n# upstream note\n")
    git("add", "taken.py")
    git("commit", "-q", "-m", "other")
    git("checkout", "-q", "main")
    (tmp_path / "local.txt").write_text("local\n")
    git("add", "local.txt")
    git("commit", "-q", "-m", "local")
    git("merge", "-q", "--no-commit", "--no-ff", "other")
    result = subprocess.run([sys.executable, checker], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

    (tmp_path / "resolved.py").write_text("y = 2\n# merge note\n")
    git("add", "resolved.py")
    result = subprocess.run([sys.executable, checker], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 1
    assert "resolved.py:2: remove code comment" in result.stderr
    assert "taken.py" not in result.stderr


def test_justfile_shebang_recipe_is_not_a_comment(tmp_path: Path) -> None:
    checker = Path(__file__).resolve().parents[1] / "scripts/check_staged_comments.py"
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    path = tmp_path / "justfile"
    recipe = 'build:\n    #!/usr/bin/env bash\n    set -euo pipefail\n    echo "#"\n'
    for source, expected in [(recipe, 0), (recipe + "    # note\n", 1)]:
        path.write_text(source)
        subprocess.run(["git", "add", "-f", "--", "justfile"], cwd=tmp_path, check=True)
        result = subprocess.run([sys.executable, checker], cwd=tmp_path, capture_output=True, text=True)
        assert result.returncode == expected, result.stderr
        if expected:
            assert "justfile:5: remove code comment" in result.stderr
