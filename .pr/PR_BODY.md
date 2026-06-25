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

- [x] **M1 - Owned surface reduction in review-runner internals** ([#44](https://github.com/dzackgarza/ai-review-ci/issues/44))
  - Complete when: avoidable owned parsing/config/glue surfaces are replaced, retired, or explicitly justified with boundary tests.
  - Evidence: #47 (GitHub-API parsing centralized into typed models, 14/14 `test_context.py`), #49 (ordered-unique → `dict.fromkeys`), #50 (dead `merge_ini.py` retired), #48 (disposed — already schema-owned; conversion would add surface).

- [x] **W1 - Typed GitHub API response parsing** ([#47](https://github.com/dzackgarza/ai-review-ci/issues/47))
  - Behavior: the per-field code-scanning-alert and review-thread extraction in `context.py` (the bespoke `_string`/`_integer`/`_mapping`/`_alert_*` helpers) is replaced by one validated boundary in `src/ai_review_ci/github_api.py` (`CodeScanningAlert`, `ReviewThread`), parsed via a fail-loud `_parse`. Raw alert dicts are still forwarded verbatim to the SARIF carry-forward payload.
  - Acceptance: malformed and accepted shapes are tested at the consumer boundary.
  - Verification: the existing `tests/test_context.py` is the unchanged oracle — accept cases, reject cases (empty `rule.id`, string `start_line`, non-string dismissed comment), and the empty-comment-thread-without-path edge. **14/14 pass.** `context.py`/`github_api.py` import only stdlib + pydantic (not `models.py`), so they run on Python 3.13 where pydantic builds — verified there in isolation; pydantic-core validation semantics are identical on 3.14.

- [x] **W2 - Typed TOML/config parsing — disposition: no conversion warranted** ([#48](https://github.com/dzackgarza/ai-review-ci/issues/48))
  - Inventory of "repeated manual TOML shape validation":
    - `tool-artifacts/scripts/python_qc_metadata.py` — `_optional_table` / `_required_list` / `_string_list`: already one small, fail-loud, schema-owned parser, exercised by `tests/test_python_qc_metadata.py`.
    - `tool-artifacts/scripts/read_qc_excludes.py` — `load_excludes`: a single list-of-strings validator, fail-loud, covered by `tests/test_justfiles.py::test_sync_qc_excludes_*`.
    - `src/ai_review_ci/policy_index.py` / `doctor.py` — thin single-load TOML (`VENDOR.toml`, manifest) consumed by name; not repeated shape validation.
  - Disposition: the standalone QC scripts run via `uv run --script` (PEP 723) with **no pydantic dependency**. Converting them to pydantic models would add a per-run dependency to restate `list[str]`-shaped validation — that *increases* owned/operational surface, the opposite of the milestone goal ("replace … **where it reduces owned surface**"). The existing per-script validators already are the schema-owned parser the issue asks for. No conversion is made; closed as already-satisfied. (Mirrors the #46 call: don't add a mechanism that doesn't pay for itself.)

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
