# Remediate Accepted PR Feedback

Only accepted current-PR findings enter this stage.
Role C implements a first-principles specification; it does not “address a comment.”

## Build the specification

The controller translates B's accepted concern into this contract:

```markdown
## Remediation spec

Original task / proof burden:
<What the PR was required to satisfy.>

Root concern:
<The correctness, proof, or architecture defect without reviewer wording.>

Required behavior:
<What must be true afterward.>

Required invariants:
- ...

Governing policy and preferred pattern:
- <exact POLICY.* code> -> <canonical style-guide card>

Banned remediation patterns:
- <invalid local fixes from the policy record and card>

Proof obligation:
<The owned boundary and plausible broken cases the witness must reject.>

Replacement requirement:
<What suspect implementation/proof surface may need replacement.>

Scope:
<Files and subsystems in scope; explicit non-goals.>
```

Do not turn reviewer patch text into the spec.
A good spec names the invariant and owned proof boundary.
For example, “replace `.flatten()` with `map_err`” is patch text; “directory reads must never turn an I/O failure into a partial successful listing, and a boundary test must reject that broken behavior” is a specification.

## Route policy into the style guide

For every `POLICY.*` code, read its `Related remediation:` mapping in [[policy-index/references/policies|the canonical policy records]], resolve that `REMEDIATE.*` code through [[style-guide/references/style-guide-index|the style-guide index]], and load the named card from that index.
The card is the canonical remediation source: preferred construction, bad pattern, rearchitecture, and proof obligation.
Do not stop at either skill entrypoint and do not invent a separate remediation interpretation.

If the accepted concern is factual or contract-only, identify the owned boundary and derive the spec from that contract.
Do not manufacture a policy code.

## C input firewall

C receives only:

- the remediation spec;
- original issue/PR contract;
- relevant source files;
- exact `POLICY.*` records and mapped style cards;
- applicable [[test-guidelines/SKILL|test proof rules]].

C must not receive exact reviewer wording, suggested patch text, B's rejected remediation, thread status, A's preferred fix, or “just address this comment” framing.

## Required C output

- changed files;
- proof commands and witnesses;
- how each witness discharges the spec and rejects plausible broken behavior;
- explicit banned-pattern audit;
- blocker, with no partial patch, if the spec cannot be met.

Tests added in response to review must prove the owned boundary.
Source-shape, exact string, existence, visibility, helper-branch, and “no banned token” assertions are not product proof.

Deletion is a remediation claim.
It is valid only when the original burden is solved, invalidated by contract evidence, transferred to another owned surface, or remains an explicit blocker.
Deletion cannot make an accepted obligation disappear.
