# PR Lifecycle (Work-Unit Issue → TDD → PR Review → Merge)

The enforced PR integration lifecycle.
Part A is the PR worker guide (work-unit issue admission gate, PR review synthesis, TDD-before-implementation, exhaustive review reading), sourced from `creating-prs.md`. Part B is the branch → commit → push → CI → merge mechanics, sourced from `pr-workflow.md`. The integration/handoff cadence rules are stated first.

For disposition of returned review feedback, see [pr-review-disposition.md](./pr-review-disposition.md).
The during-writing edit-hygiene workflow (Read → Checkpoint → Edit → Verify → Commit), commit-message format, staging discipline, and hard constraints remain advisory in the `git-guidelines` skill in `~/ai`.

## Push and Commit Cadence (integration / handoff)

**Push cadence.** Push after committing when the user asked for pushed work, when the task depends on GitHub-visible auditability, before claiming completion, and before any handoff after substantive work.
If push fails, report the exact failure instead of treating a local commit as remotely auditable.

**Commit cadence at integration points.** Commit immediately when a long-running or multi-step task reaches a coherent review point, and when the user asks whether work was committed, asks for a handoff, or asks to stop.
Do not let hours of work accumulate only in the index or working tree; a local-only commit is not a remotely auditable handoff.
The full commit cadence and message format remain advisory in the `git-guidelines` skill.

* * *

# Part A — PR Worker Guide: How to Submit Work That Produces High-Quality Review Feedback

## Purpose

This guide is for PR workers, including agentic coding systems and human contributors using LLM assistance.
Its purpose is not to optimize for "getting approved."
Its purpose is to make the work legible, falsifiable, and reviewable, so that reviewer feedback is anchored to the actual intended outcome rather than to a post-hoc story constructed after the code already exists.

The main failure to prevent is this:

- code is written first,

- completion criteria are inferred from the resulting code,

- the PR description is retrofitted to match what now exists,

- reviewers evaluate against those retrofitted criteria,

- the result is a tautologous thumbs-up on work that may not meet the original need.

This guide therefore imposes one hard rule:

> **Jules-initiated PRs:** For any PR initiated by Jules, a work-unit issue must be written or updated before implementation and used as the source of truth for the PR body.
> Do not let the code define the task after the fact.
> See the Jules skill's work-unit issue workflow for its required command mechanics, but keep the issue as the planning source of truth.

> **Other PRs:** For any nontrivial PR, or any PR derived from a finalized local plan, put the plan into the repository's GitHub issue tree and milestone scope before implementation.
> Use the work-unit issue body/comments for the story, scope, implementation checklist, proof obligations, blockers, and evidence state.
> The PR body is a review synthesis derived from the issue, not the planning surface.
> Truly trivial changes may skip PR workflow when they qualify for direct-to-main repair.

* * *

## Core principle

A review is only as good as the target it is reviewing against.

If the intended outcome is underspecified, or if the worker allows the implementation to define its own success criteria after the fact, reviewers are forced into local or stylistic review.
They can comment on naming, tests, structure, and plausibility, but they cannot reliably say whether the change meets the actual need.

The worker must therefore supply, in advance:

1. the intended outcome,

2. the non-goals,

3. the acceptance criteria,

4. the specific evidence that will count as success,

5. the boundaries of the change,

6. the exact unresolved questions, if any.

That is what enables strong process-alignment feedback.

* * *

## Work-unit issue admission gate

PR creation must be a lossless synthesis from the current work-unit issue, GitHub issue tree, and milestone scope.
It is not a second round of planning.
If the worker cannot place the work under an existing roadmap node, issue subtree, or new top-level roadmap issue without inventing scope, user behavior, acceptance criteria, proof burdens, milestone cuts, or dependency order, the work-unit issue is not ready.

The canonical model for the issue tree and milestone mapping is owned by the `plan` skill's `references/externalization.md`. Load and follow it; this guide does not restate the model.
Before implementation, the work-unit issue must already satisfy that reference's Plan Fit Gate: tree root, parent or roadmap node, GitHub Milestone scope, the issue this PR will close, parent issues referenced but not closed, and the proof obligations owned by the issue.

This guide adds only the PR-execution specializations: the review-synthesis body shape below, closing-keyword discipline, and the stop rules specific to deriving one PR from one work-unit issue.

The issue-tree, milestone, wiki, and PR projections may add owner, branch, status, blocker, commit, run, artifact, and review-link metadata.
They must not add, delete, demote, or reinterpret scope, behavior, acceptance criteria, proof burdens, dependencies, handoffs, or integration semantics.

Stop and repair the work-unit issue when any of these are true:

- the root milestone is defined as tests passing, review readiness, checklist completion, or another derived status;

- a user or system behavior is represented only by a test ID, file name, command, commit, issue number, or implementation detail;

- an obligation lacks objective acceptance criteria or proof burden;

- a task can be completed by touching documentation, changing a label, classifying a failure, or making a check green while leaving the intended behavior unresolved;

- scope relies on private phrases such as "remaining", "in flight", "other relevant", or transcript-only context;

- the issue has unresolved product, architecture, dependency, ownership, or sequencing decisions;

- scattered sources disagree and the worker would need to choose between competing intent, implementation state, hypotheses, or status claims;

- evidence is only provenance, command execution, artifact existence, or green status, without showing attained behavior and why the witness rejects plausible broken cases;

- old checkmarks, repeated claims, or source-by-source summaries would become public progress without re-evaluation against current acceptance criteria.

- a nontrivial top-level PR checkbox would lack a link to a GitHub issue that owns its scope, acceptance criteria, and proof burden.

- the PR checklist would include deferred work, out-of-scope work, backlog work, follow-up work for later PRs, unchosen alternatives, or other items that are not required before this PR can be ready for review.

- the PR body would only mention issues in checklist prose without closing keywords or manual Development links for issues this PR is meant to close.

- a closing keyword would target a parent issue, deferred issue, future issue, partial work-unit issue, or out-of-scope issue that this PR does not fully complete.

- the PR would span multiple GitHub Milestones without either splitting the PR or naming the broader milestone/release that owns the cross-milestone scope and why.

## PR body as review synthesis from issues

Use the work-unit issue as the centralized live planning and tracking surface.
The issue tree owns organizational grouping, sibling order, parent-child edges between separate work units, and blocker visibility.
The work-unit issue owns its story, scope, acceptance criteria, proof obligations, implementation tasks, and blocker state.
The GitHub Milestone owns the delivery grouping.
The PR opens when implementation starts.
Its body contains a reviewer-facing synthesis of the work-unit issue: close/reference split, review obligations, evidence, and explicit non-scope.
If a checkbox appears in the PR body, completing it is required before the PR can be submitted for review.

Minimum body shape:

```markdown
## Intended result
<externally observable project or user result>

## Scope
- Included: <finite surface>
- Excluded: <explicit non-goals>
- Preserved behavior: <baseline that must remain true>

## GitHub tracking
- Work-unit issue: <#issue fully completed by this PR>
- Organizational parent or ledger: <#parent referenced but not closed, if any>
- Milestone: <GitHub Milestone assigned to the delivery slice and this PR>
- Closes on merge:
  - Closes #<issue fully completed by this PR>
- References only:
  - Refs #<parent, deferred, or excluded issue not closed by this PR>

## Review obligations
- [ ] **<#issue or story node> - <review obligation this PR satisfies>**
  - Proof obligations addressed: <named obligations>
  - Not addressed: <obligations this PR does not satisfy>
  - Evidence required: <proof mapped to each criterion>
  - Current evidence: <links to tests, CI, screenshots, logs, artifacts, or review>

## Automated gates
<authoritative checks named, with live truth owned by CI or rulesets>
```

Use closing keywords only for issues the PR fully completes and should close on merge.
Use `Refs` or prose for parent issues, future work, deferred work, excluded scope, and issues that remain open after this PR. Do not use partial-issue closure language.
If the PR targets a non-default branch or GitHub does not show the expected Development links, add the manual Development links before asking for review.

Use typed nodes.
A roadmap, phase, feature, story, proof obligation, or implementation task should stay at its own altitude.
Stories and proof obligations normally live in the owning issue body as definition-of-done material; implementation tasks live as checklists/comments on that issue.
Split work into child issues only under organizational grouping issues, and only when the child is a separate PR-sized work unit with its own acceptance/proof boundary.
Do not split a non-organizational work-unit issue into child issues for sub-tasks, sub-stories, proof burdens, or checklist items.
Parent completion follows from semantic attainment and supported evidence, not merely from checked descendants.

Checklist items must earn reviewer attention.
A checkbox is valid only when it represents a meaningful portion of the PR's review obligation that can be independently judged complete.
Test names, commands, commits, artifacts, green checks, policy declarations, and environment setup are not top-level progress items unless they are attached to the substantive obligation they prove or unblock.

For nontrivial PRs, every top-level checkbox must link to the GitHub issue that owns that review obligation, acceptance criteria, and proof burden.
Deeper checklist nodes should normally remain on the owning issue; include them in the PR only when reviewers need them to evaluate readiness.

Do not add checkbox items for deferred work, explicitly excluded scope, future PRs, parking-lot ideas, unresolved alternatives, or nice-to-have cleanup.
Put those in the `Scope` section, linked issues, or review discussion as prose.
A visible open checkbox means the PR is not done; a checkbox that does not need to be completed before review is a false blocker and makes the PR impossible to read as complete.

Keep the work-unit issue current while any in-scope review obligation remains open.
Submit the PR for review only after the issue represents no remaining required work, the evidence under each item is current, and the automated gates are either green or named as real blockers.
If later feedback reopens required work, update the issue first and remove ready-for-review state if the platform supports it.

### Tracking item quality

A PR checkbox is reviewer-hacking when it is easy to tick but empty of correctness.
Top-level items must start from externally meaningful behavior, decisions, or work products, then attach commits, commands, tests, and artifacts as evidence under that obligation.

"Drive Beamer PDF export from the app menu" is a valid tracking item because it names a user path, expected output, and proof surface.
"Re-run proof coverage," "Update Implementation-Status," or "Commit proof-artifacts/run.json" is weak unless the item is nested under the obligation it proves and states the criterion, content, and reviewer use.

Sequencing work is valid when the PR cannot be reviewed correctly without it.
"Publish local review guidance in AGENTS.md before review" can be a legitimate precondition because it calibrates reviewers against the governing policy.
Classification labels such as `env-blocked` are not standalone tasks; put them under the blocked substantive item with concrete evidence and an unblock condition.

Do not add amendment-auditability, PR-comment-versioning, or tracking-the-tracking checkboxes.
GitHub already preserves PR comments and review history.
When a plan changes, update the work-unit issue and use normal review discussion for the decision; do not make a deliverable out of proving that the discussion exists.

## Content placement

Put each fact in the surface that can represent and enforce it:

- GitHub issue tree: canonical public grouping and ordering surface, including roadmap ledgers, milestone/backlog ledgers, parent-child edges between separate work units, sibling order, and blocker dependencies.
  Each non-organizational work-unit issue owns its acceptance criteria, proof obligations, implementation checklist, proof status, and planning comments.

- GitHub Milestone: delivery or progress bucket over issues and PRs.
  It should name the organizational ledger or explicit work-unit issue set it covers, then attach the issues and linked PRs that count toward that delivery slice.

- GitHub PR Development links: closing-keyword or manual links between the PR and the in-scope issues that should close when the PR merges.

- PR body: reviewer-facing synthesis for the current branch's work-unit issue: intended result, scope/non-scope, close/reference split, proof obligations addressed, evidence mappings, and review checklist linked to the relevant GitHub issue.
  Deferred or excluded work belongs in prose or linked issues, not as PR checkboxes.

- GitHub wiki: durable narrative context and readable roadmap projection.
  It may render or link the issue tree, but it must not become a manually maintained live status mirror.

- Repository guidance or skills: global review policy, definitions of proof/completion, evidence standards, naming conventions, and agent calibration.

- CI, rulesets, and security settings: machine-derived invariants such as tests passing, required artifact schemas, branch protection, and policy synchronization.

- PR comments or review threads: discussion, resolved objections, local debugging detail, and historical context that should not become the current tracking surface.

- Evidence artifacts: generated outputs, screenshots, structured run reports, logs, CI runs, and baselines.
  Artifact existence is not itself progress; link each witness beneath the obligation and criterion it supports.

- Local scratchpads and setup surfaces: source inventories, worksheets, command history, raw transcripts, obsolete alternatives, repeated classifications, and environment setup.
  Link them only for optional depth when the public node is self-contained.

- Linked subplans or local scratchpads: derivation material too provisional for the issue body.
  These are optional depth; the authoritative tracker is the work-unit issue.

Do not duplicate global policy in the PR body.
A PR may include a sequencing task to publish or sync required guidance before review, but the policy itself stays in the canonical governing source.

Publish the current issue state, not the consolidation process.
Do not expose source-by-source diaries, normalization worksheets, raw agent reasoning, local command history, obsolete alternatives, or manually maintained histories of PR-body edits as progress.

* * *

## Required workflow

> **Work-unit issue workflow:** The work-unit issue is the authoritative planning contract for Jules-initiated and ordinary PRs.
> If Jules-specific tooling still asks for a separate submission artifact, derive it from the issue and keep the issue authoritative.

For nontrivial non-Jules PRs, update the work-unit issue first:

```bash
# Create or select the GitHub Milestone object for this delivery slice.
# State the subtree root or explicit issue set in the description.
gh api repos/<OWNER>/<REPO>/milestones -f title="<milestone>" -f state=open -f description="<issue-tree scope>"

# Create or update the roadmap/story/work-unit node that owns this work.
gh issue create --title "<story-shaped outcome>" --body-file issue.md --label enhancement --milestone "<milestone>"

# Create child issues only for separate work units when native sub-issues are available.
gh issue create --title "<child story or work-unit node>" --body-file child-issue.md --label enhancement --milestone "<milestone>" --parent <PARENT_ISSUE_NUMBER>

# Attach existing issues as sub-issues when needed.
gh issue edit <PARENT_ISSUE_NUMBER> --add-sub-issue <CHILD_ISSUE_NUMBER>

# Encode blockers as dependencies, not as roadmap order.
gh issue edit <ISSUE_NUMBER> --add-blocked-by <BLOCKER_ISSUE_NUMBER>

# Verify tree placement and milestone scope before implementation.
gh issue view <PARENT_ISSUE_NUMBER> --json title,body,url,milestone
```

* * *

## Phase 1: TDD before implementation

The PR should be driven by failing checks written before the fix.

The point is not ceremony.
The point is to lock the target before implementation exists.

Required sequence:

1. Write failing test or verification artifact.

2. Confirm it fails for the intended reason.

3. Implement the narrowest change that should make it pass.

4. Re-run verification.

5. Record the result on the work-unit issue or in an evidence artifact linked from the issue.

### What counts as acceptable pre-implementation verification

- a failing automated test,

- a reproducible failing command,

- a failing integration check,

- a failing exact output comparison,

- a failing invariant check.

### What does not count

- informal intention,

- a TODO list,

- a verbal claim that the bug exists,

- a post-hoc explanation added after the code already passes,

- content-free checks like `is not None` or `len(x) > 0`.

### Minimal example

Bad sequence:

1. Write implementation.

2. Run tests.

3. Write PR description saying the feature now works.

Required sequence:

1. Add test showing the feature does not work.

2. Commit test or at least keep it in the branch as part of the work.

3. Implement the fix.

4. Show the exact same test now passes.

* * *

## Phase 2: Keep the diff causally legible

The PR must remain easy to evaluate against the work-unit issue.

### Rules

1. **No unrelated edits.** Do not rename nearby symbols, reformat unrelated files, update fixtures, or rewrite helpers unless they are required by the issue.

2. **No hidden goal substitution.** If the original goal becomes impossible or incorrect, update the work-unit issue explicitly before changing direction.

3. **No structural completion as substitute for functional completion.** Do not add scaffolding, registries, wrappers, or documentation to create the appearance of completeness while leaving the core behavior stubbed.

4. **No fake success via fallbacks.** Do not hide failures with defaults, silent recovery, or plausible fabricated data.

5. **Prefer deletion and reuse over additive layers.** If a wrapper, fallback, or custom implementation is not necessary, remove it.
   If a mature dependency already solves the problem, use it unless a listed constraint forbids that.

* * *

## Phase 3: Force the PR body to come from the work-unit issue

> **See the Jules skill's work-unit issue workflow** for Jules-specific mechanics, but keep the work-unit issue authoritative.
> Still apply this skill's GitHub milestone, Development-link, review-state, and re-publishing rules to Jules-created PRs.

* * *

## Phase 4: Read every review comment with `gh` or bundled tools, not selectively

A worker must not rely on memory, inbox summaries, or partial UI reading.
Review feedback is part of the task state.
It must be read exhaustively and tracked explicitly.

The worker must read:

1. the PR body as currently published,

2. issue-style PR comments,

3. formal reviews,

4. line-level review comments,

5. CI/check failures,

6. review decision state.

### Minimum command set

#### 1. Use the bundled CLI tool to read all feedback surfaces at once

The most robust way to gather all feedback is to use the `extract_unresolved_issues` tool bundled with the git-guidelines skill:

```bash
extract_tool="$AI_SKILLS_DIR/git-guidelines/scripts/extract_unresolved_issues"
uv run --directory "$extract_tool" -m extract_unresolved_issues summarize <OWNER>/<REPO>#<PR_NUMBER>
```

This will automatically fetch:

- Top-level PR comments

- Inline code review threads

- Automated check-run errors

#### 2. Inspect structured PR state manually (fallback)

```bash
gh pr view <PR_NUMBER> \
  --json title,body,reviewDecision,latestReviews,reviews,comments,files,statusCheckRollup
```

This should be treated as the baseline state snapshot.

#### 3. Read CI/check status until it settles

```bash
gh pr checks <PR_NUMBER> --watch
```

For machine-readable inspection:

```bash
gh pr checks <PR_NUMBER> --json name,state,bucket,link
```

#### Automated Check Runs

Automated checks can post annotations surfaced via GitHub's API. Treat GitHub check state and the linked check details as the current authority for that check.

**Read check status:**

```bash
# List check runs for the PR head commit
gh api repos/<OWNER>/<REPO>/commits/<HEAD_SHA>/check-runs

# Extract annotations from a specific check run
gh api repos/<OWNER>/<REPO>/check-runs/<CHECK_RUN_ID>/annotations
```

Each annotation includes `message`, `path`, `start_line`, `annotation_level`, and a `details_url` pointing to the check's detailed report when the provider exposes one.

#### 4. Read formal review objects in chronological order

```bash
gh api repos/<OWNER>/<REPO>/pulls/<PR_NUMBER>/reviews
```

#### 5. Read line-level review comments on the diff

```bash
gh api repos/<OWNER>/<REPO>/pulls/<PR_NUMBER>/comments
```

#### 6. Read issue-style PR comments

```bash
gh api repos/<OWNER>/<REPO>/issues/<PR_NUMBER>/comments
```

These are distinct surfaces.
A worker that reads only one of them will miss actionable feedback.

* * *

## Required review-log discipline

Every actionable review item must be copied into a tracked log file.

Create:

```bash
$EDITOR .pr/REVIEW_LOG.md
```

### Required fields for each item

```markdown
## Review item <N>

- Source: <review / review-comment / issue-comment / CI>
- URL or identifier: <link or id>
- Reviewer:
- File/line:
- Exact actionable request:
- Worker interpretation:
- Planned action:
- Status: open | addressed | rejected-with-rationale
- Commit addressing it:
- Notes:
```

### Hard rules

1. **No silent ignoring.** Every actionable item must appear in the log.

2. **No bundling multiple requests into vague summaries.** Preserve atomicity.

3. **No "addressed" without a commit.**

4. **No rejection without explicit rationale tied to the work-unit issue.**

5. **If a review item reveals that the issue contract is wrong, update the issue first.**

This is necessary because agentic workers often continue from their prior frame and treat review feedback as advisory decoration.
The log must force integration of each item into the task state.

* * *

## Phase 5: Respond to feedback by updating the issue, code, or both

Feedback should be handled through one of only three legal moves.

### Move A: The reviewer found a real defect within the existing issue contract

Action:

- update code/tests,

- update evidence,

- mark the review item addressed.

### Move B: The reviewer exposed missing or weak acceptance criteria

Action:

- strengthen the work-unit issue,

- add or revise tests first if needed,

- then update code.

### Move C: The reviewer identified that the issue contract itself is wrong

Action:

- revise the work-unit issue explicitly,

- commit that revision,

- then proceed with implementation changes.

### Illegal move

- silently keep the same implementation direction while merely adding a local constraint,

- say "addressed" without changing the issue or the code appropriately,

- reinterpret the reviewer's feedback into something easier and solve that instead.

* * *

## Example of proper feedback integration

Reviewer comment:

> This test only checks that a value is returned.
> It would pass on arbitrary non-empty junk.

Incorrect response pattern:

- add another `isinstance(...)` check,

- reply "done,"

- leave acceptance criteria unchanged.

Required response pattern:

1. add the review item to `.pr/REVIEW_LOG.md`,

2. update the work-unit issue so the acceptance criterion names the exact invariant or exact value to be proven,

3. replace the weak test with a substantive one,

4. commit,

5. cite the commit when marking the item addressed.

* * *

## Phase 6: Keep reviewers anchored to outcome, not process theater

The PR should make it easy for reviewers to reject process-shaped nonsense.

### Include a dedicated "Review focus" section

In the PR body derived from the issue, ask reviewers to check:

- whether the intended outcome is the right one,

- whether any acceptance criterion is missing, tautological, or implementation-defined,

- whether any file in the diff falls outside the declared boundary,

- whether any test would pass on plausible junk,

- whether any fallback hides failure instead of surfacing it,

- whether the code satisfies the problem or merely looks complete.

This materially improves reviewer alignment because it keeps the PR anchored to external success criteria defined before implementation.

* * *

## Patterns workers must actively avoid

### 1. Post-hoc PR narration

Writing the body after the code and then describing what now exists as if it were the intended target from the start.

### 2. Completion criteria drift

Changing "done" to mean whatever the current code already satisfies.

### 3. Structural completion as surrogate

Submitting scaffolding, docs, wrappers, registrations, and passing trivial tests while the core outcome is still missing.

### 4. Review-skimming

Reading only the top-level review decision or only the web summary and missing line-level or issue-level comments.

### 5. Silent partial compliance

Addressing only the easiest fragment of a review item and marking the whole item resolved.

### 6. Constraint accumulation without frame change

A correction implies "abandon this direction," but the worker instead adds a local patch and keeps the original wrong direction.

### 7. Evidence laundering

Replacing real proof with broad claims such as "tested thoroughly," "handled edge cases," or "improved reliability."

### 8. Reviewer burden shifting

Leaving reviewers to reconstruct the original goal, infer missing constraints, or detect whether the tests are tautological.

* * *

## Minimal shell workflow

A practical sequence:

```bash
# 0. put the finalized plan on the GitHub work-unit issue and milestone scope
$EDITOR issue-root.md
$EDITOR issue-foundation.md
$EDITOR issue-workstream.md
# Create the milestone if it does not already exist.
gh api repos/<OWNER>/<REPO>/milestones -f title="<milestone>" -f state=open -f description="<issue-tree scope>"
gh issue create --title "<story-shaped outcome>" --body-file issue-root.md --label enhancement --milestone "<milestone>"
gh issue create --title "<foundation work unit>" --body-file issue-foundation.md --label enhancement --milestone "<milestone>" --parent <ISSUE_ROOT_NUMBER>
gh issue create --title "<workstream work unit>" --body-file issue-workstream.md --label enhancement --milestone "<milestone>" --parent <ISSUE_ROOT_NUMBER>
# Attach existing issues as sub-issues only when they are separate work units, and encode blockers separately.
gh issue edit <ISSUE_ROOT_NUMBER> --add-sub-issue <CHILD_ISSUE_NUMBER>
gh issue edit <ISSUE_W1_NUMBER> --add-blocked-by <ISSUE_F1_NUMBER>

# 1. keep live planning state on the issue before implementation
gh issue view <WORK_UNIT_ISSUE_NUMBER>
gh issue comment <WORK_UNIT_ISSUE_NUMBER> --body-file issue-update.md

# 2. create a review log if the branch needs one
mkdir -p .pr
$EDITOR .pr/REVIEW_LOG.md

# 3. write failing tests / failing verification
pytest path/to/test_file.py -q

# 4. implement narrowly and re-run verification
pytest path/to/test_file.py -q

# 5. update the issue with proof status and any changed decisions
gh issue comment <WORK_UNIT_ISSUE_NUMBER> --body-file issue-proof-update.md

# 6. open the PR when implementation starts; synthesize the body from the issue
$EDITOR .pr/PR_BODY.md   # include Closes only for the work-unit issue; use Refs for parents/deferred work
git add .pr/PR_BODY.md .pr/REVIEW_LOG.md <changed code/tests>
git commit -m "Complete work-unit implementation"
git push -u origin HEAD
gh pr create --title "<title>" --body-file .pr/PR_BODY.md --milestone "<milestone>"
gh pr edit <PR_NUMBER> --body-file .pr/PR_BODY.md --milestone "<milestone>"

# 7. after review arrives, read all feedback surfaces
gh pr view <PR_NUMBER> --comments
gh pr view <PR_NUMBER> --json title,body,milestone,closingIssuesReferences,reviewDecision,latestReviews,reviews,comments,files,statusCheckRollup
gh api repos/<OWNER>/<REPO>/pulls/<PR_NUMBER>/reviews
gh api repos/<OWNER>/<REPO>/pulls/<PR_NUMBER>/comments
gh api repos/<OWNER>/<REPO>/issues/<PR_NUMBER>/comments
gh pr checks <PR_NUMBER> --watch

# 8. if review feedback reopens required work, update the issue before continuing
gh issue comment <WORK_UNIT_ISSUE_NUMBER> --body-file issue-review-update.md
$EDITOR .pr/PR_BODY.md
$EDITOR .pr/REVIEW_LOG.md

git add .pr/PR_BODY.md .pr/REVIEW_LOG.md <changed code/tests>
git commit -m "Address review feedback"

# 9. republish PR body from the updated issue synthesis
gh pr edit <PR_NUMBER> --body-file .pr/PR_BODY.md --milestone "<milestone>"

# 10. after reopened obligation work is complete and evidenced, request review again
gh pr comment <PR_NUMBER> --body '@codex review'
```

* * *

## What reviewers should be able to see immediately

A well-prepared PR should let a reviewer answer these questions in under a minute:

1. What exact outcome is this PR trying to achieve?

2. What counts as success?

3. What is not being changed?

4. What evidence proves the behavior now holds?

5. Which review items remain open?

6. Which ones were addressed in which commits?

If the PR does not expose those answers directly, it is not review-ready.

* * *

## Final rule set

1. Put the plan on the work-unit issue before implementation.

2. Place the work-unit issue in the GitHub issue tree and GitHub Milestone scope.

3. Assign descendant delivery issues and linked PRs to that GitHub Milestone.

4. Keep stories, plans, proof obligations, and implementation checklists on the issue.

5. Add closing-keyword Development links only for issues the PR fully satisfies on merge.

6. Use `Refs` or prose, not closing keywords, for parent issues, deferred work, future work, and out-of-scope issues.

7. Link nontrivial top-level PR review items to the owning issues.

8. Keep deferred, excluded, future, and out-of-scope work out of PR checkboxes.

9. Do not use a draft PR as the planning tracker; open the PR when implementation starts, and submit it for review only after every in-scope issue and proof obligation is complete and evidenced.

10. Derive the PR body from the work-unit issue, issue tree, and evidence, not from memory or the web form.

11. Lock acceptance criteria before code exists.

12. Use failing verification first.

13. Keep the diff within the declared boundary.

14. Read every review surface with `gh`.

15. Log every actionable review item atomically.

16. Do not mark feedback addressed without an identifying commit.

17. If feedback changes the target, update the work-unit issue, issue tree, and milestone scope first.

18. Do not let the implementation define its own success criteria.

19. Do not let a reviewer guess what "done" means.

A PR that follows these rules is much easier to review well, much harder to rubber-stamp for the wrong reasons, and much less likely to drift into post-hoc self-justifying completion theater.

* * *

# Part B — PR Workflow (Branch → Commit → Push → Merge)

Consolidated from the former `github-pr-workflow` skill.

## 1. Branch Creation

```bash
git fetch origin
git checkout main && git pull origin main
git checkout -b feat/add-user-authentication
```

Naming: `feat/description`, `fix/description`, `refactor/description`, `docs/description`, `ci/description`.

## 2. Making Commits

Use the standard edit workflow (the Read → Checkpoint → Edit → Verify → Commit workflow is advisory in the `git-guidelines` skill), then:

```bash
git add src/auth.py src/models/user.py tests/test_auth.py
git commit -m "feat: add JWT-based user authentication

- Add login/register endpoints
- Add User model with password hashing
- Add unit tests for auth flow"
```

Commit types: `feat`, `fix`, `refactor`, `docs`, `test`, `ci`, `chore`, `perf`

## 3. Pushing and Creating a PR

```bash
git push -u origin HEAD
```

**With gh:**
```bash
# Keep the work-unit issue current first.
# Prepare .pr/PR_BODY.md as a reviewer-facing synthesis from the issue.
# See "Work-unit issue admission gate" and "PR body as review synthesis from issues"
# in Part A above for the admission gate and PR body format.
gh pr create \
  --title "feat: add JWT-based user authentication" \
  --body-file .pr/PR_BODY.md \
  --milestone "<milestone>"

gh pr comment <PR_NUMBER> --body '@codex review'
```

Options: `--reviewer user1,user2`, `--label "enhancement"`, `--base develop`

**Without gh:**
```bash
BRANCH=$(git branch --show-current)

jq -n \
  --arg title "feat: add JWT-based user authentication" \
  --rawfile body .pr/PR_BODY.md \
  --arg head "$BRANCH" \
  --arg base "main" \
  '{title: $title, body: $body, head: $head, base: $base}' \
  | curl -s -X POST \
      -H "Authorization: token $GITHUB_TOKEN" \
      -H "Accept: application/vnd.github.v3+json" \
      https://api.github.com/repos/$OWNER/$REPO/pulls \
      -d @-
```

### Extracting Owner/Repo from Git Remote

```bash
REMOTE_URL=$(git remote get-url origin)
OWNER_REPO=$(echo "$REMOTE_URL" | sed -E 's|.*github\.com[:/]||; s|\.git$||')
OWNER=$(echo "$OWNER_REPO" | cut -d/ -f1)
REPO=$(echo "$OWNER_REPO" | cut -d/ -f2)
```

## 4. Monitoring CI Status

```bash
# One-shot check
gh pr checks

# Watch until all checks finish (polls every 10s)
gh pr checks --watch
```

**Without gh:**
```bash
SHA=$(git rev-parse HEAD)

curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/commits/$SHA/status \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Overall: {data['state']}\")
for s in data.get('statuses', []):
    print(f\"  {s['context']}: {s['state']} - {s.get('description', '')}\")"

# Also check GitHub Actions check runs
curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/commits/$SHA/check-runs \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for cr in data.get('check_runs', []):
    print(f\"  {cr['name']}: {cr['status']} / {cr['conclusion'] or 'pending'}\")"
```

### Poll Until Complete

```bash
SHA=$(git rev-parse HEAD)
for i in $(seq 1 20); do
  STATUS=$(curl -s \
    -H "Authorization: token $GITHUB_TOKEN" \
    https://api.github.com/repos/$OWNER/$REPO/commits/$SHA/status \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['state'])")
  echo "Check $i: $STATUS"
  if [ "$STATUS" = "success" ] || [ "$STATUS" = "failure" ] || [ "$STATUS" = "error" ]; then
    break
  fi
  sleep 30
done
```

## 5. Auto-Fixing CI Failures

### Step 1: Get Failure Details

**With gh:**
```bash
gh run list --branch $(git branch --show-current) --limit 5
gh run view <RUN_ID> --log-failed
```

**Without gh:**
```bash
BRANCH=$(git branch --show-current)
curl -s \
  -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$OWNER/$REPO/actions/runs?branch=$BRANCH&per_page=5" \
  | python3 -c "
import sys, json
runs = json.load(sys.stdin)['workflow_runs']
for r in runs:
    print(f\"Run {r['id']}: {r['name']} - {r['conclusion'] or r['status']}\")"

RUN_ID=<run_id>
curl -s -L \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/actions/runs/$RUN_ID/logs \
  -o /tmp/ci-logs.zip
cd /tmp && unzip -o ci-logs.zip -d ci-logs && cat ci-logs/*.txt
```

### Step 2: Fix and Push

```bash
git add <fixed_files>
git commit -m "fix: resolve CI failure in <check_name>"
git push
```

### Step 3: Verify

Re-check CI status using the commands from Section 4 above.

> CI failures and PR review comments are different.
> CI failures can be fixed mechanically after root-cause diagnosis.
> Review comments must first be routed to `pr-feedback-triage` (see [pr-review-disposition.md](./pr-review-disposition.md)). Do not auto-fix review comments merely because they are unresolved.

### Auto-Fix Loop Pattern

1. Check CI status → identify failures
2. Read failure logs → understand the error
3. Fix the code
4. `git add <modified files> && git commit -m "fix: ..." && git push`
5. Wait for CI → re-check status
6. Repeat if still failing (up to 3 attempts, then ask the user)

## 6. Merging

**With gh:**
```bash
# Squash merge + delete branch
gh pr merge --squash --delete-branch

# Enable auto-merge
gh pr merge --auto --squash --delete-branch
```

**Without gh:**
```bash
PR_NUMBER=<number>

# Merge via API (squash)
curl -s -X PUT \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/pulls/$PR_NUMBER/merge \
  -d "{
    \"merge_method\": \"squash\",
    \"commit_title\": \"feat: add user authentication (#$PR_NUMBER)\"
  }"

# Delete remote branch
BRANCH=$(git branch --show-current)
git push origin --delete $BRANCH

# Switch back to main
git checkout main && git pull origin main
git branch -d $BRANCH
```

Merge methods: `"merge"` (merge commit), `"squash"`, `"rebase"`.

## 7. Complete Workflow Example

```bash
# 1. Start from clean main
git checkout main && git pull origin main

# 2. Branch
git checkout -b fix/login-redirect-bug
# 3. Put the plan on the work-unit issue in the GitHub issue tree and milestone scope.
#    Include story, scope, acceptance criteria, proof obligations, and implementation
#    tasks in the issue body/comments before implementation defines its own success criteria.
gh api repos/<OWNER>/<REPO>/milestones -f title="<milestone>" -f state=open -f description="<issue-tree scope>"
gh issue view <WORK_UNIT_ISSUE_NUMBER>

# 4. (Agent makes code changes while the issue tracks open work)

# 5. Commit code changes
git add src/auth/login.py tests/test_login.py
git commit -m "fix: correct redirect URL after login"

# 6. Push implementation updates
git push -u origin HEAD

# 7. Synthesize the PR body from the issue; keep deferred work out of checkboxes
gh pr create --title "fix: correct redirect URL after login" --body-file .pr/PR_BODY.md --milestone "<milestone>"
gh pr view --json title,body,milestone,closingIssuesReferences

# 8. Monitor CI; deferred work stays out of PR checkboxes
gh pr checks --watch

# 9. Trigger review only after every in-scope issue/proof item is complete and evidenced
gh pr comment <PR_NUMBER> --body '@codex review'

# 10. Merge when green
gh pr merge --squash --delete-branch
```
