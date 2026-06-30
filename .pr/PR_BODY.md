## Implementation PR — runtime-default rule precision (#120, #130)

This PR carries the next review-sized implementation slice for the remaining
`POLICY.RUNTIME_DEFAULT` false-positive cleanup.

- **Target issue set:** #120 and #130
- **Theme:** distinguish fail-soft defaults from legitimate empty-boundary normalization
- **Issues to close on merge:** #130; #120 only if the broader `||` / `??` precision acceptance criteria are confirmed complete

## Implemented behavior

- `no-nullish-coalescing` and `ts-no-or-default` now keep flagging non-empty
  success-shaped fallbacks, booleans, `null`, and numeric fallbacks.
- Empty literal fallbacks (`""`, `[]`, `{}`) are treated as valid owned-boundary
  normalization for genuinely optional data instead of automatic runtime-default
  violations.
- Boolean connective cases remain allowed; non-empty render/data defaults remain
  blocked.

## Evidence

- `tests/fixtures/semgrep/runtime_default.ts*` includes both blocked non-empty
  fallback cases and allowed empty-boundary normalization cases.
- `tests/test_semgrep_rules.py` runs the shipped Semgrep rules against the
  annotated fixtures, so the proof covers the production rule config rather than
  a copied test-only rule.
