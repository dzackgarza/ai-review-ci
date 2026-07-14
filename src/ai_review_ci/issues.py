"""Publish validated review findings as GitHub issues — the issues ledger.

Runner-side automation for repositories where code scanning is unavailable
(private repos without a Code Security license). One issue per tracked
finding, keyed by a fingerprint marker in the issue body:

- an OPEN issue with the same fingerprint is updated in place (line numbers
  and narrative refresh), never duplicated;
- a CLOSED issue with the same fingerprint is a disposition: it is left
  untouched and suppresses re-creation — a materially different recurrence
  produces a different fingerprint and therefore a new issue;
- issues are never closed by automation merely because a later reviewer
  omitted the finding. Closing (with a reason) is the human triage act.

Issue identity is finer than the SARIF/thread fingerprint: the agent label
participates (``category | path | label``), because one file can carry two
distinct violated invariants of the same category and the issues ledger
must not collapse them into one tracked item. Open issues are fed to later
reviewers as do-not-re-raise context (see ``context.py``), which keeps
label drift from manufacturing duplicates.

New issues carry the ``ai-review``, ``needs-triage``, and
``ai-review/<report_type>`` labels and are attached as sub-issues of the
configured parent grouping issue.
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn

from ai_review_ci.models import finding_fingerprint
from ai_review_ci.reviewer_identity import reviewer_identity

JsonDict = dict[str, Any]

FINGERPRINT_MARKER = "ai-review-fingerprint:"
ISSUE_LABELS = ("ai-review", "needs-triage")
LABEL_COLORS = {
    "ai-review": "1d76db",
    "needs-triage": "d93f0b",
    "ai-review/general": "0e8a16",
    "ai-review/slop": "5319e7",
}

# Narrative fields rendered by presence, mirroring sarif._OPTIONAL_PROPERTY_KEYS.
_NARRATIVE_KEYS = (
    ("violated_invariant", "Violated invariant"),
    ("symptom", "Symptom"),
    ("source", "Source"),
    ("consequence", "Consequence"),
    ("pattern", "Slop pattern"),
    ("task_narrative", "Task narrative"),
    ("slop_narrative", "Slop narrative"),
    ("why_it_matters", "Why it matters"),
    ("user_surprise", "User surprise"),
    ("existential_justification", "Existential justification"),
    ("failure_mode", "Failure mode"),
    ("policy_code", "Policy"),
    ("remediation_code", "Remediation"),
)


def _fail(msg: str) -> NoReturn:
    print(f"FATAL: {msg}", file=sys.stderr)
    sys.exit(1)


def issue_fingerprint(category: str, path: str, label: str) -> str:
    """Issue-ledger identity: category | path | label.

    Finer than :func:`ai_review_ci.models.finding_fingerprint` (category |
    path): two distinct invariants in one file must be two tracked issues.
    The coarse fingerprint is also stamped into the body so the SARIF/thread
    identity remains recoverable.
    """
    return hashlib.sha256("|".join([category, path, label]).encode()).hexdigest()


def _gh_api(args: list[str], *, input_body: JsonDict | None = None) -> JsonDict | list[JsonDict]:
    result = subprocess.run(
        ["gh", "api", *args],
        capture_output=True,
        text=True,
        input=json.dumps(input_body) if input_body is not None else None,
    )
    if result.returncode != 0:
        _fail(f"gh api {args[0]} failed: {result.stderr.strip()}")
    data: JsonDict | list[JsonDict] = json.loads(result.stdout)
    return data


def _ensure_labels(repo: str, labels: list[str]) -> None:
    """Create any missing ledger labels; an existing label is not an error."""
    for label in labels:
        result = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{repo}/labels",
                "-f",
                f"name={label}",
                "-f",
                f"color={LABEL_COLORS.get(label, 'ededed')}",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 and "already_exists" not in result.stdout + result.stderr:
            _fail(f"creating label {label!r} failed: {result.stderr.strip()}")


def _ledger_issues(repo: str) -> list[JsonDict]:
    """Every ai-review ledger issue (open and closed), fingerprint-marked."""
    issues: list[JsonDict] = []
    page = 1
    while True:
        batch = _gh_api(
            [
                f"repos/{repo}/issues?state=all&labels=ai-review&per_page=100&page={page}",
            ]
        )
        if not isinstance(batch, list):
            _fail("gh api issues returned non-list JSON")
        issues.extend(batch)
        if len(batch) < 100:
            return [i for i in issues if "pull_request" not in i]
        page += 1


def _marked_fingerprint(body: str) -> str | None:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"<!-- {FINGERPRINT_MARKER}"):
            return stripped.removeprefix(f"<!-- {FINGERPRINT_MARKER}").removesuffix("-->").strip()
    return None


def _issue_title(finding: JsonDict, report_type: str) -> str:
    loc = finding["location"]
    return f"[ai-review/{report_type}] {finding['label']}: {loc['path']}:{loc['start_line']}"


def _issue_body(finding: JsonDict, report_type: str, parent_issue: int) -> str:
    loc = finding["location"]
    fingerprint = issue_fingerprint(finding["category"], str(loc["path"]), finding["label"])
    coarse = finding_fingerprint(finding["category"], str(loc["path"]))
    lines = [
        f"<!-- {FINGERPRINT_MARKER} {fingerprint} -->",
        f"<!-- ai-review-coarse-fingerprint: {coarse} -->",
        f"**{finding['label']}** — `{loc['path']}:{loc['start_line']}-{loc['end_line']}` ({finding['tier']}, {finding['category']})",
        "",
    ]
    for key, heading in _NARRATIVE_KEYS:
        value = finding.get(key)
        if isinstance(value, str) and value:
            lines.append(f"**{heading}:** {value}")
    proof = finding.get("proof_command")
    if isinstance(proof, str) and proof:
        lines.extend(["", "**Proof:**", "```", proof, "```"])
    identity = reviewer_identity(report_type)
    lines.extend(
        [
            "",
            f"Reviewer identity: `type={identity['type']}; agent={identity['agent']}; "
            f"prompt_id={identity['prompt_id']}; prompt_version={identity['prompt_version']}` "
            f"· commit `{os.environ.get('GITHUB_SHA', 'unknown')}`",
        ]
    )
    if parent_issue:
        lines.append(f"Tracked under #{parent_issue}.")
    lines.extend(
        [
            "",
            "_Advisory finding from continuous LLM review. Triage: fix it, or close with a reason;_",
            "_closed findings are dispositions and are fed to later reviewers as do-not-re-raise context._",
        ]
    )
    return "\n".join(lines)


def _attach_to_parent(repo: str, parent_issue: int, child_number: int) -> None:
    """Attach a new finding issue beneath the grouping issue via sub-issues."""
    child = _gh_api([f"repos/{repo}/issues/{child_number}"])
    if not isinstance(child, dict):
        _fail("gh api issue lookup returned non-object JSON")
    result = subprocess.run(
        [
            "gh",
            "api",
            "-X",
            "POST",
            f"repos/{repo}/issues/{parent_issue}/sub_issues",
            "-F",
            f"sub_issue_id={child['id']}",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        _fail(f"attaching #{child_number} under #{parent_issue} failed: {result.stderr.strip()}")


def publish_issues(artifact: Path, repo: str, parent_issue: int = 0) -> None:
    """Publish validated findings as fingerprint-tracked GitHub issues.

    Args:
        artifact: Path to validated .review-report-artifact.json.
        repo: Repository in owner/repo format.
        parent_issue: Grouping issue number new findings are attached under
            as sub-issues (0 = no parent).
    """
    if not artifact.is_file():
        _fail(f"artifact not found: {artifact}")
    data = json.loads(artifact.read_text())
    report_type = data["report_type"]
    findings = data["findings"]

    type_label = f"ai-review/{report_type}"
    _ensure_labels(repo, [*ISSUE_LABELS, type_label])

    by_fingerprint: dict[str, JsonDict] = {}
    for issue in _ledger_issues(repo):
        marked = _marked_fingerprint(issue.get("body") or "")
        if marked:
            # First hit wins: issues are listed newest-first and the newest
            # tracked item is the live one.
            by_fingerprint.setdefault(marked, issue)

    created = updated = suppressed = 0
    for finding in findings:
        loc = finding["location"]
        fingerprint = issue_fingerprint(finding["category"], str(loc["path"]), finding["label"])
        body = _issue_body(finding, report_type, parent_issue)
        existing = by_fingerprint.get(fingerprint)
        if existing is None:
            issue = _gh_api(
                [f"repos/{repo}/issues", "--input", "-"],
                input_body={
                    "title": _issue_title(finding, report_type),
                    "body": body,
                    "labels": [*ISSUE_LABELS, type_label],
                },
            )
            if not isinstance(issue, dict):
                _fail("gh api issue creation returned non-object JSON")
            if parent_issue:
                _attach_to_parent(repo, parent_issue, int(issue["number"]))
            created += 1
        elif existing["state"] == "open":
            _gh_api(
                [
                    "-X",
                    "PATCH",
                    f"repos/{repo}/issues/{existing['number']}",
                    "--input",
                    "-",
                ],
                input_body={"title": _issue_title(finding, report_type), "body": body},
            )
            updated += 1
        else:
            # Closed with the same fingerprint: a disposition. Respect it.
            suppressed += 1

    print(f"issues ledger: {created} created, {updated} updated, {suppressed} suppressed by disposition ({len(findings)} findings)")
