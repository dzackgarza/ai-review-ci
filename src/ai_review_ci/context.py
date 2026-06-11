"""Generate a compact reviewer context file from code scanning alert state.

This context is given to review agents before they run, to prevent re-raising
existing issues without new evidence.

Queries code scanning alerts for the relevant SARIF tool names
(ai-review/general, ai-review/slop) and formats them by state
(open, dismissed, fixed). The alerts API filters by tool.driver.name,
NOT by the upload-sarif category.

The output is a markdown file with open/dismissed/fixed findings grouped
by state. Pass it to the review agent as instructions:

  "Do not intentionally re-raise these issues unless you have new evidence,
  the problem reappears in a materially different form, or the previous
  resolution is directly contradicted by the current code."
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


def _fetch_alerts(repo: str, tool_name: str, ref: str | None = None) -> list[JsonDict]:
    """Fetch code scanning alerts for a repo, filtered by tool and optional ref.

    Returns an empty list when no analysis exists (404), which is the
    expected state before the first SARIF upload.
    """
    params: dict[str, str] = {"per_page": "100", "tool_name": tool_name}
    if ref:
        params["ref"] = ref

    path = f"repos/{repo}/code-scanning/alerts"
    args = ["gh", "api", "--method", "GET", path]
    for k, v in params.items():
        args.extend(["--field", f"{k}={v}"])

    result = subprocess.run(args, capture_output=True, text=True)

    if result.returncode == 0:
        alerts: list[JsonDict] = json.loads(result.stdout)
        return alerts

    if "no analysis found" in result.stderr:
        return []

    _fail(f"gh api GET {path} failed: {result.stderr.strip()}")


_THREADS_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          isResolved
          comments(first: 1) { nodes { path body } }
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
    """Digest of existing review threads on the PR: path, headline, state."""
    owner, name = repo.split("/")
    threads: list[JsonDict] = []
    cursor: str | None = None
    while True:
        page = _thread_page(owner, name, pr_number, cursor)
        for node in page["nodes"]:
            comments = node["comments"]["nodes"]
            if not comments:
                continue
            headline = (
                comments[0]["body"].splitlines()[0] if comments[0]["body"] else ""
            )
            threads.append(
                {
                    "path": comments[0].get("path") or "?",
                    "headline": headline,
                    "resolved": node["isResolved"],
                }
            )
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
    return threads


def _alert_label(alert: JsonDict) -> str:
    """Extract finding label from alert properties or rule description."""
    props = (
        alert.get("most_recent_instance", {}).get("location", {}).get("properties", {})
    )
    if props and props.get("label"):
        label: str = props["label"]
        return label
    rule = alert.get("rule", {})
    name: str = rule.get("name", rule.get("id", "?"))
    return name


def _alert_location(alert: JsonDict) -> str:
    loc = alert.get("most_recent_instance", {}).get("location", {})
    return f"{loc.get('path', '?')}:{loc.get('start_line', '?')}"


def _alert_url(alert: JsonDict) -> str:
    return str(alert.get("html_url") or alert.get("url") or "?")


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
        reason = a.get("dismissed_reason", "?")
        comment = a.get("dismissed_comment", "")
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


def _collect_alerts(repo: str, cat: str, pr_number: int) -> list[JsonDict]:
    """Repo-wide alerts for a tool, merged with PR-ref alerts on PR runs."""
    alerts = _fetch_alerts(repo, tool_name=cat)
    if pr_number:
        pr_alerts = _fetch_alerts(
            repo, tool_name=cat, ref=f"refs/pull/{pr_number}/merge"
        )
        known = {a.get("number") for a in alerts}
        alerts.extend(a for a in pr_alerts if a.get("number") not in known)
    return alerts


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
    pr_number: int = 0,
) -> None:
    """Generate reviewer context from code scanning alerts.

    Args:
        repo: Repository in owner/repo format.
        tool_names: Comma-separated SARIF tool names (tool.driver.name) to query.
        output: Output file path (default: stdout).
        pr_number: PR number for diff-scoped runs; adds PR-ref alerts and the
            digest of review threads already on the PR (0 = not a PR run).
    """
    names = [c.strip() for c in tool_names.split(",") if c.strip()]

    lines: list[str] = [
        "## Existing repo-wide review findings",
        "",
        "Do not intentionally re-raise these issues unless you have new "
        "evidence, the problem reappears in a materially different form, "
        "or the previous resolution is directly contradicted by the "
        "current code.",
        "",
    ]

    for cat in names:
        lines.extend(_alert_section(cat, _collect_alerts(repo, cat, pr_number)))

    if pr_number:
        lines.extend(_pr_thread_lines(repo, pr_number))

    text = "\n".join(lines).strip() + "\n"

    if output:
        output.write_text(text)
        print(f"Reviewer context written to {output}", file=sys.stderr)
    else:
        print(text)
