#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Drop the findings that an owner-granted exception covers from Semgrep JSON output.

    semgrep_exceptions.py <semgrep-exceptions.toml> <semgrep.json>

Rewrites <semgrep.json> in place without each finding whose rule, path and repository (the
GitHub slug of `origin` in the working directory) match an entry whose issue of
dzackgarza/ai-review-ci is open, and prints each dropped finding. The issue state comes from
the public GitHub REST API with no token (the QC tier runs without one, #218); if it cannot be
read, the gate fails. Exit 0 with no findings left, 1 with findings left,
2 when an issue state cannot be read.
"""

import json
import re
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

ISSUES = "dzackgarza/ai-review-ci"
GITHUB_REMOTE = re.compile(r"github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?/?$")


def repository() -> str | None:
    remote = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True)
    match = GITHUB_REMOTE.search(remote.stdout.strip()) if remote.returncode == 0 else None
    return match.group(1) if match else None


def issue_open(number: int) -> bool:
    url = f"https://api.github.com/repos/{ISSUES}/issues/{number}"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return json.load(response)["state"] == "open"
    except urllib.error.URLError as error:
        print(f"ERROR: semgrep exceptions: cannot read the state of {ISSUES}#{number}: {error}",
              file=sys.stderr)
        raise SystemExit(2) from error


def main() -> int:
    exceptions = tomllib.loads(Path(sys.argv[1]).read_text())["exception"]
    output = Path(sys.argv[2])
    payload = json.loads(output.read_text())
    here = repository()
    kept, open_issues = [], {}
    for result in payload["results"]:
        match = next((e for e in exceptions if e["repository"] == here and e["path"] == result["path"]
                      and e["rule"] == result["check_id"]), None)
        if match is not None and match["issue"] not in open_issues:
            open_issues[match["issue"]] = issue_open(match["issue"])
        if match is not None and open_issues[match["issue"]]:
            print(f"semgrep: excepted while {ISSUES}#{match['issue']} is open: "
                  f"{result['path']}:{result['start']['line']} {result['check_id']}")
            continue
        kept.append(result)
    payload["results"] = kept
    output.write_text(json.dumps(payload))
    return 1 if kept else 0


if __name__ == "__main__":
    raise SystemExit(main())
