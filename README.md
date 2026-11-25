# ai-review-ci

`ai-review-ci` owns deterministic quality control for the repositories it governs.
It supplies fast local syntax checks and separate CI diagnostics.
Development CI blocks on correctness failures and retains quality-debt failures as nonblocking evidence.
A stabilized release may additionally enforce all findings through PR review and branch protection.

Development is the default phase; see [CONTRIBUTING.md](./CONTRIBUTING.md) for the later stabilization policy.

## Install into a repository

Run this command from the target repository:

```bash
uvx --from git+https://github.com/dzackgarza/ai-review-ci \
  ai-review-ci install \
  --repo owner/repo \
  --branch main \
  --profile python
```

Supported profiles are `python`, `bun`, `bun-playwright`, `bun-python`, `docs-and-configs`, `rust`, and `sage`.

For Sage, the reusable workflow runs `test-ci` inside `ghcr.io/dzackgarza/sage:develop` (Python 3.14) and installs the consuming project into its Sage interpreter.
A caller's `setup_recipe` runs inside that container, with bun and node installed, and uses the image's Sage.
Sage `ambient` runs whole-tree Semgrep on the Ubuntu runner and requires no Sage installation.

A Sage repository's `tests/acceptance/` suite runs in neither `test-push` nor `test-ci`. It runs on every push in the reusable `.github/workflows/_acceptance.yml`, each file sharded across hosted-runner jobs; its header shows the caller workflow.
The doctor fails a repository that has `tests/acceptance/` and no `.github/workflows/acceptance.yml` calling it.

The default installer writes a root justfile, a push-triggered development.yml workflow, an optional scheduled ambient.yml workflow, and the CI scanner configuration.
The default does not install a pull-request review workflow, PR policy template or branch protection.

Only an explicit --phase stabilized installs those release-era controls.
The caller must decide to freeze a baseline and address existing quality debt before adopting that phase.

Existing repository-owned files are not overwritten.
Use `--skip-scaffold` when a repository already has a root `justfile`.

For a new repository on the `bun-python` profile, especially one with a Tauri crate, read [RUST-TAURI-SETUP.md](RUST-TAURI-SETUP.md) first: it lists every layout, script, installer and CI-tier expectation the gates enforce, in the order that lands the first CI run green.

## QC contract

Each governed repository declares its profile and release reference in the root `justfile`:

```justfile
ai_review_ci_schema_version := "1"
ai_review_ci_profile := "python"
ai_review_ci_ref := "main"
ai_review_ci_release_channel := "main"
ai_review_ci_workflow_template_version := "1"
ai_review_ci_local_delegation := "global-justfile"
ai_review_ci_default_branch := "main"

test-commit:
    @just -f ~/ai-review-ci/justfiles/python.just -d . test-commit

test-push:
    @just -f ~/ai-review-ci/justfiles/python.just -d . test-push

test-ci:
    @just -f ~/ai-review-ci/justfiles/python.just -d . test-ci
```

Run `doctor` to inspect this contract:

```bash
ai-review-ci doctor --target .
ai-review-ci doctor --target . --json
```

The doctor checks the development workflow and delegation without requiring branch protection or label alignment.
Stabilized installations retain the stricter release checks.

## Global Git hooks

Install the hooks once:

```bash
just install-global-hooks
```

The pre-commit hook runs exactly the repository's `just test-commit`, and the pre-push hook runs exactly its `just test-push` for QC. Every central profile's `test-commit` and `test-push` call the private `_local-check` recipe in `justfiles/shared.just`, which runs `scripts/local-check.py` to parse the candidate Git index at commit and every outgoing ref at push.
At push, the hook sets `AI_REVIEW_CI_PRE_PUSH_REMOTE` and passes Git's ref list on stdin for that recipe.

Global hooks also preserve Git LFS behavior.
When Git LFS is installed, the pre-push hook gives the unchanged ref list and original remote arguments to `git lfs pre-push` after QC succeeds (or immediately in a QC-exempt repo).
Failure in either check prevents publishing refs.
The global post-checkout, post-commit, and post-merge hooks forward Git's arguments to their native LFS counterparts, including in QC-exempt repos.
If LFS filters are configured but the executable is missing, the hook reports the broken installation rather than silently skipping LFS.

On machines using LFS, configure its filters with `git lfs install --skip-repo` so LFS does not replace the managed hooks.
Existing global installations should rerun `just install-global-hooks` to install the three post hooks.

A project adds its own cheap checks as extra lines in its root `test-commit` and `test-push` recipes, after the delegated line.
There is no side-channel script.
The hooks have no tool installation step.
Full suites and broad diagnostics remain in CI.

### Hook timing

Every run of the global `pre-commit` and `pre-push` hooks appends one JSON line to `<git-common-dir>/ai-review-ci/timing/hooks.jsonl` in the repository that ran it.
A commit runs the pre-commit checks and a push runs the pre-push checks, so the record's duration is the time those checks took.
Timing is unconditional: repositories the gate exempts still record how long the check they ran took, and linked worktrees write into the shared common directory.
No threshold is applied -- the log holds raw measurements.

At exit each hook also prints the duration to standard error, for example `pre-commit: checks took 2.3s`, so a commit or push shows how long its checks took.

Each record has:

| Field | Meaning |
| --- | --- |
| `schema` | record format version |
| `hook` | `pre-commit` or `pre-push` |
| `started_at` | hook start, ISO 8601 UTC |
| `duration_ms` | wall-clock hook duration, milliseconds |
| `exit_code` | hook exit status |
| `worktree` | absolute worktree the hook ran in, or null outside one |

The log lives under `.git/`, so Git never tracks it.
`repo-hooks/hook-timing.sh` does the timing; `scripts/hook-timing.py` writes the record.

The tiers are:

- test-commit: validate staged Python, JSON and TOML syntax; test-push: validate outgoing committed changes only, with no type checker, formatter, external dependency installation, test suite, code-style scanner, or performance restriction.
  Lean, Sage, Rust and Bun source is not subjected to a compile or type gate locally.

- test-ci: run the complete project test suite and individual correctness and code-quality checks on CI; retain each result as a JSON record, individual log, and GitHub job summary.
  Recognized test failures and source-location diagnostics receive stable finding IDs in results.json; unrecognized tool output remains a check-level failure linked to its full log.
  A branch-scoped prior CI snapshot is cached to produce burndown.json with newly failing, persistent, resolved, and currently open check IDs.
  A missing baseline is explicitly reported as unavailable, not treated as zero failures.
  In development, correctness failures block publication.
  Quality-debt failures remain failures in the report without blocking publication.

- ambient: scheduled full-tree maintenance diagnostics, also recorded rather than block publication.

During implementation, use narrowly targeted tests for the active capability.
Complete suites are CI work.
Refactoring, typing, optimization, deduplication and style cleanup are later roadmap phases, executed by fresh agents rather than interrupting implementation.

## Canonical operations

Install or update the label taxonomy:

```bash
ai-review-ci install-labels --repo owner/repo
```

Only after an explicit stabilized-phase baseline, apply required branch protection:

```bash
ai-review-ci protect-branch --repo owner/repo --branch main --profile python
```

Inspect deterministic policy tripwires:

```bash
ai-review-ci tripwire-index
ai-review-ci check-tripwire-index
```

## Repository layout

```text
.github/workflows/_qc.yml       reusable QC workflow
.github/workflows/_gates.yml    reusable deterministic PR gates
ci/runner.just                  workflow-side deterministic commands
justfiles/                      central profile recipes
scaffolds/                      root justfiles installed into consumers
src/ai_review_ci/               installer, doctor, gates, labels, and tripwires
tool-configs/                   central deterministic tool configuration
tool-artifacts/                 scripts and rules used by QC recipes
```

The policy index lives in [`automated-reviews`](https://github.com/dzackgarza/automated-reviews).

## Development

Create focused commits.
The Git hooks run the applicable QC tier.
Use targeted tests only during iteration.

The central recipes must inspect the caller repository passed with `-d .`. Tests for a recipe must use a real temporary caller repository.
