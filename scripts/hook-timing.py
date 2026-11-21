#!/usr/bin/env python3
"""Record and estimate the duration of the global pre-commit and pre-push hooks.

``repo-hooks/hook-timing.sh`` calls ``estimate`` when a hook starts and ``record``
when it exits. The history is ``<git-common-dir>/ai-review-ci/timing/hooks.jsonl``,
one JSON line per run, so each repository keeps its own durable record and linked
worktrees share it. The estimate is the median duration of the most recent
successful runs of the same hook.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
LOG_PATH = Path("ai-review-ci") / "timing" / "hooks.jsonl"
ESTIMATE_WINDOW = 10


def read_history(git_dir: Path, hook: str) -> list[int]:
    """Durations in milliseconds of successful runs of ``hook``, oldest first."""
    log = git_dir / LOG_PATH
    if not log.exists():
        return []
    records = (json.loads(line) for line in log.read_text(encoding="utf-8").splitlines())
    return [r["duration_ms"] for r in records if r["hook"] == hook and r["exit_code"] == 0]


def estimate(git_dir: Path, hook: str) -> str:
    durations = read_history(git_dir, hook)[-ESTIMATE_WINDOW:]
    if not durations:
        return f"{hook}: no timing history yet in this repository"
    seconds = statistics.median(durations) / 1000
    noun = "run" if len(durations) == 1 else "runs"
    return f"{hook}: expected {seconds:.1f}s (median of {len(durations)} previous {noun})"


def record(git_dir: Path, hook: str, started_at_ns: int, duration_ms: int, exit_code: int, worktree: str) -> None:
    log = git_dir / LOG_PATH
    log.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "schema": SCHEMA_VERSION,
        "hook": hook,
        "started_at": datetime.fromtimestamp(started_at_ns / 1e9, tz=timezone.utc).isoformat(),
        "duration_ms": duration_ms,
        "exit_code": exit_code,
        "worktree": worktree,
    }
    # One short O_APPEND write is atomic on a local filesystem, so concurrent
    # hook runs in one repository never interleave a line.
    with log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("estimate", "record"):
        command = sub.add_parser(name)
        command.add_argument("--git-dir", required=True, type=Path, help="absolute common Git directory")
        command.add_argument("--hook", required=True, help="hook name, such as pre-commit or pre-push")
    recorder = sub.choices["record"]
    recorder.add_argument("--started-at-ns", required=True, type=int)
    recorder.add_argument("--duration-ms", required=True, type=int)
    recorder.add_argument("--exit-code", required=True, type=int)
    recorder.add_argument("--worktree", required=True)
    args = parser.parse_args(argv)

    if args.command == "estimate":
        print(estimate(args.git_dir, args.hook), file=sys.stderr)
        return 0
    record(args.git_dir, args.hook, args.started_at_ns, args.duration_ms, args.exit_code, args.worktree)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
