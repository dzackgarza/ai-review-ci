<!-- policy-alignment-gate -->

## Intended result

PR review handling converges by separating disposition, remediation, and new-review windows, so review threads are not bulk-rejected, relitigated, or resolved on invented owner premises.

## Scope

- Included: ai-review-ci-owned PR review workflow guidance and any review-thread/disposition gate changes needed to make #105 enforceable after work is submitted.
- Excluded: generic agent planning behavior before a PR/review exists.
- Preserved behavior: accepted review feedback still requires committed remediation before positive disposition; rejected or modified feedback remains visible.

## GitHub tracking

- Target issue set / subtree: #105
- Milestone: Adaptive Workflow Orchestration
- Closes on merge:
  - Closes #105
- References only:
  - Refs #102 parent epic.
  - Refs #42 review delivery state context.

## Implementation plan

1. Update maintained review workflow surfaces to define disposition, remediation, and new-review windows.
2. Include durable notes for rejected, duplicate, and already-remediated findings.
3. Forbid bulk-reject and invented owner-premise shortcuts with the zotero-gui PR #7 calibration case.
4. Add gate/test coverage if the protocol is represented in review-thread evidence checks.

## Claim map

- [ ] **#105 - review windows are separated and convergence rules are visible**
  - Proof obligations claimed: workflow surface update, calibration case, and gate/test proof if enforcement code changes.
  - Partial / not claimed: delivery-channel dedup (#25/#29) or reviewer-signal eval (#28/#19/#20/#21).
  - Evidence required: docs/manifest/gate diff mapped to acceptance criteria and current tests.
  - Current evidence: issue only.

## Automated gates

Keep draft until evidence is current and relevant review/gate tests plus `just test` are green.
