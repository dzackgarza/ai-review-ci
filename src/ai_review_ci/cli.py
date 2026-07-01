"""Cyclopts CLI for ai-review-ci.

Presentation layer only: every subcommand is a typed function imported from
its logic module and registered here. Help text comes from those functions'
docstrings.

Subcommands:
- install          — write trigger workflows and apply required branch protection
- check-profile    — fail if a target repo does not match its curated profile
- check-diff       — fail if a PR unified diff introduces deterministic findings
- check-delegation — fail if a target justfile stops delegating to global QC
- check-justfile   — fail if a target justfile violates the baseline contract
- check-pr-description — fail on unchecked checklist items, or (where the gate template is installed) a missing policy-alignment section
- check-app-boot   — run the target repo's delegated bun-playwright gate
- check-review-threads — require evidence-backed ai-review thread resolution
- protect-branch   — apply required branch protection contexts
- doctor-schema    — dump the JSON Schema for the doctor payload
- validate-report  — validate a candidate report and write the artifact
- report-schema    — dump the JSON Schema for a report type
- report-metadata  — print machine-parseable metadata from an artifact
- enforce-report-status — fail if a report contains actionable findings
- to-sarif         — convert a validated artifact to SARIF 2.1.0
- fetch-context    — build reviewer context from code scanning alerts
- post-threads     — post validated findings as resolvable PR threads
- run-review       — assemble the reviewer prompt and loop opencode
"""

from cyclopts import App

from ai_review_ci.context import fetch_context
from ai_review_ci.doctor import check_justfile, doctor, doctor_schema, version_command
from ai_review_ci.gates import (
    check_app_boot,
    check_delegation,
    check_diff,
    check_profile,
    check_pr_description,
    check_review_threads,
    protect_branch,
)
from ai_review_ci.harness import run_review
from ai_review_ci.install import install
from ai_review_ci.report import (
    enforce_report_status,
    report_metadata,
    report_schema,
    validate_report,
)
from ai_review_ci.sarif import to_sarif
from ai_review_ci.threads import post_threads

app = App(
    name="ai-review-ci",
    help="Centrally-managed, OpenCode-powered review CI.",
)

app.command(install)
app.command(version_command, name="version")
app.command(doctor)
app.command(doctor_schema)
app.command(check_profile)
app.command(check_diff)
app.command(check_delegation)
app.command(check_justfile)
app.command(check_pr_description)
app.command(check_app_boot)
app.command(check_review_threads)
app.command(protect_branch)
app.command(validate_report)
app.command(report_schema)
app.command(report_metadata)
app.command(enforce_report_status)
app.command(to_sarif)
app.command(fetch_context)
app.command(post_threads)
app.command(run_review)


def main() -> None:
    """Entry point for the ai-review-ci console script."""
    app()


if __name__ == "__main__":
    main()
