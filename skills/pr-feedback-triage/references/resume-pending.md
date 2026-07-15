# Resume an Open Pending Feedback Item

Load this card only for a collected `OPEN-PENDING` item.
Role A reads the live finding, the existing canonical reply, and the current GitHub state before choosing the resume point.

## Route from the first incomplete stage

- **Complete canonical reply, unresolved inline thread:** verify that its commit, proof, and audit anchors still match the live diff, then resolve the existing thread.
  Do not redisposition or repost.
- **Incomplete accepted reply:** send the current finding and incomplete reply to a clean B for reevaluation, then continue through [[pr-feedback-triage/references/remediation|remediation]] and [[pr-feedback-triage/references/thread-resolution|verification and resolution]].
- **Incomplete rejected, duplicate, outdated, or backlog reply:** send the current finding and incomplete reply to a clean B for reevaluation, then repair the existing reply through [[pr-feedback-triage/references/thread-resolution|the canonical reply contract]].
- **Investigative reply:** continue through [[pr-feedback-triage/references/investigation|the investigation loop]].

An incomplete prior reply is evidence and resume state, not an inherited judgment.
B must reevaluate it against current source and policy.

## Preserve the stable reply

Repair or finalize the existing canonical reply instead of appending another `Disposition:` reply.
The collector prefers the latest complete canonical reply and otherwise resumes from the latest incomplete reply, so a malformed earlier reply cannot hide a later correction.
This recovery rule does not authorize duplicate replies when the existing one is editable.

If that reply cannot be edited with the active GitHub identity, leave the item open and report the exact permission failure.
Do not hide the conflict behind a second reply or a top-level ledger.
