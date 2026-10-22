# ai-review-ci

`ai-review-ci` owns deterministic quality control for the repositories it governs.
It supplies fast local syntax checks and separate, nonblocking CI diagnostics. A stabilized release may additionally opt into PR review and branch protection.

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

For Sage, the reusable workflow runs `test-ci` inside
`ghcr.io/dzackgarza/sage:develop` (Python 3.14) and installs the consuming project
into its Sage interpreter. A caller supplying `setup_recipe` provisions its own
runtime instead. Sage `ambient` runs whole-tree Semgrep on the Ubuntu runner and
requires no Sage installation.

A Sage repository's `tests/acceptance/` suite runs in neither `test-push` nor `test-ci`.
It runs on every push in the reusable `.github/workflows/_acceptance.yml`, each file
sharded across hosted-runner jobs; its header shows the caller workflow. The doctor
fails a repository that has `tests/acceptance/` and no `.github/workflows/acceptance.yml`
calling it.

The default installer writes a root justfile, a push-triggered
development.yml workflow, an optional scheduled ambient.yml workflow, and
the CI scanner configuration. The default does not install a pull-request
review workflow, PR policy template or branch protection.

Only an explicit --phase stabilized installs those release-era controls.
The caller must decide to freeze a baseline and address existing quality
debt before adopting that phase.

Existing repository-owned files are not overwritten.
Use `--skip-scaffold` when a repository already has a root `justfile`.

For a new repository on the `bun-python` profile, especially one with a Tauri crate, read
[RUST-TAURI-SETUP.md](RUST-TAURI-SETUP.md) first: it lists every layout, script, installer
and CI-tier expectation the gates enforce, in the order that lands the first CI run green.

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

The doctor checks the development workflow and delegation without requiring branch protection or label alignment. Stabilized installations retain the stricter release checks.

## Global Git hooks

Install the hooks once:

```bash
just install-global-git-hooks
```

The hooks run the target repository's delegated recipes.
They do not use a target-specific local copy of the QC implementation.

The tiers are:

- test-commit: validate staged Python, JSON and TOML syntax; test-push: validate
  outgoing committed changes only,
  with no type checker, formatter, external dependency installation, test suite,
  code-style scanner, or performance restriction. Lean, Sage, Rust and Bun source
  is not subjected to a compile or type gate locally.
- test-ci: run the complete project test suite and individual correctness and
  code-quality checks on CI; retain each result as a JSON record, individual
  log, and GitHub job summary. Recognized test failures and source-location
  diagnostics receive stable finding IDs in results.json; unrecognized tool
  output remains a check-level failure linked to its full log. A branch-scoped
  prior CI snapshot is cached
  to produce burndown.json with newly failing, persistent, resolved, and
  currently open check IDs. A missing baseline is explicitly reported as
  unavailable, not treated as zero failures. In development the checks do not
  prevent publication when they fail; they remain failures in the report.
- ambient: scheduled full-tree maintenance diagnostics, also recorded rather
  than block publication.

During implementation, use narrowly targeted tests for the active capability.
Complete suites are CI work. Refactoring, typing, optimization, deduplication
and style cleanup are later roadmap phases, executed by fresh agents rather
than interrupting implementation.

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

The policy index lives in
[`automated-reviews`](https://github.com/dzackgarza/automated-reviews).

## Development

Create focused commits. The Git hooks run the applicable QC tier.
Use targeted tests only during iteration.

The central recipes must inspect the caller repository passed with `-d .`.
Tests for a recipe must use a real temporary caller repository.
