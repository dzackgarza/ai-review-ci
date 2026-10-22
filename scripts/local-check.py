#!/usr/bin/env python3
"""Fast local validation of staged *syntax*, without tool installs or repo-wide scans.

The local tier does not compile a project, run a suite, format files, inspect
style/typing, or read the unstaged working tree. Those belong to CI diagnostics.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tomllib


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], check=True, stdout=subprocess.PIPE).stdout


def validate(path: str, content: bytes) -> None:
    text = content.decode("utf-8-sig")
    if path.endswith((".py", ".pyi")):
        ast.parse(text, filename=path)
    elif path.endswith(".json"):
        json.loads(text)
    elif path.endswith(".toml"):
        tomllib.loads(text)


def main() -> int:
    try:
        names = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").split(b"\0")
    except subprocess.CalledProcessError as error:
        print(f"Cannot inspect staged changes: {error}", file=sys.stderr)
        return 2
    relevant = (".py", ".pyi", ".json", ".toml")
    checked = 0
    errors = 0
    for raw in filter(None, names):
        path = os.fsdecode(raw)
        if not path.endswith(relevant):
            continue
        try:
            validate(path, git("show", f":{path}"))
        except (SyntaxError, UnicodeError, json.JSONDecodeError, tomllib.TOMLDecodeError, subprocess.CalledProcessError) as error:
            print(f"{path}: {error}", file=sys.stderr)
            errors += 1
        checked += 1
    if not errors:
        print(f"Staged syntax: {checked} file(s) checked; no errors.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
