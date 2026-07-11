#!/usr/bin/env python3
"""Pre-push closure-claim confrontation (ai-review-ci#244).

A push to the default branch whose commit messages carry GitHub's closing
keywords closes those issues server-side the moment the push lands — no PR,
no review, no further confirmation. This check reads the same input GitHub's
server reads (the documented closing-keyword lever) and, before allowing the
push, confronts the pusher ONCE with the verbatim bodies of the issues about
to be closed, so the closure claim is reconciled against the issues' own asks
rather than the commit message's narrative.

Acknowledgment is a one-shot file in the git dir — trivially writable by
design. The point is confrontation at the moment of the claim, not
tamper-proofing: the threat model is an agent that skips workflows but aligns
in good faith when the right guidance lands at the right time.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

# GitHub's documented closing keywords (optionally followed by a colon), same-repo #N form.
_CLOSING_RE = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s+#(\d+)", re.IGNORECASE)
ZERO_SHA = "0" * 40
ACK_FILENAME = "ai-review-ack-closes"


def closing_numbers(text: str) -> list[int]:
    """Issue numbers a commit-message text would close on the default branch."""
    return sorted({int(n) for n in _CLOSING_RE.findall(text)})


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def _default_branch(remote: str) -> str | None:
    result = _git("symbolic-ref", "--short", f"refs/remotes/{remote}/HEAD")
    if result.returncode != 0:
        return None
    return result.stdout.strip().split("/", 1)[1]


def _is_default_branch_ref(remote_ref: str, remote: str) -> bool:
    if not remote_ref.startswith("refs/heads/"):
        return False
    branch = remote_ref.removeprefix("refs/heads/")
    default = _default_branch(remote)
    if default is not None:
        return branch == default
    return branch in ("main", "master")


def _outgoing_messages(local_sha: str, remote_sha: str) -> str:
    if local_sha == ZERO_SHA:  # ref deletion pushes no commits
        return ""
    range_args = [local_sha, "--not", "--remotes"] if remote_sha == ZERO_SHA else [f"{remote_sha}..{local_sha}"]
    result = _git("log", "--format=%B", *range_args)
    return result.stdout if result.returncode == 0 else ""


def _ack_path() -> Path:
    result = _git("rev-parse", "--git-dir")
    assert result.returncode == 0, f"git rev-parse --git-dir failed: {result.stderr.strip()}"
    return Path(result.stdout.strip()) / ACK_FILENAME


def _acked_numbers(path: Path) -> set[int]:
    if not path.exists():
        return set()
    return {int(line) for line in path.read_text().split() if line.strip().isdigit()}


def _fetch_issue(number: int) -> tuple[str, str, str]:
    """(title, state, body) for one issue; a hard fetch failure blocks the push loudly."""
    result = subprocess.run(
        ["gh", "issue", "view", str(number), "--json", "title,state,body"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"confront-closes: could not fetch issue #{number}: {result.stderr.strip()}", file=sys.stderr)
        print("A push claiming to close an issue must be able to read that issue. Fix gh/network and retry.", file=sys.stderr)
        sys.exit(1)
    data = json.loads(result.stdout)
    return str(data["title"]), str(data["state"]), str(data["body"])


def _confront(open_issues: list[tuple[int, str, str]], ack_path: Path) -> None:
    bar = "─" * 64
    print(f"\n{bar}", file=sys.stderr)
    print("CLOSURE-CLAIM CONFRONTATION (ai-review-ci#244)", file=sys.stderr)
    print(
        "\nThis push lands closing keywords on the default branch; GitHub will\n"
        "close the issues below the moment it lands. Their verbatim asks follow.\n"
        "For EACH ask, verify coverage in the commits you are pushing\n"
        "(git log -p @{u}..): done / partial / untouched.\n",
        file=sys.stderr,
    )
    for number, title, body in open_issues:
        print(f"### #{number} — {title}\n", file=sys.stderr)
        print(body.strip() or "_Issue has no body._", file=sys.stderr)
        print("", file=sys.stderr)
    numbers = "\n".join(str(n) for n, _, _ in open_issues)
    print(
        "Your options:\n"
        "  (a) EVERY ask above is covered by the outgoing commits — acknowledge\n"
        "      and re-push:\n"
        f"        printf '{numbers}\\n' > {ack_path} && git push\n"
        "  (b) The work is incomplete — finish the remaining asks before pushing\n"
        "      this closure claim.\n"
        "  (c) The closure claim is false for this push — remove the closing\n"
        "      keyword (e.g. reword 'Closes #N' to 'Refs #N' via git commit\n"
        "      --amend). This only corrects the false claim: the issue stays\n"
        "      open, the work remains incomplete, and the reword itself\n"
        "      accomplishes nothing.",
        file=sys.stderr,
    )
    print(bar, file=sys.stderr)
    sys.exit(1)


def main() -> None:
    remote = sys.argv[1] if len(sys.argv) > 1 else "origin"
    claimed: set[int] = set()
    for line in sys.stdin:
        parts = line.split()
        if len(parts) != 4:
            continue
        _local_ref, local_sha, remote_ref, remote_sha = parts
        if _is_default_branch_ref(remote_ref, remote):
            claimed.update(closing_numbers(_outgoing_messages(local_sha, remote_sha)))
    if not claimed:
        return
    ack_path = _ack_path()
    if claimed <= _acked_numbers(ack_path):
        ack_path.unlink()
        print(f"confront-closes: closure claims acknowledged for {', '.join(f'#{n}' for n in sorted(claimed))}.", file=sys.stderr)
        return
    open_issues: list[tuple[int, str, str]] = []
    for number in sorted(claimed):
        title, state, body = _fetch_issue(number)
        if state.upper() != "CLOSED":
            open_issues.append((number, title, body))
    if open_issues:
        _confront(open_issues, ack_path)


if __name__ == "__main__":
    main()
