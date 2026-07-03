<!-- policy-alignment-gate -->

## Intended result

ai-review-ci documents and enforces where proof burden belongs across commit, push, PR, review, and milestone gates, so low-risk work is not forced through full push/PR ceremony while high-risk boundary work still receives fail-loud proof and review.

## Scope

- Included: risk-tiered proof-lane doctrine for the commit/push/PR/review gates this repo owns, mapping each tier to existing hook and CI surfaces.
- Excluded: live agent planning/runtime behavior before work begins, and changes that belong only in `dzackgarza/ai` skills.
- Preserved behavior: bridge-burning constraints, fail-loud policy, and existing Signal Separation work (#52-#56) are not weakened or duplicated.

## GitHub tracking

- Target issue set / subtree: #103
- Milestone: Adaptive Workflow Orchestration
- Closes on merge:
  - Closes #103
- References only:
  - Refs #102 parent epic.
  - Refs #52-#56 Signal Separation context.

## Implementation plan

1. Inventory existing commit, push, PR, review, and milestone gates owned by ai-review-ci.
2. Add a policy/workflow guide that maps low/medium/high/milestone-risk work to those gates without duplicating the Signal Separation split.
3. Include the pandoc-preview-greenfield2 and zotero-gui calibration examples.
4. Add a lightweight regression/proof check if the guide is surfaced through a maintained template, skill, or vendor manifest.

## Claim map

- [ ] **#103 - proof lanes are mapped to ai-review-ci-owned gates**
  - Proof obligations claimed: doctrine, calibration examples, mapping to commit/push/PR/review/milestone gates.
  - Partial / not claimed: pre-work agent planning behavior outside integration surfaces.
  - Evidence required: changed maintained docs/templates/skills plus tests if manifest/schema routing is touched.
  - Current evidence: issue only.

## Automated gates

Keep draft until the maintained surface is chosen, evidence maps to #103 acceptance criteria, and relevant docs/tests plus `just test` are green.
