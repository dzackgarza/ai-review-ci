---
name: git-integration-workflow
description: 'Use when integrating code at the GitHub boundary — creating or updating a PR, externalizing a plan into an issue tree, marking a PR ready, triggering automated review, dispositioning returned review/check feedback, merging, or filing and triaging issues. This is the enforced integration workflow, distinct from during-writing edit hygiene.'
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

**issue tree → draft PR → implement with TDD → mark ready → trigger review → disposition feedback → merge**

1. **Issue tree.** Externalize the finalized plan into GitHub's issue tree and GitHub Milestone scope *before* opening the PR. PR creation is a lossless projection of a finalized plan, not a second round of planning.
   If the work cannot be placed under an existing roadmap node, issue subtree, or a new top-level roadmap issue without inventing scope, behavior, acceptance criteria, proof burdens, milestone cuts, or dependency order, the plan is not ready — stop and repair the plan.
   See the admission gate in [references/pr-lifecycle.md](./references/pr-lifecycle.md).

2. **Draft PR.** Open the PR as `--draft` with a `.pr/PR_BODY.md` claim map derived from the tracked contract/issue tree, not from memory or the web form.
   Use closing keywords (`Closes`) only for issues this PR fully completes on merge; use `Refs` or prose for parents, partial claims, and deferred work.
   A visible open checkbox means the PR is not done.

3. **Implement with TDD.** Lock the target with failing verification before implementation exists: write a failing test/check, confirm it fails for the intended reason, implement the narrowest change, re-run, record the result.
   Keep the diff inside the declared boundary.
   Keep the PR draft while any in-scope claim item remains open.

4. **Mark ready.** Only after every claimed issue and proof obligation is complete and evidenced: push the branch, republish the PR body, then `gh pr ready <PR_NUMBER>`.

5. **Trigger review.** Explicitly start the automated review loop: `gh pr comment <PR_NUMBER> --body '@codex review'` (or the repo's documented equivalent).
   Before tagging reviewers, ensure the target repo's local `AGENTS.md` carries the canonical `# Review Guidelines` section.

6. **Disposition feedback.** Scan all feedback surfaces at once with `extract_unresolved_issues`, then route every item through `pr-feedback-triage`. Review feedback is a judgment task: each item gets an explicit four-way disposition, a visible human-readable thread reply, and — for rejected/modified items — a top-level disposition ledger entry.
   Positive disposition requires already-committed remediation.
   If feedback reopens required work, return the PR to draft.
   See [references/pr-review-disposition.md](./references/pr-review-disposition.md).

7. **Merge.** Merge (typically `gh pr merge --squash --delete-branch`) only when checks are green and every review surface has been substantively dispositioned.

## Traversal and issue tree management (itree)

For repositories that represent planned work as a single rooted ordered tree, use the `itree` tool located at `/home/dzack/ai-review-ci/tools/itree` to manage the issue tree and discover task ordering.

### How to invoke the tool via uv

Run the tool by pointing `uv` directly to the `itree` project directory:
```bash
uv run --project /home/dzack/ai-review-ci/tools/itree itree [subcommand]
```

### When to use itree

- **Before implementing**: Run `uv run --project /home/dzack/ai-review-ci/tools/itree itree next OWNER/REPO` to discover the next open task and its enclosing work unit.
  Focus development on the returned task, and open/use the branch corresponding to the enclosing work unit.
- **Before claiming completion**: Run `uv run --project /home/dzack/ai-review-ci/tools/itree itree doctor OWNER/REPO` to verify that the issue tree is well-formed (no unreachable issues, no singletons without justification, correct milestones, etc.). If doctor warnings exist, resolve them.
- **When creating a repository workspace**: Initialize the root ledger with `uv run --project /home/dzack/ai-review-ci/tools/itree itree root create OWNER/REPO --title "Ledger: OWNER/REPO"`.
- **When structuring work**: Attach issues with `itree attach` and move/reorder them with `itree move`.

### Key Commands

- `uv run --project /home/dzack/ai-review-ci/tools/itree itree next OWNER/REPO`: Find the next open leaf issue in preorder.
- `uv run --project /home/dzack/ai-review-ci/tools/itree itree doctor OWNER/REPO`: Verify the tree structure and list any warnings or errors.
  Use `--explain CODE` (e.g. `uv run --project /home/dzack/ai-review-ci/tools/itree itree doctor OWNER/REPO --explain E010`) to see detailed remediation steps.
- `uv run --project /home/dzack/ai-review-ci/tools/itree itree root create OWNER/REPO --title "..."`: Create a new root ledger issue.
- `uv run --project /home/dzack/ai-review-ci/tools/itree itree root declare OWNER/REPO --issue N`: Mark issue #N as the root ledger by appending the required marker.
- `uv run --project /home/dzack/ai-review-ci/tools/itree itree attach OWNER/REPO#PARENT OWNER/REPO#CHILD`: Attach an existing child issue under a parent.
- `uv run --project /home/dzack/ai-review-ci/tools/itree itree move OWNER/REPO#CHILD --under OWNER/REPO#PARENT [--before SIBLING | --after SIBLING]`: Reparent or reorder an issue.

## Hard gates

- **Completion includes PR state.** A PR-scoped task is not complete while the PR is draft, while required claim-map items are open, or before the automated review loop has been explicitly triggered and returned feedback dispositioned.
  Report any undone step as incomplete required work; do not write a completion report over it.

- **No draft-jumping.** Do not `gh pr ready` until every claimed item is complete and evidenced.
  If later feedback reopens required work, `gh pr ready --undo`.

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

- [references/pr-lifecycle.md](./references/pr-lifecycle.md) — the full PR worker guide and branch → commit → push → CI → merge mechanics: admission gate, claim-map body shape, TDD-before-implementation, exhaustive review reading, review-log discipline, CI monitoring and auto-fix, mark-ready, merge, and integration/handoff push cadence.

- [references/pr-review-disposition.md](./references/pr-review-disposition.md) — consuming and disposing of returned review feedback: `extract_unresolved_issues` command forms, the four-way disposition model, thread-reply required fields, the deletion-disposition format, top-level ledger requirement, banned PR-review behaviors, the overloaded "resolve" table, and Jules review delegation.

- [references/issue-workflow.md](./references/issue-workflow.md) — issue filing, labels, templates, the owned-repo improvement loop, and the view/create/manage/triage CLI mechanics (gh and curl).

- [references/code-review.md](./references/code-review.md) — *performing* code reviews on local changes and PRs: pre-push review, PR review on GitHub, review delegation to the policy skills, and the end-to-end review workflow.
