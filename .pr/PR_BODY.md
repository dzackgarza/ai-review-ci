## Implementation PR — own integration-time skills in `skills/` (#163)

Closes #163. Refs #63 and #164.

`ai-review-ci` is the source of truth for the integration-time skills and review/QC
doctrine it applies. The canonical surface is the repo-local `skills/` tree: each
top-level folder is a skill, and installation is `just install-skills`, which symlinks
those folders into `$AI_SKILLS_DIR`.

## Boundary

- **Owned here:** integration-time enforcement and review/QC doctrine under `skills/`.
  Policy lookup, review manifests, templates, and installed skill copies all read the
  repo-local `skills/` source.
- **Not used:** `reviews/vendor`, `VENDOR.toml`, skill manifests, or build/publish/refresh
  scripts. Those created a second source of truth after `origin/main` moved to direct
  `skills/` ownership.
- **New owned workflow:** `skills/git-integration-workflow/` owns the GitHub-boundary
  lifecycle: issue tree, draft PR, TDD, ready-for-review, review trigger, feedback
  disposition, and merge.

## Implemented behavior

- Preserves the current `origin/main` model where reviewer manifests inline
  `../skills/...` paths directly and `src/ai_review_ci/policy_index.py` loads
  `skills/policy-index`.
- Removes the stale PR #165 vendor-manifest implementation path from the reconciled
  branch: no `reviews/vendor/MANIFEST.toml`, no `vendor-owned-skills`, no
  `publish-skills`, no `refresh-consumed-skills`.
- Adds `git-integration-workflow` as a normal top-level skill folder, so it installs by
  the same `just install-skills` mechanism as every other skill.
- Keeps PR templates and AGENTS guidance pointed at canonical `skills/policy-index`
  records rather than vendored or globally installed copies.

## Policy Alignment Gate

Touched/risked policies:

- `POLICY.GLOBAL_QC_AUTHORITY` — this change preserves central ownership of review/QC
  doctrine in `ai-review-ci`.
- `POLICY.NO_QC_SILENCING` — no validator rule, threshold, suppressions, or QC target
  exclusions are weakened to make the branch pass.
- `POLICY.NO_ADMIN_COMPLETION` — the PR is not complete on comments or tracker updates;
  it requires current tests/gates and pushed code.
- `POLICY.NO_DYNAMIC_ARTIFACTS` — skill content remains tracked source under `skills/`,
  not generated from hidden runtime strings.
- `POLICY.FAIL_OPEN` / `POLICY.NO_PARTIAL_SUCCESS` — install and policy-loading paths must
  fail loudly when required files or directories are absent.

No Invalid local fix is introduced: no fallback, runtime default, optional core-state,
swallowed error, partial-success path, local QC override, or empty/falsy placeholder is
added to silence the ownership problem.

Tier 1 statement: this PR touches review/QC workflow and policy surfaces. It does not
weaken a `POLICY.*` record, convert a true finding into scanner silence, or add a local
exception to global QC. Any policy semantics remain in canonical `skills/policy-index/`.

## Evidence

- `tests/test_policy_index.py` proves runtime policy lookup resolves the repo-local
  `skills/policy-index` source and that review manifests no longer reference `vendor/`.
- `tests/test_justfiles.py` covers the `just install-skills` recipe surface.
- `PATH=/home/zack/.local/bin:$PATH uv run --python 3.14 pytest -s tests/test_policy_index.py -q`
  — 8 passed.
- `PATH=/home/zack/.local/bin:$PATH uv run --python 3.14 pytest -s tests/test_justfiles.py::test_install_global_hooks_requires_env_only_inside_recipe tests/test_justfiles.py::test_scaffold_bare_just_entrypoint_survives_working_directory_binding --tb=short -q`
  — 11 passed.
- Ruff and mypy were rerun across all Python files after the branch was reconciled:
  ruff passed, ruff format was stable under the final `just test` attempt, and mypy
  reported no issues in 42 source files.
- `git diff --check && git diff --cached --check` passed.
- `PATH=/home/zack/.local/bin:$PATH just test` is not green locally: ruff, Python syntax,
  and mypy passed, then the pytest step reported `collected 0 items` and failed during
  pytest capture cleanup with `FileNotFoundError` before running the suite. This is not
  counted as completion evidence.
