## Implementation PR — own QC/enforcement skills here; fix inverted policy-index sync (#163)

Closes #163. Refs #63, #164, and #178.

`ai-review-ci` is the source of truth for integration-time QC/enforcement skills.
`~/ai` is an install target, not the upstream source for those enforced policies.

## Boundary

- **Owned enforcement surface** — authored in this checkout under `skills/<name>/`.
- **Install target** — `just install-skills` symlinks the repo-owned skills into
  `$AI_SKILLS_DIR`.
- **Reviewer bundle** — review manifests reference `../skills/policy-index/...`
  directly; there is no `reviews/vendor` policy copy to sync or rebuild.
- **External advisory skills** — skills not owned here are named as external skills,
  not linked through machine-local `file://` paths.

## Implemented behavior

- Reconciles the PR with the current `origin/main` ownership model: `skills/` is the
  canonical enforcement source and the stale `reviews/vendor` build/refresh/publish
  machinery is removed.
- Adds `skills/git-integration-workflow` for the GitHub-boundary workflow: issue tree,
  draft PR, TDD proof, ready-for-review, automated review trigger, feedback disposition,
  and merge gates.
- Keeps review judgment and policy catalogs centralized by routing to repo-owned
  `policy-index`, `anti-slop`, `reviewing-llm-code`, and `test-guidelines` instead of
  duplicating their contents in the git integration skill.
- Adds compatibility references for the old `reviewing-llm-code` red-flag filenames that
  point to the canonical `policy-index` catalogs.
- Fixes broken machine-local skill references and stale vendor references in the PR
  template and skill documentation.

## Deliverables

- **D1 ownership inventory** — satisfied by the repo-owned `skills/` directory plus direct
  review-manifest references to `skills/policy-index`; the duplicate vendored inventory
  is intentionally removed.
- **D2 install mechanism** — satisfied by `just install-skills`, which installs every
  repo-owned skill into `$AI_SKILLS_DIR`.
- **D3 update/versioning model** — no vendored policy copy remains to pin; policy freshness
  is the checked-out git source itself, and link integrity is now tested.
- **Git integration split** — the enforced GitHub integration workflow is owned here as
  `skills/git-integration-workflow`; during-writing git hygiene remains in the external
  `git-guidelines` skill.

## Evidence

- `python -m pytest tests/test_skill_references.py -q` — passed.
- `just test-ci` — passed after final reconciliation: 243 tests in the commit-tier
  pytest leg, 243 tests in the coverage leg, 100% diff coverage for changed
  `policy_index.py` lines, and deptry/import-linter/bypass checks passed.
