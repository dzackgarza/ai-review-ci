## Implementation PR — own QC/enforcement skills here; fix inverted policy-index sync (#163)

Closes #163 (epic #63). Decision-grounding doctrine tracked in #164 (blocked-by #163) — referenced, not closed here.

`ai-review-ci` is the source of truth for the integration-time enforcement skills it applies;
`~/ai` is a downstream install target. Previously only `policy-index` was pinned and it was
vendored *from* `~/ai` — backwards, since `ai-review-ci` owns it. This PR inverts that and
generalizes the model.

## Boundary (by enforcement phase, not origin)

- **owned** — this repo's integration-time enforcement surface. Authored under `skills/<name>/`,
  built into `reviews/vendor/`, published into `~/ai`. Origin-independent: the Brooks-Lint
  composites stay owned even though byte-identical to `hyhmrright/brooks-lint`.
- **consumed** — pre-/during-writing advisory guidance `~/ai` owns (`test-guidelines`,
  `tool-provisioning-and-environment-hygiene`). Vendored for the reviewer prompt only;
  refreshed from upstream, never authored or published here.

`reviews/vendor/MANIFEST.toml` classifies every vendored entry.

## Implemented behavior

- **Owned source dir `skills/`** — ten owned enforcement skills authored here and built into
  `reviews/vendor/` byte-for-byte (reviewer bundle unchanged): `policy-index` (nested +
  sha256 `VENDOR.toml`), `anti-slop`, `reviewing-llm-code`, `fixing-slop`,
  `bespoke-software-policy`, and the composites `common`, `source-coverage`, `decay-risks`,
  `ci-sweep-protocol`, `pr-review-guide` (flat).
- **Owned enforced git integration workflow** — new `git-integration-workflow` skill
  (issue-tree → draft PR → TDD → mark-ready → trigger review → disposition → merge), migrated
  faithfully from `git-guidelines`' enforcement sections; references the already-owned
  `reviewing-llm-code`/`anti-slop`/`policy-index` instead of duplicating. Agent-facing only:
  published to `~/ai`, not in the reviewer bundle.
- **Build** — `just vendor-owned-skills` (`build-vendor-skills.py`) rebuilds owned skills from
  `skills/` per their MANIFEST `vendor_layout` (nested/flat/absent). Replaces the old
  `sync-policy-index` step that pulled from `~/ai`.
- **Publish** — `just publish-skills <hub>` (`publish-skills.py`) installs the eleven owned
  skills into `<hub>/opencode/skills/`; idempotent; skips consumed + repo-local skills.
- **Consumed refresh** — `just refresh-consumed-skills <source> [ref]`
  (`refresh-consumed-skills.py`) pulls each consumed doc from its upstream checkout at a pinned
  ref (`git show <ref>:<path>`); refreshed `test-guidelines`/`tool-provisioning` from `~/ai`.
- **Docs** — AGENTS.md and both PR-template copies describe the owned-vs-consumed model and
  point at the drift test.

## Deliverables (from the plan)

- **D1 owned-skill manifest** — done (`reviews/vendor/MANIFEST.toml`).
- **D2 install/publish mechanism** — done (`skills/` source + `publish-skills`).
- **D3 versioning/update** — done both directions (build owned→vendor, publish owned→`~/ai`,
  refresh upstream→vendor).
- **git-guidelines split** — enforcement half owned here (`git-integration-workflow`); advisory
  half (edit hygiene, commit-message format, auth, repo-management) stays in `~/ai`.

## Evidence

- `tests/test_vendor_skills.py` — every owned skill rebuilds byte-identical (drift-capable both
  directions, proven); MANIFEST partitions every vendored doc; published-only skills leave no
  vendor artifact.
- `tests/test_publish_skills.py` — only owned skills publish; byte-faithful; idempotent;
  repo-local skills (e.g. `quality-control`) excluded.
- `tests/test_refresh_consumed_skills.py` — refresh pulls upstream content, is idempotent, and
  fails loud on bad source / missing path.
- `tests/test_policy_index.py` — vendored `policy-index` is a faithful sha256-pinned build of
  its `skills/` source.
- Full gate: `just test` (251 passed) and `just test-ci` green on every pushed commit.

## Required cross-repo follow-ups (cannot live in an ai-review-ci PR)

- Remove the migrated enforcement sections from `~/ai`'s `git-guidelines` to end duplication.
- Move the `extract_unresolved_issues` tool from `~/ai/.../git-guidelines/scripts` into this repo.
- Run `just publish-skills ~/ai` (deliberate operator action) to install the owned skills; not
  run in this PR.
