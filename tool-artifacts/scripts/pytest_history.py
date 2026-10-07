#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Report per-test durations across the runs recorded by qc_test_history.

Usage:
  uv run pytest_history.py HISTORY_DIR [SUBSTRING ...]

Every test whose node id contains any SUBSTRING (all tests when none is given)
is printed with one row per recorded run, oldest first. A test that started but
never finished (the run was killed or is still going) is shown as unfinished,
and a run that never reached its finish line is marked interrupted:

  tests/test_x.sage::test_y
    20261007T120000123456Z  0123456789ab        passed      1.234s
    20261007T130000654321Z  0123456789ab+dirty  unfinished  -  (interrupted)
"""

import json
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: pytest_history.py HISTORY_DIR [SUBSTRING ...]")
    history = Path(sys.argv[1])
    substrings = sys.argv[2:]
    paths = sorted(history.glob("*.jsonl"))
    if not paths:
        sys.exit(f"ERROR: no pytest history records in {history}")

    rows: dict[str, list[str]] = {}
    for path in paths:
        events = [json.loads(line) for line in path.read_text().splitlines()]
        session = events[0]
        if session["type"] != "session":
            sys.exit(f"ERROR: {path} does not begin with a session line")
        run = path.stem.split("-", 1)[0]
        commit = session["commit"][:12] + ("+dirty" if session["dirty"] else "")
        interrupted = "" if events[-1]["type"] == "finish" else "  (interrupted)"
        finished = {event["nodeid"]: event for event in events if event["type"] == "test"}
        started = [event["nodeid"] for event in events if event["type"] == "start"]
        for nodeid in started:
            if substrings and not any(substring in nodeid for substring in substrings):
                continue
            match finished.get(nodeid):
                case None:
                    cell = f"{'unfinished':<10}  -"
                case test:
                    cell = f"{test['outcome']:<10}  {test['duration']:.3f}s"
            rows.setdefault(nodeid, []).append(f"  {run}  {commit:<18}  {cell}{interrupted}")
    if not rows:
        sys.exit(f"ERROR: no recorded test matches {substrings}")

    for nodeid in sorted(rows):
        print(nodeid)
        print("\n".join(rows[nodeid]))


if __name__ == "__main__":
    main()
