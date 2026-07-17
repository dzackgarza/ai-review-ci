# Disposition Returned PR Feedback

Role B judges each finding independently.
B may see a batch, but returns one record per stable finding ID and never proposes a patch, refactor, or remediation shape.

## Separate the decisions

For every item classify:

- **claim:** true, false, or needs investigation;
- **suggested remediation:** policy-aligned, policy-misaligned, or underspecified;
- **current-PR necessity:** remediate now, backlog minor debt, no change, or investigate.

Then select one:

- **Accepted as written** — the claim is true and the proposed fix preserves policy and product semantics.
- **Accepted with modified remediation** — the claim is true but the proposed fix violates policy or product semantics, or is underspecified.
- **Rejected** — the claim is false, unsupported, irrelevant, design-hostile, or defeated by stronger policy or contract evidence.
- **Duplicate** — the same semantic claim already has a canonical disposition; point to that thread.
- **Outdated** — a superseding PR commit has invalidated the concern; cite that commit and the invalidating evidence.
- **Investigate before action** — evidence is insufficient.
  Keep the thread open.
- **Backlogged as minor technical debt** — the claim is true but satisfies every spend gate below and is linked to an owning debt issue.

Duplicate, outdated, and superseded threads still receive their selected per-thread disposition.
Never silently skip them.

## Mandatory pre-filter

Run these gates in order before choosing the disposition.
Record exactly one line:

`Pre-filter: <gate rule that fired> | <current-PR remediation or backlog result>`

### Gate 1 — threat-model relevance

The review apparatus targets slop and real correctness/proof defects: fallback/default/ mock behavior, fail-open or error-hiding paths, cross-file fragility, non-proof tests, a lying UI, stale-state races, swallowed errors, proof-surface gaps, and unbounded hangs.

- A supported slop, correctness, or proof issue continues to Gate 2.
- A generic bug/performance/style preference with no supported defect or debt is rejected.
- Supported localized maintainability, naming, readability, or duplication debt continues to Gate 3.

Do not reject a real defect because a generic reviewer found it.

### Gate 2 — forced dispositions

First match wins:

| Finding shape | Forced disposition |
| --- | --- |
| Micro-optimization without a logged or reproduced user-visible problem | Reject. If the same finding exposes a fail-loud/proof gap, retain only that concern as accepted with modified remediation. |
| Suggests fallback, default, mock, skip, graceful degradation, or silent coercion | If the claim is supported, accept the concern with modified remediation and reject only the proposed fix under the exact governing `POLICY.*` code. Reject the finding only when no independent supported concern remains. |
| Describes actual slop but frames it as a generic bug | Accept the concern, renamed as the policy violation. Remediation removes the slop. |
| Suggests broader `try/catch` or error handling around a throw | Accept with modified remediation: fail earlier or assert the invariant; never swallow. |
| Suggests an in-code constant where configuration owns the value | Accept with modified remediation to remain config-driven, or reject if no real divergence harm exists. |
| Enterprise hardening, sandboxing, path-traversal, or symlink-escape defense in single-user bespoke software | Reject unless the application owns an explicit security boundary. |
| Flags an optional or nullable output/contract field | Apply the optional-field axiom below. |
| Resolves by deletion | Require burden disposition under `POLICY.NO_DELETION_LAUNDERING`. |
| Guarded cast after a membership check that throws on miss | Reject: this is fail-loud boundary validation, not cast-as-validation. |

### Optional-field axiom

A field is required by default, and the data is fixed so it is always present.
Genuine absence is a narrow explicitly modeled state, not a shared optional that every consumer must tolerate.
“Models real absent data” is not sufficient: identify why absence is irreducible and why require-and-fix is wrong.
Otherwise accept the finding and route `POLICY.NO_UNJUSTIFIED_OPTIONALITY`.

### Gate 3 — current-PR spend gate

A true finding requires current-PR remediation when it affects any of:

- claimed behavior, issue acceptance criteria, or proof obligations;
- a required check or hard fail-loud, type, proof, or QC-integrity policy;
- user-visible correctness, security, safety, or data integrity;
- a regression introduced or worsened by the PR.

Backlog is legal only when none applies, the concern is localized low-risk maintainability debt, batching with the same work family is more proportionate, and the PR remains semantically complete without the change.
The disposition must link an existing or newly filed work-family debt issue and record why every current-PR criterion failed to trigger.
A missing issue or missing evidence makes backlog illegal.

### Gate 4 — proposed-fix policy check

When the claim is true but the suggested fix adds a fallback, default, mock, in-code constant, defensive catch, cast, optional core state, proof-laundering test, or other invalid local fix, choose **Accepted with modified remediation**. Route the exact policy code; do not teach C the rejected fix.

## Disposition pressure test

Before returning a judgment, answer:

- What exactly would remain false or unproven if this item were merely resolved?
- Which exact policy or contract purpose would literal compliance preserve or violate?
- Which exact policy or contract purpose would rejection preserve or violate?
- What source fact would falsify this disposition?
- What audit anchor lets the maintainer verify the judgment without trusting B?

Scanner status, process compliance, a future re-review, and “already handled” are not answers.
If the source evidence cannot answer these questions, choose **Investigate before action**.

## Required B output

For each finding return:

- stable ID and source URL;
- disposition;
- claim disposition;
- suggested-remediation disposition;
- `Pre-filter:` result;
- exact `POLICY.*` codes when policy governs, otherwise an explicit sourced factual/contract basis;
- evidence anchors;
- current-PR action: remediate, backlog, no change, or investigate;
- canonical thread, superseding commit, or debt issue when applicable;
- first-principles root concern for accepted findings, without a fix proposal.

If B proposes or implies a fix shape, rerun the disposition with a clean prompt.
