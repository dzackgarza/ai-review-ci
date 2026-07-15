# Investigate a Feedback Claim Before Action

Load this card only after B returns `Investigate before action` or a pending item already carries that disposition.
Investigation is an evidence-producing loop, not a terminal disposition.

## Make the open state visible

Role A posts or repairs the investigation reply owned by [[pr-feedback-triage/references/thread-resolution|the canonical thread-local reply contract]].
The reply names the exact evidence gap, the observation that would decide it, and the current audit anchor.
Do not resolve the finding.

## Collect a factual packet

Role A performs read-only investigation at the boundary that owns the claim:

- inspect the named source and current diff;
- reproduce or query the relevant runtime, check, API, or artifact when the claim depends on it;
- record both confirming and falsifying observations;
- preserve exact source URLs, paths, lines, commands, and outputs needed to audit the result.

Do not edit implementation while the claim remains undecided.
If evidence requires user authority or unavailable external state, update the same open reply with that exact gap and stop with the item open.

## Return to an independent disposition

Send a fresh B the original raw finding plus the factual packet, not A's verdict and not the prior disposition as an instruction.
B reruns [[pr-feedback-triage/references/disposition|the disposition card]].

- If B reaches a final disposition, edit the existing investigative reply into the applicable [[pr-feedback-triage/references/thread-resolution|canonical final reply]] and continue the normal route.
- If B still needs investigation, update the same reply with the remaining evidence gap and keep the item open.

Never convert “investigated” into “resolved” without a final B disposition and the corresponding thread-local evidence.
