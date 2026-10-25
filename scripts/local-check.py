#!/usr/bin/env python3
"""Fast local validation of staged or pushed syntax, without tool installs.

The local tier does not compile a project, run a suite, format files, inspect
style/typing, or read the unstaged working tree. Those belong to CI diagnostics.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
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


RELEVANT = (".py", ".pyi", ".json", ".toml")


def commit_oid(oid: str) -> str | None:
    """Peel a ref to a commit, or reject missing/deleted/non-commit refs."""
    if not oid or set(oid) == {"0"}:
        return None
    # Missing upstreams are normal on new branches; probing them must never
    # print Git's fatal diagnostic during an otherwise successful push check.
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"{oid}^{{commit}}"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.decode().strip()


def push_base(commit: str, remote_oid: str | None, remote: str) -> str | None:
    """Find a relevant local base without fetching or traversing repository history."""
    if remote_oid and (base := commit_oid(remote_oid)):
        return base
    if remote_oid is None:
        # A manual `just test-push` has no Git pre-push stdin. Compare with
        # the branch's tracked remote, not origin/main: a feature branch that
        # is already published must not re-audit all its historical changes.
        if upstream := commit_oid("@{upstream}"):
            return upstream
    candidates = (
        f"refs/remotes/{remote}/HEAD",
        f"refs/remotes/{remote}/main",
        f"refs/remotes/{remote}/master",
        "refs/remotes/origin/main",
        "refs/heads/main",
    )
    for candidate in candidates:
        if candidate_oid := commit_oid(candidate):
            try:
                base = git("merge-base", commit, candidate_oid).decode().strip()
            except subprocess.CalledProcessError:
                continue
            if base != commit:
                return base
    # With no known remote base, checking the newest commit keeps an initial
    # publication bounded; CI remains responsible for the complete tree.
    return commit_oid(f"{commit}^")


def committed_changes(commit: str, remote_oid: str | None, remote: str) -> list[tuple[str, str]]:
    """Changed files in the candidate push, read from its committed tree."""
    base = push_base(commit, remote_oid, remote)
    if base is None:
        names = git("ls-tree", "-r", "--name-only", "-z", commit)
    else:
        names = git("diff", "--name-only", "--diff-filter=ACMR", "-z", base, commit)
    return [(os.fsdecode(raw), commit) for raw in names.split(b"\0") if raw]


def push_refs(remote: str, pre_push: bool) -> list[tuple[str, str | None]]:
    """Git's pre-push stdin is the authority for every outgoing ref."""
    refs: list[tuple[str, str | None]] = []
    if pre_push:
        for raw in sys.stdin.buffer:
            parts = raw.decode("utf-8", errors="surrogateescape").split()
            if len(parts) != 4:
                raise ValueError("Malformed Git pre-push ref update")
            _, local_oid, _, remote_oid = parts
            if commit := commit_oid(local_oid):
                refs.append((commit, remote_oid))
    else:
        if commit := commit_oid("HEAD"):
            refs.append((commit, None))
    return refs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("staged", "push"), default="staged")
    parser.add_argument("--pre-push", action="store_true")
    parser.add_argument("--remote", default="origin")
    args = parser.parse_args()
    if args.pre_push and args.mode != "push":
        parser.error("--pre-push requires --mode push")
    try:
        changes: list[tuple[str, str]] = []
        if args.mode == "staged":
            names = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
            changes.extend((os.fsdecode(raw), "index") for raw in names.split(b"\0") if raw)
        if args.mode == "push":
            for commit, remote_oid in push_refs(args.remote, args.pre_push):
                changes.extend(committed_changes(commit, remote_oid, args.remote))
    except (ValueError, UnicodeError, subprocess.CalledProcessError) as error:
        print(f"Cannot inspect candidate source: {error}", file=sys.stderr)
        return 2
    checked = 0
    errors = 0
    seen: set[tuple[str, str]] = set()
    for path, version in changes:
        if (path, version) in seen or not path.endswith(RELEVANT):
            continue
        seen.add((path, version))
        try:
            validate(path, git("show", f":{path}" if version == "index" else f"{version}:{path}"))
        except (SyntaxError, UnicodeError, json.JSONDecodeError, tomllib.TOMLDecodeError, subprocess.CalledProcessError) as error:
            print(f"{path}: {error}", file=sys.stderr)
            errors += 1
        checked += 1
    if not errors:
        title = "Push" if args.mode == "push" else "Staged"
        print(f"{title} syntax: {checked} file(s) checked; no errors.")
    if errors:
        return 1

    validator = Path("scripts/local-validate.py")
    if validator.is_file():
        if not os.access(validator, os.X_OK):
            print(f"Project local validator is not executable: {validator}", file=sys.stderr)
            return 2
        records = b"".join(
            (json.dumps({"path": path, "version": version}) + "\n").encode("utf-8")
            for path, version in dict.fromkeys(changes)
        )
        result = subprocess.run([str(validator.resolve()), "--mode", args.mode], input=records)
        return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
