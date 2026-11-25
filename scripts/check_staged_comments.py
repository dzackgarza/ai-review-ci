import os
import subprocess
import sys
from pathlib import Path

from pygments.lexers import get_lexer_by_name, get_lexer_for_filename, guess_lexer
from pygments.token import Comment
from pygments.util import ClassNotFound


def main() -> int:
    records = subprocess.check_output(
        ["git", "diff", "--cached", "--raw", "--no-abbrev", "--no-renames", "--diff-filter=AMT", "-z"]
    ).split(b"\0")
    failed = False
    for header, raw_path in zip(records[::2], records[1::2]):
        _, mode, _, blob, _ = header.split()
        if not mode.startswith(b"100"):
            continue
        path = Path(os.fsdecode(raw_path))
        data = subprocess.check_output(["git", "cat-file", "blob", blob])
        if b"\0" in data:
            continue
        source = data.decode("utf-8", errors="surrogateescape")
        try:
            if path.suffix in {".sage", ".pyi", ".pyx", ".pxd"}:
                lexer = get_lexer_by_name("cython")
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
