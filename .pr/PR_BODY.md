## Intended Result

Separate ai-review-ci verification signals by the boundary they prove: local commit checks, push/CI checks, PR-diff gates, ambient repository audits, agent-driven review runs, and deferred debt tracking.

The goal is faster, clearer feedback without weakening proof. Diff gates should block new relevant debt; ambient scans should keep repo-wide debt visible; agent reviews should run when their signal is wanted, not as duplicate churn in every deterministic gate.

## Scope

Included:

- Optimize commit vs push gate boundaries without duplicating heavy checks.
- Separate PR-diff gating from ambient repository-wide audits.
- Separate deterministic automated checks from agent-driven review runs.
- Track deferred debt as issue-linked ambient work rather than hidden quarantine.

Excluded:

- Reviewer signal-quality prompt work owned by #41.
- Review-delivery identity/dedup state owned by #42.
- Policy-index doctrine issues #57-#59.
- Weakening global QC or treating smoke/syntax checks as full proof.

Preserved behavior:

- Correctness gates still fail loudly for the boundary they own.
- Repo-wide debt remains visible and scheduled; it is not silently suppressed to make PRs green.

## GitHub Tracking

- Milestone: [Signal Separation](https://github.com/dzackgarza/ai-review-ci/milestone/6)
- Development links:
  - Closes #56
  - Closes #52
  - Closes #53
  - Closes #54
  - Closes #55
  - Refs #38

## Execution Structure

#52 establishes local gate tiers. #53 separates PR diff gates from ambient repo audits. #54 separates agent-driven review from deterministic CI. #55 defines non-blocking debt tracking without quarantine. #56 closes only when these pieces produce one coherent signal model.

## Milestone Tree

- [ ] **M1 - Signal separation and gate tiers** ([#56](https://github.com/dzackgarza/ai-review-ci/issues/56))
  - Complete when: commit, push, PR, ambient, agent-review, and debt signals each have a defined owner, trigger, output, and proof boundary.

- [ ] **F1 - Local commit/push gate tiers** ([#52](https://github.com/dzackgarza/ai-review-ci/issues/52))
  - Behavior: remove duplicate heavy work between commit and push gates while preserving a real correctness gate.
  - Acceptance: commit gate remains fast and meaningful; push gate runs the broader proof stack once; no boundary is replaced by smoke-only proof.
  - Evidence: pending justfile diffs and gate-boundary tests.

- [ ] **W1 - PR-diff gate vs ambient audit** ([#53](https://github.com/dzackgarza/ai-review-ci/issues/53))
  - Behavior: PR checks block issues introduced or touched by the PR while ambient audits track full-repo debt separately.
  - Acceptance: pre-existing unrelated debt does not block an unrelated PR, but remains visible through ambient issue/report surfaces.
  - Evidence: pending fixture repo or test harness showing changed-line and ambient cases.

- [ ] **W2 - Deterministic CI vs agent review** ([#54](https://github.com/dzackgarza/ai-review-ci/issues/54))
  - Behavior: deterministic tests/lints and agent-driven review runs have distinct triggers and status semantics.
  - Acceptance: routine commits do not trigger unnecessary model-review churn, and requested PR reviews remain auditable.
  - Evidence: pending workflow diffs and trigger tests or dry-run artifacts.

- [ ] **I1 - Deferred debt tracking without quarantine** ([#55](https://github.com/dzackgarza/ai-review-ci/issues/55))
  - Behavior: repo-wide debt is tracked as issue-linked ambient work rather than hidden behind suppressions, broad baselines, or non-proof labels.
  - Acceptance: new/changed debt can still block PRs; existing ambient debt remains scheduled and reviewable; no checker is silenced as a local fix.
  - Evidence: pending debt-report fixture and issue-linking proof.

## Automated Gates

This PR remains draft until every checklist item has commit/evidence anchors, gate-tier fixtures prove the separated boundaries, review residue is resolved or moved to a separate debt issue, and GitHub checks pass.
