#!/usr/bin/env python3
"""Compare lizard warning output and fail only on new warning signatures."""

from __future__ import annotations

import argparse
import collections
import re
from pathlib import Path


WARNING_LINE_RE = re.compile(
    r"^\s*(?P<nloc>\d+)\s+"
    r"(?P<ccn>\d+)\s+"
    r"(?P<tokens>\d+)\s+"
    r"(?P<params>\d+)\s+"
    r"(?P<length>\d+)\s+"
    r"(?P<location>.+@(?P<start>\d+)-(?P<end>\d+)@(?P<path>.+))$"
)


def warning_signatures(output: str) -> collections.Counter[str]:
    """Return comparable warning signatures from lizard text output."""
    warnings_started = False
    signatures: collections.Counter[str] = collections.Counter()
    for line in output.splitlines():
        if "!!!! Warnings" in line:
            warnings_started = True
            continue
        if not warnings_started:
            continue
        match = WARNING_LINE_RE.match(line)
        if match is None:
            continue
        location = match.group("location")
        path = match.group("path")
        name = location.rsplit("@", 2)[0]
        signatures[f"{name}@{path}"] += 1
    return signatures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-output", type=Path, required=True)
    parser.add_argument("--head-output", type=Path, required=True)
    args = parser.parse_args()

    base = warning_signatures(args.base_output.read_text())
    head = warning_signatures(args.head_output.read_text())
    new_warnings = head - base
    if not new_warnings:
        print("lizard: warnings are unchanged relative to DIFF_COVER_BASE.")
        return 0

    print("ERROR: lizard found new complexity warnings relative to DIFF_COVER_BASE:")
    for signature, count in sorted(new_warnings.items()):
        suffix = f" x{count}" if count > 1 else ""
        print(f"  {signature}{suffix}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
