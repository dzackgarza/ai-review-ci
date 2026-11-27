#!/usr/bin/env python3
"""Preparse and compile a JSON batch of (path, source) pairs under Sage."""

import json
import sys

from sage.repl.preparse import preparse_file


def main() -> int:
    failed = False
    for path, source in json.load(sys.stdin):
        try:
            compile(preparse_file(source), path, "exec")
        except (SyntaxError, ValueError) as error:
            print(f"{path}: {error}", file=sys.stderr)
            failed = True
    return int(failed)


# Sage executes .py files in its own global namespace, not as __main__.
sys.exit(main())
