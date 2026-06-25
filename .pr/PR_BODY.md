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
  - Behavior: repeated GitHub API dict extraction in `context.py` / `threads.py` is replaced or centralized through typed models where it reduces owned surface.
  - Acceptance: malformed and accepted response shapes are tested at the consumer boundary.
  - Status: NOT STARTED. This is package code that imports `models.py`; pydantic `BaseModel` cannot build on the local 3.14rc2 interpreter, so the boundary tests can only be authored against CI. Held for a CI-verifiable pass to avoid shipping an unrunnable core-parser refactor.

- [ ] **W2 - Typed TOML/config parsing** ([#48](https://github.com/dzackgarza/ai-review-ci/issues/48))
  - Behavior: repeated manual TOML shape validation is replaced by typed config models or one schema-owned parser.
  - Acceptance: valid config, missing required keys, and wrong-type values fail through the real script/parser boundary.
  - Status: NOT STARTED. Standalone-script validation (`read_qc_excludes.py`, the `_optional_table`/`_string_list` helpers) is locally verifiable; the package-side parsers (`doctor.py`, `policy_index.py`) are BaseModel-bound and CI-only. Held alongside W1.

- [x] **W3 - Ordered-unique standard idiom** ([#49](https://github.com/dzackgarza/ai-review-ci/issues/49))
  - Behavior: bespoke ordered-unique accumulation in `python_qc_metadata.py` (confirmed plain ordered dedup) replaced with `list(dict.fromkeys(...))`, inlined at all three call sites; helper removed.
  - Acceptance: order preservation + duplicate removal covered through the real public functions.
  - Evidence: `239bf4e` — `tests/test_python_qc_metadata.py` (first-party modules, dependency-group requirements, PEP 723 requirements). Run locally (stdlib-only script).

- [x] **W4 - INI merge wrapper disposition** ([#50](https://github.com/dzackgarza/ai-review-ci/issues/50))
  - Behavior: `merge_ini.py` retired — caller inventory across justfiles, workflows, scripts, docs, and the package found no invocation.
  - Acceptance: deletion backed by an empty caller inventory.
  - Evidence: `239bf4e` — `grep -rn merge_ini` returns only the (now-removed) file and this contract; file deleted.

## Automated Gates

This PR remains draft until every checklist item has commit/evidence anchors, current caller inventories are recorded for deletion/replacement decisions, boundary tests prove behavior, review residue is resolved or moved to a separate debt issue, and GitHub checks pass.
