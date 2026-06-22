# ai-review-ci

Centrally-managed, OpenCode-powered review CI. Target repositories carry only three thin trigger workflows; everything else — the reusable workflow, the review runner, the validator, the reviewer home template, the prompt corpus — lives here and is cloned inside the CI runner at execution time.
Updating this repo updates every consumer on their next run.

Two review types:

- **General review** — structural code quality audit: architectural decay, dead code, test quality, dependency mismanagement, semantic regressions.
- **Slop review** — AI-generated-code audit: bridge-burning violations, runtime control-flow defects, test/text antipatterns, validation-evasion constructs, defaults/fallbacks/mocks/skips.

Each type runs in two scopes: **repo** (full-repository sweep) and **diff** (PR review focused on the diff against the base branch).

## Installing into a repo

```bash
cd /path/to/your/repo
uvx --from git+https://github.com/dzackgarza/ai-review-ci ai-review-ci install --repo owner/repo --branch main
```

This installs the complete QC enforcement surface: it writes the three trigger workflows and applies branch protection requiring the installed PR gate jobs.

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

Requirements in the target repo: GitHub code scanning enabled (free for public repos), GitHub CLI auth with permission to edit branch protection, and the target branch named in `--branch`.
LLM review jobs are signal-only process checks: they upload SARIF and post review threads, but they do not compute or fail on a health score.
The merge gate is deterministic QC plus evidence-backed resolution of reviewer-authored PR threads.

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
Their local `justfile` should delegate the public `test` and `test-ci` recipes to the relevant language justfile in `~/ai-review-ci`.

For new projects, install the tracked scaffold instead of hand-writing the delegation surface:

```bash
cd ~/ai-review-ci
# choose one language scaffold for the target repository
just install-qc-scaffold python /path/to/new/repo
just install-qc-scaffold bun /path/to/new/repo
just install-qc-scaffold bun-app /path/to/new/repo
just install-qc-scaffold rust /path/to/new/repo
just install-qc-scaffold sage /path/to/new/repo
```

The recipe copies files from `scaffolds/<language>/` and refuses to overwrite existing files.
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

TypeScript/Bun app with real-boundary boot proof:

```justfile
test:
    @just -f ~/ai-review-ci/justfiles/bun.just -d . test

test-ci:
    @just -f ~/ai-review-ci/justfiles/bun.just -d . test-ci

app-boot:
    @bunx playwright test --config playwright.config.ts
```

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
- **Required deterministic gates**: the installed PR workflow calls the reusable `_gates.yml` workflow for `deterministic-diff`, `delegation-conformance`, `app-boot`, and `thread-resolution`.
  `install` applies branch protection; `ai-review-ci protect-branch --repo owner/repo --branch main` exists to reapply or repair the required-check contract.

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
                                       reviews/              templates, manifests, scopes, vendor/
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
| `skills/` | Agent-facing QC operating instructions owned by this repo. |
| `ci/` | Review CI runner, reviewer home, and private validator surface. |
| `reviews/` | Review prompt templates, manifests, scopes, and vendored policy text. |

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
The reusable workflow and the runner recipes take all paths from the CI-time clone, so downstream repos contain nothing but their three trigger files.
