## Intended Result

Stabilize delegated QC rule precision so downstream repositories can satisfy global QC without false positives, stale caller-root assumptions, or generic suppression escape hatches.

The milestone should preserve strict policy enforcement while making sanctioned boundary forms and rule exceptions mechanically testable through the actual delegated-rule paths.

## Scope

Included:

- Recast the just 1.46 `JUST_WORKING_DIRECTORY` issue as a regression/verification target for delegated caller-root behavior.
- Restrict `ts-no-or-default` so it blocks value defaults but admits fail-loud guard conditions.
- Define a narrow boundary form for justified double-cast/runtime-type mismatches without allowing general erasure.
- Keep downstream caller-root proof in real target repositories or fixtures, not ai-review-ci self-scans.

Excluded:

- Weakening `POLICY.RUNTIME_DEFAULT` or `POLICY.NO_TYPE_ESCAPE`.
- Adding broad suppressions, checker disables, or local downstream overrides.
- Treating the stale current-repo absence of `JUST_WORKING_DIRECTORY` as proof that downstream regressions are impossible.

Preserved behavior:

- Global QC remains authoritative; downstream repos delegate rather than reimplement.
- Correct fail-loud and typed-boundary code remains admissible when proved through the real rule path.

## GitHub Tracking

- Milestone: [Delegated QC rule precision](https://github.com/dzackgarza/ai-review-ci/milestone/4)
- Development links:
  - Closes #43
  - Closes #17
  - Closes #45
  - Closes #46

## Execution Structure

#17 is handled as a caller-root regression fixture, not as a current-repo grep finding. #45 and #46 are independent rule-precision changes. #43 closes only when the delegated rule tests prove all three without weakening global policy.

## Milestone Tree

- [ ] **M1 - Delegated QC compatibility and deterministic rule precision** ([#43](https://github.com/dzackgarza/ai-review-ci/issues/43))
  - Complete when: delegated rule behavior is precise enough that correct downstream code can pass while policy violations still fail through the actual QC path.

- [ ] **F1 - Delegated caller-root regression proof** ([#17](https://github.com/dzackgarza/ai-review-ci/issues/17))
  - Behavior: prove the delegated just/caller-root contract under current `just` semantics with a downstream-style fixture.
  - Acceptance: the regression test covers `JUST_WORKING_DIRECTORY`/`-d` behavior without relying on ai-review-ci self-QC and fails for wrong-root routing.
  - Evidence: pending fixture or temp-target test output.

- [ ] **W1 - Runtime-default rule precision** ([#45](https://github.com/dzackgarza/ai-review-ci/issues/45))
  - Behavior: `ts-no-or-default` blocks value/default positions while allowing boolean guards that fail loudly or exit narrowly.
  - Acceptance: tests include both blocking fallback defaults and allowed fail-loud guards through the real rule path.
  - Evidence: pending rule diffs and fixture output.

- [ ] **W2 - Sanctioned double-cast boundary form** ([#46](https://github.com/dzackgarza/ai-review-ci/issues/46))
  - Behavior: define a narrow typed-boundary assertion for documented runtime/type mismatches.
  - Acceptance: arbitrary double casts remain blocked; allowed boundary casts require justification and are mechanically distinguishable from suppression.
  - Evidence: pending rule/schema diffs and fixture output.

## Automated Gates

This PR remains draft until every checklist item has commit/evidence anchors, real delegated-rule fixtures prove blocking and allowed cases, review residue is resolved or moved to a separate debt issue, and GitHub checks pass.
