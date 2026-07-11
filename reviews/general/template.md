## CI Constraints (MANDATORY)

This runs in a CI environment.
Follow these rules exactly:

- **Do NOT modify any workflow files, scripts, or CI infrastructure.** You are running in a restricted mode.
- Do not ask questions.
  Do not request confirmation.
  Do not pause for input.

## Task

Analyze the code in scope (defined by the scope instructions above) for structural code defects, architectural decay, and quality regressions.

### Execution

1. Cover the code in scope following the coverage strategy from the scope instructions above.
2. Check test quality, dead code, architectural problems.
3. Apply the Six Decay Risks (R1-R6) to real files you read.
4. Record every file you read in `checked_surfaces` with the reason and lines examined.

### Policy Alignment

Findings must stay inside the project's policy axioms; a finding whose implied direction violates them is guaranteed-reject churn.

- Fail-loud: never frame a finding so its natural fix adds defensive layers, catch-all handling, or error-kind proliferation.
  If the code swallows or flattens errors, that swallow is the finding — cite the `POLICY.*` code.
- No speculative performance findings: raise performance only when auditable to a real logged or reported user performance problem.
- Config-driven constants: do not push consolidation into in-code constant tables; behavioral values belong in the declared config surface (`POLICY.NO_HIDDEN_CONFIG`).
- Optional/absent data: an optional field tolerating absent data is presumed invalid; the aligned direction is require-and-fix-the-producer (`POLICY.NO_UNJUSTIFIED_OPTIONALITY`), not accommodating absence.
- When the defect you are describing is itself a slop pattern (fallback, default, mock, catch-all, non-proving test), name it with its `POLICY.*` code instead of writing generic bug analysis around it.

### No Remediation

Diagnose only.
Do not propose fixes, patches, or code changes — remediation is handled by separate agents after disposition.

### Honest Empty Reports

If the code in scope yields no real finding, submit a report with an empty `findings` array (`"findings": []`), keeping `review_scope` and `checked_surfaces` accurate.
Never invent or pad findings to make the report look substantive.

### Output Format

Write a JSON report to `.agents/review-runner/candidates/submitted.json`.

To get the exact schema (fields, types, constraints), run: `/home/reviewer/bin/submit-candidate --help`

Key rules every finding must satisfy:

- `violated_invariant`: The named contract, behavior, or invariant that was violated.
  "This file is too long" is insufficient — what behavior fails because of this length?
  A violated invariant names a required behavior that is provably impossible, silently skipped, unverifiable, or non-deterministic.
- `proof_command`: The exact command, grep pattern, or code path that proves the violation exists.
  A file path alone is not proof — show the command output, the code flow, or the diagnostic that demonstrates the failure.
- `symptom`, `source`, `consequence`: diagnosis only — what is observably wrong, what produces it, what breaks because of it.
- `policy_code`: include the matching vendored `POLICY.*` ID when the finding is policy-bearing.
  Do not invent IDs.
  Leave `remediation_code` absent unless a canonical `REMEDIATE.*` ID is explicitly required by the schema; deterministic rendering resolves the canonical remediation after validation.
- `evidence`: At least one entry with `kind`, `path`, and `lines` showing the exploration.

**Tier rules:**

- **Tier 1** (significant): Label as `[BLOCKER]` or `[SHOULD FILE ISSUE]`. Must have a non-low-signal category.
- **Tier 2** (cleanup): Label as `[NOTE]`. Lower-signal categories (code-style, naming, formatting, file-length, etc.) must be Tier 2.

**Forbidden:**

- Runner-internals findings about `/opt/ai-review`, `/home/reviewer/.review/infra`, `quality-control/ci`, or validator implementation files.
- `score` and `report` fields — rejected by the validator.

## Submitting Your Report

Write your report to `.agents/review-runner/candidates/submitted.json`. Then run `/home/reviewer/bin/submit-candidate` (no arguments).

If the script exits 0, your report was accepted and you are done.
If it exits non-zero, read the errors, fix the SAME file, and re-run the script.
Repeat until the script exits 0.
