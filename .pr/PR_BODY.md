<!-- policy-alignment-gate -->

## Intended result
Downstream Python repositories can run the centrally delegated `just test` and `just test-ci` recipes without contradictory local QC configuration or central-map blind spots.

## Scope
- Included: Python central QC recipes for import-linter and deptry, caller-root behavior, and fixture-backed downstream proof for #167 and #162.
- Excluded: unrelated Python QC tools, downstream workaround commits, and broad policy changes to allow local QC overrides.
- Preserved behavior: downstream justfiles remain thin delegators; nested central calls preserve `-d .`; true dependency/import violations still fail loudly.

## GitHub tracking
- Target issue set / subtree: #167 and #162
- Milestone: Delegated QC rule precision
- Closes on merge:
  - Closes #167
  - Closes #162
- References only: none

## Implementation plan
1. Add red downstream-target fixtures that reproduce both failures from a caller repo boundary.
2. Fix `_import-linter` so config isolation and push-tier import-linter can both be satisfied without project-owned QC overrides.
3. Fix `_deptry` map handling so target package-module maps are honored or merged without overriding central policy.
4. Prove both recipes scan the caller repository, not `~/ai-review-ci` implementation files.

## Claim map
- [ ] **#167 - Python `test-ci` import-linter contradiction is removed**
  - Proof obligations claimed: red fixture, fixed central recipe, caller-root regression.
  - Partial / not claimed: broad import-linter policy redesign.
  - Evidence required: fixture fails before/fails for the right reason, then passes after the central fix.
  - Current evidence: issue reproduction only.
- [ ] **#162 - deptry package-module maps preserve target project semantics**
  - Proof obligations claimed: target map repro using mismatched package/module names, central recipe fix, no false DEP001/DEP002.
  - Partial / not claimed: downstream agent-memory remediation commits.
  - Evidence required: canonical target fixture and central recipe run with `-d .`.
  - Current evidence: issue reproduction only.

## Automated gates
Keep draft until red/green fixture proof exists and `just test` plus relevant targeted recipe tests are green.
