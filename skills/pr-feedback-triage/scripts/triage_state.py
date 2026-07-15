#!/usr/bin/env python3
"""Collect resumable, thread-local PR feedback triage state.

The collector paginates every inline review thread and every comment in those
threads, derives a stable finding identity, recognizes only the canonical
thread-local disposition contract, and emits a worklist:
NEW | RE-RAISED | OPEN-PENDING | CLOSED.

Machine resume state lives under Git metadata. It never creates a tracked
review log or a top-level disposition ledger.

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
    r"Duplicate|Investigate before action|Backlogged as minor technical debt)\s*\.?\s*$"
)
POLICY_CODE_RE = re.compile(r"\bPOLICY\.[A-Z][A-Z0-9_]*\b", re.IGNORECASE)
COMMIT_RE = re.compile(r"(?im)^Commit:\s*([0-9a-f]{7,40})\s*$")
SUPERSEDING_COMMIT_RE = re.compile(
    r"(?im)^Superseding commit:\s*([0-9a-f]{7,40})\s*$"
)
DEBT_ISSUE_RE = re.compile(
    r"https://github\.com/[^\s/]+/[^\s/]+/issues/\d+\s*$",
    re.IGNORECASE,
)
BURDEN_DISPOSITION_RE = re.compile(
    r"(?i)^(?:solved by|invalidated by|transferred to|remains open in)\b"
)

THREADS_QUERY = (
    "query($owner:String!,$name:String!,$pr:Int!,$cursor:String){"
    " repository(owner:$owner,name:$name){ pullRequest(number:$pr){ headRefOid"
    "  reviewThreads(first:100, after:$cursor){ pageInfo{hasNextPage endCursor}"
    "   nodes{ id isResolved isOutdated path line"
    "    comments(first:100){ pageInfo{hasNextPage endCursor}"
    "     nodes{ id databaseId url author{login} body createdAt }}}}}}}}"
)
COMMENTS_QUERY = (
    "query($thread:ID!,$cursor:String){ node(id:$thread){"
    " ... on PullRequestReviewThread { comments(first:100, after:$cursor){"
    "  pageInfo{hasNextPage endCursor}"
    "  nodes{ id databaseId url author{login} body createdAt }}}}}"
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
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        sys.exit(f"gh graphql returned invalid JSON: {error}")
    if not isinstance(payload, dict):
        sys.exit("gh graphql returned a non-object payload.")
    return payload


def _object(value: object, context: str) -> dict:
    if not isinstance(value, dict):
        sys.exit(f"GitHub returned invalid {context}: expected an object.")
    return value


def _array(value: object, context: str) -> list:
    if not isinstance(value, list):
        sys.exit(f"GitHub returned invalid {context}: expected an array.")
    return value


def _field_value(body: str, label: str) -> str | None:
    match = re.search(
        rf"(?im)^\s*{re.escape(label)}:\s*(?P<value>\S(?:.*\S)?)\s*$",
        body,
    )
    if match is None:
        return None
    value = match.group("value").strip()
    if re.fullmatch(r"<[^>]+>", value):
        return None
    return value


def _basis_is_valid(body: str) -> bool:
    policy = _field_value(body, "Policy basis")
    if policy is not None and POLICY_CODE_RE.search(policy):
        return True
    return _field_value(body, "Factual/contract basis") is not None


def _deletion_fields_are_valid(body: str) -> bool:
    artifact = _field_value(body, "Deleted artifact")
    if artifact is None:
        return False
    if artifact.casefold() == "none":
        return True
    burden = _field_value(body, "Original burden")
    disposition = _field_value(body, "Burden disposition")
    verification = _field_value(body, "Verification")
    return bool(
        burden
        and disposition
        and BURDEN_DISPOSITION_RE.search(disposition)
        and verification
    )


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


def _remaining_comments(thread_id: str, cursor: str) -> list[dict]:
    comments: list[dict] = []
    next_cursor: str | None = cursor
    while next_cursor:
        payload = gh_graphql(
            COMMENTS_QUERY,
            thread=thread_id,
            cursor=next_cursor,
        )
        data = _object(payload.get("data"), "GraphQL data")
        node = data.get("node")
        if node is None:
            sys.exit(f"Review thread {thread_id} not found or inaccessible.")
        connection = _object(
            _object(node, "review thread").get("comments"),
            "review-thread comments connection",
        )
        comments.extend(
            _array(connection.get("nodes"), "review-thread comment nodes")
        )
        page_info = _object(
            connection.get("pageInfo"),
            "review-thread comment page info",
        )
        if not page_info.get("hasNextPage"):
            break
        next_cursor = page_info.get("endCursor")
        if not isinstance(next_cursor, str) or not next_cursor:
            sys.exit("GitHub reported another comment page without an end cursor.")
    return comments


def fetch_threads(repo: str, pr: int) -> tuple[str, list[dict]]:
    owner, name = repo.split("/", 1)
    threads: list[dict] = []
    head_sha: str | None = None
    cursor: str | None = None
    while True:
        variables: dict[str, object] = {
            "owner": owner,
            "name": name,
            "pr": int(pr),
        }
        if cursor:
            variables["cursor"] = cursor
        payload = gh_graphql(THREADS_QUERY, **variables)
        data = _object(payload.get("data"), "GraphQL data")
        repository = data.get("repository")
        if repository is None:
            sys.exit(f"Repository {repo} not found or inaccessible.")
        pull_request = _object(repository, "repository").get("pullRequest")
        if pull_request is None:
            sys.exit(f"Pull request #{pr} not found in {repo}.")
        pr_data = _object(pull_request, "pull request")
        observed_head = pr_data.get("headRefOid")
        if not isinstance(observed_head, str) or not re.fullmatch(
            r"[0-9a-f]{40}", observed_head, re.IGNORECASE
        ):
            sys.exit(f"Pull request #{pr} returned an invalid head SHA.")
        if head_sha is None:
            head_sha = observed_head
        elif head_sha != observed_head:
            sys.exit("The PR head changed during collection; rerun the collector.")

        connection = _object(
            pr_data.get("reviewThreads"),
            "review-threads connection",
        )
        page_threads = _array(connection.get("nodes"), "review-thread nodes")
        for raw_thread in page_threads:
            thread = _object(raw_thread, "review thread")
            comments = _object(
                thread.get("comments"),
                "review-thread comments connection",
            )
            nodes = _array(comments.get("nodes"), "review-thread comment nodes")
            page_info = _object(
                comments.get("pageInfo"),
                "review-thread comment page info",
            )
            if page_info.get("hasNextPage"):
                comment_cursor = page_info.get("endCursor")
                if not isinstance(comment_cursor, str) or not comment_cursor:
                    sys.exit(
                        "GitHub reported another comment page without an end cursor."
                    )
                nodes.extend(
                    _remaining_comments(str(thread.get("id", "")), comment_cursor)
                )
            comments["nodes"] = nodes
            thread["comments"] = comments
            threads.append(thread)

        page_info = _object(connection.get("pageInfo"), "review-thread page info")
        if not page_info.get("hasNextPage"):
            assert head_sha is not None
            return head_sha, threads
        cursor = page_info.get("endCursor")
        if not isinstance(cursor, str) or not cursor:
            sys.exit("GitHub reported another review-thread page without an end cursor.")


def _visible_finding(body: str) -> str:
    visible = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    visible = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", visible)
    visible = re.sub(
        r"\[(General|Slop) Review\]\[tier\d\]",
        "",
        visible,
        flags=re.IGNORECASE,
    )
    visible = re.sub(r"ai-review/\w+\s*/", "", visible)
    return " ".join(visible.casefold().split())


def normalized_title(body: str) -> str:
    """Return the first meaningful line without badges or review markup."""
    visible_body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    for raw in visible_body.splitlines():
        line = raw
        line = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", line)
        line = re.sub(r"[#>*\x60\[\]]", "", line)
        line = re.sub(
            r"\[(General|Slop) Review\]\[tier\d\]",
            "",
            line,
            flags=re.IGNORECASE,
        )
        line = re.sub(r"ai-review/\w+\s*/", "", line)
        line = line.strip()
        if len(line) >= 8:
            return line.lower()[:160]
    return visible_body.strip().lower()[:160]


def stable_key(thread: dict) -> str:
    comments = _object(thread.get("comments"), "review-thread comments")
    nodes = _array(comments.get("nodes"), "review-thread comment nodes")
    first_body = str(_object(nodes[0], "root review comment").get("body", "")) if nodes else ""
    match = FINGERPRINT_RE.search(first_body)
    if match:
        return f"fp:{match.group(1)}"
    payload = f"{thread.get('path', '')}|{_visible_finding(first_body)}".encode()
    return f"ct:{hashlib.sha256(payload).hexdigest()[:20]}"


def _complete_disposition(body: str, verdict: str) -> bool:
    common = _basis_is_valid(body) and all(
        _field_value(body, label) is not None
        for label in (
            "Pre-filter",
            "Claim",
            "Code/action taken or explicit non-change",
            "Audit anchor",
        )
    )
    normalized = verdict.lower()
    if normalized.startswith("accepted"):
        commit = COMMIT_RE.search(body)
        return common and bool(
            _field_value(body, "Remediation")
            and _field_value(body, "Proof")
            and commit
            and _deletion_fields_are_valid(body)
        )
    if normalized == "duplicate":
        return common and _field_value(body, "Canonical thread") is not None
    if normalized == "outdated":
        return common and SUPERSEDING_COMMIT_RE.search(body) is not None
    if normalized == "backlogged as minor technical debt":
        issue = _field_value(body, "Debt issue")
        return common and bool(issue and DEBT_ISSUE_RE.fullmatch(issue))
    if normalized == "rejected":
        return common
    return False


def disposition_of(thread: dict) -> dict | None:
    """Return the latest complete disposition reply, or latest incomplete reply."""
    comments = _object(thread.get("comments"), "review-thread comments")
    nodes = _array(comments.get("nodes"), "review-thread comment nodes")
    candidates: list[dict] = []
    for raw_comment in nodes[1:]:
        comment = _object(raw_comment, "review comment")
        body = str(comment.get("body") or "")
        match = DISPOSITION_RE.search(body)
        if not match:
            continue
        verdict = match.group(1)
        commit = COMMIT_RE.search(body)
        author = comment.get("author")
        login = _object(author, "review-comment author").get("login") if author else None
        candidates.append(
            {
                "verdict": verdict.lower(),
                "complete": _complete_disposition(body, verdict),
                "commit": commit.group(1) if commit else None,
                "by": login,
                "url": comment.get("url"),
                "comment_id": comment.get("databaseId"),
                "created_at": comment.get("createdAt"),
                "body": body,
            }
        )
    for candidate in reversed(candidates):
        if candidate["complete"]:
            return candidate
    return candidates[-1] if candidates else None


def state_path(repo: str, pr: int) -> Path:
    repo_slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", repo).strip("-")
    result = run(
        [
            "git",
            "rev-parse",
            "--git-path",
            f"ai-review-ci/{repo_slug}/pr-feedback-triage-{pr}.json",
        ]
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
    if not isinstance(payload, dict):
        sys.exit(f"Invalid triage state {path}: expected a JSON object.")
    records = payload.get("records", [])
    if not isinstance(records, list):
        sys.exit(f"Invalid triage state {path}: records must be an array.")
    dispositions: dict[str, dict] = {}
    for raw_record in records:
        if not isinstance(raw_record, dict):
            sys.exit(f"Invalid triage state {path}: every record must be an object.")
        key = raw_record.get("key")
        disposition = raw_record.get("disp")
        if not isinstance(key, str):
            sys.exit(f"Invalid triage state {path}: record key must be a string.")
        if disposition is None:
            continue
        if not isinstance(disposition, dict):
            sys.exit(f"Invalid triage state {path}: disposition must be an object.")
        if disposition.get("complete") is True:
            dispositions[key] = disposition
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


def build_records(
    threads: list[dict],
    previous: dict[str, dict],
    head_sha: str,
) -> list[dict]:
    records: list[dict] = []
    seen_complete = dict(previous)
    for thread in threads:
        key = stable_key(thread)
        disposition = disposition_of(thread)
        state = classify(thread, disposition, seen_complete.get(key))
        comments_connection = _object(thread.get("comments"), "review-thread comments")
        comments = _array(comments_connection.get("nodes"), "review-thread comment nodes")
        finding = _object(comments[0], "root review comment") if comments else {}
        author = finding.get("author")
        record = {
            "key": key,
            "thread_id": thread["id"],
            "url": finding.get("url"),
            "path": thread["path"],
            "line": thread["line"],
            "resolved": thread["isResolved"],
            "outdated": thread["isOutdated"],
            "state": state,
            "head_sha": head_sha,
            "author": _object(author, "review-comment author").get("login") if author else None,
            "finding": finding,
            "comments": comments,
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
    path = state_path(repo, pr)
    previous = load_previous(path)
    head_sha, threads = fetch_threads(repo, pr)
    records = build_records(threads, previous, head_sha)

    counts: dict[str, int] = {}
    for record in records:
        counts[record["state"]] = counts.get(record["state"], 0) + 1
    inline_threads_converged = not any(
        counts.get(state, 0) for state in ("NEW", "RE-RAISED", "OPEN-PENDING")
    )
    payload = {
        "repo": repo,
        "pr": pr,
        "head_sha": head_sha,
        "counts": counts,
        "inline_threads_converged": inline_threads_converged,
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
                    "head_sha": head_sha,
                    "counts": counts,
                    "inline_threads_converged": inline_threads_converged,
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
        "INLINE THREADS CONVERGED: "
        f"{inline_threads_converged}  "
        "(whole-PR convergence also requires every non-thread surface)\n"
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
