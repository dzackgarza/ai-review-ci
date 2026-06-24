## Intended Result

Extend the canonical policy-index architecture beyond the completed #40 signal chain so the policy database gives agents precise doctrine for fail-closed error handling, runtime defaults, and remediation examples.

The outcome is not a token-ban patch. The policy index should teach total dataflow, fail-loud boundaries, narrow admitted exceptions, and golden transformations keyed to `POLICY.*` / `REMEDIATE.*` IDs.

## Scope

Included:

- Refine the error-handling policy around `POLICY.NO_ERROR_DISCARD`, `POLICY.FAIL_OPEN`, and boundary exception rules.
- Refine runtime-default doctrine around total boundary models, total core state, and irreducible domain absence.
- Replace remediation examples that invite token swaps, sentinel laundering, or optional-core-state patterns.
- Preserve the vendored policy/remediation index signal chain landed by #40/#51.

Excluded:

- Reopening #40 or reimplementing the vendored index loader.
- Treating raw `try`/`catch`, `||`, or `??` token bans as sufficient policy doctrine.
- Turning examples into local remediation recipes detached from canonical policy IDs.
- Documentation-only cleanup of historical planning paths from #61.

Preserved behavior:

- Detector output and rendered guidance continue to route through the vendored policy index.
- Reviewer agents remain diagnosis-only; remediation guidance stays in canonical deterministic surfaces.

## GitHub Tracking

- Milestone: [Policy index architecture](https://github.com/dzackgarza/ai-review-ci/milestone/1)
- Development links:
  - Closes #63
  - Closes #57
  - Closes #58
  - Closes #59
  - Refs #40

## Execution Structure

#57 and #58 are doctrine foundations. #59 depends on them because examples must demonstrate the corrected doctrine rather than preserve the current sentinel/default framing. Final integration verifies the examples and index references cannot drift from the canonical IDs.

## Milestone Tree

- [ ] **M1 - Policy index doctrine extension** ([#63](https://github.com/dzackgarza/ai-review-ci/issues/63))
  - Complete when: error handling, runtime defaults, and remediation examples are codified in the policy-index architecture with current tests or fixtures proving the intended interpretation.

- [ ] **F1 - Fail-closed error policy** ([#57](https://github.com/dzackgarza/ai-review-ci/issues/57))
  - Behavior: codify when error-catching constructs violate fail-loud execution and when a boundary conversion is explicitly admitted.
  - Acceptance: policy text names the relevant `POLICY.*` obligations, distinguishes swallowing/fallback from boundary conversion, and lists exception requirements without allowing generic defensive catches.
  - Evidence: pending commit hashes, policy/reference diffs, and validation tests or fixtures.

- [ ] **F2 - Runtime-default and optionality doctrine** ([#58](https://github.com/dzackgarza/ai-review-ci/issues/58))
  - Behavior: define total boundary models and total core state as the default remediation for runtime defaults.
  - Acceptance: policy text rejects token substitution and sentinel laundering; domain variants are admitted only for irreducible absence with explicit invariants.
  - Evidence: pending commit hashes, policy/reference diffs, and validation tests or fixtures.

- [ ] **W1 - Golden remediation examples** ([#59](https://github.com/dzackgarza/ai-review-ci/issues/59))
  - Behavior: publish before/after examples keyed to canonical policy and remediation IDs.
  - Acceptance: examples show architectural dataflow repair rather than local token swaps, optional-core-state widening, or sentinel defaults.
  - Evidence: pending commit hashes, example files, and checks that examples stay linked to valid policy/remediation IDs.

- [ ] **I1 - Policy-index drift proof**
  - Behavior: prove the new doctrine and examples remain synchronized with the vendored policy/remediation IDs.
  - Acceptance: stale IDs, missing remediation links, and example/index drift fail mechanically.
  - Evidence: pending verification command output.

## Automated Gates

This PR remains draft until every checklist item has commit/evidence anchors, the policy/example checks prove the intended behavior, review residue is either resolved or moved into a separate debt issue, and GitHub checks pass.
