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

Issue #52 establishes local gate tiers. #53 separates PR diff gates from ambient repo audits. #54 separates agent-driven review from deterministic CI. #55 defines non-blocking debt tracking without quarantine. #56 closes only when these pieces produce one coherent signal model.

## Milestone Tree

- [x] **M1 - Signal separation and gate tiers** ([#56](https://github.com/dzackgarza/ai-review-ci/issues/56))
  - Complete when: commit, push, PR, ambient, agent-review, and debt signals each have a defined owner, trigger, output, and proof boundary.
  - Signal model — each tier has a distinct trigger, owner, and proof boundary, self-applied here and shareable downstream:
    - **commit** = `just test` — owned by the local **pre-commit hook** (fast correctness). Not a CI job.
    - **push/CI** = `just test-ci` — owned by the **pre-push hook** locally and **`ci.yml`** remotely (a push/PR is the push boundary). Deterministic, diff-aware (`_diff-cover`).
    - **ambient** = `just ambient` — owned by scheduled **`ambient.yml`** (full-repo debt, non-blocking).
    - **agent-review** = `_review.yml` (separate triggers/status).
    - **debt** = surfaced by the ambient run + issue tracker; no baseline/quarantine.

- [x] **F1 - Local commit/push gate tiers** ([#52](https://github.com/dzackgarza/ai-review-ci/issues/52))
  - Behavior: the `test` (commit) and `test-ci` (push) tiers are now expressed as a real, self-applied profile. New `justfiles/qc-tooling.just` (the profile for repos whose product *is* QC infra) reuses python.just's correctness subrecipes via a single deduped invocation: `test` = project-shape + normalize + syntax + mypy + pytest; `test-ci` = + coverage + diff-cover + deptry + import-linter. No slop/style/duplication self-application.
  - Evidence: `justfiles/qc-tooling.just`; root `justfile` `test`/`test-ci` now delegate to it; `just -f justfiles/qc-tooling.just --list` + dry-run verified locally.

- [x] **W0 - Standardized, shareable, self-applied QC workflow** (dogfooding gap)
  - Behavior: this repo ran no pytest in CI (only CodeQL + GitGuardian). `_qc.yml` (reusable, `workflow_call`, `tier` input) runs the consuming repo's own `just test`/`test-ci`/`ambient`; `ci.yml` wires it onto ai-review-ci itself on push/PR. Same reusable shape the installer will write downstream.
  - Trigger boundary: a push/PR is the *push* boundary, so CI runs the PUSH/CI tier (`just test-ci`) only — the remote mirror of the pre-push hook. The COMMIT tier (`just test`) stays the local pre-commit hook's gate (nothing is committed in CI, and `test-ci` is a superset of `test`).
  - Evidence: the `test-ci / qc` gate is **green on PR #99** (full 168-test suite on CI's Python 3.14.6 — which also retroactively validates the package-importing tests unrunnable on the local rc2 container). Four dogfooding-surfaced gaps fixed en route: dropped the downstream preflight, installed ripgrep + bun, and gave `_diff-cover` a valid `origin/<base>` compare-branch.

- [x] **W1 - PR-diff gate vs ambient audit** ([#53](https://github.com/dzackgarza/ai-review-ci/issues/53))
  - Behavior: the PR/push gate (`ci.yml` → `test`/`test-ci`) is deterministic and diff-aware (`_diff-cover` scores only changed lines against the PR base); the full-repo deferred-debt audit (complexity, dead code, duplication) runs in a separate **scheduled** `ambient.yml`, never on `pull_request`.
  - Acceptance: pre-existing unrelated repo-wide debt cannot block an unrelated PR (it is not in the PR gate), but stays visible/reviewable through the scheduled ambient run.
  - Evidence: `.github/workflows/ambient.yml` (schedule + dispatch only), `qc-tooling.just` `ambient` recipe (`_ambient-python-debt`), `_qc.yml` `tier: ambient`; trigger separation verified — `ci.yml` has no `schedule`, `ambient.yml` has no `pull_request`.

- [x] **W2 - Deterministic CI vs agent review** ([#54](https://github.com/dzackgarza/ai-review-ci/issues/54))
  - Behavior: deterministic QC (`_qc.yml`, runs `just test`/`test-ci`) is now a distinct workflow from agent review (`_review.yml`) — separate files, separate triggers, separate status. Deterministic checks run on every push/PR; agent review keeps its own (cron/dispatch/diff) triggers.
  - Evidence: `_qc.yml` + `ci.yml` are deterministic-only and never invoke `_review.yml`.

- [x] **I1 - Deferred debt tracking without quarantine** ([#55](https://github.com/dzackgarza/ai-review-ci/issues/55))
  - Behavior: deferred repo-wide debt is surfaced by the scheduled `ambient.yml` run (reviewable in Actions, tracked as issues) instead of a baseline/quarantine file. Deliberately **no** baseline file is introduced — the epic excludes "broad baselines" and the repo's `_no-bypass`/no-suppression doctrine forbids silencing checkers.
  - Acceptance: new/changed debt still blocks PRs (the deterministic diff gate fails on changed-code type/test/coverage regressions); existing ambient debt remains scheduled + reviewable via `ambient.yml`; no checker is silenced and no quarantine file is added.
  - Evidence: `ambient.yml` is the non-blocking debt surface; `git grep` shows no baseline/quarantine/`# noqa`-style suppression file added; PR gate (`ci.yml`) is independent of the ambient audit.
  - Scope note (resolves the #55-suggested-phases vs epic tension): #55's "baseline/quarantine file" suggestion is **declined** in favor of the epic's issue-linked, no-baseline model.

## Automated Gates

This PR remains draft until every checklist item has commit/evidence anchors, gate-tier fixtures prove the separated boundaries, review residue is resolved or moved to a separate debt issue, and GitHub checks pass.
