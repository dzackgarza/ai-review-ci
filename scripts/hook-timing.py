#!/usr/bin/env python3
"""Record the duration of one run of the global pre-commit or pre-push hook.

``repo-hooks/hook-timing.sh`` calls this once, when the hook exits. The run's
wall-clock duration is printed and appended to
``<git-common-dir>/ai-review-ci/timing/hooks.jsonl``, one JSON line per run, so
each repository keeps its own durable record and linked worktrees share it.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
LOG_PATH = Path("ai-review-ci") / "timing" / "hooks.jsonl"


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
    parser.add_argument("--git-dir", required=True, type=Path, help="absolute common Git directory")
    parser.add_argument("--hook", required=True, help="hook name, such as pre-commit or pre-push")
    parser.add_argument("--started-at-ns", required=True, type=int)
    parser.add_argument("--duration-ms", required=True, type=int)
    parser.add_argument("--exit-code", required=True, type=int)
    parser.add_argument("--worktree", required=True)
    args = parser.parse_args(argv)

    record(args.git_dir, args.hook, args.started_at_ns, args.duration_ms, args.exit_code, args.worktree)
    print(f"{args.hook}: checks took {args.duration_ms / 1000:.1f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
