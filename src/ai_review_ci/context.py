"""Generate a compact reviewer context file from code scanning alert state.

This context is given to review agents before they run. It suppresses duplicate
report prose; open alerts are carried forward mechanically by SARIF conversion.

Queries code scanning alerts for the relevant SARIF tool names
(ai-review/general, ai-review/slop) and formats them by state
(open, dismissed, fixed). The alerts API filters by tool.driver.name,
NOT by the upload-sarif category.

The output is a markdown file with open/dismissed/fixed guardrails grouped
by state. Pass it to the review agent as instructions:

  "Open alerts are carried forward by automation. Do not duplicate them in your
  report unless you have new evidence, the problem reappears in a materially
  different form, or the previous resolution is directly contradicted by the
  current code."
"""

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn

JsonDict = dict[str, Any]

DEFAULT_TOOL_NAMES = "ai-review/general,ai-review/slop"


def _fail(msg: str) -> NoReturn:
    print(f"FATAL: {msg}", file=sys.stderr)
    sys.exit(1)


def _fetch_alerts(
    repo: str, tool_name: str, ref: str | None = None, state: str | None = None
) -> list[JsonDict]:
    """Fetch code scanning alerts for a repo, filtered by tool and optional ref.

    Returns an empty list when no analysis exists (404), which is the
    expected state before the first SARIF upload.
    """
    params: dict[str, str] = {"per_page": "100", "tool_name": tool_name}
    if ref:
        params["ref"] = ref
    if state:
        params["state"] = state

    path = f"repos/{repo}/code-scanning/alerts"
    alerts: list[JsonDict] = []
    page = 1

    while True:
        args = ["gh", "api", "--method", "GET", path]
        for k, v in params.items():
            args.extend(["--field", f"{k}={v}"])
        args.extend(["--field", f"page={page}"])

        result = subprocess.run(args, capture_output=True, text=True)

        if result.returncode != 0:
            if "no analysis found" in result.stderr:
                return []
            _fail(f"gh api GET {path} failed: {result.stderr.strip()}")

        page_alerts = json.loads(result.stdout)
        if not isinstance(page_alerts, list):
            _fail(f"gh api GET {path} returned non-list JSON")
        alerts.extend(page_alerts)
        if len(page_alerts) < 100:
            return alerts
        page += 1


_THREADS_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          isResolved
          comments(first: 1) { nodes { path } }
        }
      }
    }
  }
}
"""


def _thread_page(owner: str, name: str, pr_number: int, cursor: str | None) -> JsonDict:
    """Fetch one page of review threads via the GraphQL API."""
    args = [
        "gh",
        "api",
        "graphql",
        "-f",
        f"query={_THREADS_QUERY}",
        "-F",
        f"owner={owner}",
        "-F",
        f"name={name}",
        "-F",
        f"number={pr_number}",
    ]
    if cursor:
        args.extend(["-F", f"cursor={cursor}"])
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        _fail(f"gh api graphql reviewThreads failed: {result.stderr.strip()}")
    page: JsonDict = json.loads(result.stdout)["data"]["repository"]["pullRequest"][
        "reviewThreads"
    ]
    return page


def _fetch_pr_threads(repo: str, pr_number: int) -> list[JsonDict]:
    """Digest of existing review threads on the PR: path and state only."""
    owner, name = repo.split("/")
    threads: list[JsonDict] = []
    cursor: str | None = None
    while True:
        page = _thread_page(owner, name, pr_number, cursor)
        for node in page["nodes"]:
            comments = node["comments"]["nodes"]
            if not comments:
                continue
            threads.append(
                {
                    "path": comments[0].get("path") or "?",
                    "resolved": node["isResolved"],
                }
            )
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
    return threads


def _alert_location(alert: JsonDict) -> str:
    loc = alert.get("most_recent_instance", {}).get("location", {})
    return f"{loc.get('path', '?')}:{loc.get('start_line', '?')}"


def _alert_url(alert: JsonDict) -> str:
    return str(alert.get("html_url") or alert.get("url") or "?")


def _format_alert_guardrail(alert: JsonDict) -> str:
    number = alert.get("number", "?")
    state = alert.get("state", "?")
    loc = _alert_location(alert)
    url = _alert_url(alert)
    return f"- alert #{number}; state={state}; location=`{loc}`; url={url}"


def _open_lines(alerts: list[JsonDict]) -> list[str]:
    if not alerts:
        return []
    return [
        "",
        "**Open / accepted finding guardrails:**",
        *(_format_alert_guardrail(a) for a in alerts),
    ]


def _dismissed_lines(alerts: list[JsonDict]) -> list[str]:
    if not alerts:
        return []
    lines = ["", "**Dismissed / rejected finding guardrails:**"]
    for a in alerts:
        reason = a.get("dismissed_reason", "?")
        lines.append(f"{_format_alert_guardrail(a)}; disposition={reason}")
    return lines


def _fixed_lines(alerts: list[JsonDict]) -> list[str]:
    if not alerts:
        return []
    return [
        "",
        "**Fixed finding guardrails:**",
        *(_format_alert_guardrail(a) for a in alerts),
    ]


_STATE_RENDERERS: tuple[tuple[str, Callable[[list[JsonDict]], list[str]]], ...] = (
    ("open", _open_lines),
    ("dismissed", _dismissed_lines),
    ("fixed", _fixed_lines),
)


def _alert_section(cat: str, alerts: list[JsonDict]) -> list[str]:
    """Markdown section for one SARIF tool name, grouped by alert state."""
    if not alerts:
        return [f"### {cat}", "", "_No existing findings._", ""]
    lines = [f"### {cat}"]
    for state, render in _STATE_RENDERERS:
        lines.extend(render([a for a in alerts if a.get("state") == state]))
    lines.append("")
    return lines


def _collect_alerts(
    repo: str, cat: str, pr_number: int, state: str | None = None
) -> list[JsonDict]:
    """Repo-wide alerts for a tool, merged with PR-ref alerts on PR runs."""
    alerts = _fetch_alerts(repo, tool_name=cat, state=state)
    if pr_number:
        pr_alerts = _fetch_alerts(
            repo, tool_name=cat, ref=f"refs/pull/{pr_number}/merge", state=state
        )
        known = {a.get("number") for a in alerts}
        alerts.extend(a for a in pr_alerts if a.get("number") not in known)
    return alerts


def _collect_context_alerts(repo: str, cat: str, pr_number: int) -> list[JsonDict]:
    """Alerts rendered for reviewer context, grouped by GitHub state."""
    alerts: list[JsonDict] = []
    for state in ("open", "dismissed", "fixed"):
        alerts.extend(_collect_alerts(repo, cat, pr_number, state=state))
    return alerts


def _carry_forward_payload(repo: str, cats: list[str], pr_number: int) -> JsonDict:
    """Open alert payload consumed later by SARIF conversion."""
    entries: list[JsonDict] = []
    for cat in cats:
        entries.extend(
            {"tool_name": cat, "alert": alert}
            for alert in _collect_alerts(repo, cat, pr_number, state="open")
        )
    return {"schema_version": 1, "alerts": entries}


def _pr_thread_lines(repo: str, pr_number: int) -> list[str]:
    """Digest section of review threads already surfaced on the PR."""
    threads = _fetch_pr_threads(repo, pr_number)
    lines = [
        "## Review items already surfaced on this PR",
        "",
        "These paths already have review threads on this pull request. "
        "They are non-actionable guardrails, not examples or evidence. "
        "Do not re-raise them; a resolved thread is a disposition.",
        "",
    ]
    if threads:
        for t in threads:
            state = "resolved" if t["resolved"] else "open"
            lines.append(f"- [{state}] `{t['path']}`")
    else:
        lines.append("_No existing review threads._")
    lines.append("")
    return lines


def fetch_context(
    repo: str,
    tool_names: str = DEFAULT_TOOL_NAMES,
    output: Path | None = None,
    alerts_output: Path | None = None,
    pr_number: int = 0,
) -> None:
    """Generate reviewer context from code scanning alerts.

    Args:
        repo: Repository in owner/repo format.
        tool_names: Comma-separated SARIF tool names (tool.driver.name) to query.
        output: Output file path (default: stdout).
        alerts_output: JSON sidecar for open alerts that must be carried into
            the next SARIF upload.
        pr_number: PR number for diff-scoped runs; adds PR-ref alerts and the
            digest of review threads already on the PR (0 = not a PR run).
    """
    names = [c.strip() for c in tool_names.split(",") if c.strip()]

    lines: list[str] = [
        "## Existing repo-wide review findings",
        "",
        "Open alerts are carried forward into the next SARIF upload by "
        "automation. Do not duplicate them in your report unless you have "
        "new evidence, the problem reappears in a materially different form, "
        "or the previous resolution is directly contradicted by the current "
        "code.",
        "",
        "The entries below are denylist guardrails, not examples and not "
        "evidence for a new report. Do not reuse prior alert labels, review "
        "thread wording, dismissed comments, or nearby paraphrases as finding "
        "content.",
        "",
    ]

    for cat in names:
        lines.extend(_alert_section(cat, _collect_context_alerts(repo, cat, pr_number)))

    if pr_number:
        lines.extend(_pr_thread_lines(repo, pr_number))

    text = "\n".join(lines).strip() + "\n"

    if output:
        output.write_text(text)
        print(f"Reviewer context written to {output}", file=sys.stderr)
    else:
        print(text)

    if alerts_output:
        alerts_output.write_text(
            json.dumps(_carry_forward_payload(repo, names, pr_number), indent=2) + "\n"
        )
        print(f"Carry-forward alerts written to {alerts_output}", file=sys.stderr)
