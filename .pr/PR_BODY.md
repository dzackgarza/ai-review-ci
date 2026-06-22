## Intended Result

Reduce owned parsing, validation, and glue code inside ai-review-ci where standard library facilities, typed models, or narrower schema-owned boundaries can carry the obligation more clearly.

The milestone should remove avoidable custom surface without deleting forensic evidence of real requirements or weakening the QC contract.

## Scope

Included:

- Inventory and centralize GitHub API response parsing into typed models or one schema-owned parser.
- Replace repeated TOML shape validation with typed config models or one schema-owned parser.
- Replace `_ordered_unique` only if it is still plain ordered deduplication.
- Retire `merge_ini.py` if caller inventory proves it unused, or document and test the retained boundary if it is still needed.

Excluded:

- Broad style refactors not tied to owned-surface reduction.
- Deleting glue before transferring or invalidating its original burden.
- Source-text-only tests that prove a symbol changed without proving behavior.

Preserved behavior:

- Existing review-runner and QC behavior remains semantically equivalent unless a child issue explicitly changes it.
- Config/API validation fails loudly at owned boundaries.

## GitHub Tracking

- Milestone: [Owned surface reduction](https://github.com/dzackgarza/ai-review-ci/milestone/5)
- Development links:
  - Closes #44
  - Closes #47
  - Closes #48
  - Closes #49
  - Closes #50

## Execution Structure

Every child issue starts with current caller/inventory evidence. #47 and #48 create typed/schema boundaries. #49 is a small standard-idiom replacement only if semantics are still plain ordered dedupe. #50 either deletes unused INI merge glue with proof or keeps it with a documented boundary and coverage. #44 closes only when the owned-surface reductions are integrated and evidenced.

## Milestone Tree

- [ ] **M1 - Owned surface reduction in review-runner internals** ([#44](https://github.com/dzackgarza/ai-review-ci/issues/44))
  - Complete when: avoidable owned parsing/config/glue surfaces are replaced, retired, or explicitly justified with boundary tests.

- [ ] **W1 - Typed GitHub API response parsing** ([#47](https://github.com/dzackgarza/ai-review-ci/issues/47))
  - Behavior: repeated GitHub API dict extraction is replaced or centralized through typed models where it reduces owned surface.
  - Acceptance: malformed and accepted response shapes are tested at the consumer boundary.
  - Evidence: pending parser/model diffs and boundary tests.

- [ ] **W2 - Typed TOML/config parsing** ([#48](https://github.com/dzackgarza/ai-review-ci/issues/48))
  - Behavior: repeated manual TOML shape validation is replaced by typed config models or one schema-owned parser.
  - Acceptance: valid config, missing required keys, and wrong-type values fail through the real script/parser boundary.
  - Evidence: pending parser/model diffs and boundary tests.

- [ ] **W3 - Ordered-unique standard idiom** ([#49](https://github.com/dzackgarza/ai-review-ci/issues/49))
  - Behavior: replace bespoke ordered-unique accumulation only if current semantics are still plain ordered deduplication.
  - Acceptance: order preservation and duplicate removal are covered by focused tests or existing script-level proof.
  - Evidence: pending inventory, diff, and tests.

- [ ] **W4 - INI merge wrapper disposition** ([#50](https://github.com/dzackgarza/ai-review-ci/issues/50))
  - Behavior: retire `merge_ini.py` if caller inventory remains empty; otherwise justify the retained boundary and test it.
  - Acceptance: deletion is backed by caller inventory, or retention has a specific constraint and coverage.
  - Evidence: pending caller search output, deletion/retention diff, and verification.

## Automated Gates

This PR remains draft until every checklist item has commit/evidence anchors, current caller inventories are recorded for deletion/replacement decisions, boundary tests prove behavior, review residue is resolved or moved to a separate debt issue, and GitHub checks pass.
