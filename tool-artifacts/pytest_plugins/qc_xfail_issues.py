r"""Enforce POLICY.NO_SKIP_MASK and its one sanctioned exception on collected tests.

Loaded by every pytest recipe (``-p qc_xfail_issues``). It inspects collected items, not
source text, so it covers ``.sage`` tests and parametrized cases as well as ``.py`` files.

A test may be red by design only as ``@pytest.mark.xfail(reason="... #N", strict=True)``
(or the same mark on a ``pytest.param``), where ``#N`` is an issue of this repository's own
GitHub tracker that is open. The marker therefore clears itself: a case that starts passing
fails the run (strict XPASS), and once issue N closes every marker citing it fails
collection. ``skip`` and ``skipif`` are never sanctioned.

Issue state comes from the public GitHub REST API without a token, as for the Semgrep
exceptions; an unreadable state fails the run.
"""

import json
import re
import subprocess
import urllib.error
import urllib.request

import pytest

ISSUE = re.compile(r"#(\d+)")
GITHUB_REMOTE = re.compile(r"github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?/?$")


def _repository(rootdir) -> str:
    remote = subprocess.run(["git", "-C", str(rootdir), "remote", "get-url", "origin"], capture_output=True, text=True)
    match = GITHUB_REMOTE.search(remote.stdout.strip()) if remote.returncode == 0 else None
    if match is None:
        raise pytest.UsageError(f"qc_xfail_issues: origin of {rootdir} is not a GitHub remote, so xfail issue citations cannot be checked")
    return match.group(1)


def _issue_open(repository: str, number: int) -> bool:
    url = f"https://api.github.com/repos/{repository}/issues/{number}"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return json.load(response)["state"] == "open"
    except urllib.error.URLError as error:
        raise pytest.UsageError(f"qc_xfail_issues: cannot read the state of {repository}#{number}: {error}") from error


def pytest_collection_modifyitems(session, config, items) -> None:
    violations: list[str] = []
    cited: dict[int, list[str]] = {}
    for item in items:
        for name in ("skip", "skipif"):
            if item.get_closest_marker(name) is not None:
                violations.append(f"{item.nodeid}: {name} is never sanctioned (POLICY.NO_SKIP_MASK)")
        for mark in item.iter_markers("xfail"):
            reason = mark.kwargs.get("reason", mark.args[1] if len(mark.args) > 1 else "")
            numbers = ISSUE.findall(reason)
            if mark.kwargs.get("strict") is not True:
                violations.append(f"{item.nodeid}: xfail must be strict=True")
            if not numbers:
                violations.append(f"{item.nodeid}: xfail reason must cite the owning issue as #N: {reason!r}")
            for number in numbers:
                cited.setdefault(int(number), []).append(item.nodeid)
    if cited:
        repository = _repository(config.rootpath)
        for number, nodeids in sorted(cited.items()):
            if not _issue_open(repository, number):
                violations.append(
                    f"{repository}#{number} is closed, but {len(nodeids)} xfail case(s) still cite it, e.g. {nodeids[0]}: "
                    "an issue closes only when its cases pass"
                )
    if violations:
        raise pytest.UsageError("POLICY.NO_SKIP_MASK violations:\n  " + "\n  ".join(violations))
