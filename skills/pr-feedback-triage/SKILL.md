---
name: pr-feedback-triage
description: Use when collecting, judging, remediating, replying to, resolving, or converging returned pull-request review feedback. Owns the thread-local policy-routed workflow; generating review findings belongs elsewhere.
---

# PR Feedback Triage

This is the single entrypoint for returned PR feedback. A review comment is a claim to
evaluate, not an instruction to implement and not an administrative obstacle to clear.

The review thread or comment surface is the audit trail. Do not create a top-level
disposition ledger or a tracked review-ledger file. Those detach the judgment from the
finding and are not substitutes for a reply on the finding's own surface.

## Role firewall

Keep these roles separate:

- **A — controller:** collects live feedback, preserves stable identities, routes work,
  verifies landed remediation, and resolves only after the required reply exists.
- **B — disposition:** judges each claim and suggested fix against the code, literal owner
  statements, and [[policy-index/SKILL|canonical policy]]. B proposes no remediation.
- **C — remediation:** receives a first-principles specification, the exact governing
  `POLICY.*` codes, and the relevant [[style-guide/SKILL|style-guide cards]]. C does not
  receive the reviewer's wording or B's fix ideas.

A may batch findings within B or C when context and ownership permit. Batched processing
never permits grouped judgments: every finding gets its own disposition and its own reply.

## Routed workflow

Load only the stage currently being executed:

1. [[pr-feedback-triage/references/collect|Collect and identify every live feedback item]]
2. [[pr-feedback-triage/references/disposition|Disposition each claim and proposed fix]]
3. [[pr-feedback-triage/references/remediation|Translate accepted findings into policy-routed remediation]]
4. [[pr-feedback-triage/references/thread-resolution|Verify, commit, reply on the thread, and resolve]]
5. [[pr-feedback-triage/references/convergence|Re-scan and repeat until the review window converges]]

Each reference owns its stage. Integration guides, AGENTS fragments, PR templates, and
reviewer guidance should route here rather than restating the state machine or reply
formats.

## Hard gates

- Never resolve an inline thread without first posting a visible reply on that thread.
- Never post a positive disposition until the remediation is committed and the reply
  cites the commit and proof.
- Policy-governed judgments cite exact `POLICY.*` codes. When no policy governs, use an
  explicit factual/contract basis with a source anchor; do not invent a policy code.
- A rejected finding records the evidence that defeats it and an explicit non-change.
- Duplicate and outdated findings point to the canonical thread or superseding commit.
- `Investigate before action` is an open state, never a resolvable disposition.
- Green checks, zero unresolved counts, and a clean scanner are receipts, not evidence
  that the feedback was understood.
- If feedback reopens the PR's issue contract or proof burden, update the owning issue and
  readiness state before continuing.

## Optional review producer

When the user explicitly asks Jules to generate review feedback, load
[[jules/SKILL|jules]] and [[jules/references/anti-slop-report-review|its anti-slop review reference]] together with
[[reviewing-llm-code/SKILL|reviewing-llm-code]], [[anti-slop/SKILL|anti-slop]],
[[reviewing-subagent-work/SKILL|reviewing-subagent-work]], and
[[test-guidelines/SKILL|test-guidelines]] when proof surfaces are in scope. Jules produces
raw findings only. Every returned finding still enters this workflow at
[[pr-feedback-triage/references/collect|collection]]; Jules does not disposition or
resolve its own output.

## Completion

The feedback phase is complete only when every current surface has been re-read, every
substantive item has a thread- or surface-local disposition, accepted work is committed
and proven, no required thread is open, and a fresh scan finds no new or pending item.
