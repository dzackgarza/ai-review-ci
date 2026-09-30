#!/usr/bin/env python3
"""Report `sorry` terms in Lean source, ignoring comments and string literals.

    lean_sorry_scan.py FILE...          scan files on disk
    lean_sorry_scan.py --stdin NAME     scan stdin, reported as NAME

Prints `file:line: text` for each hit and exits 1 if there is any. A `sorry` in a docstring, a
comment, or an error-message string is not a proof term. The lexer follows Lean 4's own token
rules in `src/Lean/Parser/Basic.lean` (`whitespace`/`finishCommentBlock` for nested `/- -/` and
`--` comments, `strLitFnAux` for string escapes, `rawStrLitFnAux` for `r#"…"#`, `charLitFnAux`
for character literals).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SORRY = re.compile(r"(?<![\w.'])sorry(?![\w'])")
CHAR_LIT = re.compile(r"'(?:\\(?:x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|.)|[^\\'\n])'")
RAW_STR = re.compile(r'r(#*)"')


def code_only(text: str) -> str:
    """`text` with comments and string and character literals blanked; newlines are kept."""
    out: list[str] = []
    i, n = 0, len(text)

    def blank(j: int) -> None:
        out.extend("\n" if c == "\n" else " " for c in text[i:j])

    while i < n:
        if text.startswith("--", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            blank(j); i = j; continue
        if text.startswith("/-", i):
            depth, j = 1, i + 2
            while j < n and depth:
                if text.startswith("/-", j):
                    depth += 1; j += 2
                elif text.startswith("-/", j):
                    depth -= 1; j += 2
                else:
                    j += 1
            blank(j); i = j; continue
        prev = text[i - 1] if i else " "
        raw = RAW_STR.match(text, i) if not (prev.isalnum() or prev in "_'.") else None
        if raw:
            end = text.find('"' + raw.group(1), raw.end())
            j = n if end < 0 else end + 1 + len(raw.group(1))
            blank(j); i = j; continue
        if text[i] == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n)
            blank(j); i = j; continue
        if text[i] == "'" and not (prev.isalnum() or prev in "_'"):
            m = CHAR_LIT.match(text, i)
            if m:
                blank(m.end()); i = m.end(); continue
        out.append(text[i]); i += 1
    return "".join(out)


def hits(name: str, text: str) -> list[str]:
    lines = text.splitlines()
    return [f"{name}:{k}: {lines[k - 1].strip()}"
            for k, line in enumerate(code_only(text).splitlines(), start=1) if SORRY.search(line)]


def main() -> int:
    args = sys.argv[1:]
    if args[:1] == ["--stdin"] and len(args) == 2:
        found = hits(args[1], sys.stdin.read())
    elif args and "--stdin" not in args:
        found = [h for f in args for h in hits(f, Path(f).read_text(errors="replace"))]
    else:
        raise SystemExit(__doc__)
    if not found:
        return 0
    print("\n".join(found))
    return 1


if __name__ == "__main__":
    sys.exit(main())
