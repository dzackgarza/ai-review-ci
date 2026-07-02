# PR Review Disposition

How to consume, judge, and dispose of returned review feedback on a PR. This is the
enforcement surface for the "trigger review → disposition feedback" leg of the
integration lifecycle. Sourced from the `git-guidelines` PR Review Workflow section.

For consuming, triaging, or acting on existing review comments as a firewalled loop, this
skill routes to `pr-feedback-triage` (advisory, in `~/ai`). This file owns the enforced
disposition doctrine that `pr-feedback-triage` operationalizes.

## Completion gate

For nontrivial features: branch + draft PR tracks implementation while work is still
incomplete. Completion is not local implementation; it includes GitHub PR state.

A PR-scoped task is not complete until:

- the branch is pushed and the PR body or claim map is current;
- the PR is no longer draft (`gh pr ready <PR_NUMBER>`);
- the automated review loop has been explicitly triggered (`gh pr comment <PR_NUMBER>
  --body '@codex review'`, or the repo's documented equivalent);
- returned review and check feedback has been scanned with `extract_unresolved_issues`
  and routed through `pr-feedback-triage`, or a real blocker has been reported.

Do not write a completion report while any of those remain undone. Report the missing
PR-state or review-loop step as incomplete required work.

## extract_unresolved_issues: scan all PR feedback first

Before reading any PR comments manually, **scan all feedback surfaces at once** using
the bundled CLI tool. This is the primary entry point for handling PR feedback — it
automatically pulls inline review threads, issue-style comments, and automated check-run
errors in a single command.

```bash
# Summarize all feedback on a PR
uv run --directory ~/ai/opencode/skills/git-guidelines/scripts/extract_unresolved_issues \
    -m extract_unresolved_issues summarize <owner>/<repo>#<N>

# Get only unresolved (actionable) issues
uv run --directory ~/ai/opencode/skills/git-guidelines/scripts/extract_unresolved_issues \
    -m extract_unresolved_issues issues <owner>/<repo>#<N>
```

Usage from anywhere (full path to the module):
```bash
uv run -m extract_unresolved_issues --help
```

This tool pulls:
- Top-level PR comments
- Inline code review threads
- Automated check-run errors

After dispositioning feedback, resolve threads with a required justification:
```bash
uv run --directory ~/ai/opencode/skills/git-guidelines/scripts/extract_unresolved_issues \
    -m extract_unresolved_issues resolve <COMMENT_ID> \
    "Accepted in commit 1234abc. Reason: <why this satisfies the review concern>."
```

**The output is never stale.** Automated bots (Gemini, kilo-code-bot, and CI checks) update
comments in place when new commits land. Open threads stay listed until "Resolve
Conversation" is clicked. Every item requires disposition — there is no such thing as
an already-handled item that still appears.

**All checks, warnings, and notices must be resolved before the PR can be accepted.**
This includes low-severity notices from automated tools.

**Loop until the check clears:**
```bash
while true; do
    gh pr checks <N> --repo <owner>/<repo>
    uv run --directory ~/ai/opencode/skills/git-guidelines/scripts/extract_unresolved_issues \
        -m extract_unresolved_issues issues <owner>/<repo>#<N>
    sleep 90
done
```
Stop only when `gh pr checks` shows all green and `issues` reports `NOT RESOLVED: 0`.

## Publish review guidance before submission

Before opening a PR, updating a PR for review, or tagging automated reviewers, ensure
the target repo's local `AGENTS.md` contains the canonical review guidance from
the [Review Guidelines](https://github.com/dzackgarza/ai/wiki/Review-Guidelines) wiki page.

The [Review Guidelines](https://github.com/dzackgarza/ai/wiki/Review-Guidelines) wiki page is the durable source of truth.
The repo-local `AGENTS.md` copy is a required distribution copy because Codex and other
review agents read the target repo's local guidance.
Do not replace it with a link, summary, or paraphrase.

Required handling:

- If the target repo has no local `AGENTS.md`, create one containing the canonical
  `# Review Guidelines` section from the [Review Guidelines](https://github.com/dzackgarza/ai/wiki/Review-Guidelines) wiki page.

- If local `AGENTS.md` already has a top-level `# Review Guidelines` section, replace
  that section with the current contents of the [Review Guidelines](https://github.com/dzackgarza/ai/wiki/Review-Guidelines) wiki page.

- If local `AGENTS.md` lacks that section, append the current contents of
  the [Review Guidelines](https://github.com/dzackgarza/ai/wiki/Review-Guidelines) wiki page.

- Do not create duplicate `# Review Guidelines` sections.

- Verify with `git diff` that the section is present, current, and the only local
  `AGENTS.md` change unless the user requested other edits.

If repo policy or permissions prevent updating local `AGENTS.md`, do not request review
yet. Report the blocker and the exact repo policy or permission issue.

## Review feedback is a judgment task

Review comments are not administrative obstacles to clear.
They are claims about the work that must be understood, accepted or rejected, and made
legible to the human maintainer.

Before resolving a thread, reporting a PR as clean, or moving to check polling, you must
be able to state:

> The reviewer is asking us to change or believe ___. The repo rule or project norm in
> tension is ___. The purpose of that rule is ___. My disposition is ___ because ___.
> The user can audit this in ___.

If you cannot fill those blanks with concrete evidence from the diff, source, repo
policy, or review text, you have not handled the feedback.
Read more, inspect the code, or stop and report the blocker.

Use Socratic pressure to test the disposition:

- What would be false or missing if I simply marked this resolved?

- What evidence would convince the user that I understood the suggestion?

- Which repo rule's purpose would be harmed by literal compliance?

- Which repo rule's purpose would be harmed by ignoring the suggestion?

- If I reject this advice, what concrete source or policy fact defeats it?

If any answer is scanner status, check status, process compliance, or a claim that a bot
will re-review later, stop.
That is not judgment.

## Positive disposition requires committed remediation

Never reply "accepted," "aligned," "fixed," "addressed," or "will address" to a review
thread unless the remediation is already committed.

Accepted feedback follows this sequence:
1. classify the claim internally;
2. write first-principles remediation spec;
3. assign independent remediation subagent;
4. review the subagent output against the spec and banned-pattern catalogs;
5. commit the accepted remediation;
6. only then reply and resolve the thread with commit/proof anchors.

A thread cannot be resolved on intent.

## Top-level ledger requirement

Before resolving any rejected or modified feedback thread, ensure the disposition appears
in a top-level PR comment titled `Review feedback disposition ledger`.

## Split feedback from remediation

Every review item has two separable claims:

1. The feedback claim: what is allegedly wrong?
2. The suggested remediation: what change is being proposed?

Classify both. A true claim does not make the proposed fix acceptable.
A bad proposed fix does not make the underlying claim false.

Disposition options:
- Accepted as written
- Accepted with modified remediation
- Rejected
- Investigate before action

## Interpret policy by purpose

Repo rules exist to protect the work, not to excuse abandoning it.
When review feedback conflicts with a literal reading of repo guidance, do judicial
analysis:

- Identify the substantive concern raised by the reviewer.

- Identify the literal repo rule, hook, or policy that appears to block the fix.

- State the purpose of that rule.

- Decide which action best preserves that purpose and the project objective.

- Leave the reasoning in the thread response or commit message.

Some correct decisions may contradict a literal reading of a repo rule.
That is allowed only when the decision preserves the rule's purpose, is source-backed,
and leaves a clear audit trail.
Never use this to bypass hard safety constraints such as secrets handling, destructive
git operations, or explicit user refusal.

## Thread responses are audit notes for users

A review reply is not a conversation with the bot.
Automated reviewers usually will not return to debate the point.
Write every reply for the human maintainer who needs to understand exactly why the
suggestion was accepted, modified, or rejected.

Each substantive reply must include:

- Disposition: accepted, accepted with modification, or rejected.

- Reason: the source evidence, repo policy, and tradeoff that determined the decision.

- Audit anchor: the commit, file, line, command output, or linked issue where the user
  can verify the disposition.

- Policy interpretation: when repo guidance is involved, explain how the action follows
  the spirit of the rule, not merely its literal text.

Visible thread reply must state:

- Claim disposition:
- Remediation disposition:
- Policy basis:
- Code/action taken or explicit non-change:
- Audit anchor:

A PR thread resolved by deletion must not say only "removed." It must follow the deletion disposition format:

- Deleted artifact:
- Original burden:
- Burden disposition:
  - solved by:
  - invalidated by:
  - transferred to:
  - remains open in:
- Verification:

Do not write replies like "fixed", "done", "addressed", "acknowledged", or "will follow
up" unless the surrounding text contains the actual disposition and evidence.
Do not address the reviewer as if it is waiting to chat.

Never resolve a review thread without first posting a visible human-readable reply on
that thread. The resolve-tool justification is not an audit trail; it is hidden from the
user in the normal PR reading flow.
Resolving without a visible reply hides feedback and is banned, even if the code was
changed correctly.

## Banned PR-review behavior

- Treating `NOT RESOLVED: 0`, green checks, or a clean scanner as proof that review
  advice was understood.

- Treating a hook, policy, or tool rejection as a terminal reason to abandon
  source-backed feedback without interpreting the rule's purpose.

- Resolving a review comment without a visible thread response that records the
  disposition, evidence, and policy reasoning.

- Resolving a thread before the code, commit message, or thread response shows the
  disposition and reasoning.

- Polling checks while any review, top-level comment, check annotation, or summary
  comment has not been substantively dispositioned.

- Reporting "remaining: none" when only inline threads were scanned.

- Laundering feedback through process language such as "scanner clean", "thread
  resolved", or "bot pending" instead of stating the judgment made.

## "Resolve" is overloaded — clear each surface separately

| Object | How to resolve |
| --- | --- |
| Inline review thread | Reply in thread + resolve via GraphQL |
| Top-level PR comment | Reply on comment surface (no resolution bit) |
| Review summary comment | Reply on PR comment surface |
| Linked GitHub issue | Update/comment/close the issue itself — PR-thread resolution does NOT close the issue |

## After replying or resolving

Rerun the full PR scan AND the relevant issue scan.
Bots can post follow-up comments after your reply.

```bash
gh issue view <N> --repo <owner>/<repo> --json state,title,url
gh api repos/<owner>/<repo>/issues/<N>/comments
```

## Jules Review Delegation

If the user asks to use Jules for review, load:
- [jules](file:///home/dzack/ai/opencode/skills/jules/SKILL.md)
- [jules/references/anti-slop-report-review.md](file:///home/dzack/ai/opencode/skills/jules/references/anti-slop-report-review.md)
- [reviewing-llm-code](file:///home/dzack/ai/opencode/skills/reviewing-llm-code/SKILL.md)
- [anti-slop](file:///home/dzack/ai/opencode/skills/anti-slop/SKILL.md)
- [reviewing-subagent-work](file:///home/dzack/ai/opencode/skills/reviewing-subagent-work/SKILL.md)
- `test-guidelines` if tests/QC/proof surfaces are in scope
- `pr-feedback-triage` if existing review comments are being evaluated
