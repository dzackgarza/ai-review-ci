<!-- policy-alignment-gate -->

## Intended result
Review delivery stops doubling maintainer triage load without dropping a channel that uniquely finds accepted issues.

## Scope
- Included: empirical unique-yield measurement for current review channels (#29), then the delivery/dedup decision for double emission (#25).
- Excluded: reviewer prompt quality and slop classification work owned by Reviewer signal quality.
- Preserved behavior: no review channel is removed or silenced until accepted-finding overlap/unique-yield evidence supports the change.

## GitHub tracking
- Target issue set / subtree: #29 then #25
- Milestone: Review delivery state machine
- Closes on merge:
  - Closes #29
  - Closes #25
- References only:
  - Refs #42 parent epic.
  - Refs PR #147, which keeps the separate review-state implementation slice.

## Implementation plan
1. Extract accepted findings from the representative PR archaeology named by #29.
2. Measure per-channel overlap and unique yield.
3. Decide whether to remove, dedup, or keep channels based on that evidence.
4. Implement the smallest delivery-state change that follows from the data.

## Claim map
- [ ] **#29 - channel unique-yield is measured before consolidation**
  - Proof obligations claimed: accepted-finding corpus, source/channel labels, overlap/unique-yield summary.
  - Partial / not claimed: prompt/classifier quality.
  - Evidence required: reproducible extraction or auditable manual ledger.
  - Current evidence: issue evidence only.
- [ ] **#25 - double-emission is removed or justified by measured yield**
  - Proof obligations claimed: delivery decision and implementation/proof if consolidation is warranted.
  - Partial / not claimed: external Kilo policy beyond measured additive value.
  - Evidence required: before/after delivery behavior or explicit no-change justification grounded in #29.
  - Current evidence: blocked by #29 measurement.

## Automated gates
Keep draft until #29 evidence exists. If implementation changes review/QC delivery, run `just test` and targeted delivery-state tests.
