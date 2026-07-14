# ai-review-ci

## Doctrine

The durable doctrine for global QC and review behavior lives in the [Global QC and Review Doctrine](https://github.com/dzackgarza/ai-review-ci/wiki/Global-QC-and-Review-Doctrine) wiki page.
Use it when changing gates, scaffolds, review runners, reviewer state, or downstream enforcement contracts.

Centrally-managed, OpenCode-powered review CI. Target repositories carry three thin trigger workflows plus explicit `ai_review_ci_*` contract variables in their root `justfile`; everything else — the reusable workflow, the review runner, the validator, the reviewer home template, the prompt corpus — lives here and is cloned inside the CI runner at execution time.
Updating this repo updates every consumer on their next run.

Two review types:

- **General review** — structural code quality audit: architectural decay, dead code, test quality, dependency mismanagement, semantic regressions.
- **Slop review** — AI-generated-code audit: bridge-burning violations, runtime control-flow defects, test/text antipatterns, validation-evasion constructs, defaults/fallbacks/mocks/skips.

Each type runs in two scopes: **repo** (full-repository sweep) and **diff** (PR review focused on the diff against the base branch).

## Installing the skills

This repo is the canonical home of the skills under `skills/` — each top-level directory there is one skill.
Install them by cloning this repo and symlinking every skill into your skills directory:

```bash
# In ~/.envrc (direnv): point at your harness's skills directory
export AI_SKILLS_DIR="$HOME/ai/opencode/skills"

cd /path/to/clone/of/ai-review-ci
just install-skills
```

Each `skills/<name>` becomes a symlink `$AI_SKILLS_DIR/<name>` pointing into the clone, so `git pull` updates every installed skill in place.
The recipe refuses to replace a non-symlink (a real directory already at that name) and is idempotent otherwise.

## Installing into a repo

```bash
cd /path/to/your/repo
uvx --from git+https://github.com/dzackgarza/ai-review-ci ai-review-ci install --repo owner/repo --branch main --profile bun-playwright
```

Pass `--profile <profile>` with one of `python`, `bun`, `bun-playwright`, `bun-python`, `rust`, or `sage`. The profile is the enforced project bin: it selects the required project shape, the central justfile delegation target, the installed PR gates, and the branch-protection checks.

This installs the complete QC enforcement surface: it writes the root `justfile` contract, writes the three trigger workflows, and applies branch protection requiring the installed PR gate jobs for the declared profile.

| File | Triggers |
| --- | --- |
| `review-general.yml` | weekly cron, push to main, manual dispatch |
| `review-slop.yml` | weekly cron, push to main, manual dispatch |
| `review-pr.yml` | every pull request (both types, diff-scoped) |

The three files are minimally-correct base configuration and become **repo-owned** the moment they are installed: edit crons, branches, thresholds, and the upstream `@ref` directly in the YAML — that is the whole downstream surface.
The installer never overwrites them.
All review *behavior* lives upstream and needs no reinstall: every run clones this repo fresh.
Branch protection is not optional setup; without it the workflows can run without enforcing the merge gate.

What an installed trigger looks like (`review-general.yml` — pure configuration pointing at the upstream reusable workflow):

```yaml
name: General Review
on:
  workflow_dispatch:
  schedule:
    - cron: '0 8 * * 1'
  push:
    branches: [main]
jobs:
  general:
    uses: dzackgarza/ai-review-ci/.github/workflows/_review.yml@main
    permissions:
      contents: read
      security-events: write
      actions: read
      pull-requests: write
    with:
      report_type: general
      scope: repo
```

The canonical templates live in [`src/ai_review_ci/templates/`](src/ai_review_ci/templates/).

The reusable workflow also accepts three optional repo-owned configuration inputs:

- `advisory` (boolean, default `false`): advisory runs upload the full SARIF ledger snapshot but never let findings determine the workflow conclusion — the tier-1 enforcement step is skipped while every infrastructure step still fails loudly. Use this for a continuous, non-blocking stream of review reports on `main`; findings are then triaged as code scanning alerts (dismissed with reason, or fixed), and dispositions feed later reviewer context as do-not-re-raise instructions.
- `policy_paths` (string, default empty): newline-delimited repo-relative document paths inlined into the reviewer prompt in every scope (`#` comments and blank lines are skipped; a missing path fails the run). Use it to hand the reviewer a repo-local policy catalogue — style guides, terminology dictionaries, mathematical specifications — beyond the README/AGENTS docs that repo sweeps auto-collect.
- `focus_prompt` (string, default empty): short repo-specific instructions inlined into the reviewer prompt, for narrowing the review to particular concerns (for example, mathematical correctness against a named specification).
- `context_archive` (string, default empty): repo-relative path to a tar archive — the repo-assembled **review packet**. The runner explodes it into `.review-context/` inside the reviewer repo; a top-level `PROMPT.md` leads the inlined section, every other `*.md` document is inlined in sorted path order, and non-Markdown files are listed by path for the reviewer to read from disk. This is the extensible context surface: the consumer repo owns a recipe that assembles the packet (from tracked files, untracked vault documents, other repos — anything), and the archive itself is the only thing tracked.

Report schemas accept an honest empty report: `findings: []` is valid, and the substantive-finding requirement only rejects padding in non-empty reports. A reviewer that finds nothing must submit an empty report rather than invent debt.

Requirements in the target repo: GitHub code scanning enabled (free for public repos), GitHub CLI auth with permission to edit branch protection, the target branch named in `--branch`, and a repo shape that satisfies the declared `--profile`. LLM review jobs are signal-only process checks: they upload SARIF and post review threads, but they do not compute or fail on a health score.
The merge gate is deterministic QC plus evidence-backed resolution of reviewer-authored PR threads.

### QC justfile contract and doctor

Each installed target repo carries an executable QC contract in its repository-root `justfile`.
The `ai_review_ci_*` variables are the declaration surface that `doctor` evaluates, and the public recipes are the execution surface that `doctor` cross-checks:

```justfile
ai_review_ci_schema_version := "1"
ai_review_ci_profile := "bun-playwright"
ai_review_ci_ref := "main"
ai_review_ci_release_channel := "main"
ai_review_ci_workflow_template_version := "1"
ai_review_ci_local_delegation := "global-justfile"
ai_review_ci_default_branch := "main"

test:
    @just -f ~/ai-review-ci/justfiles/bun.just -d . test

test-ci:
    @just -f ~/ai-review-ci/justfiles/bun.just -d . test-ci

app-boot:
    @just -f ~/ai-review-ci/justfiles/bun.just -d . app-boot
```

`ai_review_ci_schema_version`, `ai_review_ci_profile`, `ai_review_ci_ref`, `ai_review_ci_release_channel`, `ai_review_ci_workflow_template_version`, `ai_review_ci_local_delegation`, and `ai_review_ci_default_branch` are required.
A repo declares its executable QC contract; there is no local opt-out of global QC. A repo with active findings is noncompliant — extra justfile variables do not suppress findings.

Inspect a target repo with:

```bash
uvx --from git+https://github.com/dzackgarza/ai-review-ci ai-review-ci version
uvx --from git+https://github.com/dzackgarza/ai-review-ci ai-review-ci doctor --target /path/to/repo --json
uvx --from git+https://github.com/dzackgarza/ai-review-ci ai-review-ci doctor-preflight --target /path/to/repo
uvx --from git+https://github.com/dzackgarza/ai-review-ci ai-review-ci doctor-schema
```

The doctor reports the tool and schema version, target root, origin remote, HEAD, justfile declaration hash, declared and effective profile, required and observed workflow refs, required and observed justfile delegation, branch-protection requirements and observations, canonical label-set alignment (missing, drifted, and case/spelling-variant labels against `data/labels.json`; extra repo-specific labels are allowed), profile proof requirements, findings, remediation commands, invalidation inputs, installation state, and dashboard `global_status`. Consumers should use `global_status` rather than re-infer status from workflow filenames.

Status mapping is fixed:

| Doctor observation | `installation_state` | Dashboard `global_status` |
| --- | --- | --- |
| justfile contract, workflows, delegation, profile proof, branch protection, and canonical label alignment satisfy the declared contract | `compliant` | `current` |
| installed workflow refs differ from the justfile contract's required ref | `outdated` | `stale` |
| justfile contract missing, required workflow missing, wrong profile, wrong delegation, missing `bun-playwright` app boot, missing branch-protection contexts, or canonical labels missing/drifted/present only as a case or spelling variant | `uninstalled` or `noncompliant` | `misconfigured` |
| branch protection or canonical label alignment cannot be verified from the target remote/API state | `unknown` | `unverifiable` |

Only `current` exits zero.
All other statuses fail the command and the `qc-doctor` PR gate.

Every public `just test` begins with `doctor-preflight`. It is the local, no-network subset of doctor: it requires a valid justfile contract and the declared profile's required project shape before normalization, type checking, or tests run. Composite project shapes are centrally defined profiles; `bun-python` requires both Python and Bun project evidence and delegates to both central gates. A preflight failure is project initialization work, not a code-quality finding and must not enter the QC triage routes.

## Installing QC Surfaces

Clone this repository once on the machine that should own the shared QC stack:

```bash
cd ~
git clone git@github.com:dzackgarza/ai-review-ci.git
cd ~/ai-review-ci
```

### Global Git hooks

Global hooks are user-level Git hooks.
The QC stack is two-tier: `pre-commit` runs `just test` (the commit gate — correctness and normalization only) and `pre-push` runs `just test-ci` (the push gate — the full style/slop/coverage stack on top of the commit gate).
The install recipe requires `GIT_GLOBAL_HOOKS_DIR` to name the explicit hooks directory, symlinks `global-hooks/pre-commit` and `global-hooks/pre-push` into that directory, and sets the user's global `core.hooksPath` to the same value:

```bash
cd ~/ai-review-ci
direnv allow
just install-global-hooks
```

Verify the active global hook path with:

```bash
git config --global core.hooksPath
```

### Repo-local Git hooks

Repo-local hooks are installed into one repository's `.git/hooks` directory.
They do not change global Git configuration:

```bash
cd ~/ai-review-ci
just install-repo-hooks /path/to/target/repo
```

Use this when a repository needs local hook files without changing the user's global hook path.

### Repo-local QC delegation

Target repositories should not copy QC configs, tool pins, or hook scripts.
Their local `justfile` should delegate the public `test` and `test-ci` recipes to the central justfile for the repository's enforced profile in `~/ai-review-ci`.

For new projects, install the tracked scaffold instead of hand-writing the delegation surface:

```bash
cd ~/ai-review-ci
# choose one enforced project profile for the target repository
just install-qc-scaffold python /path/to/new/repo
just install-qc-scaffold bun /path/to/new/repo
just install-qc-scaffold bun-playwright /path/to/new/repo
just install-qc-scaffold rust /path/to/new/repo
just install-qc-scaffold sage /path/to/new/repo
```

The recipe copies files from `scaffolds/<profile>/` and refuses to overwrite existing files.
Edit the tracked scaffold here when the standard project surface changes; do not copy sample snippets into downstream repos by hand.

The scaffold contents are intentionally small.
They install the repo-local command surface; the actual QC behavior remains global.

Python:

```justfile
test:
    @just -f ~/ai-review-ci/justfiles/python.just -d . test

test-ci:
    @just -f ~/ai-review-ci/justfiles/python.just -d . test-ci
```

TypeScript/Bun:

```justfile
test:
    @just -f ~/ai-review-ci/justfiles/bun.just -d . test

test-ci:
    @just -f ~/ai-review-ci/justfiles/bun.just -d . test-ci
```

TypeScript/Bun project with mandatory Playwright GUI proof:

```justfile
test:
    @just -f ~/ai-review-ci/justfiles/bun.just -d . test

test-ci:
    @just -f ~/ai-review-ci/justfiles/bun.just -d . test-ci

app-boot:
    @just -f ~/ai-review-ci/justfiles/bun.just -d . app-boot
```

`bun-playwright` repositories must keep `package.json`, `bun.lock` or `bun.lockb`, and the Playwright configuration at repository-root `playwright.config.ts`. The local justfile delegates the invocation to global QC; it must not call Playwright directly.

Rust:

```justfile
test:
    @just -f ~/ai-review-ci/justfiles/rust.just -d . test

test-ci:
    @just -f ~/ai-review-ci/justfiles/rust.just -d . test-ci
```

SageMath:

```justfile
test:
    @just -f ~/ai-review-ci/justfiles/sage.just -d . test

test-ci:
    @just -f ~/ai-review-ci/justfiles/sage.just -d . test-ci
```

Project-specific checks may be added only as private recipes composed after the global gate.
Generic linting, formatting, typechecking, coverage, complexity, copy-paste, slop detection, tool configs, and tool versions stay owned by this repository.

## Canonical Operations

### Running repo-wide reviews

- **Automatic:** every push to the default branch runs both review types; weekly crons re-run them on schedule.
- **On demand:** `gh workflow run "General Review"` or `gh workflow run "Slop Review"` (or the Actions UI).

### Finding all outstanding reported issues

The single ledger is **GitHub code scanning alerts**, under tool names `ai-review/general` and `ai-review/slop`:

- Agent/CLI, formatted (the same context document CI reviewers receive — open / dismissed-with-reason / fixed, each with `path:line` and alert URL):

  ```bash
  uvx --from git+https://github.com/dzackgarza/ai-review-ci ai-review-ci fetch-context --repo owner/repo
  ```

- Raw API:

  ```bash
  gh api "repos/owner/repo/code-scanning/alerts?state=open&tool_name=ai-review/slop"
  ```

- Humans: the repo's Security tab → Code scanning.

Disposition semantics: each run uploads a complete ledger snapshot for its tool/category.
The snapshot is the union of existing open, non-dismissed alerts carried forward by automation and new findings from the current reviewer.
Reviewer omission is not a disposition.
Dismissed/fixed alerts feed future reviewer context as do-not-re-raise instructions, but only open alerts are carried into the next SARIF upload.

### PR findings

Diff-scoped findings surface twice, deliberately:

- **Code scanning**: uploaded under the same SARIF categories as repo-wide runs, so GitHub natively computes "new alerts introduced by this PR" and annotates the diff.
  The review job itself is signal-only; branch protection should block on deterministic gates and thread-resolution.
- **Resolvable review threads**: one review block per run (summary + metadata) with one inline, individually-resolvable comment per finding, for later disposition/remediation by separate agents.
  Off-diff findings are listed in the review body only — they are already in the ledger.
- **Required deterministic gates**: the installed PR workflow calls the reusable `_gates.yml` workflow for `deterministic-diff`, `delegation-conformance`, and `thread-resolution`; `bun-playwright` also installs `app-boot`. `install` applies branch protection; `ai-review-ci protect-branch --repo owner/repo --branch main --profile <profile>` exists to reapply or repair the required-check contract.

## Architecture

```
target repo                          this repo (cloned at CI time)
.github/workflows/review-*.yml  -->  .github/workflows/_review.yml (reusable)
                                       ci/runner.just        all runner recipes
                                       ai_review_ci.harness  prompt assembly + opencode loop
                                       ci/private/           root-owned validator (pydantic)
                                       ci/reviewer_home/     static /home/reviewer template
                                       ai_review_ci.sarif    artifact -> SARIF
                                       ai_review_ci.context  alert/thread context
                                       ai_review_ci.threads  PR review poster
                                       reviews/              templates, manifests, scopes
```

## QC Layout

The non-CI quality-control stack is split by operational concern:

| Directory | Owns |
| --- | --- |
| `global-hooks/` | User-level Git hooks installed with `just install-global-hooks`. |
| `repo-hooks/` | Per-repository hook templates installed with `just install-repo-hooks`. |
| `scaffolds/` | Repo-local QC delegation scaffolds copied with `just install-qc-scaffold`. |
| `tool-configs/` | Static tool configuration and QC planning notes. |
| `tool-artifacts/` | Scripts, generated model artifacts, and helper code consumed by QC recipes. |
| `justfiles/` | Shared and language-specific QC recipe hierarchy. |
| `skills/` | Canonical skills owned by this repo, symlink-installed via `just install-skills`. |
| `ci/` | Review CI runner, reviewer home, and private validator surface. |
| `reviews/` | Review prompt templates, manifests, and scopes (policy text is inlined from `skills/`). |

Use the migrated quality gate directly from a target repo:

```bash
just -f ~/ai-review-ci/justfiles/python.just -d . test
```

The quality gate is split into two tiers so that committing during feature work is cheap while heavier triage is deferred to push:

- `just test` (commit tier, run by `pre-commit`) catches *plainly incorrect* code: project preflight, shared normalization (Markdown/JSON/YAML formatting + Semgrep autofix), language auto-fixers (ruff/biome/cargo fmt), syntax, type-checking (mypy/tsc/clippy), the project's own tests (no coverage threshold), and bypass-comment detection.
- `just test-ci` (push tier, run by `pre-push`) depends on `test` and adds the *style/slop/coverage* stack: 100% coverage + diff-cover, deptry, import-linter, dead-code (vulture/grain/knip), jscpd, lizard, ast-grep, semgrep, vibecheck, and ai-slop.

Every language-specific tier runs shared normalization first: Markdown/JSON/YAML formatting and Semgrep autofix happen before language-specific checks and before verification gates.

The root `test` recipe for this repo routes through that same migrated hierarchy.

### How a run works

```
trigger -> _review.yml (cross-repo reusable workflow)
  -> checkout target repo; clone this repo into $RUNNER_TEMP
  -> install tools; fetch reviewer context (existing alerts; on PRs also
     existing review threads)
  -> prepare: create `reviewer` user, install root-owned validator to
     /opt/ai-review/private, install static home + review definitions to
     /home/reviewer, narrow sudo rule, copy sanitized repo
  -> [diff scope] stage the PR diff into the reviewer repo
  -> `ai-review-ci run-review` (as reviewer): assemble prompt (context + scope +
     manifest-inlined guides + repo docs + template), loop `opencode run`
     until `ai-review-ci validate-report` accepts a submitted artifact
       agent: analyze -> write report JSON to fixed path ->
              `/home/reviewer/bin/submit-candidate --help` for schema ->
              `/home/reviewer/bin/submit-candidate` -> fix on
              FIX-guided rejection -> repeat until exit 0
  -> `ai-review-ci to-sarif` -> upload to code scanning
  -> [diff scope] `ai-review-ci post-threads` posts resolvable review threads to the PR
  -> [diff scope] thread-resolution gate verifies ai-review PR threads are resolved with commit or disposition-ledger evidence
```

### The agent contract

The reviewer agent's only job is intelligent analysis producing a data file that fits a validated schema, retrying on rejection.
Everything else is automation.
The agent never supplies infrastructure facts: provenance (commit, repo) is attached runner-side from the CI environment; the validator (root-owned, unreadable and unmodifiable by the reviewer) checks schema, semantic field rules, and the trivial hallucination surfaces — every cited path must exist in the real checkout, every line range must lie within the file.
Reports are diagnosis-only: no remediation fields exist.

### Security model

The CI workflow runs as `runner`. The agent runs as a dedicated `reviewer` user with exactly one sudo rule: the private submit command.
It reads a sanitized repo copy (no `.git`, no `.github`), cannot see this infrastructure, and discovers the report schema only through `/home/reviewer/bin/submit-candidate --help`.

### Finding identity

`sha256(category|path)` is the stable identity for both SARIF alerts (`partialFingerprints.reviewFindingKey`) and PR threads (an `ai-review-fingerprint` marker in the thread body).
Labels, line numbers, and SHAs are excluded so the same defect class in the same file maps to one tracked item across runs.
During SARIF conversion, existing open alerts are re-emitted unless the current reviewer report contains the same fingerprint, in which case the current report replaces the carried copy.
Resolved PR threads and dismissed/fixed code-scanning alerts are dispositions, not carry-forward entries.

## Developing

Edit here, push to `main`, and every consumer's next run uses the new behavior (consumers that pinned a different `@ref` in their trigger files update on their chosen ref).
The reusable workflow and the runner recipes take all paths from the CI-time clone, so downstream repos contain only their trigger files and root `justfile` contract.
