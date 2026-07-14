# Local QC Bypass

> **Style card `QC-BYPASS`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

## Bad pattern: A project defines quality gates (test runner, type checker, linter) through local scripts or configs that bypass the global quality control system, giving agents a narrower set of checks to pass.

## Preferred construction: Route all quality gates through the global QC system (`~/ai-review-ci/justfiles/<language>.just`). Local justfiles may compose global recipes but must not define independent checks that duplicate or override global gates.
A local QC surface that passes when global QC fails is a bypass.

## Use this pattern when:
- A project-local test/lint/type-check recipe exists that does not delegate to global QC.
- The local recipe uses different flags, coverage thresholds, or exclusion patterns than the global equivalent.

## Choose a different pattern when:
- The local recipe ADDS checks beyond the global baseline (stricter, not looser).
- The global QC system does not cover the project's language or toolchain.
