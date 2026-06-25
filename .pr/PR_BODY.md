## Intended Result

Stabilize delegated QC rule precision so downstream repositories can satisfy global QC without false positives, stale caller-root assumptions, or generic suppression escape hatches.

The milestone preserves strict policy enforcement while making rule precision mechanically testable through the actual delegated-rule paths.

## Scope

Included:

- Recast the just 1.46 `JUST_WORKING_DIRECTORY` issue as a regression/verification target for delegated caller-root behavior.
- Restrict `ts-no-or-default` / `no-nullish-coalescing` so they block value defaults but admit boolean-connective positions (folds in #120).
- Decide the double-cast boundary form: there is **no** sanctioned form — block every double cast and route to architectural remediation.
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
  - Closes #120

## Execution Structure

#17 is handled as a caller-root regression fixture, not as a current-repo grep finding. #45/#120 and #46 are independent rule-precision changes. #43 closes when the delegated rule tests prove all three without weakening global policy.

## Milestone Tree

- [x] **M1 - Delegated QC compatibility and deterministic rule precision** ([#43](https://github.com/dzackgarza/ai-review-ci/issues/43))
  - Complete when: delegated rule behavior is precise enough that correct downstream code can pass while policy violations still fail through the actual QC path.
  - Evidence: the three children below, each with a fixture-backed test through the real rule / just path.

- [x] **F1 - Delegated caller-root regression proof** ([#17](https://github.com/dzackgarza/ai-review-ci/issues/17))
  - Behavior: a bare `just <recipe>` in a scaffold consumer parses and routes under just >= 1.46 without exporting `JUST_WORKING_DIRECTORY`, which that version binds to `-d/--working-directory` (then requiring `--justfile`).
  - Acceptance: bare entrypoint routes for every scaffold; no scaffold reintroduces the export; the collision is reproduced when the var is set.
  - Evidence: `7dfd99d`, `97a4558`, `243fe16` — `test_python_scaffold_bare_just_test_reaches_downstream_preflight_without_working_directory_env`, `..._breaks_when_just_working_directory_is_exported`, `test_scaffold_bare_just_entrypoint_survives_working_directory_binding` (×5 scaffolds), `test_scaffold_does_not_export_working_directory_routing_hint`.

- [x] **W1 - Runtime-default rule precision** ([#45](https://github.com/dzackgarza/ai-review-ci/issues/45), folds in [#120](https://github.com/dzackgarza/ai-review-ci/issues/120))
  - Behavior: `ts-no-or-default` and `no-nullish-coalescing` flag only value-default positions (right operand is a literal stub), not boolean connectives in guards/predicates/JSX.
  - Acceptance: blocking value defaults and admitting boolean guards both proven — through the native rule path and the real `_semgrep` recipe.
  - Evidence: `f3fc8b2` — `tests/test_semgrep_rules.py::test_runtime_default_rules_flag_only_value_default_positions` (annotated fixtures: 7 defaults flagged, 0 boolean-connective FPs vs 8 before) plus `test_semgrep_blocks_typescript_value_defaults` / `test_semgrep_allows_fail_loud_typescript_guards` through the gate.

- [x] **W2 - Double-cast boundary form: none** ([#46](https://github.com/dzackgarza/ai-review-ci/issues/46))
  - Decision: there is **no** sanctioned double-cast form. A justification comment or `boundaryCast` escape is reward-hackable (confabulate a reason) and forces QC to adjudicate reasons. Every double cast — `as unknown as`, `as any as`, parenthesized, comment-"justified" — stays blocked and routes to `REMEDIATE.STRUCTURED_TYPES`.
  - Acceptance: arbitrary erasure blocked; a justification comment is not an escape hatch; single casts do not fire.
  - Evidence: `97a4558` — `no-double-cast` rule documents the decision; `tests/test_semgrep_rules.py::test_no_double_cast_blocks_every_erasure_with_no_escape_hatch`.

## Automated Gates

The rule-precision children are proven through the real rule / just paths with fixtures. Full-suite proof is the CI boundary (the local container runs CPython 3.14.0rc2, which the pinned pydantic-core cannot import; the package needs 3.14 deferred annotations, so 3.13 cannot substitute). Tests that do not import the package were run locally against semgrep 1.168.0 and just 1.54.0.
