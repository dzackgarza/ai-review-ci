# ai-review-ci

Centrally-managed, OpenCode-powered review CI. Target repositories carry only
three thin trigger workflows; everything else — the reusable workflow, the
review runner, the validator, the reviewer home template, the prompt corpus —
lives here and is cloned inside the CI runner at execution time. Updating this
repo updates every consumer on their next run.

Two review types:

- **General review** — structural code quality audit: architectural decay,
  dead code, test quality, dependency mismanagement, semantic regressions.
- **Slop review** — AI-generated-code audit: bridge-burning violations,
  runtime control-flow defects, test/text antipatterns, validation-evasion
  constructs, defaults/fallbacks/mocks/skips.

Each type runs in two scopes: **repo** (full-repository sweep) and **diff**
(PR review focused on the diff against the base branch).

## Installing into a repo

```bash
cd /path/to/your/repo
uvx git+https://github.com/dzackgarza/ai-review-ci install
```

This writes exactly three files into `.github/workflows/` and nothing else:

| File | Triggers |
|------|----------|
| `review-general.yml` | weekly cron, push to main, manual dispatch |
| `review-slop.yml` | weekly cron, push to main, manual dispatch |
| `review-pr.yml` | every pull request (both types, diff-scoped) |

The three files are minimally-correct base configuration and become
**repo-owned** the moment they are installed: edit crons, branches,
thresholds, and the upstream `@ref` directly in the YAML — that is the
whole downstream surface. The installer never overwrites them. All review
*behavior* lives upstream and needs no reinstall: every run clones this
repo fresh.

What an installed trigger looks like (`review-general.yml` — pure
configuration pointing at the upstream reusable workflow):

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
      fail_below: ${{ vars.GENERAL_FAIL_BELOW }}
```

The canonical templates live in
[`src/ai_review_ci/templates/`](src/ai_review_ci/templates/).

Requirements in the target repo: GitHub code scanning enabled (free for
public repos); optionally the Actions vars `GENERAL_FAIL_BELOW` /
`SLOP_FAIL_BELOW` to gate runs on a health score.

## Canonical Operations

### Running repo-wide reviews

- **Automatic:** every push to the default branch runs both review types;
  weekly crons re-run them on schedule.
- **On demand:** `gh workflow run "General Review"` or
  `gh workflow run "Slop Review"` (or the Actions UI).

### Finding all outstanding reported issues

The single ledger is **GitHub code scanning alerts**, under tool names
`ai-review/general` and `ai-review/slop`:

- Agent/CLI, formatted (the same context document CI reviewers receive —
  open / dismissed-with-reason / fixed, each with `path:line` and alert URL):

  ```bash
  uv run ci/fetch-reviewer-context.py --repo owner/repo
  ```

- Raw API:

  ```bash
  gh api "repos/owner/repo/code-scanning/alerts?state=open&tool_name=ai-review/slop"
  ```

- Humans: the repo's Security tab → Code scanning.

Disposition semantics: an alert stays **open** until remediated (the next
analysis stops reporting its fingerprint → auto-closes as fixed) or
**dismissed** with a reason. Both states feed back into every future
reviewer's context as do-not-re-raise instructions.

### PR findings

Diff-scoped findings surface twice, deliberately:

- **Code scanning**: uploaded under the same SARIF categories as repo-wide
  runs, so GitHub natively computes "new alerts introduced by this PR" and
  annotates the diff. Make the check blocking via branch protection.
- **Resolvable review threads**: one review block per run (summary +
  metadata) with one inline, individually-resolvable comment per finding,
  for later disposition/remediation by separate agents. Off-diff findings
  are listed in the review body only — they are already in the ledger.

## Architecture

```
target repo                          this repo (cloned at CI time)
.github/workflows/review-*.yml  -->  .github/workflows/_review.yml (reusable)
                                       ci/runner.just        all runner recipes
                                       ci/run-review.py      prompt assembly + opencode loop
                                       ci/private/           root-owned validator (pydantic)
                                       ci/reviewer_home/     static /home/reviewer template
                                       ci/report-to-sarif.py artifact -> SARIF
                                       ci/fetch-reviewer-context.py  alert/thread context
                                       ci/post-review-threads.py     PR review poster
                                       reviews/              templates, manifests, scopes, vendor/
```

## QC Layout

The non-CI quality-control stack is split by operational concern:

| Directory | Owns |
|-----------|------|
| `global-hooks/` | User-level Git hooks installed with `just install-global-hooks`. |
| `repo-hooks/` | Per-repository hook templates installed with `just install-repo-hooks`. |
| `tool-configs/` | Static tool configuration, project templates, and QC planning notes. |
| `tool-artifacts/` | Scripts, generated model artifacts, and helper code consumed by QC recipes. |
| `justfiles/` | Shared and language-specific QC recipe hierarchy. |
| `ci/` | Review CI runner, reviewer home, and private validator surface. |
| `reviews/` | Review prompt templates, manifests, scopes, and vendored policy text. |

Use the migrated quality gate directly from a target repo:

```bash
just -f ~/ai-review-ci/justfiles/python.just test
```

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
  -> run-review.py (as reviewer): assemble prompt (context + scope +
     manifest-inlined guides + repo docs + template), loop `opencode run`
     until a validated artifact exists
       agent: analyze -> write report JSON to fixed path ->
              `submit-candidate --help` for schema -> submit -> fix on
              FIX-guided rejection -> repeat until exit 0
  -> convert artifact to SARIF -> upload to code scanning
  -> [diff scope] post resolvable review threads to the PR
  -> [optional] health-score threshold gate
```

### The agent contract

The reviewer agent's only job is intelligent analysis producing a data file
that fits a validated schema, retrying on rejection. Everything else is
automation. The agent never supplies infrastructure facts: provenance
(commit, repo) is attached runner-side from the CI environment; the
validator (root-owned, unreadable and unmodifiable by the reviewer) checks
schema, semantic field rules, and the trivial hallucination surfaces — every
cited path must exist in the real checkout, every line range must lie within
the file. Reports are diagnosis-only: no remediation fields exist.

### Security model

The CI workflow runs as `runner`. The agent runs as a dedicated `reviewer`
user with exactly one sudo rule: the private submit command. It reads a
sanitized repo copy (no `.git`, no `.github`), cannot see this
infrastructure, and discovers the report schema only through
`submit-candidate --help`.

### Finding identity

`sha256(category|path)` is the stable identity for both SARIF alerts
(`partialFingerprints.reviewFindingKey`) and PR threads (an
`ai-review-fingerprint` marker in the thread body). Labels, line numbers,
and SHAs are excluded so the same defect class in the same file maps to one
tracked item across runs; duplicates are skipped at posting time, and
resolved threads / dismissed alerts count as dispositions.

## Developing

Edit here, push to `main`, and every consumer's next run uses the new
behavior (consumers that pinned a different `@ref` in their trigger files
update on their chosen ref). The reusable workflow and the runner recipes
take all paths from the CI-time clone, so downstream repos contain nothing
but their three trigger files.
