## Implementation PR — delegated QC rule precision (#43)

This PR carries the remaining review-sized implementation slice for the
Delegated QC rule precision milestone.

- **Target issue set / subtree:** Epic #43 and children #45, #46
- **GitHub milestone:** Delegated QC rule precision
- **Issues to close on merge:** #45, #46
- **Broader parent referenced only:** #43 (epic)

## Implemented behavior

- #45: `ts-no-or-default` remains restricted to fail-soft value/default
  positions and does not flag fail-loud boolean guards. The fixture-backed
  rule path for this behavior is already present in `runtime_default.ts*` and
  `test_runtime_default_rules_flag_only_value_default_positions`.
- #46: arbitrary `as unknown as` / `as any as` double casts remain blocked, and
  a sanctioned `runtimeBoundaryCast<T>(value, predicate, reason)` boundary form
  is defined for documented runtime/type-surface mismatches.

## Boundary assertion contract (#46)

The only sanctioned boundary form requires:

1. an explicit `runtimeBoundaryCast<T>(...)` call;
2. a runtime predicate argument, so the caller supplies executable evidence for
   the claimed target type; and
3. a source-backed reason string containing an issue reference or URL.

Near misses remain blocked: arbitrary double casts, empty reasons, missing
predicate arguments, and local-story-only reasons.

## Evidence

- `tests/fixtures/semgrep/runtime_default.ts*` covers both blocked fail-soft
  defaults and allowed fail-loud/boolean connective cases.
- `tests/fixtures/semgrep/no_double_cast.ts` covers blocked double casts,
  allowed single casts, the sanctioned boundary form, and invalid nearby
  boundary-form cases.
- `tests/test_semgrep_rules.py` runs the real shipped Semgrep rules against the
  annotated fixtures, not copied test-only rule definitions.
