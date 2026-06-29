## Intended Result

Build a review delivery state machine that gives maintainers one reliable, structured view of review findings, disposition state, reviewer identity, and merge readiness.

The output should stop re-emitting the same catalog on every push, stop relying on inconsistent check status as the only merge signal, and gate PR readiness on issue-linked contract evidence rather than arbitrary markdown checklist theater.

## Scope

Included:

- Structured reviewer identity and finding provenance.
- Stable finding fingerprints and cross-run convergence.
- Consistent pass/fail plus machine-readable finding state.
- Evidence-backed decision about duplicate channels after measuring unique yield.
- PR contract completeness gate scoped to issue-linked Milestone Trees.

Excluded:

- Reviewer signal-quality prompt work owned by #41.
- Signal-tier scheduling work owned by #56.
- Generic branch protection unrelated to review finding state.

Preserved behavior:

- Review comments and SARIF/code-scanning surfaces remain auditable.
- Findings must stay tied to source evidence and stable identity, not only bot display names.

## GitHub Tracking

- Milestone: [Review delivery state machine](https://github.com/dzackgarza/ai-review-ci/milestone/3)
- Development links:
  - Closes #42
  - Closes #22
  - Closes #23
  - Closes #25
  - Closes #26
  - Closes #29
  - Closes #60

## Execution Structure

Reviewer identity and structured state are foundations. Cross-run dedup uses that identity. Channel consolidation depends on #29’s unique-yield research. The PR contract gate in #60 must consume issue-linked evidence state, not raw unchecked markdown text.

## Milestone Tree

- [ ] **M1 - Review delivery state, identity, and convergence** ([#42](https://github.com/dzackgarza/ai-review-ci/issues/42))
  - Complete when: review delivery exposes stable reviewer/finding identity, converges across pushes, and provides a reliable merge-readiness signal grounded in structured state.

- [ ] **F1 - Reviewer identity and provenance** ([#23](https://github.com/dzackgarza/ai-review-ci/issues/23))
  - Behavior: every finding carries machine-readable reviewer type, prompt/version provenance, and accurate source location context.
  - Acceptance: downstream triage can route feedback to the producing reviewer and detect mislocated headers.
  - Evidence: pending schema/template diffs and fixture output.

- [ ] **F2 - Structured status and finding output** ([#26](https://github.com/dzackgarza/ai-review-ci/issues/26))
  - Behavior: checks and workflow outputs expose consistent pass/fail and structured findings state.
  - Acceptance: a consumer can determine whether actionable findings exist without scraping all threads.
  - Evidence: pending output schema, tests, and example run artifacts.

- [ ] **W1 - Cross-run deduplication and disposition convergence** ([#22](https://github.com/dzackgarza/ai-review-ci/issues/22))
  - Behavior: stable fingerprints suppress reraising findings already resolved, rejected, or superseded on the same PR.
  - Acceptance: repeated review rounds monotonically converge unless new code changes produce genuinely new findings.
  - Evidence: pending state-machine tests across simulated pushes.

- [ ] **W2 - Unique-yield research for channel decisions** ([#29](https://github.com/dzackgarza/ai-review-ci/issues/29))
  - Behavior: measure accepted-finding unique yield across advanced-security, workflow comments, and external reviewers.
  - Acceptance: channel consolidation decisions are backed by accepted-finding overlap data rather than volume assumptions.
  - Evidence: pending research artifact and decision note.

- [ ] **W3 - Channel consolidation or deduplication** ([#25](https://github.com/dzackgarza/ai-review-ci/issues/25))
  - Behavior: reduce duplicate finding emission while preserving sources with demonstrated unique yield.
  - Acceptance: duplicate surfaces stop creating redundant triage work without dropping proved real coverage.
  - Evidence: pending implementation commit and comparison artifact.

- [ ] **I1 - PR contract completeness gate** ([#60](https://github.com/dzackgarza/ai-review-ci/issues/60))
  - Behavior: gate PR readiness on issue-linked Milestone Tree completion and evidence anchors.
  - Acceptance: the gate rejects in-scope unchecked obligations without treating arbitrary markdown checkboxes, deferred work, or tracking-the-tracking items as blockers.
  - Evidence: pending parser/check tests with valid and invalid PR body fixtures.


## Incremental implementation landed

- #127 (under #42): the thread-resolution gate is now source-agnostic. It evaluates every resolvable PR review thread, not only `ai-review` fingerprinted threads. Unresolved threads from any source fail the gate, and resolved threads from any source require commit or disposition-ledger evidence. Evidence: `src/ai_review_ci/gates.py::check_review_threads` and `tests/test_gates.py` source-agnostic regression cases.

## Automated Gates

This PR remains draft until every checklist item has commit/evidence anchors, state-machine fixtures cover repeated review rounds and PR-body contract cases, review residue is resolved or moved to a separate debt issue, and GitHub checks pass.
