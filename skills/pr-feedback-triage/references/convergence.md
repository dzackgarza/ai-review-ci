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
  -> commit and push
  -> complete each item on its own surface; resolve inline threads only after their replies
  -> wait for the review/check window to settle
  -> collect again
```

Close the entire current window.
A disposition recorded internally while its required thread reply or remediation remains open is not progress toward convergence.

## Re-raised findings

- Same finding already dispositioned elsewhere: reply `Duplicate` with the canonical thread.
- Finding attached to code replaced by a later commit: verify that the concern no longer applies, then reply `Outdated` with the superseding commit and proof.
  If it still applies to replacement code, reattach or redisposition it.
- Same fingerprint re-emitted after a push: verify that the same semantic concern and evidence still hold before using the canonical disposition.
  If affected semantic code changed, produce a fresh disposition.

Similarity or fingerprint equality alone is insufficient.
Confirm the same concern on the same semantic code before calling it a duplicate or inheriting prior judgment.

## Readiness and issue state

When accepted feedback reopens a claimed obligation, update the work-unit issue and make the PR not ready before remediation.
When the disposition changes scope or reveals a contract defect, update the owning issue before code.

Push accepted remediation before waiting for the next review round.
After verification closes every obligation claimed by the work-unit issue's ready-for-review gate, update the issue/PR claim map and run `gh pr ready <number>`; otherwise the PR remains not ready and convergence is false.
Do not call repeated review a snowball or infer its cause from growth alone.
Recollect the live surfaces and determine whether each added item is newly exposed, independently discovered, reintroduced, caused by remediation, or previously missed before routing it.

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
