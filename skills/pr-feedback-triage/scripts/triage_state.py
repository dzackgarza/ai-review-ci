#!/usr/bin/env python3
"""Collect resumable, thread-local PR feedback triage state.

The collector paginates every inline review thread, derives a stable finding identity,
recognizes only the canonical thread-local disposition contract, and emits a worklist:
NEW | RE-RAISED | OPEN-PENDING | CLOSED.

Machine resume state lives under Git metadata. It never creates a tracked review log or
a top-level disposition ledger.

Usage:
  triage_state.py [--repo owner/name] [--pr N] [--json] [--no-write]

Defaults: --repo and --pr are derived from the current branch's PR when omitted.
Requires: gh (authenticated) and git. Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

FINGERPRINT_RE = re.compile(r"ai-review-fingerprint:\s*([0-9a-f]{8,})")
DISPOSITION_RE = re.compile(
    r"(?im)^Disposition:\s*"
    r"(Accepted as written|Accepted with modified remediation|Rejected|Outdated|"
    r"Duplicate|Investigate before action|Backlogged as minor technical debt)\s*$"
)
POLICY_BASIS_RE = re.compile(r"(?im)^Policy basis:\s*POLICY\.[A-Z0-9_]+\s*$")
FACTUAL_BASIS_RE = re.compile(r"(?im)^Factual/contract basis:\s*\S.+$")
ACTION_RE = re.compile(
    r"(?im)^Code/action taken or explicit non-change:\s*\S.+$"
)
PREFILTER_RE = re.compile(r"(?im)^Pre-filter:\s*\S.+$")
CLAIM_RE = re.compile(r"(?im)^Claim:\s*\S.+$")
REMEDIATION_RE = re.compile(r"(?im)^Remediation:\s*\S.+$")
PROOF_RE = re.compile(r"(?im)^Proof:\s*\S.+$")
COMMIT_RE = re.compile(r"(?im)^Commit:\s*([0-9a-f]{7,40})\s*$")
AUDIT_ANCHOR_RE = re.compile(r"(?im)^Audit anchor:\s*\S.+$")
CANONICAL_THREAD_RE = re.compile(r"(?im)^Canonical thread:\s*\S.+$")
SUPERSEDING_COMMIT_RE = re.compile(
    r"(?im)^Superseding commit:\s*([0-9a-f]{7,40})\s*$"
)
DEBT_ISSUE_RE = re.compile(
    r"(?im)^Debt issue:\s*https://github\.com/[^\s/]+/[^\s/]+/issues/\d+\s*$"
)


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False)


def gh_graphql(query: str, **variables: object) -> dict:
    args = ["gh", "api", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        flag = "-F" if isinstance(value, int) and not isinstance(value, bool) else "-f"
        args.extend([flag, f"{key}={value}"])
    result = run(args)
    if result.returncode != 0:
        sys.exit(f"gh graphql failed: {result.stderr.strip()[:400]}")
    return json.loads(result.stdout)


def resolve_target(repo: str | None, pr: int | None) -> tuple[str, int]:
    if not repo:
        result = run(
            ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]
        )
        repo = result.stdout.strip()
    if not pr:
        result = run(["gh", "pr", "view", "--json", "number", "-q", ".number"])
        if result.returncode != 0 or not result.stdout.strip():
            sys.exit("No PR for the current branch; pass --pr N.")
        pr = int(result.stdout.strip())
    if not repo or "/" not in repo:
        sys.exit("Could not resolve --repo owner/name.")
    return repo, int(pr)


def fetch_threads(repo: str, pr: int) -> list[dict]:
    owner, name = repo.split("/", 1)
    query = (
        "query($owner:String!,$name:String!,$pr:Int!,$cursor:String){"
        " repository(owner:$owner,name:$name){ pullRequest(number:$pr){"
        "  reviewThreads(first:100, after:$cursor){ pageInfo{hasNextPage endCursor}"
        "   nodes{ id isResolved isOutdated path line"
        "    comments(first:100){ nodes{ id databaseId url author{login} body createdAt }}}}}}}"
    )
    threads: list[dict] = []
    cursor: str | None = None
    while True:
        variables: dict[str, object] = {
            "owner": owner,
            "name": name,
            "pr": int(pr),
        }
        if cursor:
            variables["cursor"] = cursor
        data = gh_graphql(query, **variables)
        connection = data["data"]["repository"]["pullRequest"]["reviewThreads"]
        threads.extend(connection["nodes"])
        if not connection["pageInfo"]["hasNextPage"]:
            return threads
        cursor = connection["pageInfo"]["endCursor"]


def normalized_title(body: str) -> str:
    """Return the first meaningful line without badges or review markup."""
    visible_body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    for raw in visible_body.splitlines():
        line = raw
        line = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", line)
        line = re.sub(r"[#>*`\[\]]", "", line)
        line = re.sub(r"\[(General|Slop) Review\]\[tier\d\]", "", line, flags=re.I)
        line = re.sub(r"ai-review/\w+\s*/", "", line)
        line = line.strip()
        if len(line) >= 8:
            return line.lower()[:160]
    return visible_body.strip().lower()[:160]


def stable_key(thread: dict) -> str:
    comments = thread["comments"]["nodes"]
    first_body = comments[0]["body"] if comments else ""
    match = FINGERPRINT_RE.search(first_body)
    if match:
        return f"fp:{match.group(1)}"
    payload = f"{thread['path']}|{normalized_title(first_body)}".encode()
    return f"ct:{hashlib.sha256(payload).hexdigest()[:20]}"


def _complete_disposition(body: str, verdict: str) -> bool:
    has_basis = bool(POLICY_BASIS_RE.search(body) or FACTUAL_BASIS_RE.search(body))
    common = has_basis and bool(
        PREFILTER_RE.search(body)
        and CLAIM_RE.search(body)
        and ACTION_RE.search(body)
        and AUDIT_ANCHOR_RE.search(body)
    )
    normalized = verdict.lower()
    if normalized.startswith("accepted"):
        return common and bool(
            REMEDIATION_RE.search(body)
            and PROOF_RE.search(body)
            and COMMIT_RE.search(body)
        )
    if normalized == "duplicate":
        return common and bool(CANONICAL_THREAD_RE.search(body))
    if normalized == "outdated":
        return common and bool(SUPERSEDING_COMMIT_RE.search(body))
    if normalized == "backlogged as minor technical debt":
        return common and bool(DEBT_ISSUE_RE.search(body))
    if normalized == "rejected":
        return common
    return False


def disposition_of(thread: dict) -> dict | None:
    """Parse the first canonical disposition reply, never the finding itself."""
    for comment in thread["comments"]["nodes"][1:]:
        body = comment["body"] or ""
        match = DISPOSITION_RE.search(body)
        if not match:
            continue
        verdict = match.group(1)
        commit = COMMIT_RE.search(body)
        return {
            "verdict": verdict.lower(),
            "complete": _complete_disposition(body, verdict),
            "commit": commit.group(1) if commit else None,
            "by": comment["author"]["login"] if comment["author"] else None,
            "url": comment.get("url"),
        }
    return None


def state_path(pr: int) -> Path:
    result = run(
        ["git", "rev-parse", "--git-path", f"ai-review-ci/pr-feedback-triage-{pr}.json"]
    )
    if result.returncode != 0 or not result.stdout.strip():
        sys.exit("Could not resolve Git metadata path; run inside the PR worktree.")
    return Path(result.stdout.strip())


def load_previous(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        sys.exit(f"Could not read triage state {path}: {error}")
    dispositions: dict[str, dict] = {}
    for record in payload.get("records", []):
        disposition = record.get("disp")
        if disposition and disposition.get("complete"):
            dispositions[record["key"]] = disposition
    return dispositions


def classify(
    thread: dict,
    disposition: dict | None,
    previous_disposition: dict | None,
) -> str:
    if disposition and disposition.get("complete") and thread["isResolved"]:
        return "CLOSED"
    if disposition:
        return "OPEN-PENDING"
    if previous_disposition:
        return "RE-RAISED"
    return "NEW"


def build_records(threads: list[dict], previous: dict[str, dict]) -> list[dict]:
    records: list[dict] = []
    seen_complete = dict(previous)
    for thread in threads:
        key = stable_key(thread)
        disposition = disposition_of(thread)
        state = classify(thread, disposition, seen_complete.get(key))
        first_comment = (
            thread["comments"]["nodes"][0] if thread["comments"]["nodes"] else {}
        )
        record = {
            "key": key,
            "thread_id": thread["id"],
            "url": first_comment.get("url"),
            "path": thread["path"],
            "line": thread["line"],
            "resolved": thread["isResolved"],
            "outdated": thread["isOutdated"],
            "state": state,
            "disp": disposition,
        }
        records.append(record)
        if disposition and disposition.get("complete"):
            seen_complete[key] = disposition
    return records


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resumable thread-local PR review triage state."
    )
    parser.add_argument("--repo")
    parser.add_argument("--pr", type=int)
    parser.add_argument("--json", action="store_true", help="emit the worklist as JSON")
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="do not update resumable state under Git metadata",
    )
    args = parser.parse_args()

    repo, pr = resolve_target(args.repo, args.pr)
    path = state_path(pr)
    previous = load_previous(path)
    records = build_records(fetch_threads(repo, pr), previous)

    counts: dict[str, int] = {}
    for record in records:
        counts[record["state"]] = counts.get(record["state"], 0) + 1
    converged = not any(
        counts.get(state, 0) for state in ("NEW", "RE-RAISED", "OPEN-PENDING")
    )
    payload = {
        "repo": repo,
        "pr": pr,
        "counts": counts,
        "converged": converged,
        "records": records,
    }

    if not args.no_write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    worklist = [
        record
        for record in records
        if record["state"] in ("NEW", "RE-RAISED", "OPEN-PENDING")
    ]
    if args.json:
        print(
            json.dumps(
                {
                    "counts": counts,
                    "converged": converged,
                    "state_path": None if args.no_write else str(path),
                    "worklist": worklist,
                },
                indent=2,
            )
        )
        return

    rendered_counts = "  ".join(
        f"{state}={count}" for state, count in sorted(counts.items())
    )
    print(f"{repo} PR #{pr}: {len(records)} threads  {rendered_counts}")
    print(
        "CONVERGED: "
        f"{converged}  "
        "(terminate only when NEW=0, RE-RAISED=0, and OPEN-PENDING=0)\n"
    )
    for state in ("NEW", "RE-RAISED", "OPEN-PENDING"):
        rows = [record for record in records if record["state"] == state]
        if not rows:
            continue
        print(f"== {state} ({len(rows)}) ==")
        for record in rows:
            verdict = (
                f" [{record['disp']['verdict']}]" if record["disp"] else ""
            )
            print(
                f"  {record['path']}:{record['line']}  "
                f"{record['key']}{verdict}  {record['thread_id'][-8:]}"
            )
        print()


if __name__ == "__main__":
    main()
