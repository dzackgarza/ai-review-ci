<!-- policy-alignment-gate -->

## Intended result

ai-review-ci reviewer/QC surfaces prefer user-observable boundary proof over implementation-internal tests and flag bespoke parity work that fails to consider existing tools, file formats, libraries, or protocols first.

## Scope

- Included: reviewer/QC guidance and any deterministic fixtures/rules that operate after work is submitted, covering #106 and #107.
- Excluded: live planning workflow inside `dzackgarza/ai` unless a later explicit transfer says otherwise.
- Preserved behavior: no mocks/fakes/defaults/fallbacks are introduced as proof shortcuts, and policy-index edits respect the owned-source/vendor boundary.

## GitHub tracking

- Target issue set / subtree: #106 and #107
- Milestone: Adaptive Workflow Orchestration
- Closes on merge:
  - Closes #106
  - Closes #107
- References only:
  - Refs #102 parent epic.
  - Refs #62 / PR #146 fixture work.
  - Refs #44 owned-surface reduction context.

## Implementation plan

1. Add or update maintained reviewer/QC guidance for user-observable proof first (#106).
2. Add or update maintained reviewer/QC guidance for parity-first decisions before bespoke implementations (#107).
3. Include calibration examples: app boot/rendering/fuzzy search for #106; QuickTeX/fzf for #107.
4. Add at least one reviewer signal or fixture where the repo has a real post-work checking surface.

## Claim map

- [ ] **#106 - proof-shape doctrine prefers user-observable boundaries**
  - Proof obligations claimed: maintained guidance, calibration examples, and one signal/fixture where feasible.
  - Partial / not claimed: replacing #62's full torture fixture suite.
  - Evidence required: guidance/test diff mapped to acceptance criteria.
  - Current evidence: issue only.

- [ ] **#107 - parity-first doctrine is visible to reviewer/QC surfaces**
  - Proof obligations claimed: checklist/guidance and reviewer prompt routing for custom-engine smells.
  - Partial / not claimed: ai-review-ci internal owned-surface cleanup already handled by #44.
  - Evidence required: maintained surface diff and manifest/prompt proof if applicable.
  - Current evidence: issue only.

## Automated gates

Keep draft until policy/vendor placement is correct and relevant reviewer/QC tests plus `just test` are green.
