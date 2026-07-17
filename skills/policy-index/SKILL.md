---
name: policy-index
description: Use before code review, slop review, PR feedback triage, testing, QC changes, or remediation when deciding which global policy rule owns the obligation. Central source of truth for bridge-burning policy identity, red-flag catalogs, proof/test rules, QC authority, and slop remediation routing.
---

# Policy Index

Canonical source of truth for bridge-burning policy identity and policy-owned reference catalogs.

Other skills may teach how to review, test, debug, or remediate within their domains.
They must not define competing bridge-burning policy text.
They point here for policy codes, red flags, runtime control-flow rules, banned test shapes, exception rules, and remediation routing.

Each full policy record names exactly one canonical remediation route.
The disposition agent classifies the source against the policy and its adjacent red flags; it does not choose a route.
The fixer follows the route named by that record into the [[style-guide/SKILL|style guide]].

Policy material must remain independent of the machinery that raised a finding.
Implementation details invite source disposition based on tooling limits instead of the bespoke policy and the complete local workflow.

## Use Protocol

- Load this skill before code review, slop review, PR feedback triage, test review, QC changes, or remediation.
- Use `POLICY.*` codes from this skill and `references/policies.md` as authoritative.
- Use `references/red-flags.md` to classify validation-evasion constructs.
- Use `references/runtime-control-flow.md` to classify runtime branch shapes.
- Use `references/error-handling-as-control-flow.md` to classify failure-driven ordinary branching, state probing, and guess-catch-retry behavior.
- Use `references/runtime-control-flow.md#addd-assert-dump-data-direct` as the canonical ADDD coding style lookup for assertions: assert early, dump related data, then direct the maintainer to the owning fix surface.
- Use `references/test-proof-rules.md` to classify proof and assertion shapes.
- Do not remediate from the finding message alone.
- State the weakened obligation before editing.
- Use a separate reviewer/fixer context when QC triage requires it.
- If acting as the issue-seeing reviewer, classify the policy finding without proposing a card or patch.
- If acting as the remediation/fixer agent, follow the exact remediation route named by the policy record before changing code.
- Treat local token replacement as invalid unless the remediation reference explicitly says the finding is mechanical.

## Database Files

| File | Audience | Contents |
| --- | --- | --- |
| `references/policies.md` | Reviewers, triage agents, fixers after code assignment | Categorized policy database with named `POLICY.*` records. |
| `references/red-flags.md` | Reviewers and disposition agents | Validation-evasion red flags and language-specific signatures. |
| `references/runtime-control-flow.md` | Reviewers, disposition agents, and fixers after code assignment | Runtime branch admission rules, banned branch shapes, ADDD assertion style, and examples. |
| `references/error-handling-as-control-flow.md` | Reviewers, disposition agents, test writers, and coding-style authors | Canonical rationale for banning exception-driven ordinary control flow and guess-check-retry state probing. |
| `references/test-proof-rules.md` | Test writers, test reviewers, and disposition agents | Banned test/assertion shapes and proof-admission rules. |
| [[style-guide/references/style-guide-index\|style-guide index]] | Before implementation and during repair | Canonical preferred constructions, bad patterns, rearchitecture, and proof obligations. |

## Policy Categories

- Runtime, Config, and State
- Fail-Loud Execution
- Proof and Test Integrity
- Type and Interface Integrity
- Architecture Ownership
- QC Authority
- Artifact Ownership
- Migration and Remediation Integrity
- Anti-Speculation

## Policy Registry

The complete registry lives in `references/policies.md`. Each record owns its policy text, invalid local fixes, adjacent detection handles, and exact remediation route.
Other documents cite the code; they do not copy the record.

## Exception Protocol

A policy exception requires all of:

- Explicit user request or source-backed product requirement.
- Exact `POLICY.*` code being violated.
- Explanation of why the blanket rule blocks required behavior.
- Replacement invariant that prevents the old evasion.
- Boundary proof.
- Visible audit trail in commit, PR, or issue.

## Policy Routing Index

| Question | Canonical source |
| --- | --- |
| What named policy applies? | `references/policies.md` and [Policy Registry](#policy-registry). |
| What code/test red flags should I scan for? | `references/red-flags.md`. |
| What runtime control-flow shapes are banned? | `references/runtime-control-flow.md`. |
| Why is exception-driven ordinary control flow banned, and what explicit models does it displace? | `references/error-handling-as-control-flow.md` and `POLICY.NO_EXCEPTION_CONTROL_FLOW`. |
| What is the coding style for assertions and invariant failures? | `references/runtime-control-flow.md#addd-assert-dump-data-direct`. |
| What test assertion patterns are banned? | `references/test-proof-rules.md`. |
| What codenamed remediation applies? | Follow the policy record's exact `Related remediation` code into [[style-guide/references/style-guide-index\|style-guide index]]. |
| What policy applies to creating files dynamically from code? | `POLICY.NO_DYNAMIC_ARTIFACTS` in `references/policies.md`. |
| What policy applies to embedding large strings/prompts/messages inline in code? | `POLICY.NO_DYNAMIC_ARTIFACTS` in `references/policies.md`. |
| What policy applies to embedding one language inside another? | `POLICY.NO_DYNAMIC_ARTIFACTS` in `references/policies.md`. |
| What policy applies to mypy `import-untyped`, missing stubs, or missing `py.typed`? | `POLICY.NO_UNTYPED_IMPORT_LEAK`; follow that record's canonical remediation route rather than changing dependencies. |
| What policy applies to token-local fixes that preserve the architectural failure process? | `POLICY.NO_MYOPIC_PATCHING` in `references/policies.md`. |
| How do I review LLM-produced code? | [[reviewing-llm-code/SKILL\|reviewing-llm-code]]. |
| How do I fix slop without laundering? | [[fixing-slop/SKILL\|fixing-slop]] plus [[style-guide/references/style-guide-index\|style-guide index]]. |
| What makes a test valid proof? | [[test-guidelines/SKILL\|test-guidelines]] plus `references/test-proof-rules.md`. |
| Who owns QC invocation/config/tooling? | `POLICY.GLOBAL_QC_AUTHORITY`; operational QC invocation remains in the global [[quality-control/SKILL\|quality-control]] skill. |
| How do I triage PR feedback? | [[pr-feedback-triage/SKILL\|pr-feedback-triage]]. |
| A reviewer asserts an external library's convention/namespace/API ("the standard is X")? | `POLICY.NO_UNVERIFIED_CONVENTION_CLAIMS` in `references/policies.md` — verify once against the pinned checkout; stale ⇒ reject wholesale with file:line evidence. |
| How do I debug without prior-shaped probing? | [[reality-grounded-debugging/SKILL\|reality-grounded-debugging]] plus [[systematic-debugging/SKILL\|systematic-debugging]]. |
| How do I handle external tool/library/compiler uncertainty? | [[known-solution-first/SKILL\|known-solution-first]]. |
| How do I provision tools? | [[tool-provisioning-and-environment-hygiene/SKILL\|tool-provisioning-and-environment-hygiene]]. |
