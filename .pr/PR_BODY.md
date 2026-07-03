<!-- policy-alignment-gate -->

## Intended result

Parallel-writer coordination and long-horizon state ledgers are represented in the active ai-review-ci work queue as one issue-scoped draft work unit, rather than remaining orphan issues outside PR burn-down.

## Scope

- Included: #104 worktree/file-ownership boundaries for parallel writers and #108 current-state ledger expectations for long-horizon workstreams.
- Excluded: pre-emptively transferring either issue to another repo without maintainer approval.
- Preserved behavior: if implementation discovers that a requirement belongs in `dzackgarza/ai` rather than ai-review-ci, the PR must update the issue with that evidence and get maintainer disposition before closing or transferring.

## GitHub tracking

- Target issue set / subtree: #104 and #108
- Milestone: Adaptive Workflow Orchestration
- Closes on merge:
  - Closes #104
  - Closes #108
- References only:
  - Refs #102 parent epic.

## Implementation plan

1. Re-read #104 and #108 against the clarified boundary: `ai` owns before/as-work workflows; `ai-review-ci` owns after-work integration and enforcement.
2. For each issue, identify the concrete ai-review-ci surface, if one exists: PR body requirements, review guidance, doctor/gate behavior, templates, or post-work evidence expectations.
3. Implement the ai-review-ci-owned surface, or record the maintainer-approved transfer decision before changing issue state.
4. Update #178 as each item is completed, transferred, or split.

## Claim map

- [ ] **#104 - parallel writer worktree/file ownership is dispositioned and implemented in the right surface**
  - Proof obligations claimed: ownership analysis, maintained surface update or approved transfer, calibration example retained.
  - Partial / not claimed: live subagent runtime enforcement unless explicitly assigned to this repo.
  - Evidence required: docs/gate/template diff or maintainer-approved transfer pointer.
  - Current evidence: issue only.

- [ ] **#108 - current-state ledger contract is dispositioned and implemented in the right surface**
  - Proof obligations claimed: ownership analysis, maintained surface update or approved transfer, calibration example retained.
  - Partial / not claimed: agent-memory runtime behavior unless explicitly assigned to this repo.
  - Evidence required: docs/gate/template diff or maintainer-approved transfer pointer.
  - Current evidence: issue only.

## Automated gates

Keep draft until both issues are either implemented in an ai-review-ci-owned post-work surface or explicitly transferred/closed with maintainer-approved rationale. Run `just test` for repo-owned doc/template/gate changes.
