# ai-review-ci

`ai-review-ci` owns deterministic quality control for the repositories it governs.
It supplies QC recipes, profile checks, Git hooks, branch protection, and repository diagnostics.

[`automated-reviews`](https://github.com/dzackgarza/automated-reviews) owns all LLM review behavior.
It publishes the review workflows, prompts, schemas, runner, delivery code, policy material, and model metadata.
This package consumes those published workflows during installation.

Read [CONTRIBUTING.md](./CONTRIBUTING.md) before you change a rule or open a pull request.

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

The installer writes these repository-owned files:

- a root `justfile` with the QC contract;
- `.github/workflows/review-pr.yml`;
- `.github/workflows/review-slop.yml`;
- `.github/pull_request_template.md`;
- `.aislop/config.yml`.

The review jobs call reusable workflows from `automated-reviews`.
The deterministic jobs call reusable workflows from `ai-review-ci`.

Existing repository-owned files are not overwritten.
Use `--skip-scaffold` when a repository already has a root `justfile`.

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

The doctor checks the declared profile, workflow references, required gates, labels, branch protection, and QC delegation.

## Global Git hooks

Install the hooks once:

```bash
just install-global-git-hooks
```

The hooks run the target repository's delegated recipes.
They do not use a target-specific local copy of the QC implementation.

The tiers are:

- `test-commit` for staged changes;
- `test-push` for repository tests and dependency checks;
- `test-ci` for the complete remote acceptance tier.

Do not run a complete suite by hand when a commit or push will run the required tier.

## Canonical operations

Install or update the label taxonomy:

```bash
ai-review-ci install-labels --repo owner/repo
```

Apply required branch protection:

```bash
ai-review-ci protect-branch --repo owner/repo --branch main --profile python
```

Inspect deterministic policy tripwires:

```bash
ai-review-ci tripwire-index
ai-review-ci check-tripwire-index
```

Run LLM reviews, replay frozen review environments, or change the active model with `automated-reviews`.

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

Review resources and reusable LLM workflows live in
[`automated-reviews`](https://github.com/dzackgarza/automated-reviews).

## Development

Create focused commits. The Git hooks run the applicable QC tier.
Use targeted tests only during iteration.

The central recipes must inspect the caller repository passed with `-d .`.
Tests for a recipe must use a real temporary caller repository.
