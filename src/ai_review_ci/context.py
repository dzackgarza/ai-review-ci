"""Generate a compact reviewer context file from code scanning alert state.

This context is given to review agents before they run. It suppresses duplicate
report prose; open alerts are carried forward mechanically by SARIF conversion.

Queries code scanning alerts for the relevant SARIF tool names
(ai-review/general, ai-review/slop) and formats them by state
(open, dismissed, fixed). The alerts API filters by tool.driver.name,
NOT by the upload-sarif category.

The output is a markdown file with open/dismissed/fixed findings grouped
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
          path
          isResolved
          comments(first: 1) { nodes { body } }
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


def _thread_digest(node: JsonDict) -> JsonDict | None:
    comments = node["comments"]["nodes"]
    if not comments:
        return None
    headline = comments[0]["body"].splitlines()[0] if comments[0]["body"] else ""
    return {
        "path": node["path"],
        "headline": headline,
        "resolved": node["isResolved"],
    }


def _fetch_pr_threads(repo: str, pr_number: int) -> list[JsonDict]:
    """Digest of existing review threads on the PR: path, headline, state."""
    owner, name = repo.split("/")
    threads: list[JsonDict] = []
    cursor: str | None = None
    while True:
        page = _thread_page(owner, name, pr_number, cursor)
        for node in page["nodes"]:
            digest = _thread_digest(node)
            if digest is not None:
                threads.append(digest)
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
    return threads


def _alert_label(alert: JsonDict) -> str:
    loc = alert["most_recent_instance"]["location"]
    if "properties" in loc:
        props = loc["properties"]
        assert isinstance(props, dict)
        if "label" in props:
            label = props["label"]
            assert isinstance(label, str) and label
            return label
    rule = alert["rule"]
    name = rule["name"]
    assert isinstance(name, str) and name
    return name


def _alert_location(alert: JsonDict) -> str:
    loc = alert["most_recent_instance"]["location"]
    path = loc["path"]
    start_line = loc["start_line"]
    assert isinstance(path, str) and path
    assert isinstance(start_line, int)
    return f"{path}:{start_line}"


def _alert_url(alert: JsonDict) -> str:
    if "html_url" in alert:
        url = alert["html_url"]
    else:
        url = alert["url"]
    assert isinstance(url, str) and url
    return url


def _format_alert(alert: JsonDict) -> str:
    label = _alert_label(alert)
    loc = _alert_location(alert)
    url = _alert_url(alert)
    return f"- **{label}** at `{loc}`  \n  Alert: {url}"


def _open_lines(alerts: list[JsonDict]) -> list[str]:
    if not alerts:
        return []
    return ["", "**Open / accepted findings:**", *(_format_alert(a) for a in alerts)]


def _dismissed_lines(alerts: list[JsonDict]) -> list[str]:
    if not alerts:
        return []
    lines = ["", "**Dismissed / rejected findings:**"]
    for a in alerts:
        reason = a["dismissed_reason"]
        assert isinstance(reason, str) and reason
        comment = a["dismissed_comment"] if "dismissed_comment" in a else None
        assert comment is None or isinstance(comment, str)
        extra = f" ({reason}: {comment})" if comment else f" ({reason})"
        lines.append(_format_alert(a) + extra)
    return lines


def _fixed_lines(alerts: list[JsonDict]) -> list[str]:
    if not alerts:
        return []
    return ["", "**Fixed findings:**", *(_format_alert(a) for a in alerts)]


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
        "These findings already have review threads on this pull request. "
        "Do not re-raise them; a resolved thread is a disposition.",
        "",
    ]
    if threads:
        for t in threads:
            state = "resolved" if t["resolved"] else "open"
            lines.append(f"- [{state}] `{t['path']}` — {t['headline']}")
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
