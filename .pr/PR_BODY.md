## Intended Result

Coordinate the adaptive workflow changes identified in the June 16-23 Claude workstream audit so `ai-review-ci` places proof burden, parallel-agent coordination, review-window handling, parity guidance, current-state ledgers, and external-source budgeting at the correct boundary without weakening fail-loud review/QC policy.

This milestone should externalize one coherent workflow contract across reviewer doctrine, QC prompts, planning guidance, and downstream proof expectations instead of scattering the same rule across unrelated milestones or the `~/ai` orchestration repo.

## Scope

Included:

- Risk-tiered proof-lane doctrine for stronger-model work.
- Parallel-agent worktree and file-ownership boundaries.
- Review-window convergence rules for disposition, remediation, and fresh review.
- User-observable proof doctrine for reviewer and QC surfaces.
- Parity-first interop guidance before bespoke implementations.
- Current-state ledger guidance for long-horizon workstreams.
- Source-disposition budgets for long external-source cascades.

Excluded:

- Replacing milestone [Signal Separation](https://github.com/dzackgarza/ai-review-ci/milestone/6) or reopening its commit/push/PR/ambient gate split work.
- Repeating `Owned surface reduction` or `~/ai` orchestration work unless a child issue explicitly transfers the burden here.
- Lowering bridge-burning constraints, adding fallbacks, or treating self-scans of `ai-review-ci` as downstream proof.

Preserved behavior:

- Review and QC policy stays fail-loud at real repo boundaries.
- Existing milestone ownership stays intact unless a child issue explicitly moves work here.
- Draft-planning work does not count as completion until downstream or fixture proof shows the intended workflow change.

## GitHub Tracking

- Milestone: [Adaptive Workflow Orchestration](https://github.com/dzackgarza/ai-review-ci/milestone/8)
- Development links:
  - Closes #102
  - Closes #103
  - Closes #104
  - Closes #105
  - Closes #106
  - Closes #107
  - Closes #108
  - Closes #109

## Execution Structure

Start by fixing the workflow-allocation doctrine that controls later reviewer/QC edits: #103 defines risk tiers, #104 defines parallel-writer ownership, #105 defines convergent review windows, and #108 plus #109 define the durable ledger and source-budget state that long workstreams must carry. Land #106 and #107 by projecting those workflow rules into reviewer/QC/planning surfaces rather than inventing a second policy stack. Close #102 only after the doctrine converges and at least one real downstream repo or fixture boundary proves the changed review/QC behavior.

## Milestone Tree

- [ ] **M1 - Adaptive workflow orchestration contract lands in repo-owned surfaces** ([#102](https://github.com/dzackgarza/ai-review-ci/issues/102))
  - Complete when: reviewer doctrine, QC prompts, planning guidance, and downstream proof expectations all express the same adaptive workflow contract and at least one real downstream or fixture boundary proves the behavior change.
  - Evidence: pending linked diffs across review/QC surfaces, downstream proof run, and gate results.

- [ ] **W1 - Risk-tiered proof lanes for stronger-model work** ([#103](https://github.com/dzackgarza/ai-review-ci/issues/103))
  - Behavior: low-, medium-, high-risk, and milestone-completion work each route to the correct proof lane without duplicating Signal Separation gate placement.
  - Acceptance: the guidance preserves bridge-burning constraints, names calibration examples, and maps each tier to commit/push/PR/milestone gates.
  - Evidence: pending workflow-doc diff, reviewer/QC references, and downstream or fixture proof that the new lane changes behavior at the intended boundary.

- [ ] **W2 - Parallel-agent ownership boundaries** ([#104](https://github.com/dzackgarza/ai-review-ci/issues/104))
  - Behavior: parallel implementation work requires one writer per worktree or disjoint file set, with manager-owned integration authority.
  - Acceptance: agent-facing guidance states when shared worktrees are allowed, how ownership is assigned, and how proof artifacts are returned.
  - Evidence: pending coordination-guidance diff and calibration note covering the `github-dashboard` overlapping-writer failure.

- [ ] **W3 - Convergent review windows** ([#105](https://github.com/dzackgarza/ai-review-ci/issues/105))
  - Behavior: disposition, remediation, and new-review rounds are separated so thread handling converges instead of re-litigating the same residue.
  - Acceptance: the workflow docs forbid bulk-reject and invented owner-premise shortcuts, and require durable notes for rejected, duplicate, or already-remediated findings.
  - Evidence: pending review-protocol diff, thread/state examples, and proof that the updated review window contract is reflected in the maintained surfaces.

- [ ] **W4 - User-observable proof doctrine** ([#106](https://github.com/dzackgarza/ai-review-ci/issues/106))
  - Behavior: reviewer and QC guidance prefers user-observable or boundary-visible proof before implementation-internal assertions.
  - Acceptance: the doctrine distinguishes user-story proof from implementation-preservation tests, links to existing slop-fixture work, and includes concrete calibration examples.
  - Evidence: pending reviewer/QC guidance diff, fixture or signal addition, and downstream proof of a changed review/QC outcome.

- [ ] **W5 - Parity-first interop before bespoke implementations** ([#107](https://github.com/dzackgarza/ai-review-ci/issues/107))
  - Behavior: parity work starts by identifying the existing tool, format, library, or protocol that already owns the behavior before custom implementation is considered.
  - Acceptance: planning or policy guidance contains the parity-first checklist, concrete examples, and reviewer coverage for custom-engine smells.
  - Evidence: pending policy/planning diff plus cross-links to the owned-surface milestone where repo-internal reinvention work already lives.

- [ ] **W6 - Current-state ledgers for long workstreams** ([#108](https://github.com/dzackgarza/ai-review-ci/issues/108))
  - Behavior: each long-horizon workstream has one current-state ledger that records shipped/open/blocked/next state without inventing extra approval stages.
  - Acceptance: the guidance distinguishes ledgers from changelogs and explains how this interacts with repos that already use `agent-memory` plan records.
  - Evidence: pending workflow-guidance diff and calibration note covering stale-plan and ratification drift.

- [ ] **W7 - Source-disposition budgets for external-source cascades** ([#109](https://github.com/dzackgarza/ai-review-ci/issues/109))
  - Behavior: long external-source searches expose per-source timeout/disposition state and a total budget before the proof loop begins.
  - Acceptance: the guidance distinguishes legitimate source exhaustion from partial-source failure and resolves whether this burden stays in `ai-review-ci` or transfers to a better-owning repo.
  - Evidence: pending workflow-guidance diff plus the Zotero cascade calibration example and ownership disposition.

## Validation / Proof Checklist

- Real downstream repo or fixture proof must reproduce at least one targeted churn/proof-shape defect before the contract changes claim success.
- The replacement guidance must be verified at the downstream repo boundary rather than by self-scanning `ai-review-ci`.
- `just check`
- `just test`
- `just test-ci` when shared workflow, reviewer, or QC gate behavior changes.

## Blocked / Open Questions

- Which adaptive workflow rules belong in `~/ai` skills/prompts versus `ai-review-ci` reviewer/QC doctrine?
- Which child issues require fixture-backed proof in this repo versus narrative workflow guidance only?
- Does #109 stay owned here, or should its long external-source budget contract move to the relevant agent-process or Zotero repo with a closing pointer?

## Review-Readiness Gate

This PR stays draft until every in-scope issue-linked checklist item has linked diffs and evidence, ownership-transfer questions are resolved or explicitly transferred, at least one downstream or fixture boundary proves the changed workflow behavior, and the required repo checks are green. Once review begins, unresolved review residue is tracked in `.pr/REVIEW_LOG.md` rather than backfilled into the milestone checklist.
