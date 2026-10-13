# Code Review (Performing Reviews)

Consolidated from the former `github-code-review` skill.

> This skill is for *performing* code reviews and generating review feedback.
> For consuming, triaging, or acting on returned review comments, route to [[pr-feedback-triage/SKILL|pr-feedback-triage]]. This review guide generates findings; it does not own their disposition or remediation.

## 1. Reviewing Local Changes (Pre-Push)

```bash
# Staged changes
git diff --staged

# All changes vs main
git diff main...HEAD

# File names only
git diff main...HEAD --name-only

# Stat summary
git diff main...HEAD --stat
```

### Review Strategy

1. **Get the big picture:**
```bash
git diff main...HEAD --stat
git log main..HEAD --oneline
```

2. **Review file by file** — use `read_file` for full context:
```bash
git diff main...HEAD -- src/auth/login.py
```

3. **Check for common issues:**
```bash
# Debug statements, TODOs, console.logs
git diff main...HEAD | grep -n "print(\|console\.log\|TODO\|FIXME\|HACK\|XXX\|debugger"

# Large files accidentally staged
git diff main...HEAD --stat | sort -t'|' -k2 -rn | head -10

# Secrets or credential patterns
git diff main...HEAD | grep -in "password\|secret\|api_key\|token.*=\|private_key"

# Merge conflict markers
git diff main...HEAD | grep -n "<<<<<<\|>>>>>>\|======="
```

4. **Present structured feedback.**

### Review Output Format

```
## Code Review Summary

### Critical
- **<file>:<line>** — <Critical finding>. Suggestion: <Remediation>.

### Warnings
- **<file>:<line>** — <Warning description>.

### Suggestions
- **<file>:<line>** — <Suggestion description>.

### Looks Good
- <What looks good>
```

* * *

## 2. Reviewing a Pull Request on GitHub

### View PR Details

**With gh:**
```bash
gh pr view 123
gh pr diff 123
gh pr diff 123 --name-only
```

**Without gh:**
```bash
PR_NUMBER=123

# PR details
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/pulls/$PR_NUMBER

# Changed files
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/pulls/$PR_NUMBER/files \
  | python3 -c "
import sys, json
for f in json.load(sys.stdin):
    print(f\"{f['status']:10} +{f['additions']:-4} -{f['deletions']:-4}  {f['filename']}\")"
```

### Check Out PR Locally

```bash
git fetch origin pull/123/head:pr-123
git checkout pr-123

# View diff against base
git diff main...pr-123
```

**With gh (shortcut):** `gh pr checkout 123`

### Leave Comments

**General PR comment — with gh:**
```bash
gh pr comment 123 --body "Overall looks good, a few suggestions below."
```

**Single inline comment:**
```bash
HEAD_SHA=$(gh pr view 123 --json headRefOid --jq '.headRefOid')

gh api repos/$OWNER/$REPO/pulls/123/comments \
  --method POST \
  -f body="<Feedback detail>" \
  -f path="<file_path>" \
  -f commit_id="$HEAD_SHA" \
  -f line=<line_number> \
  -f side="RIGHT"
```

### Submit a Formal Review

```bash
gh pr review 123 --approve --body "LGTM!"
gh pr review 123 --request-changes --body "See inline comments."
gh pr review 123 --comment --body "Some suggestions, nothing blocking."
```

* * *

## 3. Review Delegation

All code evaluation rules, anti-slop guidelines, and validation-evasion auditing are delegated to canonical policy skills:

- **Code Review Policy & Bridge-Burning**: `reviewing-llm-code` and its red-flag catalogs

- **PR Guidance & Triage**: `pr-feedback-triage`

- **Proof & Test Obligations**: `test-guidelines`

Always consult `policy-index` to find the canonical skill for any code review, testing, or remediation question.

When you need "how to review a suspect PR" — the slop field guide, bridge-burning red flags, and validation-evasion auditing — do NOT rebuild it here.
Load [[reviewing-llm-code/SKILL|reviewing-llm-code]] and [[anti-slop/SKILL|anti-slop]]. This file owns the review *mechanics*; those skills own the review *judgment*.

* * *

## 4. Pre-Push Review Workflow

1. `git diff main...HEAD --stat` — see scope of changes

2. `git diff main...HEAD` — read the full diff

3. For each changed file, use `read_file` for context

4. Apply the review checklist

5. Present findings (Critical / Warnings / Suggestions / Looks Good)

6. If critical issues found, offer to fix before push

* * *

## 5. PR Review Workflow (End-to-End)

### Step 1: Auth

Ensure authenticated (see `auth.md` in the `git-guidelines` skill, advisory in `~/ai`).

### Step 2: Gather PR context

```bash
gh pr view 123
gh pr diff 123 --name-only
gh pr checks 123
```

Retrieve the `semgrep-review-<run revision>` artifact from the QC run associated with the current PR head.
Check the run's `headSha` and, for a PR merge checkout, its head parent against the current PR head; inspect the report directory's revision.
An old run or absent required report is missing review input, not a clean scan.
For local review, the scanner prints its report directory under the caller's Git metadata for a clean committed caller.
An uncommitted caller prints a separate temporary report directory and claims no committed identity: rerun against the source being reviewed, and never use that report as evidence about a PR head.

Read every WARNING/INFO finding in `head.json`'s `results` and every scanner `warn`/`info` diagnostic in its `errors` before completing review.
Preserve and inspect the raw report's complete diagnostic type, message, path and spans.
For each scanner diagnostic, identify the affected source and rule, the analysis that did not complete, and the independent evidence needed to assess that gap; record its semantic disposition in the PR review.
A native nonfatal diagnostic allows publication but does not establish that the affected analysis succeeded.
A report explicitly marked `ai_review_ci.evaluation = "empty-domain"` records a successful selection of zero targets; a missing report, malformed report or failed evaluation supplies no such evidence.
Unresolved diagnostic dispositions leave independent review incomplete.

Read each finding's source context.
Apply the finding's canonical policy through `policy-index` and record its semantic disposition in the PR review: a demonstrated defect, an inapplicable heuristic with source evidence, or missing evidence.
A suffix match alone does not establish a mathematical shim.
A policy code on a warning does not turn it into a hard-failure remediation request.
Unresolved warning dispositions leave the independent review incomplete, even when deterministic checks pass.

### Step 3: Check out PR locally

```bash
git fetch origin pull/<PR_NUMBER>/head:pr-<PR_NUMBER>
git checkout pr-<PR_NUMBER>
```

### Step 4: Read the diff

```bash
git diff main...HEAD --name-only
git diff main...HEAD -- path/to/file.py
```

### Step 5: Run automated checks

```bash
just test-push
```

### Step 6: Apply review checklist (see Section 3 above)

### Step 7: Post the review

```bash
# If no issues
gh pr review <PR_NUMBER> --approve --body "Reviewed with no blocking findings."

# If issues found
gh pr review <PR_NUMBER> --request-changes --body "Blocking findings are recorded inline."
```

### Step 8: Also post a summary comment

```bash
gh pr comment <PR_NUMBER> --body "$(cat <<'EOF'
## Code Review Summary

**Verdict: <Approve | Comment | Changes Requested>**

### Critical
- **<file>:<line>** — <Critical finding>

### Warnings
- **<file>:<line>** — <Warning>

### Suggestions
- **<file>:<line>** — <Suggestion>

### Looks Good
- <Positive feedback>
EOF
)"
```

### Step 9: Clean up

```bash
git checkout main
git branch -D pr-<PR_NUMBER>
```

### Decision: Approve vs Request Changes vs Comment

- **Approve** — no critical or warning-level issues

- **Request Changes** — any critical or warning-level issue that should be fixed before merge

- **Comment** — observations and suggestions, nothing blocking
