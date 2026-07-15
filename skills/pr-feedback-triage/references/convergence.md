# Converge the PR Feedback Loop

Role A re-reads GitHub after every disposition/remediation window.
GitHub is the current state; a cached worklist is only a resume aid.

## Round

```text
collect every surface
  -> resume each OPEN-PENDING item from its first incomplete stage
  -> B disposition for each NEW, RE-RAISED, or incomplete pending finding
  -> investigate evidence gaps and return the evidence packet to a fresh B
  -> reply and close rejected, duplicate, outdated, and eligible backlog items
  -> first-principles specs for accepted current-PR findings
  -> C remediation
  -> A verification
  -> commit, push, thread-local replies, and resolution
  -> wait for the review/check window to settle
  -> collect again
```

Close the entire current window.
A disposition recorded internally while its required thread reply or remediation remains open is not progress toward convergence.

## Re-raised findings

- Same finding already dispositioned elsewhere: reply `Duplicate` with the canonical thread.
- Finding attached to code replaced by a later commit: reply `Outdated` with the superseding commit.
- Same fingerprint re-emitted after a push: inherit only from the verified canonical disposition; do not re-litigate and do not silently skip.

Similarity alone is insufficient.
Confirm the same concern on the same semantic code before calling it a duplicate.

## Readiness and issue state

When accepted feedback reopens a claimed obligation, update the work-unit issue and make the PR not ready before remediation.
When the disposition changes scope or reveals a contract defect, update the owning issue before code.

Push accepted remediation before waiting for the next review round.
Do not call repeated review a snowball: a growing window is evidence that remediation is introducing defects or that collection/disposition is incomplete.

## Termination

The loop terminates only when a fresh settled scan shows:

- every feedback surface was read;
- no `NEW`, `RE-RAISED`, or `OPEN-PENDING` item;
- every substantive item has its surface-local evidenced disposition;
- every accepted item has committed remediation and owned-boundary proof;
- all required checks are settled and green;
- the work-unit issue and PR claim are current.

Zero unresolved inline threads alone is not convergence.
Neither is a clean scanner, green CI, or an internal disposition count.
