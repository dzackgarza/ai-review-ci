# Issue Workflow (Filing, View, Create, Manage, Triage)

Issue tracking at integration time: the owned-repo improvement loop, filing rules and templates, labels, and the CLI mechanics for viewing, creating, managing, and triaging issues.
Sourced from the `git-guidelines` Issue Workflow section and `issues.md`.

For planning-tree issues — roadmap, phase, feature, story, proof obligation, or work-unit node — load `plan` and read its `references/externalization.md` before creating or restructuring anything.
The model is: GitHub issues are the planning drafts.
Put stories, plans, proof obligations, acceptance criteria, blocker state, and implementation checklists in the issue body or comments.
Use child issues only for separate work units, never for ordinary implementation tasks.

## Creation Routing by Ownership

The examples below abbreviate `uvx --from git+https://github.com/dzackgarza/itree itree` to `itree`.

A repository is `itree`-governed when planned work lives in one rooted, ordered GitHub issue tree.
Confirm that ownership from repository guidance and `itree doctor OWNER/REPO`. A missing root does not authorize raw creation; initialize the tree or obtain an explicit decision that the repository is outside `itree` governance.

In a governed repository:

- create a work unit with `itree new` and an explicit `--under` grouping parent;
- create a GitHub Milestone and its matching ledger with `itree milestone` and an explicit `--under` grouping parent;
- use raw `gh issue create`, direct issue POSTs, or manual GitHub Milestone construction only when the repository is explicitly not `itree`-governed.

Omitting `--under` is a placement inquiry, never a default-to-root mutation.
`itree new` prints existing work units, grouping targets, and exact placement commands without creating an issue.
`itree milestone` likewise creates nothing, prints existing milestone ledgers, valid grouping targets, and an exact invocation, then exits nonzero.

## Owned Repo Improvement Loop

For repos owned by this system, observed defects should not remain as chat residue or private notes.
If an app, tool, plugin, QC gate, or agent workflow has a small observed error, inefficiency, false green, confusing edge case, or recurring paper cut, do one of these before handoff:

- fix it in the current coherent work unit and commit the fix;
- file a GitHub issue on the owning repo with evidence and concrete expected behavior;
- if ownership or scope is ambiguous, ask the user where to file it.

Do not file speculative bugs.
Do not create issues for vague dissatisfaction without an observed example.
Do not bury observed owned-repo defects only in memory; memory can note the durable lesson, but the actionable project gap belongs on GitHub.

## Filing Issues

**All issues must be labeled immediately upon creation.**

For an `itree`-governed repository, create beneath the selected grouping issue, then apply the required label to the returned issue reference before any other action:

```bash
itree new OWNER/REPO "Title" --under OWNER/REPO#PARENT --body-file issue.md
gh issue edit NEW_ISSUE --repo OWNER/REPO --add-label "<label>"
```

For a repository explicitly outside `itree` governance, use the raw GitHub route:

```bash
gh issue create --repo <owner>/<repo> --title "..." --body-file issue.md --label "<label>"
```

For roadmap, feature, PRD, or cross-agent planning issues, first load the `plan` skill's `references/externalization.md`. Create story-shaped work-unit issues, use native sub-issues only for grouping and separate work-unit edges, use dependencies only for blockers, assign the GitHub Milestone that owns the delivery slice, and keep live planning state on the issue body/comments.

**Mandatory Issue Rules:**

1. **Deep description**: Explain exactly what is happening or missing.

2. **Proof**: Include relevant logs, outputs, error traces, or code snippets that PROVE the issue exists.
   Provide as many clear examples as possible.

3. **Concrete Expectations**: Describe new designs, specs, and expected behavior.
   Include TDD-style pseudocode showing what the expected new behavior looks like.
   Do not list "benefits".

4. **Informative Only**: Use plain, technical language.
   No marketing or selling language.

5. **No Implementation Code**: Do NOT attempt to write the actual code to fix the problem in the issue body.
   The issue may carry the plan, checklist, proof obligations, and design decisions, but not a pasted implementation.

6. **Work-Unit Plan Lives Here**: For work-unit issues, include the live plan directly in the issue body or comments.
   Use issue checklists and comments for implementation tasks, proof status, decisions, and blockers.
   Do not create child issues for ordinary implementation tasks and do not open a draft PR to hold this state.

7. **No Time Estimates**: NEVER include time estimates.

**Minimal Issue Template:**

Create a local `.md` file for the body.
Pass it to `itree new ... --body-file` in a governed repository, or to `gh issue create --body-file` only in a repository explicitly outside `itree` governance:

```markdown
# Description

<Deep description of the problem or feature>

# Evidence

<Logs, outputs, or code proving the issue exists. Clear examples.>

# Expected Behavior

<Concrete expectations. TDD-style pseudocode.>

# Acceptance Criteria

<Observable criteria that make the issue complete.>

# Proof Obligations

<Tests, commands, screenshots, logs, or live checks required to prove completion.>

# Implementation Tasks

- [ ] <Task tracked on this issue, not as a child issue>
```

## Available Labels

- `bug`: Observed bugs, failures, or incorrect behavior.

- `enhancement`: Feature requests, improvements, or design ideas.

- `documentation`: Improvements or additions to documentation.

**Mandatory**: If an observed owned-repo defect, inefficiency, false green, or recurring paper cut cannot be fixed in the current coherent work unit, log it as an issue on the owning repo.
Do not file speculative concerns; frame observed improvement ideas as `enhancement` when they are not bugs.

* * *

# CLI Mechanics (View, Create, Manage, Triage)

The rest of this file is mechanics only, consolidated from the former `github-issues` skill.

## Setup

```bash
if command -v gh &>/dev/null && gh auth status &>/dev/null; then
  AUTH="gh"
else
  AUTH="git"
  if [ -z "$GITHUB_TOKEN" ]; then
    if [ -f ~/.hermes/.env ] && grep -q "^GITHUB_TOKEN=" ~/.hermes/.env; then
      GITHUB_TOKEN=$(grep "^GITHUB_TOKEN=" ~/.hermes/.env | head -1 | cut -d= -f2 | tr -d '\n\r')
    fi
  fi
fi

REMOTE_URL=$(git remote get-url origin)
OWNER_REPO=$(echo "$REMOTE_URL" | sed -E 's|.*github\.com[:/]||; s|\.git$||')
OWNER=$(echo "$OWNER_REPO" | cut -d/ -f1)
REPO=$(echo "$OWNER_REPO" | cut -d/ -f2)
```

* * *

## 1. Viewing Issues

**With gh:**
```bash
gh issue list
gh issue list --state open --label "bug"
gh issue list --assignee @me
gh issue list --search "authentication error" --state all
gh issue view 42
```

**Without gh:**
```bash
# List open issues
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$OWNER/$REPO/issues?state=open&per_page=20" \
  | python3 -c "
import sys, json
for i in json.load(sys.stdin):
    if 'pull_request' not in i:
        labels = ', '.join(l['name'] for l in i['labels'])
        print(f\"#{i['number']:5}  {i['state']:6}  {labels:30}  {i['title']}\")"

# View a specific issue
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/issues/42 \
  | python3 -c "
import sys, json
i = json.load(sys.stdin)
labels = ', '.join(l['name'] for l in i['labels'])
print(f\"#{i['number']}: {i['title']}\")
print(f\"State: {i['state']}  Labels: {labels}\")
print(f\"\n{i['body']}\")"
```

## 2. Creating Issues Outside `itree` Governance

The raw creation routes in this section apply only after the repository has been explicitly classified as outside `itree` governance.
In a governed repository, use `itree new ... --under ...` from [Creation Routing by Ownership](#creation-routing-by-ownership).

**With gh (explicitly non-`itree`-governed repositories only):**
```bash
gh issue create \
  --title "Login redirect ignores ?next= parameter" \
  --body "## Description\nAfter logging in, users always land on /dashboard." \
  --label "bug,backend" \
  --assignee "username"
```

**Without gh:**
```bash
curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/issues \
  -d '{
    "title": "Login redirect ignores ?next= parameter",
    "body": "## Description\nAfter logging in, users always land on /dashboard.",
    "labels": ["bug", "backend"],
    "assignees": ["username"]
  }'
```

## 3. Managing Issues

### Add/Remove Labels

```bash
gh issue edit 42 --add-label "priority:high,bug"
gh issue edit 42 --remove-label "needs-triage"
```

**Without gh:**
```bash
curl -s -X POST -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/issues/42/labels \
  -d '{"labels": ["priority:high", "bug"]}'

curl -s -X DELETE -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/issues/42/labels/needs-triage
```

### Assignment

```bash
gh issue edit 42 --add-assignee username
```

### Parent and Sub-Issues

Use native sub-issues for tree edges when the repository's GitHub surface supports them.
Do not use labels, title numbering, or dependencies to simulate ordinary parent/child order.
Do not create sub-issues for implementation tasks inside one work unit.
Put those tasks in the parent issue body or comments.

**With itree (Recommended):** To manage parent/child relationships programmatically, use the `itree` CLI:
```bash
# Create a new child work-unit issue under an organizational parent.
itree new OWNER/REPO "Title of new child" --under OWNER/REPO#PARENT_NUMBER --body-file issue.md

# Attach an existing child work-unit issue under an organizational parent.
itree attach OWNER/REPO#PARENT_NUMBER OWNER/REPO#CHILD_NUMBER

# Reparent or reorder an issue (under a parent, optionally before/after a sibling).
itree move OWNER/REPO#CHILD_NUMBER --under OWNER/REPO#PARENT_NUMBER [--before OWNER/REPO#SIBLING_NUMBER | --after OWNER/REPO#SIBLING_NUMBER]
```

**With gh (explicitly non-`itree`-governed repositories only):**
```bash
# Create a new child work-unit issue under an organizational parent.
gh issue create --title "<child story or work-unit node>" --body-file issue.md --parent 42

# Attach or detach existing issues.
gh issue edit 42 --add-sub-issue 43
gh issue edit 42 --remove-sub-issue 43

gh issue edit 43 --parent 42
gh issue edit 43 --remove-parent
```

### Dependencies

Use dependencies for blockers, not roadmap traversal order.

For an `itree`-governed repository, create the work unit under its grouping parent, then record the blocker on the returned issue:

```bash
itree new OWNER/REPO "<blocked work>" --under OWNER/REPO#PARENT --body-file issue.md
gh issue edit NEW_ISSUE --repo OWNER/REPO --add-blocked-by 41
```

For a repository explicitly outside `itree` governance, raw creation may carry the dependency directly:

```bash
gh issue create --title "<blocked work>" --body-file issue.md --blocked-by 41
gh issue edit 42 --add-blocked-by 41 --add-blocking 44
gh issue edit 42 --remove-blocked-by 41 --remove-blocking 44
```

### Milestones

Milestones are delivery/progress buckets over issues and PRs.
They do not replace the issue tree.

In an `itree`-governed repository, create the GitHub Milestone and its matching ledger together:

```bash
itree milestone OWNER/REPO "<milestone>" \
  --under OWNER/REPO#GROUPING_PARENT \
  --body-file milestone.md \
  --issues OWNER/REPO#FIRST OWNER/REPO#SECOND
```

`--issues` is not metadata-only assignment.
In argument order, each distinct, open, same-repository work-unit leaf moves beneath the new ledger and receives the new milestone: a parentless issue uses attach semantics, and an already placed issue uses replace-parent semantics.

The command is one preflighted orchestration, not a cross-resource GitHub transaction.
A preflight failure performs no writes.
Once mutation starts, the command stops at the first failed operation, performs no rollback or compensating close, and reports three separate sets: operations confirmed complete, operations confirmed untouched, and the current operation if its remote outcome is indeterminate after a timeout, interruption, or unusable response.
Partial state is never reported as success.
Recovery begins by rereading the live GitHub Milestone, issue, parentage, sibling order, and milestone-assignment state; never infer remote state from a lost response.

If installed `itree --help` does not list `milestone`, stop.
Do not replace the command with raw `gh api` construction.

For a repository explicitly outside `itree` governance, existing GitHub issue milestone assignment remains available:

```bash
gh issue edit 42 --milestone "<milestone>"
```

### Commenting

```bash
gh issue comment 42 --body "Investigated — root cause is in auth middleware."
```

### Closing and Reopening

```bash
gh issue close 42
gh issue close 42 --reason "not planned"
gh issue reopen 42
```

### Linking Issues to PRs

Issues close automatically when a PR merges with these keywords in the body:
```
Closes #42
Fixes #42
Resolves #42
```

## 4. Issue Triage Workflow

1. **List untriaged issues:**
```bash
gh issue list --label "needs-triage" --state open
```

2. **Read and categorize** each issue
3. **Apply labels and priority**
4. **Assign** if the owner is clear
5. **Comment with triage notes** if needed

## 5. Bulk Operations

```bash
# Close all issues with a specific label
gh issue list --label "wontfix" --json number --jq '.[].number' | \
  xargs -I {} gh issue close {} --reason "not planned"
```

## Quick Reference

| Action | CLI | API endpoint |
| --- | --- | --- |
| List issues | `gh issue list` | `GET /repos/{o}/{r}/issues` |
| View issue | `gh issue view N` | `GET /repos/{o}/{r}/issues/N` |
| Create governed work unit | `itree new ... --under ...` | `itree`-owned orchestration |
| Create issue outside `itree` governance | `gh issue create ...` | `POST /repos/{o}/{r}/issues` |
| Create governed milestone and ledger | `itree milestone ... --under ...` | `itree`-owned orchestration |
| Add labels | `gh issue edit N --add-label ...` | `POST /repos/{o}/{r}/issues/N/labels` |
| Assign | `gh issue edit N --add-assignee ...` | `POST /repos/{o}/{r}/issues/N/assignees` |
| Attach governed issue | `itree attach PARENT CHILD` | `itree`-owned orchestration |
| Move governed issue | `itree move CHILD --under PARENT` | `itree`-owned orchestration |
| Add sub-issue outside `itree` governance | `gh issue edit PARENT --add-sub-issue CHILD` | Use GitHub CLI native sub-issue support |
| Add blocker | `gh issue edit N --add-blocked-by BLOCKER` | Use GitHub CLI native dependency support |
| Set milestone outside `itree` governance | `gh issue edit N --milestone "<milestone>"` | `PATCH /repos/{o}/{r}/issues/N` |
| Comment | `gh issue comment N --body ...` | `POST /repos/{o}/{r}/issues/N/comments` |
| Close | `gh issue close N` | `PATCH /repos/{o}/{r}/issues/N` |
| Search | `gh issue list --search "..."` | `GET /search/issues?q=...` |
