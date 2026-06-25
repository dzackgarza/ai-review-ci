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

- [x] **F1 - Local commit/push gate tiers** ([#52](https://github.com/dzackgarza/ai-review-ci/issues/52))
  - Behavior: the `test` (commit) and `test-ci` (push) tiers are now expressed as a real, self-applied profile. New `justfiles/qc-tooling.just` (the profile for repos whose product *is* QC infra) reuses python.just's correctness subrecipes via a single deduped invocation: `test` = project-shape + normalize + syntax + mypy + pytest; `test-ci` = + coverage + diff-cover + deptry + import-linter. No slop/style/duplication self-application.
  - Evidence: `justfiles/qc-tooling.just`; root `justfile` `test`/`test-ci` now delegate to it; `just -f justfiles/qc-tooling.just --list` + dry-run verified locally.

- [ ] **W0 - Standardized, shareable, self-applied QC workflow** (dogfooding gap)
  - Behavior: this repo runs no pytest in CI today (only CodeQL + GitGuardian). `_qc.yml` (reusable, `workflow_call`, `tier` input) runs the consuming repo's own `just test`/`test-ci`; `ci.yml` wires it onto ai-review-ci itself on push/PR. Same reusable shape the installer will write downstream.
  - Evidence: `.github/workflows/_qc.yml`, `.github/workflows/ci.yml`; YAML validated locally; **the workflow self-verifies once it runs in CI** (3.14-final, where pydantic builds, so it also exercises the package-importing tests that can't run on the local rc2 container).

- [ ] **W1 - PR-diff gate vs ambient audit** ([#53](https://github.com/dzackgarza/ai-review-ci/issues/53))
  - Behavior: PR checks block issues introduced or touched by the PR while ambient audits track full-repo debt separately.
  - Acceptance: pre-existing unrelated debt does not block an unrelated PR, but remains visible through ambient issue/report surfaces.
  - Evidence: pending fixture repo or test harness showing changed-line and ambient cases.

- [x] **W2 - Deterministic CI vs agent review** ([#54](https://github.com/dzackgarza/ai-review-ci/issues/54))
  - Behavior: deterministic QC (`_qc.yml`, runs `just test`/`test-ci`) is now a distinct workflow from agent review (`_review.yml`) — separate files, separate triggers, separate status. Deterministic checks run on every push/PR; agent review keeps its own (cron/dispatch/diff) triggers.
  - Evidence: `_qc.yml` + `ci.yml` are deterministic-only and never invoke `_review.yml`.

- [ ] **I1 - Deferred debt tracking without quarantine** ([#55](https://github.com/dzackgarza/ai-review-ci/issues/55))
  - Behavior: repo-wide debt is tracked as issue-linked ambient work rather than hidden behind suppressions, broad baselines, or non-proof labels.
  - Acceptance: new/changed debt can still block PRs; existing ambient debt remains scheduled and reviewable; no checker is silenced as a local fix.
  - Evidence: pending debt-report fixture and issue-linking proof.

## Automated Gates

This PR remains draft until every checklist item has commit/evidence anchors, gate-tier fixtures prove the separated boundaries, review residue is resolved or moved to a separate debt issue, and GitHub checks pass.
