"""Sanctioned route for committing an intentionally hook-failing red proof.

The repo's pre-commit gate runs ``just test-commit`` and rejects any commit whose checks
fail. That is correct for ordinary commits, but the red/green workflow requires
landing a genuinely-failing test (a red proof) *before* its fix. The only ad-hoc
escape is ``git commit --no-verify`` — an unaudited bypass with no owning-issue
trail and no check that the commit is actually red.

``red-commit`` is the on-rails alternative. It requires an owning issue, runs the
same gate the hook runs against the staged candidate in an isolated worktree,
respects the installed hook's exemptions, and refuses unless the gate
*genuinely fails* — a passing gate is not a red proof. On a genuine red gate it stamps an auditable
``Red-Proof: #<issue>`` trailer and performs a single ``--no-verify`` commit.
Ordinary hooks stay installed and active for every other commit.
"""

import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, NoReturn

from cyclopts import Parameter

RED_PROOF_TRAILER = "Red-Proof"

_SKILL_POINTER = (
    'Sanctioned route: `ai-review-ci red-commit --issue <owning-issue> -m "<message>"`. '
    "See the git-integration-workflow skill (red-proof route) and "
    "test-guidelines (RED-GREEN-REVERT)."
)


def _reject(message: str) -> NoReturn:
    print(f"red-commit rejected: {message}\n{_SKILL_POINTER}", file=sys.stderr)
    sys.exit(1)


def _git_output(target: Path, *args: str, stdin: str | None = None) -> str:
    return subprocess.run(
        ["git", *args], cwd=target, input=stdin, text=True, stdout=subprocess.PIPE, check=True
    ).stdout.strip()


def _require_managed_gate(target: Path) -> None:
    """Ask the installed hook's own exemption predicate; do not duplicate its policy."""
    hook = Path(_git_output(target, "rev-parse", "--git-path", "hooks/pre-commit"))
    hook = (target / hook).resolve()
    exemption = hook.with_name("qc-exempt.sh")
    if not hook.is_file() or not os.access(hook, os.X_OK) or not exemption.is_file():
        _reject("no installed ai-review-ci pre-commit gate; commit normally with `git commit`.")
    result = subprocess.run(
        ["sh", "-e", "-c", '. "$1"; qc_should_gate', str(hook), str(exemption)],
        cwd=target,
    )
    if result.returncode != 0:
        _reject("QC-exempt repository or unavailable gate; no red-proof bypass is needed. Commit normally with `git commit`.")


def _candidate_gate(target: Path, tree: str, base: str) -> int:
    """Evaluate the exact staged tree without exposing the caller's checkout or index."""
    local_git_vars = set(_git_output(target, "rev-parse", "--local-env-vars").splitlines())
    env = {key: value for key, value in os.environ.items() if key not in local_git_vars}
    with TemporaryDirectory(prefix="ai-review-ci-red-commit-") as tmp:
        checkout = Path(tmp) / "candidate"
        subprocess.run(
            ["git", "worktree", "add", "--detach", "--no-checkout", str(checkout), base],
            cwd=target, env=env, check=True,
        )
        try:
            subprocess.run(
                ["git", "read-tree", "--reset", "-u", tree], cwd=checkout, env=env, check=True,
            )
            recipe = subprocess.run(
                ["just", "--show", "test-commit"],
                cwd=checkout, env=env, stdout=subprocess.DEVNULL,
            )
            if recipe.returncode != 0:
                _reject("the staged candidate has no runnable test-commit recipe.")
            gate = subprocess.run(["just", "test-commit"], cwd=checkout, env=env)
            if gate.returncode < 0:
                _reject("the commit gate was terminated before returning a verdict.")
            return gate.returncode
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(checkout)],
                cwd=target, env=env, check=True,
            )


def _head(target: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "HEAD"],
        cwd=target, text=True, stdout=subprocess.PIPE, check=False,
    )
    if result.returncode == 1:
        return ""
    result.check_returncode()
    return result.stdout.strip()


def red_commit(
    *,
    issue: int,
    message: Annotated[str, Parameter(name=["-m", "--message"])],
    target: Path = Path("."),
) -> None:
    """Commit an intentionally hook-failing red proof without disabling hooks.

    The commit gate (``just test-commit``) is run against the staged candidate in
    an isolated worktree of ``target`` and MUST fail: a red proof is a test that
    genuinely fails because the bug is unfixed. If the gate passes, this is not a red proof — commit normally with ``git commit``. On a
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

    target = Path(_git_output(target, "rev-parse", "--show-toplevel"))
    _require_managed_gate(target)
    tree = _git_output(target, "write-tree")
    head = _head(target)
    base = head or _git_output(
        target, "commit-tree", _git_output(target, "mktree", stdin=""),
        "-m", "Temporary empty baseline for red proof",
    )
    if _candidate_gate(target, tree, base) == 0:
        _reject("the commit gate PASSED, so this is not a red proof. A red proof is a test that genuinely fails because the bug is unfixed. Commit normally with `git commit`.")

    if _head(target) != head or _git_output(target, "write-tree") != tree:
        _reject("HEAD or staged candidate changed during the gate; run the proof again.")

    body = f"{message.rstrip()}\n\n{RED_PROOF_TRAILER}: #{issue}\nIntentional hook-failing red proof landed before its green fix (red/green workflow)."
    subprocess.run(["git", "commit", "--no-verify", "-m", body], cwd=target, check=True)
    print(
        f"Sanctioned red proof committed for issue #{issue}. The commit gate was bypassed for this single commit only; ordinary hooks remain active. Land the green fix next."
    )
