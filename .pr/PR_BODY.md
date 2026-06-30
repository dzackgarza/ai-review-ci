## Implementation PR — stale proof thread convergence (#126)

This PR carries the next review-state bugfix for findings re-raised after their
own proof no longer reproduces on the reviewed SHA.

- **Target issue:** #126
- **Theme:** let the thread-resolution gate withdraw stale ai-review threads when their safe proof grep no longer matches
- **Issue to close on merge:** #126, if the review accepts grep/rg proof re-evaluation as the intended first slice

## Implemented behavior

- The thread-resolution gate extracts `**Proof:** \`...\`` commands from ai-review
  thread bodies that contain the machine fingerprint marker.
- Only safe `grep` / `rg` proof commands are eligible for automatic re-checking;
  shell composition and broad unsafe grep shapes are rejected.
- If a safe proof exits with status `1` (no matches), the gate resolves the
  stale GitHub review thread instead of continuing to count it as unresolved.
- If the proof still reproduces, cannot be parsed safely, or errors, the thread
  remains blocking.

## Evidence

- `tests/test_gates.py` covers auto-resolving a stale grep proof, preserving a
  still-reproducing proof as a blocker, and rejecting shell-composed proofs.
- The production gate path is covered directly: tests call `check_review_threads`
  with mocked thread nodes and mocked `gh`/proof-command execution.
