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


def test_pep723_inline_script_metadata_is_not_a_comment(tmp_path: Path) -> None:
    checker = Path(__file__).resolve().parents[1] / "scripts/check_staged_comments.py"
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    path = tmp_path / "docs_query.py"
    script = (
        "#!/usr/bin/env -S uv run --script\n"
        "# /// script\n"
        '# requires-python = ">=3.12"\n'
        '# dependencies = ["networkx>=3.4"]\n'
        "# ///\n"
        "import networkx\n"
        "graph = networkx.DiGraph()\n"
    )
    for source, expected in [(script, 0), (script + "# note\n", 1)]:
        path.write_text(source)
        subprocess.run(["git", "add", "-f", "--", "docs_query.py"], cwd=tmp_path, check=True)
        result = subprocess.run([sys.executable, checker], cwd=tmp_path, capture_output=True, text=True)
        assert result.returncode == expected, result.stderr
        if expected:
            assert "docs_query.py:8: remove code comment" in result.stderr


def test_semgrep_rule_fixture_annotations_are_not_code_comments(tmp_path: Path) -> None:
    checker = Path(__file__).resolve().parents[1] / "scripts/check_staged_comments.py"
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    source = "# ruleid: py-no-type-ignore\nx: int = f()  # type: ignore\n"
    for relative, expected in [("tests/fixtures/semgrep/a.py", 0), ("tests/fixtures/other/a.py", 1)]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True)
        path.write_text(source)
        subprocess.run(["git", "add", "-f", "--", relative], cwd=tmp_path, check=True)
        result = subprocess.run([sys.executable, checker], cwd=tmp_path, capture_output=True, text=True)
        assert result.returncode == expected, result.stderr


def test_justfile_doc_attribute_with_hash_after_colon_is_not_a_comment(tmp_path: Path) -> None:
    checker = Path(__file__).resolve().parents[1] / "scripts/check_staged_comments.py"
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "justfile").write_text('[doc("Build the project: see issue #1.")]\nbuild:\n    echo build\n')
    subprocess.run(["git", "add", "-f", "--", "justfile"], cwd=tmp_path, check=True)
    result = subprocess.run([sys.executable, checker], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_markdown_fenced_code_is_not_source(tmp_path: Path) -> None:
    checker = Path(__file__).resolve().parents[1] / "scripts/check_staged_comments.py"
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "conversation.md").write_text("## assistant\n\n```python\nx = 1\n# recorded note\n```\n")
    subprocess.run(["git", "add", "-f", "--", "conversation.md"], cwd=tmp_path, check=True)
    result = subprocess.run([sys.executable, checker], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_script_metadata_passes_pre_commit_but_staged_explanatory_comment_fails(
    tmp_path: Path, newline: str
) -> None:
    root = Path(__file__).resolve().parents[1]
    hook = root / "repo-hooks/pre-commit"
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=tmp_path, check=True)
    (tmp_path / "justfile").write_text(
        f'test-commit:\n    @just -f "{root / "justfiles/python.just"}" -d . test-commit\n'
    )
    script = tmp_path / "query.py"
    source = newline.join([
        "#!/usr/bin/env -S uv run --script",
        "# /// script",
        '# requires-python = ">=3.12"',
        "# dependencies = [",
        '#   "torch",',
        "# ]",
        "#",
        "# [tool.uv.sources]",
        '# torch = { index = "pytorch-cpu" }',
        "# [[tool.uv.index]]",
        '# name = "pytorch-cpu"',
        '# url = "https://download.pytorch.org/whl/cpu"',
        "# explicit = true",
        "# ///",
        "print(42)",
        "",
    ])
    script.write_bytes(source.encode())
    script.chmod(0o755)
    subprocess.run(["git", "add", "--", script.name], cwd=tmp_path, check=True)

    script.write_bytes((source + "# explanation" + newline).encode())
    accepted = subprocess.run([hook], cwd=tmp_path, capture_output=True, text=True)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr

    subprocess.run(["git", "add", "--", script.name], cwd=tmp_path, check=True)
    rejected = subprocess.run([hook], cwd=tmp_path, capture_output=True, text=True)
    assert rejected.returncode == 1, rejected.stdout + rejected.stderr
    assert f"{script.name}:16: remove code comment" in rejected.stderr


@pytest.mark.parametrize(("filename", "source", "line"), [
    ("a.py", '# /// script\n# dependencies = []\nprint(42)\n', 1),
    ("a.py", '# /// script\n# not TOML\n# ///\nprint(42)\n', 1),
    ("a.py", '# /// script\n# dependencies = 42\n# ///\nprint(42)\n', 1),
    ("a.py", '# /// script\n# dependencies = ["not a dependency?"]\n# ///\nprint(42)\n', 1),
    ("a.py", '# /// script\n# requires-python = "not a version specifier"\n# ///\nprint(42)\n', 1),
    ("a.py", '# /// script\n# dependencies = [""]\n# ///\nprint(42)\n', 1),
    ("a.py", '# /// script\n# dependencies = ["numpy; invalid_marker == \'x\'"]\n# ///\nprint(42)\n', 1),
    ("a.py", '# /// custom\n# dependencies = []\n# ///\nprint(42)\n', 1),
    ("a.py", '# /// script\n# dependencies = []\n# ///\n# ordinary comment\nprint(42)\n', 4),
    ("a.py", '# /// script\n# dependencies = []\n# ///\n\n# /// script\n# dependencies = []\n# ///\nprint(42)\n', 1),
    ("a.py", '# /// script\n#dependencies = []\n# ///\nprint(42)\n', 1),
    ("a.py", 'if True:\n    # /// script\n    # dependencies = []\n    # ///\n    print(42)\n', 2),
    ("a.py", 'text = """\n# /// script\n# ///\n"""\n# ordinary comment\n', 5),
    ("a.py", "text = \"\"\"\n# /// script\n# [tool]\n# text = '''\n# \"\"\"\n# ordinary comment\n# '''\n# ///\n", 6),
    ("a.sh", '# /// script\n# dependencies = []\n# ///\necho 42\n', 1),
    ("a.sage", '# /// script\n# dependencies = []\n# ///\nprint(42)\n', 1),
])
def test_metadata_like_comments_are_not_exempt(
    tmp_path: Path, filename: str, source: str, line: int
) -> None:
    checker = Path(__file__).resolve().parents[1] / "scripts/check_staged_comments.py"
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / filename).write_text(source)
    subprocess.run(["git", "add", "--", filename], cwd=tmp_path, check=True)
    result = subprocess.run([sys.executable, checker], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"{filename}:{line}: remove code comment" in result.stderr
