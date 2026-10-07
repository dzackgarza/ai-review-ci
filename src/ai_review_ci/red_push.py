"""Sanctioned route for pushing while the push gate is intentionally red.

The pre-push hook runs ``just test-push`` and rejects any push whose checks fail. A
repository whose acceptance suite is written up front stays red until its last work unit
lands, and a red/green workflow lands red proofs before their fixes, so a correct push
can meet a red gate. The only ad-hoc escape is ``git push --no-verify``: an unaudited
bypass with no owning issue and no check that the gate is red at all.

``red-push`` is the on-rails alternative, the push-side twin of ``red-commit``. It
requires an owning issue, runs the same gate the hook runs, and refuses unless the gate
genuinely fails: a passing gate needs no bypass. On a red gate it records a
``Red-Push: #<issue>`` note on the pushed commit under ``refs/notes/red-push`` and pushes
the current branch to its upstream together with that notes ref, bypassing the gate for
that single push. Ordinary hooks stay installed and active for every other push.
"""

import subprocess
import sys
from pathlib import Path
from typing import NoReturn

RED_PUSH_TRAILER = "Red-Push"
NOTES_REF = "red-push"

_SKILL_POINTER = (
    "Sanctioned route: `ai-review-ci red-push --issue <owning-issue>`. "
    "See the git-integration-workflow skill (red-gate push route)."
)


def _reject(message: str) -> NoReturn:
    print(f"red-push rejected: {message}\n{_SKILL_POINTER}", file=sys.stderr)
    sys.exit(1)


def _git(target: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=target, check=True, text=True, capture_output=True).stdout.strip()


def red_push(*, issue: int, target: Path = Path(".")) -> None:
    """Push the current branch while its push gate is red, with an auditable note.

    The push gate (``just test-push``) is run in ``target`` and MUST fail. On a red gate a
    ``Red-Push: #<issue>`` note is added to ``HEAD`` under ``refs/notes/red-push`` and the
    branch is pushed to its upstream together with that notes ref, with the gate bypassed
    for this push only.

    Parameters
    ----------
    issue:
        Owning issue whose open work keeps the gate red (must be positive).
    target:
        Repository directory to push from (default: current directory).
    """
    target = target.resolve()
    if issue <= 0:
        _reject(f"--issue must be a positive owning-issue number (got {issue}).")
    upstream = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], cwd=target, text=True, capture_output=True
    )
    if upstream.returncode != 0:
        _reject(f"the current branch has no upstream to push to: {upstream.stderr.strip()}")
    remote = _git(target, "config", f"branch.{_git(target, 'branch', '--show-current')}.remote")

    gate = subprocess.run(["just", "test-push"], cwd=target)
    if gate.returncode == 0:
        _reject("the push gate PASSED, so there is nothing to bypass. Push normally with `git push`.")

    head = _git(target, "rev-parse", "HEAD")
    note = f"{RED_PUSH_TRAILER}: #{issue}\nPushed with `just test-push` red; the open work of #{issue} owns the failure."
    _git(target, "notes", f"--ref={NOTES_REF}", "append", "-m", note, head)
    subprocess.run(["git", "push", "--no-verify"], cwd=target, check=True)
    subprocess.run(["git", "push", "--no-verify", remote, f"refs/notes/{NOTES_REF}"], cwd=target, check=True)
    print(
        f"Sanctioned red-gate push of {head} for issue #{issue}, noted under refs/notes/{NOTES_REF}. "
        "The push gate was bypassed for this push only; ordinary hooks remain active."
    )
