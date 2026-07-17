"""Post validated review findings to a PR as one review with resolvable threads.

Runner-side automation: consumes the validated artifact and the PR diff,
never involves the reviewer agent. One review per run: a top-level body
(summary + metadata) plus one inline, individually-resolvable comment per
finding. Findings are deduplicated against threads already on the PR via a
fingerprint marker (``finding_fingerprint``, the same components as the
SARIF reviewFindingKey: category | path; agent-chosen labels are excluded
because they are free text reinvented each run).

Anchor classification (computed from the diff before posting, no fallbacks):
- a finding line visible in the diff       -> line-anchored thread
- file in diff, lines outside its hunks    -> thread on the file's first
                                              visible line (body carries the
                                              real range)
- file not in the diff                     -> listed in the top-level body
                                              only (already tracked in code
                                              scanning)

Thread bodies are diagnosis-only: no remediation is rendered or expected.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn

from unidiff import PatchSet

from ai_review_ci.models import finding_fingerprint
from ai_review_ci.policy_index import canonical_route
from ai_review_ci.reviewer_identity import reviewer_identity

JsonDict = dict[str, Any]

FINGERPRINT_MARKER = "ai-review-fingerprint:"
REVIEW_LABELS = {"general": "General Review", "slop": "Slop Review"}
REVIEW_IDENTITY_MARKER = "ai-review-reviewer:"

THREADS_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes { comments(first: 1) { nodes { body } } }
      }
    }
  }
}
"""


def _fail(msg: str) -> NoReturn:
    print(f"FATAL: {msg}", file=sys.stderr)
    sys.exit(1)


def _gh_json(args: list[str], body: JsonDict | None = None) -> JsonDict:
    result = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        input=json.dumps(body) if body is not None else None,
    )
    if result.returncode != 0:
        _fail(f"gh {' '.join(args[:3])} failed: {result.stderr.strip()}")
    data: JsonDict = json.loads(result.stdout)
    return data


def parse_diff(text: str) -> dict[str, set[int]]:
    """Map each file in the diff to its commentable RIGHT-side line numbers.

    Commentable lines are those visible in the unified diff on the new side:
    added lines and context lines within hunks. Deleted files have no new
    side and are omitted.
    """
    files: dict[str, set[int]] = {}
    for patched_file in PatchSet(text.splitlines(keepends=True)):
        if patched_file.is_removed_file:
            continue
        commentable: set[int] = set()
        for hunk in patched_file:
            for line in hunk:
                if not (line.is_added or line.is_context):
                    continue
                if line.target_line_no is None:
                    _fail(f"missing target line number in diff for {patched_file.path}")
                commentable.add(line.target_line_no)
        files[patched_file.path] = commentable
    return files


def existing_fingerprints(repo: str, pr_number: int) -> set[str]:
    """Fingerprints already present in any review thread on the PR."""
    owner, name = repo.split("/")
    found: set[str] = set()
    cursor: str | None = None
    while True:
        args = [
            "api",
            "graphql",
            "-f",
            f"query={THREADS_QUERY}",
            "-F",
            f"owner={owner}",
            "-F",
            f"name={name}",
            "-F",
            f"number={pr_number}",
        ]
        if cursor:
            args.extend(["-F", f"cursor={cursor}"])
        data = _gh_json(args)
        threads = data["data"]["repository"]["pullRequest"]["reviewThreads"]
        for node in threads["nodes"]:
            for comment in node["comments"]["nodes"]:
                for m in re.finditer(
                    re.escape(FINGERPRINT_MARKER) + r"\s*([0-9a-f]{64})",
                    comment["body"],
                ):
                    found.add(m.group(1))
        if not threads["pageInfo"]["hasNextPage"]:
            break
        cursor = threads["pageInfo"]["endCursor"]
    return found


def pick_anchor(finding: JsonDict, commentable: dict[str, set[int]]) -> int | None:
    """Best RIGHT-side anchor line for a finding, or None if file is off-diff."""
    loc = finding["location"]
    lines = commentable.get(str(loc["path"]))
    if not lines:
        return None
    for ln in range(loc["start_line"], loc["end_line"] + 1):
        if ln in lines:
            return ln
    return min(lines)


def _thread_body_lines(finding: JsonDict, review_label: str, fp: str) -> list[str]:
    loc = finding["location"]
    review_type = next((key for key, label in REVIEW_LABELS.items() if label == review_label), "general")
    identity = reviewer_identity(review_type)
    lines = [
        f"### [{review_label}][{finding['tier']}] {finding['label']}",
        f"<!-- {FINGERPRINT_MARKER} {fp} -->",
        f"<!-- {REVIEW_IDENTITY_MARKER} {json.dumps(identity, sort_keys=True)} -->",
        "",
        f"**Location:** `{loc['path']}:{loc['start_line']}-{loc['end_line']}`",
        (f"**Reviewer identity:** `type={review_type}; agent={identity['agent']}; prompt_id=reviews/{review_type}; prompt_version={identity['prompt_version']}`"),
        f"**Violated invariant:** {finding['violated_invariant']}",
        f"**Proof:** `{finding['proof_command']}`",
    ]
    for key, title in [
        ("symptom", "Symptom"),
        ("source", "Source"),
        ("consequence", "Consequence"),
        ("pattern", "Pattern"),
        ("why_it_matters", "Why this matters"),
    ]:
        if finding.get(key):
            lines.append(f"**{title}:** {finding[key]}")
    ev_parts = [f"`{e['path']}:{e['lines'][0]}-{e['lines'][1]}` ({e['kind']})" for e in finding["evidence"]]
    lines.append(f"**Evidence:** {', '.join(ev_parts)}")
    policy_code = finding.get("policy_code")
    if isinstance(policy_code, str):
        route = canonical_route(policy_code)
        lines.extend(
            [
                "",
                "#### Canonical catalogue route",
                f"`{route.policy_code}` → `{route.remediation_code}`",
            ]
        )
    return lines


def render_thread_body(finding: JsonDict, review_label: str, fp: str) -> str:
    return "\n".join(_thread_body_lines(finding, review_label, fp))


def render_review_body(
    review_label: str,
    findings: list[JsonDict],
    posted: int,
    possible_duplicates: int,
    off_diff: list[JsonDict],
) -> str:
    run_url = f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    tier1 = sum(1 for f in findings if f["tier"] == "tier1")
    tier2 = sum(1 for f in findings if f["tier"] == "tier2")
    lines = [
        f"## {review_label} — automated PR review",
        "",
        f"Run: {run_url}",
        f"Findings: {len(findings)} (tier1 {tier1}, tier2 {tier2}) | "
        f"threads posted: {posted} | possible duplicates: {possible_duplicates} | "
        f"off-diff (tracker only): {len(off_diff)}",
    ]
    if off_diff:
        lines.extend(
            [
                "",
                "### Off-diff findings (tracked in code scanning, no thread)",
                "",
            ]
        )
        for f in off_diff:
            loc = f["location"]
            lines.append(f"- `{loc['path']}:{loc['start_line']}-{loc['end_line']}` — [{f['tier']}] {f['label']}: {f['violated_invariant']}")
    return "\n".join(lines)


def partition_findings(
    findings: list[JsonDict],
    commentable: dict[str, set[int]],
    seen: set[str],
    review_label: str,
) -> tuple[list[JsonDict], list[JsonDict], int]:
    """Split findings into new inline comments, off-diff entries, and skipped duplicates."""
    seen = set(seen)
    comments: list[JsonDict] = []
    off_diff: list[JsonDict] = []
    possible_duplicates = 0
    for finding in findings:
        loc = finding["location"]
        fp = finding_fingerprint(finding["category"], str(loc["path"]))
        if fp in seen:
            possible_duplicates += 1
            continue
        seen.add(fp)
        thread_body = render_thread_body(finding, review_label, fp)
        anchor = pick_anchor(finding, commentable)
        if anchor is None:
            off_diff.append(finding)
            continue
        comments.append(
            {
                "path": str(loc["path"]),
                "line": anchor,
                "side": "RIGHT",
                "body": thread_body,
            }
        )
    return comments, off_diff, possible_duplicates


def post_threads(artifact: Path, diff: Path, repo: str, pr_number: int) -> None:
    """Post validated findings as resolvable PR review threads.

    Args:
        artifact: Path to the validated .review-report-artifact.json.
        diff: Path to the staged PR diff (reviewer-diff.patch).
        repo: Repository in owner/repo format.
        pr_number: Pull request number to post the review on.
    """
    data: JsonDict = json.loads(artifact.read_text())
    report_type = data["report_type"]
    review_label = REVIEW_LABELS[report_type]
    findings = data["findings"]

    commentable = parse_diff(diff.read_text())
    seen = existing_fingerprints(repo, pr_number)

    comments, off_diff, possible_duplicates = partition_findings(findings, commentable, seen, review_label)

    if not comments and not off_diff:
        print(f"All {len(findings)} finding(s) already have threads on PR #{pr_number}; nothing to post.")
        return

    payload = {
        "event": "COMMENT",
        "body": render_review_body(review_label, findings, len(comments), possible_duplicates, off_diff),
        "comments": comments,
    }
    _gh_json(
        [
            "api",
            "--method",
            "POST",
            f"repos/{repo}/pulls/{pr_number}/reviews",
            "--input",
            "-",
        ],
        body=payload,
    )
    print(f"Posted review to PR #{pr_number}: {len(comments)} thread(s), {possible_duplicates} possible duplicate(s), {len(off_diff)} off-diff.")
