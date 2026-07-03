<!-- policy-alignment-gate -->

## Intended result
ai-review-ci owns a reusable label taxonomy, issue/PR template distribution path, and agent-facing label-routing guidance so downstream repositories receive consistent triage metadata during installation.

## Scope
- Included: canonical label taxonomy, idempotent install-labels command or install flag, vendored issue/PR templates, and label-routing skill/guidance.
- Excluded: repo-specific label bikeshedding and manual label cleanup in every downstream repo.
- Preserved behavior: existing workflow/scaffold installation remains non-destructive and repo-owned files are not overwritten silently.

## GitHub tracking
- Target issue set / subtree: #166
- Milestone: Versioned QC distribution
- Closes on merge:
  - Closes #166
- References only: none

## Implementation plan
1. Define the canonical taxonomy in one machine-readable source.
2. Add an idempotent label installation command that creates or updates labels safely.
3. Extend install/template distribution only where conflicts are explicit and fail-loud.
4. Add label-routing guidance so agents opening issues pick the right labels.

## Claim map
- [ ] **#166 - downstream repos can install and use the canonical label taxonomy**
  - Proof obligations claimed: taxonomy source, installer behavior, conflict/idempotence proof, templates/guidance.
  - Partial / not claimed: applying labels to every existing downstream repo in this PR.
  - Evidence required: tests with an isolated target/repo API boundary or mocked `gh` boundary that proves create/update/skip behavior.
  - Current evidence: issue definition only.

## Automated gates
Keep draft until installer tests, template conflict behavior, and `just test` are green.
