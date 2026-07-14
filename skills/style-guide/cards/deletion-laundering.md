# Deletion Laundering / Proof-Burden Erasure

> **Style card `DELETION-LAUNDERING`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

## Bad pattern: A criticized slop artifact is deleted without solving or recording the original problem it attempted to address.
The codebase looks cleaner, but the proof burden is now hidden.
The next agent is likely to recreate the same fake proof, fallback, wrapper, or harness because the original requirement is absent from the new PR narrative.

Detection:
- deletion follows review or user criticism;
- commit message emphasizes cleanup, removal, or simplification;
- no replacement proof or capability exists;
- no issue, contract, or blocker records the original problem;
- final report says the review item is resolved because the artifact is gone;
- the original requirement is absent from the new PR narrative.

## Preferred construction: Require a burden disposition: the original problem must be either solved, invalidated, transferred to real proof, or explicitly recorded as unresolved.
Deletion is not a disposition — it is the removal of an artifact.
The record of what was wrong and why must survive the deletion.

```python
# BAD: commit message says "removed dead code" — the original problem is gone
# BAD: PR says "addressed review feedback by deleting the test" — no replacement

# CORRECT dispositions:
# - Solved: the problem was real and the replacement proof covers it
# - Invalidated: the problem was spurious and has been demonstrated irrelevant
# - Transferred: the proof burden moved to a different artifact (integration test, QC check)
# - Recorded unresolved: the problem is real but deferred, with a visible issue or blocker
```

## Use this pattern when:
- A deletion follows criticism and the commit message frames it as cleanup.
- The deleted artifact was the only coverage for a requirement, edge case, or failure mode.
- The review finding was about existence of a proof, not about the artifact's labeling.

## Choose a different pattern when:
- The artifact was genuinely dead code with no corresponding requirement (no one asked for it, no test covered it, no spec mentioned it).
- The deletion is part of a larger replacement that demonstrably covers the original requirement.
