---
name: pr-scoping
description: Use before drafting, scoping, or opening any pull request (including draft work-unit PRs), when deciding whether a change warrants a PR at all, and when triaging a backlog into units of work. Forces PRs to be scoped as significant work units that close constellations of related issues, routes small urgent repairs direct to main, and bans the trivial single-nudge PRs agents default to.
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

Timidity is not safety. It is the most expensive possible way to work. A
merged partial fix is worse than no PR: it leaves the tool in a mixed
half-fixed state that *generates* new issues, and every subsequent agent must
first reconstruct which issue text is stale, what partial progress landed,
and which symptoms remain — before doing any work. When inbound issue flow
exceeds the outbound fix rate, the repo is in churn, not progress.

The reward signal is **backlog burn-down per review cycle**, not landed PRs.
A landed PR that leaves its issue open moved the project backward.

## Two paths — there is no third

Every change takes exactly one of these routes:

1. **Direct to main.** Urgent crash relief, trivial fixes, doc/config nudges,
   behavioural updates — anything the owner would accept as a direct repair.
   No PR, no review loop. Add a regression test when cheap. If the crash is a
   symptom of an open root-cause issue, note the relief on that issue and
   leave it open.
2. **Review-loop PR.** Issue-complete, cluster-complete, or milestone-subtree
   work: rewrites, feature grafts, structural consolidations. Enough scope to
   justify the review cost.

The review loop is an expensive mechanism for validating substantial changes,
not a ritual for all changes. A small fix routed through the PR pipeline
burns a review budget sized for architecture on a traceback tweak. A
crash-fix-only PR is invalid unless the owner explicitly asks for one. Small
urgent repairs go to main; large coherent repairs go through review; small
timid PRs do not exist.

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
   These are bespoke owner-local tools (see `bespoke-software-policy`): no
   downstream consumers exist, so break internal APIs freely and rewrite the
   subsystem when that is simpler than preserving broken structure.
   "Bespoke" means *move aggressively* — not "be careful because policy
   exists."
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

If a change fails the floor, it does not become its own PR. It goes direct to
main if it qualifies for that path, rides along inside the significant PR
whose territory it belongs to, or waits until that PR forms.

## Draft work-unit PRs are scope artifacts — the same floor applies

A draft PR that pre-scopes a work unit for pickup is a *design decision about
the unit of work*, and it is where timidity actually enters: if the draft
defines the unit below the issue boundary or below the root-cause cluster, the
failure has already happened before any code is written. Every rule in this
skill applies to drafts at creation time, not just to ready-for-review.

- **Issues are the minimum unit of work.** A draft scoped to *part* of an
  issue is invalid — there is no altitude below one whole issue. The valid
  altitudes are: one genuinely atomic issue, a root-cause cluster, or a
  milestone subtree.
- **A draft whose "not claimed" list contains the actual feature the issue
  requests is invalid.** Scoping the easy fragments and deferring the
  requested behavior is the timid slice in draft form. Re-scope upward.
- **A planning-shell draft must not carry `Closes #N`.** Issue-closing
  semantics attach only when the branch actually delivers the closing
  behavior; until then use `Refs`.
- **Drafts exist to hand agents pre-scoped ambitious units**, so smaller
  agents can pick up a coherent rewrite without re-deriving the constellation.
  A draft that hands them a sliver defeats its own purpose.

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
- **Shrinking scope behind a manufactured blocker.** "Needs a design
  decision," "blocked by research," "split into a follow-up PR," "belongs
  upstream" — occasionally real, but never a license to carve out a smaller
  safe PR around the blocker. Make the design decision and implement it, or
  stop and report the blocker. Uncertainty does not convert into a nudge.
- **Crash-fix and urgent-slice PRs.** Crashes are symptoms. Fix them inside
  the root-cause branch, or if owner-blocking right now, relieve them direct
  to main. A crash is usually evidence the subsystem boundary is wrong — not
  evidence that the correct PR is smaller.

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

0. Does this change warrant a PR at all, or is it a direct-to-main repair?
   (A PR for something the owner would accept as a direct fix = wrong path.)
1. What constellation does this PR close? (Naming one issue = probable nudge.)
2. What symptom generator does it remove? ("None, it patches an instance" =
   re-scope to the generator.)
3. Would a sibling of this bug/finding still exist after merge? (Yes = the PR
   is scoped to the wrong altitude.)
4. Is there an open epic this change is secretly a sliver of? (Yes = claim the
   epic's slice instead.)
5. If you opened five PRs of this size this week, would the backlog be
   meaningfully smaller? (No = you are burning review cycles, not working.)
