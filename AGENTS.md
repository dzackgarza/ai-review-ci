# Agent Rules

## QC Delegation

- Treat `~/ai-review-ci` as the authoritative QC implementation.
  Downstream repositories carry only thin `test` and `test-ci` recipes that delegate to this repo.

- Every command that loads a central justfile from another repository must preserve the caller repository with `-d .`:

  ```justfile
  test:
      @just -f ~/ai-review-ci/justfiles/python.just -d . test

  test-ci:
      @just -f ~/ai-review-ci/justfiles/python.just -d . test-ci
  ```

- Apply the same caller-root rule to nested central calls.
  Language justfiles calling `shared.just`, and Sage calling Python QC, must include `-d .` on every nested `just -f` invocation.

- Do not patch a downstream repository first when a shared QC command runs in the wrong directory.
  Fix the central scaffold or central language justfile in this repository, then reinstall or recopy downstream only if the downstream file itself is stale.

- Prove caller-root fixes with a red test before editing the scaffold or justfile.
  Use a real temporary target repository whose target-specific preflight failure differs from the failure produced in `~/ai-review-ci/justfiles`.

## Testing Central QC Changes

- Do not run central QC recipes against `~/ai-review-ci` as proof of behavior.
  This repository owns the checkers, rules, and justfiles; self-scanning the checker implementation is not the boundary those recipes are meant to prove.

- Proper proof for central QC behavior uses repo-owned canonical fixtures.
  Add or update "bad" target-code fixtures that intentionally violate the policy under test, then run the relevant justfile recipes against those fixture repositories or fixture worktrees.

- The fixture suite must prove the downstream caller contract: the recipe receives a caller repository with `-d .`, scans that caller's target files, reports the expected finding, and does not diagnose `~/ai-review-ci` implementation files as the subject under review.

- Treat self-QC findings as invalid proof until the target boundary is established.
  For example, a rule that bans `try` statements may itself contain code or text about `try`; diagnosing that self-reference starts a false triage loop, not a real product failure.

## Semgrep Findings

- Separate Semgrep rule provenance from finding ownership.
  Paths under `~/ai-review-ci/tool-configs/` identify the rule config; the finding target path identifies the code being checked.

- Do not conclude that QC scanned its own files because output mentions `tool-configs/semgrep.yml`. Confirm the process cwd, the target paths, and the target count before diagnosing wrong-repo scanning.

- A downstream report that “Semgrep found issues about CI files” is a cwd/provenance triage problem until target paths prove otherwise.
  Reproduce the run from the target repository and inspect the exact reported paths before editing rules or suppressions.

## Hook Tiers

- The global hook split is intentional: `pre-commit` runs `just test`, and `pre-push` runs `just test-ci`.

- Slop/style/coverage findings during an ordinary commit indicate a hook-tier or delegation problem.
  Do not reinstall hooks or weaken QC until the active hook path, hook contents, and delegated cwd have been verified.

> Optimized tool-use workflow for agents: see [SDL.md](./SDL.md).

# Policy Alignment Gate

Every PR against this repo must reconcile against the burned-bridge policy before it
leaves draft or merges. This gate exists because agents — local and, especially, remote —
arrive with strong priors that *want* fail-soft slop accepted. A "noisy detector" reads as
"make it quieter"; the obvious fix (allow an empty-array default, add a fallback, widen a
type, swallow an error) is exactly the policy violation. The reviewer cannot catch a change
that weakens the reviewer, so the check lives in the definition of done for the work itself,
not only in CI.

Concrete failure this prevents: **PR #143** "fixed" a noisy `POLICY.RUNTIME_DEFAULT`
detector by allowing `?? ""` / `?? []` / `?? {}` as "boundary normalization" — converting a
true `POLICY.FAIL_OPEN` finding into scanner silence, and blessing the fail-open pattern for
every downstream consumer. It was merged, then reopened for policy-aligned remediation
(#120, #130).

## Canonical policy source (self-contained — no external fetch)

The authoritative policy travels with this repo, vendored and hash-pinned. Load it from the
checkout:

- `reviews/vendor/policy-index/SKILL.md` and `reviews/vendor/policy-index/references/policies.md`
  — the `POLICY.*` records and their **Invalid local fixes**.
- `reviews/vendor/reviewing-llm-code-references/bridge-burning-red-flags.md` — the red-flag
  inventory.

Do not rely on globally-installed skills: remote review/coding agents (Codex, Jules, cloud
runs) do not have them. The vendored copy is the contract.

Policy **content** is owned upstream at `github.com/dzackgarza/ai`. Changing what a policy
*says* is an upstream edit re-vendored via `just sync-policy-index`; the vendored files are
sha256-pinned (`tests/test_policy_index.py`) and a local edit fails the pin and is clobbered.

## Tier 0 — every PR

Before requesting review or merging, the PR body (or disposition ledger) must state:

- Which `POLICY.*` records the change touches or risks.
- That no **Invalid local fix** from those records was introduced — no new fallback, runtime
  default, optional core-state, swallowed error, or partial-success path added to make
  required work look successful after it should have failed loudly.

Empty and falsy literals are not exceptions. A fallback whose value is a placeholder — the
vendored `POLICY.FAIL_OPEN` record names `None`, `[]`, `{}`, and `false`; empty strings behave
the same way — is a `POLICY.FAIL_OPEN` violation, not "safe boundary normalization." Genuinely
optional product state is represented as an explicit typed/semantic state at the owned
boundary, never laundered through an empty default.

## Tier 1 — PRs that change the QC tooling itself

Any PR touching `tool-configs/`, `reviews/`, the detectors, or QC `justfiles/` additionally
must carry an **adversarial regression-lock**:

- A fixture (`// ruleid:` or equivalent) proving each previously-flagged banned pattern
  **still fires** after the change. A precision fix narrows by **position** — excluding
  genuine boolean/control-flow uses — never by **value**. No fallback value is reclassified
  as safe.
- An explicit statement that the change weakens no `POLICY.*` and converts no true finding
  into scanner silence.

This is the gate PR #143 would have failed: a `ruleid` fixture on `?? ""` / `?? []` / `?? {}`
makes any future empty-literal whitelist a red test.

See `# Review Guidelines` → Evidence Expectations for the reviewer-side counterpart, and the
wiki page [Policy Alignment Gate](https://github.com/dzackgarza/ai-review-ci/wiki/Policy-Alignment-Gate)
for the full rationale.

# Review Guidelines

These are additional requirements for reviewing agent work.
They do not replace the reviewer’s normal role, repo-specific standards, or technical judgment.
They provide the failure model that should shape the review.

The task is not merely to review a PR. The task is to decide whether a completion claim is true under the original objective.
The standard is full, correct, provable completion against the original requirements and repo guidelines.
Anything less is incomplete work that must not be treated as a win.

## Failure Model

Agents systematically produce impressive non-completion.
Common patterns are: polished summaries that imply finished work, caveats that quietly narrow the goal, reclassification without proof, delegated discovery presented as resolution, process language that substitutes for evidence, merged PRs treated as completion, passing checks treated as semantic proof, and artifacts that look substantial while leaving required work unowned.

Treat the agent’s summary, PR description, closing comment, issue closure, “goal completed” statement, and self-reported validations as untrusted.
They may be diagnostic pointers, but they are not evidence that the work is complete.
The evidence is the original issue or task, the code diff, tests, source/runtime facts, review comments, and produced artifacts.

## Decisive Invariants

Preserve the original success condition.
Read the original issue or task before accepting any restatement of it.
Keep its quantifiers intact: “all,” “complete,” "full subset," “zero remaining,” and similar terms cannot be quietly narrowed to examples, partial coverage, known blockers, or whatever the PR happened to touch.

Nothing required may disappear silently.
A required work family must be implemented, explicitly falsified, or validly reclassified with evidence that satisfies the issue’s own standard.
Partial implementation is not completion.
Future work is not completion.
Count reduction is not completion.
Resolved review threads are not completion.
Passing checks are not completion.
Substantial-looking work is not completion.
“Better than before” is not completion.

Goal substitution is the main thing to detect.
Ask whether the submitted work solves the original problem or merely produces a narrower artifact: cleaner metadata, a partial subset, a better explanation, a new issue, a renamed scope, a local workaround, or proof that someone should investigate later.

Technically correct administrative artifacts can be goal substitution.
A well-written issue, comment, audit note, scope statement, or enumeration of remaining work may be required, but it does not complete implementation, testing, proof, or downstream cleanup.
If the original task requires execution, the artifact is only useful insofar as it drives that execution; it must not become the stopping point.

Treat self-scoped remaining-work lists as a severe completion-laundering pattern.
When an agent is asked to enumerate remaining work, the domain is the original full completion requirement, not the agent’s intended subset, the PR’s current shape, a closeability criterion, or the work left after deferral and reclassification.
A valid enumeration subtracts only artifact-proven completed work from the original contract.
Deferrals, routed follow-ups, owner changes, and truthful incompletion notes remain unresolved work unless the original task explicitly made that administrative routing the whole deliverable.

If an agent repeats a narrowed enumeration after being corrected, treat that as a hard misalignment signal, not as an innocent wording issue.
The reviewer should identify the original full requirement, the scope the agent substituted, and the required work hidden by that substitution.

Silent reclassification is not resolution.
If the PR says remaining work is out-of-scope, research-owned, stub-owned, plugin-owned, downstream-owned, or future-owned, require evidence from the relevant source/runtime behavior, repo boundary, or original acceptance criteria.
A sentence in the PR description is not enough.

Ownership boundaries matter.
The submitting repo must prove its own claimed behavior and do the blocker forensics required by its own issue.
Do not require a receiving or downstream repo to classify another project’s internal uncertainty unless the original issue explicitly made that part of acceptance.
When an external issue is created, it should be written for that receiving repo, not for a reader who already knows the submitting repo’s context.

## Evidence Expectations

Review tests as evidence, not as decoration.
Valid tests exercise the real production path or semantic requirement.
Be skeptical of helper-only tests, tautologies, assertions of the implementation’s own output, bypasses around the runtime/plugin/stub path, example-only coverage where the issue required full coverage, weakened assertions, and missing invalid-nearby cases where the fix could overgeneralize.

For plugin work, the evidence should usually distinguish valid generic behavior from invalid nearby ordinary Python and should not hard-code a downstream consumer.
For stubs work, the evidence should be source-backed: the upstream surface exists, the stub matches public behavior, no fake API is added, no Any/object opacity escape is introduced, and inherited-method inflation is not used unless source exposes that surface.

Watch for code-level laundering: hard-coded consumer names, support for local research abstractions as if they were external API, fake stubs, broad Any/object escapes, line suppressions, diagnostic filtering, deletion of required data, broad type widening, and any move that makes checks pass by weakening the problem instead of solving it.

## When Acting on Review Feedback

A positive disposition requires a commit.

Do not resolve an accepted review comment until the code/proof remediation is committed and the reply cites the commit.

Never reply “accepted,” “aligned,” “fixed,” “addressed,” or “will address” to a review thread unless the remediation is already committed.
A thread cannot be resolved on intent or future work.

Rejected and modified feedback must be collected in a top-level PR comment titled `Review feedback disposition ledger` so resolved threads do not hide the audit trail.

Review comments are not implementation specs.
The worker must translate accepted feedback into first-principles remediation requirements before assigning implementation.

For each comment:
- Identify the concern.
- Identify the proposed fix.
- Decide whether the concern is true under global + repo policy.
- Decide whether the proposed fix preserves those policies.
- If the concern is true but the fix is wrong, apply a policy-compatible remediation.

## Writing the Review

Write nuanced feedback for an intelligent reader.
Do not force a machine-readable template, a mandatory table, or a simplistic pass/fail label when prose communicates the situation better.
Do make the completion judgment clear: whether the original task can be considered complete, what evidence supports that judgment, and which unresolved requirements block completion if any remain.

Do not foreground effort, progress, good intentions, volume of work, or “substantial” partial implementation when required work remains.
Mention completed pieces only when they are necessary to identify the exact remaining blockers or to prevent redoing already-correct work.
Do not compare incomplete work to “no work done” or “completely fake work”; compare it to the expected standard: the task done correctly, completely, and provably.

When required work remains, lead with the incompleteness and the concrete blockers.
Do not make the reader excavate the missing work from beneath praise, context-setting, or a narrative of what did get done.

Nuance belongs in the evidence and blocker analysis, not in softening the completion standard.
The review should make it easy to finish the work, not easy to feel satisfied with less than the original contract required.
