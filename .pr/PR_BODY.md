<!-- policy-alignment-gate -->

## Intended result
Every policy-touching repo decision cites the governing `POLICY.*` record, and policy deviations require explicit user approval plus integration into the owned policy text instead of local carve-outs.

## Scope
- Included: repo-owned policy/workflow surfaces that agents read when making PR, triage, review, and QC decisions.
- Excluded: detector implementation changes, automated meta-linting, and changes that belong in `~/ai` before #163 resolves ownership.
- Preserved behavior: burned-bridge policy remains fail-loud; this PR must not create self-granted exceptions.

## GitHub tracking
- Target issue set / subtree: #164
- Milestone: Policy index architecture
- Closes on merge:
  - Closes #164
- References only:
  - Refs #163 / PR #165 as the ownership prerequisite.

## Implementation plan
1. Wait for or rebase onto the #163 ownership boundary if needed.
2. Add the decision-citation doctrine to the owned policy/workflow surfaces.
3. Wire the doctrine into the install/publish path established by #163.
4. Add proof that the repo-owned source, vendored copy, and installed skill target cannot drift silently.

## Claim map
- [ ] **#164 - policy-touching decisions cite policy and cannot self-except**
  - Proof obligations claimed: source doctrine, installed/vendored propagation, no local exception path.
  - Partial / not claimed: any automated lint/meta-rule engine.
  - Evidence required: diff of governing surfaces plus install/vendor verification after #163 lands.
  - Current evidence: blocked by #163 / PR #165.

## Automated gates
Keep draft until #163 lands or this PR explicitly rebases onto its final ownership model, then run relevant skill/vendor tests plus `just test`.
