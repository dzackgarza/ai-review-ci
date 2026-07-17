# Non-Proof / Administrative Artifacts

> **Style card `ADMIN-ARTIFACT`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

## Bad pattern: Test-shaped artifacts that prove nothing (smoke tests, coverage-only tests, import tests, constructor tests), quarantine labels that launder slop ("smoke", "non-proof", "diagnostic-only", "legacy"), and administrative records (issues, comments, docs) presented as completion of an implementation or proof obligation.

All three patterns share the same root: an artifact that looks like evidence but carries no proof weight, creating a surface future agents can cite as "already handled."

## Preferred construction: For each artifact, determine whether it carries a real proof burden:
- Remove test-shaped artifacts that add no proof (they will be cited later as evidence of a real test suite).
- Move non-proof diagnostics to a non-QC diagnostic surface (separate tool, separate command, separate directory, not in the test suite).
- Require burden disposition for quarantine labels — either the artifact is real proof or it is removed.
- Administrative records (issues, comments, docs) document what remains to be done; they do not close the obligation.

## Use this pattern when:
- The test file uses "smoke", "non-proof", "diagnostic-only", or similar disclaimers.
- The test asserts nothing about the source-of-truth boundary (imports, constructor, status labels).
- An issue, PR comment, or doc change is presented as completion of a code/proof task.

## Choose a different pattern when:
- The diagnostic surface is explicitly maintained for debugging and never cited in QC or reviews.
- The administrative record genuinely closes the task (e.g., a research decision documented in an issue is the completion).
