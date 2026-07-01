## Implementation PR — structured review state and meaningful review checks (#26)

This PR carries the next review-state milestone slice: make review jobs expose a
machine-readable finding state and fail consistently when actionable findings are
present.

- **Target issue:** #26
- **Theme:** stop requiring consumers to scrape review prose to know whether a run has actionable findings
- **Issue to close on merge:** #26

## Implemented behavior

- `report-metadata` now emits a structured `findings` array with fingerprint,
  tier, review type, category, label, path, line range, and status.
- New `enforce-report-status` CLI command fails when the validated report has
  tier1 findings and passes when no tier1 findings are present.
- `_review.yml` writes `.review-findings.json`, uploads it as a workflow
  artifact, then enforces the review status after SARIF upload and PR thread
  posting so the evidence remains available even when the review check fails.

## Evidence

- `tests/test_report.py` validates the structured state payload and tier1/tier2
  status behavior directly against validated report-shaped artifacts.
- `tests/test_install.py` verifies the reusable review workflow uploads the
  structured state artifact before enforcing the final status.
