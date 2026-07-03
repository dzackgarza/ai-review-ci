<!-- policy-alignment-gate -->

## Intended result
Reviewer output is empirically anchored to the burned-bridge threat model: it separates slop from generic bugs/perf churn, blocks policy-violating remediation suggestions, and handles optional/absent data from policy instead of priors.

## Scope
- Included: #28 eval corpus, #19 threat-model drift correction, #20 remediation firewall, and #21 optionality doctrine consumption once policy-index doctrine is available.
- Excluded: deterministic torture fixtures already covered by PR #146 / #62; delivery-channel dedup covered by #29/#25.
- Preserved behavior: reviewer findings remain diagnosis-first and must not invent generic enterprise hardening, fallback/default fixes, or optional-core-state escapes.

## GitHub tracking
- Target issue set / subtree: #28, #19, #20, #21
- Milestone: Reviewer signal quality
- Closes on merge:
  - Closes #28
  - Closes #19
  - Closes #20
  - Closes #21
- References only:
  - Refs #41 parent epic.
  - Refs #58 / PR #149 as the policy-index dependency for optionality doctrine.
  - Refs #62 / PR #146 for fixture slice already split out.

## Implementation plan
1. Build the labeled corpus from the PR #7 review archaeology (#28).
2. Update reviewer prompt/classification surfaces so generic bug/perf findings are rejected unless within threat model (#19).
3. Add the remediation firewall so true claims cannot carry policy-violating suggested fixes (#20).
4. Integrate optional/absent-data doctrine after #58 gives the canonical policy source (#21).
5. Prove changed behavior against the eval corpus and fixture surfaces.

## Claim map
- [ ] **#28 - empirical eval corpus exists and is reusable**
  - Proof obligations claimed: labeled cases with source evidence and expected classifications.
  - Partial / not claimed: delivery transport changes.
  - Evidence required: corpus artifact plus evaluation command.
  - Current evidence: issue definition only.
- [ ] **#19 - reviewer stops surfacing out-of-threat-model generic churn**
  - Proof obligations claimed: prompt/config change and eval proof preserving real slop recall.
  - Partial / not claimed: deterministic Semgrep policy precision (#120).
  - Evidence required: before/after eval showing generic bug/perf suppression without dropping real slop.
  - Current evidence: blocked by #28 corpus.
- [ ] **#20 - reviewer remediation cannot violate project policy**
  - Proof obligations claimed: canonical remediation routing and eval cases for policy-misaligned suggestions.
  - Partial / not claimed: PR-feedback triage implementation outside reviewer output.
  - Evidence required: eval proving violating suggestions are rejected or rewritten as policy-compatible diagnosis.
  - Current evidence: blocked by #28 corpus.
- [ ] **#21 - optional/absent-data handling is policy-grounded**
  - Proof obligations claimed: reviewer consumes canonical optionality doctrine once #58 lands.
  - Partial / not claimed: authoring the #58 policy itself.
  - Evidence required: eval cases distinguishing irreducible absence from weakened required fields.
  - Current evidence: blocked by #58 / PR #149.

## Automated gates
Keep draft until the corpus and eval command exist, policy dependencies are resolved, and reviewer-signal tests plus `just test` are green.
