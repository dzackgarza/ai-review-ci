"""Collate the acceptance shards' JUnit reports into one failure list.

Usage: acceptance_summary.py RESULTS_DIR

RESULTS_DIR holds one directory per shard (<name>-<shard>, written by
_sage-acceptance-shard), each with junit.xml and commit. Writes a Markdown report to
stdout and exits 1 when any shard lacks a report or any case did not pass. A skipped case
did not pass: the acceptance suite runs with --runxfail, so it has no sanctioned skips.
"""

import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

OUTCOMES = ("failure", "error", "skipped")


def main(results_dir: Path) -> int:
    shard_dirs = sorted(path for path in results_dir.iterdir() if path.is_dir())
    if not shard_dirs:
        raise SystemExit(f"no shard results in {results_dir}")
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    failures: dict[str, list[str]] = defaultdict(list)
    missing: list[str] = []
    commits = sorted({(shard / "commit").read_text().strip() for shard in shard_dirs if (shard / "commit").is_file()})
    for shard in shard_dirs:
        name = shard.name.rsplit("-", 1)[0]
        report = shard / "junit.xml"
        if not report.is_file():
            missing.append(shard.name)
            continue
        for case in ET.parse(report).getroot().iter("testcase"):
            node = f"{case.get('classname')}::{case.get('name')}"
            outcome = next((child for child in case if child.tag in OUTCOMES), None)
            if outcome is None:
                counts[name]["passed"] += 1
                continue
            counts[name][outcome.tag] += 1
            message = outcome.get("message", "")
            failures[name].append(f"- `{node}` ({outcome.tag}): {message.splitlines()[0] if message else ''}")
    print(f"# Acceptance at {', '.join(commits)}\n")
    print("| Suite | passed | failure | error | skipped |\n| --- | --- | --- | --- | --- |")
    for name in sorted(counts):
        row = counts[name]
        print(f"| {name} | {row['passed']} | {row['failure']} | {row['error']} | {row['skipped']} |")
    if missing:
        print("\n## Shards without a JUnit report (setup failure or hard timeout)\n")
        print("\n".join(f"- {shard}" for shard in missing))
    for name in sorted(failures):
        print(f"\n## {name}\n")
        print("\n".join(failures[name]))
    return 1 if missing or failures else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
