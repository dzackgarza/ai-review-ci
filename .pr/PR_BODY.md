## Scaffold draft PR — milestone claim

This is a planning/claim scaffold so this work unit is picked up as one coherent,
review-sized PR instead of fragmented one-issue-per-PR. It carries no implementation
yet; the implementer pushes commits here and switches `Refs` to `Closes` as each
obligation lands with proof.

- **Target issue set / subtree:** Epic #43 and children #45, #46
- **GitHub milestone:** Delegated QC rule precision
- **Issues to close on merge:** #45, #46 (when each lands with proof)
- **Broader parent referenced only:** #43 (epic)
- **Proof obligations claimed:** QC rules fire only on sanctioned positions (ts-no-or-default on value/default, not fail-loud guards) with a defined boundary form for justified no-double-cast cases.
- **Proof obligations not claimed:** None deferred within this unit.

## Local implementation plan
- #45: restrict ts-no-or-default to value/default positions.
- #46: define sanctioned boundary form for no-double-cast.

## Evidence required
Each claimed issue lands with a committed red reproducer that fails on current behavior
and passes after the fix, verified under `just test-ci`.

## Exclusions / split conditions
Reviewer threat-model/classification work is out of scope (Reviewer signal quality).
