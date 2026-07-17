"""Sanctioned route for committing an intentionally hook-failing red proof.

The repo's pre-commit gate runs ``just test-commit`` and rejects any commit whose checks
fail. That is correct for ordinary commits, but the red/green workflow requires
landing a genuinely-failing test (a red proof) *before* its fix. The only ad-hoc
escape is ``git commit --no-verify`` — an unaudited bypass with no owning-issue
trail and no check that the commit is actually red.

``red-commit`` is the on-rails alternative. It requires an owning issue, runs the
same gate the hook runs, and refuses unless the gate *genuinely fails* — a
passing gate is not a red proof. On a genuine red gate it stamps an auditable
``Red-Proof: #<issue>`` trailer and performs a single ``--no-verify`` commit.
Ordinary hooks stay installed and active for every other commit.
"""

import subprocess
import sys
from pathlib import Path
from typing import Annotated, NoReturn

from cyclopts import Parameter

RED_PROOF_TRAILER = "Red-Proof"

# The one skill that documents this route; hook bounce messages name it too.
_SKILL_POINTER = (
    'Sanctioned route: `ai-review-ci red-commit --issue <owning-issue> -m "<message>"`. '
    "See the git-integration-workflow skill (red-proof route) and "
    "test-guidelines (RED-GREEN-REVERT)."
)


def _reject(message: str) -> NoReturn:
    print(f"red-commit rejected: {message}\n{_SKILL_POINTER}", file=sys.stderr)
    sys.exit(1)


def red_commit(
    *,
    issue: int,
    message: Annotated[str, Parameter(name=["-m", "--message"])],
    target: Path = Path("."),
) -> None:
    """Commit an intentionally hook-failing red proof without disabling hooks.

    The commit gate (``just test-commit``) is run in ``target`` and MUST fail: a red
    proof is a test that genuinely fails because the bug is unfixed. If the gate
    passes, this is not a red proof — commit normally with ``git commit``. On a
    genuine red gate, an auditable ``Red-Proof: #<issue>`` trailer is stamped and
    the staged changes are committed with the gate bypassed for that single
    commit only; ordinary hooks remain active for every other commit.

    Parameters
    ----------
    issue:
        Owning issue number the red proof reproduces (must be positive).
    message:
        Commit message describing the red proof.
    target:
        Repository directory to commit in (default: current directory).
    """
    target = target.resolve()
    if issue <= 0:
        _reject(f"--issue must be a positive owning-issue number (got {issue}).")
    if not message.strip():
        _reject("a commit message describing the red proof is required (-m).")

    gate = subprocess.run(["just", "test-commit"], cwd=target)
    if gate.returncode == 0:
        _reject("the commit gate PASSED, so this is not a red proof. A red proof is a test that genuinely fails because the bug is unfixed. Commit normally with `git commit`.")

    body = f"{message.rstrip()}\n\n{RED_PROOF_TRAILER}: #{issue}\nIntentional hook-failing red proof landed before its green fix (red/green workflow)."
    subprocess.run(["git", "commit", "--no-verify", "-m", body], cwd=target, check=True)
    print(
        f"Sanctioned red proof committed for issue #{issue}. The commit gate was bypassed for this single commit only; ordinary hooks remain active. Land the green fix next."
    )
