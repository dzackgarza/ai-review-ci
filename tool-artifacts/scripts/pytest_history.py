#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Report per-test durations across the runs recorded by qc_test_history.

Usage:
  uv run pytest_history.py HISTORY_DIR [SUBSTRING ...]

Every test whose node id contains any SUBSTRING (all tests when none is given)
is printed with one row per recorded run, oldest first:

  tests/test_x.sage::test_y
    20261007T120000123456Z  0123456789ab        passed    1.234s
    20261007T130000654321Z  0123456789ab+dirty  failed    0.987s
"""

import json
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: pytest_history.py HISTORY_DIR [SUBSTRING ...]")
    history = Path(sys.argv[1])
    substrings = sys.argv[2:]
    paths = sorted(history.glob("*.json"))
    if not paths:
        sys.exit(f"ERROR: no pytest history records in {history}")

    rows: dict[str, list[str]] = {}
    for path in paths:
        record = json.loads(path.read_text())
        run = path.stem.split("-", 1)[0]
        commit = record["commit"][:12] + ("+dirty" if record["dirty"] else "")
        for test in record["tests"]:
            nodeid = test["nodeid"]
            if substrings and not any(substring in nodeid for substring in substrings):
                continue
            rows.setdefault(nodeid, []).append(f"  {run}  {commit:<18}  {test['outcome']:<8}  {test['duration']:.3f}s")
    if not rows:
        sys.exit(f"ERROR: no recorded test matches {substrings}")

    for nodeid in sorted(rows):
        print(nodeid)
        print("\n".join(rows[nodeid]))


if __name__ == "__main__":
    main()
