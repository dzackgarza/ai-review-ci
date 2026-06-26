## Scaffold draft PR — milestone claim

This is a planning/claim scaffold so this work unit is picked up as one coherent,
review-sized PR instead of fragmented one-issue-per-PR. It carries no implementation
yet; the implementer pushes commits here and switches `Refs` to `Closes` as each
obligation lands with proof.

- **Target issue set / subtree:** Epic #44 and children #49, #50
- **GitHub milestone:** Owned surface reduction
- **Issues to close on merge:** #49, #50 (when each lands with proof)
- **Broader parent referenced only:** #44 (epic)
- **Proof obligations claimed:** Bespoke internals are retired in favor of standard idioms or explicitly justified: merge_ini wrapper and ordered-unique accumulator.
- **Proof obligations not claimed:** None deferred within this unit.

## Local implementation plan
- #50: retire or justify merge_ini.
- #49: replace ordered-unique accumulator with a standard idiom where still present.

## Evidence required
Each claimed issue lands with a committed red reproducer that fails on current behavior
and passes after the fix, verified under `just test-ci`.

## Exclusions / split conditions
Unrelated runner internals are out of scope.
