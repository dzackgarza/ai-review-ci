#!/usr/bin/env python3
"""Select program source from a NUL-delimited Git inventory."""

from __future__ import annotations

import sys
from pathlib import Path

SOURCE_SUFFIXES = frozenset(
    "py pyi sage pyx pxd pxi jl lean sh bash zsh js jsx mjs cjs ts tsx mts cts "
    "rs c h cc hh cpp hpp cxx hxx go java kt kts scala swift rb php pl pm r "
    "lua ex exs erl hrl hs lhs ml mli fs fsx cs vb sql css scss sass less "
    "svelte vue j2 jinja jinja2 just".split()
)
SOURCE_NAMES = frozenset(("justfile", "makefile", "gnumakefile", "dockerfile", "containerfile"))


def main() -> None:
    for raw_path in sys.stdin.buffer.read().split(b"\0"):
        if not raw_path:
            continue
        path = Path(raw_path.decode(sys.getfilesystemencoding(), "surrogateescape"))
        if path.suffix.lower().removeprefix(".") in SOURCE_SUFFIXES or path.name.lower() in SOURCE_NAMES:
            if path.is_file():
                sys.stdout.buffer.write(raw_path + b"\0")
            continue
        if path.suffix or not path.is_file():
            continue
        with path.open("rb") as source:
            if source.read(2) == b"#!":
                sys.stdout.buffer.write(raw_path + b"\0")


if __name__ == "__main__":
    main()
