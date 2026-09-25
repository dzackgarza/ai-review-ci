"""Cyclopts CLI for deterministic ai-review-ci controls.

Presentation layer only: every subcommand is a typed function imported from
its logic module and registered here. Help text comes from those functions'
docstrings.

Subcommands:
- install          — write trigger workflows and apply required branch protection
- red-commit        — sanctioned, auditable route to commit an intentionally hook-failing red proof
- install-labels    — create/update the canonical label taxonomy on a target repo
- check-profile    — fail if a target repo does not match its curated profile
- check-staged-bypass — fail if staged added lines introduce validator bypasses
- check-delegation — fail if a target justfile stops delegating to global QC
- check-justfile   — fail if a target justfile violates the baseline contract
- check-pr-description — fail on unchecked checklist items, or (where the gate template is installed) a missing policy-alignment section
- check-app-boot   — run the target repo's delegated bun-playwright gate
- check-review-threads — require evidence-backed ai-review thread resolution
- check-review-guidelines — fail if the head repo's AGENTS.md lacks the current canonical # Review Guidelines section
- tripwire-index — print the derived maintainer-only tripwire inventory
- check-tripwire-index — validate tripwire/policy/remediation index integrity
- protect-branch   — apply required branch protection contexts
- doctor-ci       — validate repository-owned doctor checks for CI
- doctor-preflight — validate local justfile/profile health before code QC
- doctor-schema    — dump the JSON Schema for the doctor payload
"""

from cyclopts import App

from ai_review_ci.doctor import check_justfile, doctor, doctor_ci, doctor_preflight, doctor_schema, version_command
from ai_review_ci.gates import (
    check_app_boot,
    check_delegation,
    check_pr_description,
    check_profile,
    check_review_threads,
    check_staged_bypass,
    protect_branch,
)
from ai_review_ci.install import install
from ai_review_ci.labels import install_labels
from ai_review_ci.red_commit import red_commit
from ai_review_ci.review_guidelines import check_review_guidelines
from ai_review_ci.tripwire_index import check_tripwire_index, tripwire_index

app = App(
    name="ai-review-ci",
    help="Centrally managed deterministic review QC.",
)

app.command(install)
app.command(red_commit, name="red-commit")
app.command(install_labels)
app.command(version_command, name="version")
app.command(doctor)
app.command(doctor_ci, name="doctor-ci")
app.command(doctor_preflight, name="doctor-preflight")
app.command(doctor_schema)
app.command(check_profile)
app.command(check_staged_bypass)
app.command(check_delegation)
app.command(check_justfile)
app.command(check_pr_description)
app.command(check_app_boot)
app.command(check_review_threads)
app.command(check_review_guidelines)
app.command(tripwire_index, name="tripwire-index")
app.command(check_tripwire_index, name="check-tripwire-index")
app.command(protect_branch)


def main() -> None:
    """Entry point for the ai-review-ci console script."""
    app()


if __name__ == "__main__":
    main()
