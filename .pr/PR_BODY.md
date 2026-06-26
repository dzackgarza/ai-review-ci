## Scaffold draft PR — milestone claim

This is a planning/claim scaffold so this work unit is picked up as one coherent,
review-sized PR instead of fragmented one-issue-per-PR. It carries no implementation
yet; the implementer pushes commits here and switches `Refs` to `Closes` as each
obligation lands with proof.

- **Target issue set / subtree:** Epic #112
- **GitHub milestone:** Versioned QC distribution
- **Issues to close on merge:** #112 (on completion with proof)
- **Broader parent referenced only:** —
- **Proof obligations claimed:** Versioned QC releases, doctor, and quick setup deliver a reproducible consumer install with a published contract.
- **Proof obligations not claimed:** None.

## Local implementation plan
- Implement versioned QC release + doctor + quick-setup per epic #112.

## Evidence required
Each claimed issue lands with a committed red reproducer that fails on current behavior
and passes after the fix, verified under `just test-ci`.

## Exclusions / split conditions
—
