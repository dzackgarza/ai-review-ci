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
        subprocess.run(["git", "add", "--", filename], cwd=tmp_path, check=True)
        result = subprocess.run([sys.executable, checker], cwd=tmp_path, capture_output=True, text=True)
        assert result.returncode == expected, result.stderr
        if expected:
            assert f"{filename}:2: remove code comment" in result.stderr
