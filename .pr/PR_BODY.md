<!-- policy-alignment-gate -->

## Intended result

Returned PR feedback is handled by one progressively disclosed, thread-local state machine.
Every substantive finding is independently dispositioned against exact policy or sourced
facts, remediated from a first-principles specification when necessary, answered on its
originating GitHub surface, and resolved only after committed proof.

## Scope

- Included: the canonical pr-feedback-triage skill tree; collection and resumable state;
  thread-reply evidence gates; policy/style remediation routing; integration, AGENTS,
  template, and reviewer routes; style-guide path normalization required by the official
  skill validator.
- Excluded: the downstream installed-skill changes, which are claimed by
  [dzackgarza/ai#40](https://github.com/dzackgarza/ai/pull/40).

## GitHub tracking

- Target work unit: Closes #268.
- Milestone: Review delivery state machine.
- Linked downstream PR: [dzackgarza/ai#40](https://github.com/dzackgarza/ai/pull/40).

## Claim map

- [x] **One progressive state machine**
  - The entrypoint routes collection, disposition, investigation, pending-item resume,
    remediation, thread reply/resolution, and convergence to one-level cards.
  - Git integration, AGENTS guidance, templates, and review guidance route to the skill
    instead of restating it.
- [x] **Thread-local auditable disposition**
  - Policy-governed findings require exact POLICY codes; factual or contract-only
    findings require explicit sourced basis.
  - Accepted and modified findings require committed remediation and owned-boundary proof.
  - Rejected, duplicate, outdated, and minor-debt dispositions require their own evidence.
  - Top-level ledgers and tracked review logs are not accepted as thread evidence.
- [x] **Resumable collection and convergence**
  - Stable identities cover formal reviews, inline threads, top-level comments, check
    annotations, linked issues, and update-in-place bot comments.
  - NEW, RE-RAISED, OPEN-PENDING, and CLOSED remain distinct collection states.
  - Zero unresolved inline threads alone cannot satisfy whole-PR convergence.
- [x] **Downstream installation**
  - The linked draft PR removes the authoritative duplicate, installs this skill by
    symlink, and keeps only a thin A/B/C harness adapter.

## Evidence

- Focused gate, installer, and current-AGENTS checks: 7 passed.
- Issue workflow checks: 6 passed.
- Mypy: no issues in 51 source files.
- Canonical skill validation and skill-link checks pass.
- Live review collector after thread-local replies: 45 CLOSED, zero worklist items,
  inline_threads_converged true.
- Downstream post-dependency assembly: 179 installed skills accepted; Lychee reports
  zero WikiLink errors.
- All 45 upstream inline review threads carry canonical thread-local replies; the seven
  previously open threads were resolved only after those replies.

## Policy alignment

- POLICY.NO_ADMIN_COMPLETION
- POLICY.NO_QC_SILENCING
- POLICY.GLOBAL_QC_AUTHORITY
- POLICY.NO_PARTIAL_SUCCESS

No local override, fallback, ledger-only evidence route, or weakened proof path is
introduced.
