---
name: git-integration-workflow
description: 'Use when integrating code at the GitHub boundary — creating or updating a PR, updating work-unit issues, marking a PR ready, triggering automated review, dispositioning returned review/check feedback, merging, or filing and triaging issues. This is the enforced integration workflow, distinct from during-writing edit hygiene.'
---

# Git Integration Workflow

The enforced git *integration* workflow: what agents must do when they take finished work across the GitHub boundary.
This owns the integration-time gates.
During-writing hygiene (the Read → Checkpoint → Edit → Verify → Commit edit workflow, commit-message format, staging discipline, safe deletion, destructive-git bans, hard constraints) stays advisory in the `git-guidelines` skill in `~/ai` and is not restated here.

For "how to review a suspect PR" — the slop field guide, bridge-burning red flags, and validation-evasion auditing — this skill references [reviewing-llm-code](../reviewing-llm-code/SKILL.md) rather than duplicating it.
For banned patterns, policy codes, and disposition doctrine, reference [anti-slop](../anti-slop/SKILL.md) and [policy-index](../policy-index/SKILL.md).

## Enforced lifecycle

Nontrivial work crosses the boundary in this order.
Each arrow is a gate, not a suggestion.

**work-unit issue → implement with TDD → PR review synthesis → trigger review → disposition feedback → merge**

1. **Work-unit issue.** Put the story, scope, acceptance criteria, proof obligations, implementation checklist, blocker state, and planning decisions on the GitHub issue itself, in the body or comments.
   The issue is the draft.
   Do not create child issues for ordinary implementation tasks, and do not use a draft PR as the planning surface.
   If the work cannot be placed under an existing roadmap node, issue subtree, or new top-level roadmap issue without inventing scope, behavior, acceptance criteria, proof burdens, milestone cuts, or dependency order, the issue is not ready — stop and repair the issue.
   See the admission gate in [references/pr-lifecycle.md](./references/pr-lifecycle.md).

2. **Implement with TDD.** Lock the target with failing verification before implementation exists: write a failing test/check, confirm it fails for the intended reason, implement the narrowest change, re-run, record the result on the issue or in evidence linked from the issue.
   Keep the diff inside the issue boundary.
   Keep issue checklist items open while any in-scope work remains open.

   **Red-proof route.** When the red/green workflow calls for landing the genuinely-failing red proof as its own commit *before* the green fix, the pre-commit gate (`just test`) will reject it.
   Do NOT reach for `git commit --no-verify` — that is an unaudited bypass.
   Use the single sanctioned, auditable route:
   ```bash
   ai-review-ci red-commit --issue <owning-issue> -m "<message>"
   ```
   It runs the same gate, refuses unless the gate genuinely fails (a passing gate is not a red proof), stamps an auditable `Red-Proof: #<issue>` trailer, and bypasses the gate for that one commit only — ordinary hooks stay active.
   This is the same route named by the pre-commit hook's rejection message and by the `test-guidelines` skill (Red-Green Evidence).

3. **PR review synthesis.** Open or update the PR from the current work-unit issue: summarize the issue scope, close/reference split, proof obligations addressed, evidence, and reviewer checklist.
   The PR body is a review submission derived from the issue, not a second planning tracker.
   Use closing keywords (`Closes`) only for the work-unit issue this PR fully completes on merge; use `Refs` or prose for organizational parents and deferred work.
   A visible open checkbox in the PR body is a reviewer-facing blocker copied from the issue; if it is still open, the PR is not ready.

4. **Mark ready.** Only after every in-scope issue and proof obligation is complete and evidenced: push the branch, ensure the issue body/comments are current, publish the PR body, then request review.

5. **Trigger review.** Explicitly start the automated review loop: `gh pr comment <PR_NUMBER> --body '@codex review'` (or the repo's documented equivalent).
   Before tagging reviewers, ensure the target repo's local `AGENTS.md` carries the canonical `# Review Guidelines` section.

6. **Disposition feedback.** Scan all feedback surfaces at once with `extract_unresolved_issues`, then route every item through `pr-feedback-triage`. Review feedback is a judgment task: each item gets an explicit four-way disposition, a visible human-readable thread reply, and — for rejected/modified items — a top-level disposition ledger entry.
   Positive disposition requires already-committed remediation.
   If feedback reopens required work, update the work-unit issue first and mark the PR not ready if it had already been submitted for review.
   See [references/pr-review-disposition.md](./references/pr-review-disposition.md).

7. **Merge.** Merge (typically `gh pr merge --squash --delete-branch`) only when checks are green and every review surface has been substantively dispositioned.

## Traversal and issue tree management (itree)

For repositories that represent planned work as a single rooted, ordered GitHub issue tree, use the standalone `itree` tool from `dzackgarza/itree` to discover the next task and keep the tree well-formed.
`itree help model` prints the full organization model — ontology, repo state machine, the four rails, and proportionality doctrine; this section is the operational summary.

### How to invoke

Run the tool directly from GitHub via `uvx` — no local checkout required:
```bash
uvx --from git+https://github.com/dzackgarza/itree itree [subcommand]
```

The command lines below abbreviate that prefix to `itree`.

### Governance boundary

A repository is `itree`-governed when its planned work is represented by one rooted,
ordered GitHub issue tree. Confirm that ownership from repository guidance and
`itree doctor OWNER/REPO`; a missing root is not permission to create an orphan with raw
GitHub commands. Initialize the tree or obtain an explicit decision that the repository
is not `itree`-governed.

In a governed repository, create work units with `itree new` and create delivery
milestones with `itree milestone`. Raw `gh issue create`, direct issue POSTs, and manual
GitHub Milestone construction are reserved for repositories explicitly outside `itree`
governance. See [references/issue-workflow.md](./references/issue-workflow.md) for the
creation and recovery contract.

### Doctrine (matches `itree help model`)

- A **work unit** is a coherent PR/review/proof boundary and is ALWAYS A LEAF: its acceptance criteria, proof obligations, implementation checklist, and status live in the issue body or comments — never in child issues (violating this is `itree` finding E015).
- **Grouping issues** (root ledger, milestone, backlog, roadmap, phase) order work units but are not themselves units of work.
- `next` returns the single next open work unit in preorder.
  That work unit *is* the next task; there is no separate task enclosed within it.
- Keep the tree as small as the work is.
  A candidate smaller than a PR is body content of an existing unit — absorb it, don't fragment.

### Commands

- `itree next OWNER/REPO`: the single next open work unit in preorder and its standing instruction.
- `itree doctor OWNER/REPO`: classify repo state and report structure findings.
  Use `--explain CODE` (e.g. `--explain E010`, `--explain E015`) for detailed remediation.
- `itree scan OWNER`: account-wide health, one line per issue-bearing repo.
- `itree init OWNER/REPO "Ledger: OWNER/REPO"`: create the root ledger for a repo that has no tree yet.
- `itree triage OWNER/REPO`: repair orphaned issues one at a time (absorb, attach, or close each).
- `itree new OWNER/REPO "Title" --under OWNER/REPO#PARENT [--body-file FILE]`: file a new work unit under a grouping issue.
  Without `--under` it creates nothing and prints the existing work units, valid grouping targets, and exact placement commands, so sub-PR items are absorbed rather than fragmented.
- `itree milestone OWNER/REPO "Title" --under OWNER/REPO#PARENT [--body BODY | --body-file FILE] [--issues OWNER/REPO#ISSUE ...]`: create one GitHub Milestone and its matching `Milestone: Title` grouping issue under an explicit parent.
  Omitting `--under` is a non-mutating placement inquiry: the command prints existing milestone ledgers, valid grouping targets, and an exact invocation, then exits nonzero.
  Each supplied work unit moves beneath the new ledger in argument order — attach when parentless, replace its parent when already placed — and receives the new milestone assignment.
  This is one preflighted orchestration command, not a GitHub transaction: preflight failure changes nothing; after mutation begins, the command stops at the first failure without rollback and distinguishes confirmed operations, untouched operations, and an indeterminate current operation.
  Partial state is never reported as success.
  Recovery always starts with a live GitHub/tree reread.
  If installed `itree --help` does not list `milestone`, stop; do not construct a manual fallback.
- `itree absorb OWNER/REPO#SOURCE --into OWNER/REPO#UNIT` (or `--into OWNER/REPO#UNIT --title "..." --body-file FILE` for not-yet-filed content): merge sub-PR content into a work unit verbatim; the source issue is cross-linked, detached, and closed as duplicate.
- `itree attach OWNER/REPO#PARENT OWNER/REPO#CHILD`: attach an existing issue as a child of a grouping issue.
- `itree move OWNER/REPO#CHILD --under OWNER/REPO#PARENT [--before SIBLING | --after SIBLING]`: reparent or reorder an issue.
- `itree close OWNER/REPO#N --reason completed`: close a finished work unit.

## Hard gates

- **Completion includes PR state when a PR exists.** A PR-scoped task is not complete while reviewer-facing PR checklist items are open, or before the automated review loop has been explicitly triggered and returned feedback dispositioned.
  Report any undone step as incomplete required work; do not write a completion report over it.

- **No planning in draft PRs.** Use the work-unit issue as the draft planning surface.
  Do not open a draft PR merely to hold scope, plans, proof obligations, or task checklists.

- **No readiness laundering.** Do not request review until every reviewer-facing obligation is complete and evidenced.
  If later feedback reopens required work, update the work-unit issue and PR body before requesting review again.

- **Push before handoff.** Push after committing before claiming completion and before any handoff after substantive work.
  A local-only commit is not remotely auditable; if push fails, report the exact failure.

- **CI failures ≠ review comments.** CI failures may be fixed mechanically after root-cause diagnosis.
  Review comments must first be routed through `pr-feedback-triage`; do not auto-fix a review comment merely because it is unresolved.

- **Disposition is judgment, not process.** Never treat `NOT RESOLVED: 0`, green checks, or a clean scanner as proof that review advice was understood.
  Never resolve a thread without a visible reply recording disposition, evidence, and policy reasoning.
  Never reply "fixed/addressed/accepted" without committed remediation.

- **Owned-repo defects go to GitHub.** A small observed defect, inefficiency, false green, or recurring paper cut in an owned repo is either fixed in the current work unit or filed as a labeled issue — never left as chat residue.
  Do not file speculative bugs.

## Structure

- [references/pr-lifecycle.md](./references/pr-lifecycle.md) — the full PR worker guide and branch → commit → push → CI → merge mechanics: work-unit issue admission gate, reviewer-facing PR synthesis, TDD-before-implementation, exhaustive review reading, review-log discipline, CI monitoring and auto-fix, mark-ready, merge, and integration/handoff push cadence.

- [references/pr-review-disposition.md](./references/pr-review-disposition.md) — consuming and disposing of returned review feedback: `extract_unresolved_issues` command forms, the four-way disposition model, thread-reply required fields, the deletion-disposition format, top-level ledger requirement, banned PR-review behaviors, the overloaded "resolve" table, and Jules review delegation.

- [references/issue-workflow.md](./references/issue-workflow.md) — issue filing, labels, templates, the owned-repo improvement loop, and the view/create/manage/triage CLI mechanics (gh and curl).

- [references/code-review.md](./references/code-review.md) — *performing* code reviews on local changes and PRs: pre-push review, PR review on GitHub, review delegation to the policy skills, and the end-to-end review workflow.
