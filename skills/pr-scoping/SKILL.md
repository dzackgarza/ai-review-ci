---
name: pr-scoping
description: Use before drafting, scoping, or opening any pull request, and when triaging a backlog into units of work. Forces PRs to be scoped as significant work units that close constellations of related issues, and bans the trivial single-nudge PRs agents default to.
---

# PR Scoping: Significant Work Units, Not Nudges

## The failure mode this skill exists to kill

Agents left to their own priors carve out the **minimum defensible diff**: one
symptom, one file, one caller, ten lines. Each such PR burns a full review
cycle — CI runs, automated review, feedback triage, thread gardening, human
attention, merge — on a change that moved the project almost nowhere. Meanwhile
the epics naming the actual root causes sit open and untouched, because every
agent that visits the repo shaves off another sliver instead of doing the
rewrite that would close the whole cluster.

Observed steady state of this failure: fifteen single-fix PRs merged in a week
(`fix(threads): skip already-threaded findings`, `fix(gates): auto-resolve
stale proof threads`, `fix(qc): retire unused dependency blocking`, ...) while
five epic work-units sat open the entire time. Millions of tokens spent on
review overhead; the architecture unchanged.

**Review overhead is per-PR and roughly constant.** A 10-line PR costs nearly
as much to shepherd through the loop as a 1,000-line PR. Ten timid PRs cost
~10× the review budget of one ambitious PR that closes the same ground — and
deliver less, because the ten nudges never remove the root cause that keeps
generating new symptoms.

Timidity is not safety. It is the most expensive possible way to work.

## The unit of work is the constellation, not the issue

Before drafting any PR:

1. **Cluster first.** Read the open issues, review findings, and epics. Group
   them by shared root cause: same subsystem, same design defect, same missing
   abstraction, same class of symptom. That cluster — not any single member —
   is the candidate unit of work.
2. **Ask the obviation question.** Is there a rewrite, consolidation, or
   design change that makes the whole cluster impossible rather than
   individually patched? If yes, **that rewrite is the PR.** The rewrite is
   the *smaller* change when measured in total system cost: one review cycle
   instead of N, and the symptom generator removed instead of throttled.
3. **Scope the PR as a claim against the cluster.** The PR body names the
   issues it closes, the epic or subtree it advances, and the class of future
   findings it obviates. `Closes #a, #b, #c; advances epic #z` is the expected
   shape.

## The significance floor

Every PR must satisfy at least one of:

- **Closes multiple related issues** (or a whole subtree) via a shared-cause
  fix, or
- **Is a structural change** that removes a symptom generator — a rewrite,
  boundary change, or consolidation that obviates a class of findings, not an
  instance, or
- **Carries an explicit atomicity justification** in the PR body: one or two
  sentences proving the change is genuinely isolated — no sibling symptoms, no
  parent epic, no cluster it could join. Silence is not justification.

If a change fails the floor, it does not ship alone. It rides along inside the
significant PR whose territory it belongs to, or it waits until that PR forms.

## Banned scopes

- **`partial #x` as a PR scope.** A PR that partially addresses an issue and
  leaves the rest open is a nudge wearing a claim. Take the whole issue or
  take the subtree containing it.
- **Fixing one caller when siblings share the bug.** The lazy fix and the
  root-cause fix are the same fix: one change where all callers route through.
  Patching only the path the finding named leaves every sibling broken and
  guarantees N follow-up PRs.
- **Patching a symptom while the epic naming its cause sits open.** If a
  review finding is an instance of an open epic, the PR claims the epic's
  next coherent slice — not the instance.
- **Splitting a coherent rewrite into "safer" sequential slices.** Slices of
  one design change are not independently reviewable anyway; each slice-PR
  re-pays the full review cost and the intermediate states are dead weight.
  Ship the rewrite as one PR with a clear narrative.
- **One-finding remediation PRs.** Review findings arrive in batches; their
  remediations ship in batches, grouped by root cause.

## What this does NOT license

Significance is measured in **cohesion × consequence**, not line count.

- **No unrelated-change dumping.** A big PR is one root cause and all its
  symptoms — not a grab bag of every open nit. If two clusters have different
  root causes, they are two PRs.
- **No scope-laundering.** "While I'm here" additions that don't serve the
  claimed cluster are still banned. Ambition means claiming the whole cluster,
  not annexing neighbors.
- **Cohesion is the reviewability contract.** A 2,000-line PR with one design
  narrative ("moved all finding delivery through the state machine; closes
  #42, #140, #141, #144") is *more* reviewable than ten disconnected 40-line
  PRs, because the reviewer holds one idea instead of ten contexts.

## Self-check before opening

Answer these; if any answer is wrong, re-scope:

1. What constellation does this PR close? (Naming one issue = probable nudge.)
2. What symptom generator does it remove? ("None, it patches an instance" =
   re-scope to the generator.)
3. Would a sibling of this bug/finding still exist after merge? (Yes = the PR
   is scoped to the wrong altitude.)
4. Is there an open epic this change is secretly a sliver of? (Yes = claim the
   epic's slice instead.)
5. If you opened five PRs of this size this week, would the backlog be
   meaningfully smaller? (No = you are burning review cycles, not working.)
