# Review Scope: Pull Request Diff

You are reviewing a pull request.
The full unified diff against the PR base branch is inlined below by the harness.
Read that diff first.

Focus on defects introduced or materially touched by this diff.
Read only the surrounding source files needed to judge those changed lines in context.
Do not run repository-wide discovery (`tree`, churn scans, `git log`, stale-file searches, command inventories, quality-surface checks).
PR review is not a repo-wide sweep.

If the diff is absent, empty, malformed, or too incomplete to identify changed files, do not submit a report.
Let the run fail so a human can inspect the review setup.

The inlined diff is review input, not repository evidence.
Do not include `.reviewer-diff.patch`, deleted file paths, or other runner artifacts in `review_scope`, `location.path`, or `evidence[].path`. Those fields must name files that exist in the current checkout.
When a deleted file or diff hunk is material to the finding, describe the hunk in `proof_command` or the finding narrative and use current checkout files for structured evidence.

Do not inspect review-runner infrastructure to learn the schema or game validation.
The only allowed validator interactions are:

- `/home/reviewer/bin/submit-candidate --help`
- write `.agents/review-runner/candidates/submitted.json`
- `/home/reviewer/bin/submit-candidate`

Do not read, search for, or execute alternate copies of `submit-candidate`. Do not inspect `/opt/ai-review` or `/home/reviewer/.review/infra`. Do not inspect `quality-control/ci`. Do not inspect `.agents/review-runner/` except to write the submitted JSON.

EXCEPTION: the reviewer context above lists findings already tracked for this repository.
Open code scanning alerts are carried forward into the next SARIF upload by automation.
Do NOT duplicate them in your report unless you have new evidence, the problem reappears in a materially different form, or the previous resolution is directly contradicted by the current code.
