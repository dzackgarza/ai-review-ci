import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

from pygments.lexers import get_lexer_by_name, get_lexer_for_filename, guess_lexer
from pygments.lexers.python import PythonLexer
from pygments.token import Comment
from pygments.util import ClassNotFound

SEMGREP_RULE_FIXTURES = Path("tests/fixtures/semgrep")
INLINE_METADATA = re.compile(
    r"^# /// (?P<type>[a-zA-Z0-9-]+)\n(?P<content>(?:^#(?: .*)?\n)*)^# ///$",
    re.MULTILINE,
)


def script_metadata_range(source: str) -> range:
    """Find the PEP 723 script block using the PyPA inline metadata grammar.

    The staged comment check recognizes structured TOML, not the runner's
    dependency resolution or tool-specific configuration semantics.
    """
    matches = [
        match for match in INLINE_METADATA.finditer(source)
        if match.group("type") == "script"
    ]
    if len(matches) != 1:
        return range(0)
    match = matches[0]
    content = match.group("content")
    if re.search(r"^# /// [a-zA-Z0-9-]+$", content, re.MULTILINE):
        return range(0)
    raw = "".join(
        line[2:] if line.startswith("# ") else line[1:]
        for line in content.splitlines(keepends=True)
    )
    try:
        metadata = tomllib.loads(raw)
    except tomllib.TOMLDecodeError:
        return range(0)
    dependencies = metadata.get("dependencies", [])
    if not isinstance(dependencies, list) or not all(isinstance(item, str) for item in dependencies):
        return range(0)
    if not isinstance(metadata.get("requires-python", ""), str) or not isinstance(metadata.get("tool", {}), dict):
        return range(0)
    return range(*match.span())


def merge_heads() -> list[bytes]:
    merge_head = Path(subprocess.check_output(["git", "rev-parse", "--git-path", "MERGE_HEAD"]).decode().strip())
    return merge_head.read_bytes().split() if merge_head.exists() else []


def blob_in(commit: bytes, path: bytes) -> bytes | None:
    listed = subprocess.check_output(["git", "ls-tree", "-z", commit, "--", path]).split(b"\0")[0]
    return listed.split(b"\t")[0].split()[2] if listed else None


def recipe_shebang(source: str, offset: int, value: str) -> bool:
    line_start = source.rfind("\n", 0, offset) + 1
    line = source[line_start:].split("\n", 1)[0]
    if not line[:1].isspace() or not line.lstrip().startswith("#!") or not value.lstrip().startswith("#!"):
        return False
    previous = source[:max(line_start - 1, 0)].rsplit("\n", 1)[-1]
    return bool(previous) and not previous[0].isspace() and not previous.startswith(("#", "[")) and ":" in previous and ":=" not in previous


def main() -> int:
    records = subprocess.check_output(
        ["git", "diff", "--cached", "--raw", "--no-abbrev", "--no-renames", "--diff-filter=AMT", "-z"]
    ).split(b"\0")
    heads = merge_heads()
    failed = False
    for header, raw_path in zip(records[::2], records[1::2]):
        _, mode, _, blob, _ = header.split()
        if not mode.startswith(b"100"):
            continue
        if any(blob_in(head, raw_path) == blob for head in heads):
            continue
        path = Path(os.fsdecode(raw_path))
        if path.parent == SEMGREP_RULE_FIXTURES or path.suffix.lower() in {".md", ".markdown"}:
            continue
        data = subprocess.check_output(["git", "cat-file", "blob", blob])
        if b"\0" in data:
            continue
        source = data.decode("utf-8", errors="surrogateescape").replace("\r\n", "\n")
        try:
            if path.suffix in {".sage", ".pyi"}:
                lexer = get_lexer_by_name("python")
            elif path.suffix in {".pyx", ".pxd", ".pxi"}:
                lexer = get_lexer_by_name("cython")
            elif path.suffix == ".M2":
                lexer = get_lexer_by_name("macaulay2")
            elif path.suffix == ".tikz":
                lexer = get_lexer_by_name("tex")
            elif path.suffix == ".lean":
                lexer = get_lexer_by_name("lean4")
            elif path.name.lower() == "justfile" or path.suffix == ".just":
                lexer = get_lexer_by_name("make")
            else:
                lexer = get_lexer_for_filename(path.name, source)
        except ClassNotFound:
            if not source.startswith("#!"):
                continue
            lexer = guess_lexer(source)
        is_justfile = path.name.lower() == "justfile" or path.suffix == ".just"
        metadata = (
            script_metadata_range(source)
            if isinstance(lexer, PythonLexer) and path.suffix not in {".sage", ".pyi"}
            else range(0)
        )
        metadata_started = False
        for offset, token, value in lexer.get_tokens_unprocessed(source):
            if token not in Comment or token in Comment.Preproc or token in Comment.PreprocFile:
                continue
            if offset == metadata.start:
                metadata_started = True
            if metadata_started and offset in metadata:
                continue
            if offset == 0 and value.startswith("#!"):
                continue
            if is_justfile and recipe_shebang(source, offset, value):
                continue
            if is_justfile and source[source.rfind("\n", 0, offset) + 1:].startswith("["):
                continue
            line = source.count("\n", 0, offset) + 1
            print(f"{path}:{line}: remove code comment", file=sys.stderr)
            failed = True
            break
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
