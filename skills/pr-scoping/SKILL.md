---
name: pr-scoping
description: Use before scoping or opening any pull request, when deciding whether a change warrants a PR at all, and when triaging a backlog into units of work. Forces every non-organizational issue to be a significant PR-sized work unit, routes small urgent repairs direct to main, and bans the trivial single-nudge PRs agents default to.
---

# PR Scoping: Significant Work Units, Not Nudges

## The failure mode this skill exists to kill

Agents left to their own priors carve out the **minimum defensible diff**: one symptom, one file, one caller, ten lines.
Each such PR burns a full review cycle — CI runs, automated review, feedback triage, thread gardening, human attention, merge — on a change that moved the project almost nowhere.
Meanwhile the epics naming the actual root causes sit open and untouched, because every agent that visits the repo shaves off another sliver instead of doing the rewrite that would close the whole cluster.

Observed steady state of this failure: fifteen single-fix PRs merged in a week (`fix(threads): skip already-threaded findings`, `fix(gates): auto-resolve stale proof threads`, `fix(qc): retire unused dependency blocking`, ...) while five epic work-units sat open the entire time.
Millions of tokens spent on review overhead; the architecture unchanged.

**Review overhead is per-PR and roughly constant.** A 10-line PR costs nearly as much to shepherd through the loop as a 1,000-line PR. Ten timid PRs cost ~10× the review budget of one ambitious PR that closes the same ground — and deliver less, because the ten nudges never remove the root cause that keeps generating new symptoms.

Timidity is not safety.
It is the most expensive possible way to work.
A merged partial fix is worse than no PR: it leaves the tool in a mixed half-fixed state that *generates* new issues, and every subsequent agent must first reconstruct which issue text is stale, what partial progress landed, and which symptoms remain — before doing any work.
When inbound issue flow exceeds the outbound fix rate, the repo is in churn, not progress.

The reward signal is **backlog burn-down per review cycle**, not landed PRs.
A landed PR that leaves its issue open moved the project backward.

## Two paths — there is no third

Every change takes exactly one of these routes:

1. **Direct to main.** Urgent crash relief, trivial fixes, doc/config nudges, behavioural updates — anything the owner would accept as a direct repair.
   No PR, no review loop.
   Add a regression test when cheap.
   If the crash is a symptom of an open root-cause issue, note the relief on that issue and leave it open.
2. **Review-loop PR.** Issue-complete work: rewrites, feature grafts, structural consolidations.
   Enough scope to justify the review cost.

The review loop is an expensive mechanism for validating substantial changes, not a ritual for all changes.
A small fix routed through the PR pipeline burns a review budget sized for architecture on a traceback tweak.
A crash-fix-only PR is invalid unless the owner explicitly asks for one.
Small urgent repairs go to main; large coherent repairs go through review; small timid PRs do not exist.

## Calibrate ambition to actual capability, not to fear

Your prior about what fits in one PR is years out of date.
A 2026 frontier model can read an entire issue tree, understand the app, and deliver the subsystem rewrite that obviates most of it — with regression tests and decent code — in a single work window.
Smaller agents can do the same when the issue already self-describes the root-cause cluster.
These repos are small bespoke tools; "simple subsystem rewrite with regression tests" is a normal, one-shot-able unit of work here, not a special project requiring staging.

So when a scope feels "too big," check which is actually true:

- **It fits your window.** Then the feeling is the miscalibrated prior — the trained reflex toward the minimum defensible diff.
  Do the rewrite.
- **It genuinely exceeds your window.** Then the correct move is to update or create the work-unit issue for the *full* cluster so a more capable agent can pick it up — never silently shrinking the scope below the issue boundary so it fits.
  Scope is set by the root cause; capability decides *who* executes, not *what* the unit is.

The "hard" work agents route around — reconciling a subsystem, collapsing two command surfaces onto one path, replacing a hand-rolled layer — is typically not hard.
It is just larger than a nudge, and it is exactly the work that closes issue trees.

## Selecting the work unit: start from the backlog, not the symptom

"Grab the most urgent work" does not mean "fix the most immediately broken thing."
The most immediately broken thing is almost always a symptom of an umbrella problem that is generating it *and* several siblings, and patching it leaves the generator running.
Urgency means leverage: the fix or rewrite that obviates this issue and as many others as possible.

The selection procedure, in order:

1. **Read the whole backlog first** — every open issue, epic, and milestone in the repo.
   Not the newest issue, not the one that paged loudest.
   You cannot pick the right unit of work from one issue.
2. **Find the umbrella.** Which subsystem, design defect, or missing abstraction is generating the most open issues?
   Dozens of issues in one area almost always mean one root cause that agents have been sidestepping because it looks "hard" — and it is usually not hard, just bigger than a nudge: a subsystem rewrite with regression tests.
3. **Ask what rewrite or feature obviates the largest cluster.** A rewrite that closes or invalidates ten issues outranks ten individual fixes — always.
   Large rewrites and whole features are not the risky option to attempt after the small fixes; they are the *first-choice* unit of work precisely because they burn down the backlog instead of grooming it.
4. **That umbrella is the most urgent work.** Only when a repo genuinely has no umbrella — all open issues atomic and unrelated — does single-issue work become the right unit.

## The unit of work is the issue

Every issue that is not purely organizational is a PR-sized work unit.
The issue itself carries the constellation: the story, root cause, sibling symptoms, proof burdens, implementation checklist, blocker state, and review requirements.
Do not break a work-unit issue into sub-issues for sub-tasks, sub-stories, proof obligations, or checklist items.
Those belong in the issue body or issue comments.
Before opening any PR:

1. **Cluster first.** Read the open issues, review findings, and epics.
   Group them by shared root cause: same subsystem, same design defect, same missing abstraction, same class of symptom.
   If the cluster is currently scattered across issues, first rewrite or create the work-unit issue so it self-describes the whole cluster.
   Do not preserve the scattered issues as the PR's live decomposition.
2. **Ask the obviation question.** Is there a rewrite, consolidation, or design change that makes the whole cluster impossible rather than individually patched?
   If yes, put that rewrite on the work-unit issue, then execute that issue through one PR. The rewrite is the *smaller* change when measured in total system cost: one review cycle instead of N, and the symptom generator removed instead of throttled.
   These are bespoke owner-local tools (see `bespoke-software-policy`): no downstream consumers exist, so break internal APIs freely and rewrite the subsystem when that is simpler than preserving broken structure.
   "Bespoke" means *move aggressively* — not "be careful because policy exists."
3. **Scope the PR from the issue.** Open the PR when implementation starts.
   The PR body is synthesized from the work-unit issue and its evidence: what issue it closes, what organizational parent it advances, and what future findings it obviates.
   `Closes #a; refs organizational ledger #z` is the expected shape.

## The significance floor

Every PR must satisfy at least one of:

- **Closes one substantive work-unit issue** that self-describes the related symptoms, proof burdens, and implementation checklist, or
- **Is a structural change** that removes a symptom generator — a rewrite, boundary change, or consolidation that obviates a class of findings, not an instance, or
- **Carries an explicit atomicity justification** in the PR body synthesized from the issue: one or two sentences proving the issue is genuinely isolated — no sibling symptoms, no parent epic, no cluster it could join.
  Silence is not justification.

If a change fails the floor, it does not become its own PR. It goes direct to main if it qualifies for that path, rides along inside the significant PR whose territory it belongs to, or waits until that PR forms.

## Work-unit issues are scope artifacts — the same floor applies

A work-unit issue is a *design decision about the unit of work*, and it is where timidity actually enters: if the issue defines the unit below the root-cause cluster, the failure has already happened before any code is written.
Every rule in this skill applies when writing or updating the issue, not just when opening a PR.

- **Issues are the minimum unit of work.** A PR scoped to *part* of an issue is invalid — there is no altitude below one whole issue.
  The valid altitudes are: one genuinely atomic issue, or one issue that self-describes the root-cause cluster.
  Purely organizational issues may group and order work units, but they are not implementation scope.
- **An issue whose open task list excludes the actual requested feature is invalid.** Scoping the easy fragments and deferring the requested behavior is the timid slice in issue form.
  Re-scope the issue upward.
- **A planning issue is not implementation completion.** Issue-closing semantics attach only when the branch actually delivers the closing behavior; until then update the issue body/comments.
- **Work-unit issues exist to hand agents ambitious units**, so smaller agents can pick up a coherent rewrite without re-deriving the constellation.
  An issue that hands them a sliver defeats its own purpose.

## Banned scopes

- **`partial #x` as a PR scope.** An issue is already the *minimum* unit of work, so a PR that partially closes one is guaranteed to be wildly underambitious — it is below the floor by construction, a nudge wearing a claim.
  There is no judgment call to make here: if you find yourself writing "partial", the scope is wrong.
  Take the whole issue, or rewrite the issue so the true work unit is explicit before implementation starts.
- **Work-unit sub-issues.** A non-organizational issue is already the PR boundary.
  Do not create child issues for its sub-tasks, sub-stories, proof burdens, or implementation checklist.
  Move that decomposition into the issue body/comments, or convert the parent into an organizational ledger if the children are truly separate PR-sized work units.
- **Fixing one caller when siblings share the bug.** The lazy fix and the root-cause fix are the same fix: one change where all callers route through.
  Patching only the path the finding named leaves every sibling broken and guarantees N follow-up PRs.
- **Patching a symptom while the epic naming its cause sits open.** If a review finding is an instance of an open epic, the PR addresses the epic's next coherent work-unit cluster — not the instance.
- **Splitting a coherent rewrite into "safer" sequential slices.** Slices of one design change are not independently reviewable anyway; each slice-PR re-pays the full review cost and the intermediate states are dead weight.
  Ship the rewrite as one PR with a clear narrative.
- **One-finding remediation PRs.** Review findings arrive in batches; their remediations ship in batches, grouped by root cause.
- **Shrinking scope behind a manufactured blocker.** "Needs a design decision," "blocked by research," "split into a follow-up PR," "belongs upstream" — occasionally real, but never a license to carve out a smaller safe PR around the blocker.
  Make the design decision and implement it, or stop and report the blocker.
  Uncertainty does not convert into a nudge.
- **Crash-fix and urgent-slice PRs.** Crashes are symptoms.
  Fix them inside the root-cause branch, or if owner-blocking right now, relieve them direct to main.
  A crash is usually evidence the subsystem boundary is wrong — not evidence that the correct PR is smaller.

## What this does NOT license

Significance is measured in **cohesion × consequence**, not line count.

- **No unrelated-change dumping.** A big PR is one root cause and all its symptoms — not a grab bag of every open nit.
  If two clusters have different root causes, they are two PRs.
- **No scope-laundering.** "While I'm here" additions that don't serve the selected cluster are still banned.
  Ambition means addressing the whole cluster, not annexing neighbors.
- **Cohesion is the reviewability contract.** A 2,000-line PR with one design narrative ("moved all finding delivery through the state machine; closes #42, #140, #141, #144") is *more* reviewable than ten disconnected 40-line PRs, because the reviewer holds one idea instead of ten contexts.

## The completion contract: burn down the tree, don't just land the diff

A work unit is finished when the issue tree reflects the new reality, not when the PR merges.
The work-unit issue must already state the plan, acceptance criteria, proof obligations, and implementation checklist.
The final PR body synthesizes that issue state for reviewers and must state, concretely:

- **Issue closed** — with regression proof witnessing the reported failure or requested behavior.
  No `partial #N` closure language anywhere.
- **The shared root cause removed** — and what old behavior is now *impossible*, not just fixed.
- **Issues made obsolete or narrowed** — the rewrite usually invalidates more issues than it formally closes.
  Name them.

Then do the hygiene, as part of the unit: close the obsoleted issues with a one-line reason, and update any issue the rewrite narrowed so its text describes what actually remains.
This is not paperwork — it is the point.
The next wave of issues should be about *the rewrite*, filed against a coherent new state, not about a partial in-progress state nobody can map.
An agent arriving after you should read the open issues and see the true remaining work, without reconstructing which issue text is stale, what partial progress landed, or which symptoms still reproduce.
If they must do that archaeology, the work unit failed even though the PR merged.

## Self-check before opening

Answer these; if any answer is wrong, re-scope:

0. Does this change warrant a PR at all, or is it a direct-to-main repair?
   (A PR for something the owner would accept as a direct fix = wrong path.)
1. Which work-unit issue does this PR close?
   (If the answer is "part of #N" or "several issues without one issue owning the contract", re-scope.)
2. What symptom generator does it remove?
   ("None, it patches an instance" = re-scope to the generator.)
3. Would a sibling of this bug/finding still exist after merge?
   (Yes = the PR is scoped to the wrong altitude.)
4. Is there an open epic this change is secretly a sliver of?
   (Yes = scope the work to the epic's coherent cluster instead.)
5. If you opened five PRs of this size this week, would the backlog be meaningfully smaller?
   (No = you are burning review cycles, not working.)
