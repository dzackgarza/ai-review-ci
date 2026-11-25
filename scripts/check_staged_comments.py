import os
import subprocess
import sys
from pathlib import Path

from pygments.lexers import get_lexer_by_name, get_lexer_for_filename, guess_lexer
from pygments.token import Comment
from pygments.util import ClassNotFound


def merge_heads() -> list[bytes]:
    merge_head = Path(subprocess.check_output(["git", "rev-parse", "--git-path", "MERGE_HEAD"]).decode().strip())
    return merge_head.read_bytes().split() if merge_head.exists() else []


def blob_in(commit: bytes, path: bytes) -> bytes | None:
    listed = subprocess.check_output(["git", "ls-tree", "-z", commit, "--", path]).split(b"\0")[0]
    return listed.split(b"\t")[0].split()[2] if listed else None


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
        data = subprocess.check_output(["git", "cat-file", "blob", blob])
        if b"\0" in data:
            continue
        source = data.decode("utf-8", errors="surrogateescape")
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
        for offset, token, value in lexer.get_tokens_unprocessed(source):
            if token not in Comment or token in Comment.Preproc or token in Comment.PreprocFile:
                continue
            if offset == 0 and value.startswith("#!"):
                continue
            line = source.count("\n", 0, offset) + 1
            print(f"{path}:{line}: remove code comment", file=sys.stderr)
            failed = True
            break
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
