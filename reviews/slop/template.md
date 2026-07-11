## CI Constraints (MANDATORY)

This runs in a CI environment.
Follow these rules exactly:

- **Do NOT modify any workflow files, scripts, or CI infrastructure.** You are running in a restricted mode.
- Do not ask questions.
  Do not request confirmation.
  Do not pause for input.

### Do not waste effort

Every command you run should serve a finding. Specifically:

- The review copy has **no `.git` directory**. Git commands (`git status`, `git log`, `git diff`, …) are denied and answer nothing; work from the files on disk.
- The complete set of valid `POLICY.*` and `REMEDIATE.*` codes is already inlined in the policy-index documents above. Do not probe Python modules, importable packages, or the review infrastructure to discover policy registries — cite codes from the inlined index or use `null`.
- Do not re-run `submit-candidate --help` more than once; the schema does not change between calls.

## Task: Slop Audit

Perform a comprehensive, fresh analysis of the code in scope (defined by the scope instructions above) focused exclusively on **slop**.

"Slop" means structural AI-generated-code defects as defined by the loaded skills: bridge-burning violations, validation-evasion constructs, runtime defaults, mocks/skips/fakes in proof paths, proof-laundering, dead control flow, dependency-inversion failures, bespoke reinvention of standard patterns, and myopic patching that hacks linters/tests into compliance.

### Execution

1. Start from the in-scope diff or repo-scope instructions above.
   For PR diff scope, the unified diff is already in the prompt; use it as the source of changed files before opening anything else.
2. Read the changed code and only the surrounding files needed to understand the changed behavior.
   Do not run broad repository-discovery probes unless the scope instructions explicitly say this is a repository-wide sweep.
3. Report actual slop patterns in any changed or materially touched file, including workflow, config, agent-facing, test, and documentation files.
4. Check these specific slop categories:
   - **Bridge-Burning Red Flags**: Runtime defaults, fallbacks, try-import, mock/fake as proof, backwards-compat shims, boolean mode flags, stringly errors, soft guards.
   - **Runtime Control-Flow Red Flags**: Conditional logic compensating for model code-writing failure.
   - **Test Pattern Violations**: Meta-assertions on source, helper-level proof laundered as boundary proof, smoke tests in proof paths, fake data.
   - **Proof-Laundering / Claim-vs-Evidence Mismatch (#185)**: When the reviewer context carries a "## PR claim map" section, compare the PR's *claimed boundary obligation* against the *evidence shape* in the diff.
     A PR that claims a real boundary (app boot, browser, subprocess, downstream repo, hook) is satisfied but supplies only a fake executable, argv recorder, helper-only test, call-count assertion, synthetic provider, or empty config generation is proof-laundering — flag it as `POLICY.NO_MOCK_PROOF` or `POLICY.NO_HELPER_PROOF`. Do not accept green CI / passing tests as proof when the claim names a boundary the evidence does not cross.
   - **Text Pattern Violations**: Weasel words, hedged claims, presenting procedural completion as substantive.
   - **UX Antipatterns**: Silent failure, error swallowing, missing diagnostics.
   - **Review-Gaming Patterns**: checking boxes instead of reading the diff, probing validator internals, treating schema success as review success, submitting clean-shaped findings, or using unrelated command failures as evidence.

### Threat Model

Slop review is calibrated to a specific threat model.
The threat is:

- fake / fallback / default / mock behavior that stops the app failing when it should, so the user is surprised later;
- real bugs that fail slow or silently, so the user never knows and cannot provision an agent to diagnose;
- cross-file fragility, where the next agent's small feature breaks many files;
- tests that prove nothing;
- the app lying to the user.

The threat is NOT "find every esoteric bug or technically-not-quite-right detail."
Generic correctness nitpicks, speculative micro-performance, style preferences, and "semantically not-quite-right" observations are off-target findings; do not emit them.
Do not raise a performance finding unless it is auditable to a real logged or reported user performance problem.

When you are staring at a slop pattern — a catch-all handler that flattens distinct failure domains, a fallback, a default, a mock, a fail-slow path, stringly errors, a non-proving test — name it as slop tersely with its `POLICY.*` code.
Do not reframe it as a generic bug and produce paragraphs of fine-grained bug analysis around it; the pattern itself is the finding.

Do not frame a finding so that its natural fix violates policy.
A catch-all swallow's policy-aligned direction is fail-early removal of the swallow, not "add a distinct error kind" (which drives more error-handling layers).
An unjustified optional's direction is require-and-fix-the-data (`POLICY.NO_UNJUSTIFIED_OPTIONALITY`), not accommodating the absence.
The `policy_code` field carries the obligation; deterministic rendering resolves the canonical remediation — your narrative must not push a direction the policy index forbids.

### Finding Labeling

Each finding MUST carry one of these labels in the JSON `label` field:

- `SLOP` — Definite slop violation.
- `SLOP SUSPECT` — Likely slop but needs human judgment to confirm.

Do not submit `NOTE`, "clean", "no issues", or all-clear findings.
If you cannot identify a real `SLOP` or `SLOP SUSPECT` finding from the in-scope material, submit a report with an empty `findings` array (`"findings": []`) and the `review_scope` you actually examined.
An honest empty report is always preferable to an invented or padded finding — never manufacture slop to have something to submit.

### No Remediation

Slop review is an adversarial audit.
Diagnose the fraud and trace its causal path, not patch it.
Do not include remediation steps.

### Output Format

Write a JSON report to `.agents/review-runner/candidates/submitted.json`.

To get the exact schema (fields, types, constraints), run: `/home/reviewer/bin/submit-candidate --help`

Do not inspect validator internals.
Do not read or search for `submit-candidate` implementations.
Do not inspect `/opt/ai-review`, `/home/reviewer/.review/infra`, `quality-control/ci`, or alternate copies of review infrastructure.
Validation is not a research surface; it is only the final report gate.

Key rules every finding must satisfy:

- `violated_invariant`: The named contract, behavior, or invariant that was violated.
  A slop finding's violated invariant names a required behavior that is provably impossible, silently swallowed, replaced by a fake, or non-deterministic.
- `proof_command`: The exact command, grep pattern, or code path that proves the violation exists.
  Not a file path — the actual command output or code flow that demonstrates the failure.
- `policy_code`: the vendored `POLICY.*` ID for the bridge-burning obligation being weakened.
  Do not invent IDs and do not write remediation prose.
  Leave `remediation_code` absent unless the canonical index requires an explicit override; deterministic rendering resolves the canonical remediation after validation.
- All seven slop-specific narrative fields (`pattern`, `task_narrative`, `slop_narrative`, `why_it_matters`, `user_surprise`, `existential_justification`, `failure_mode`).
- `evidence`: At least one entry with `kind`, `path`, and `lines`.

**Forbidden:**

- Clean-report findings: labels, patterns, invariants, or narratives claiming the diff is clean, has no issues, or has nothing to report.
- Review-theater fields such as `checked_surfaces` or `rejected_easy_wins`.
- `score` and `report` fields — rejected by the validator.

## Submitting Your Report

Write your report to `.agents/review-runner/candidates/submitted.json`. Then run `/home/reviewer/bin/submit-candidate` (no arguments).

If the script exits 0, your report was accepted and you are done.
If it exits non-zero, read the errors, fix the SAME JSON file, and re-run the script.
If the error shows that a finding is clean-shaped, out of scope, or based on review-runner internals, remove that finding (an empty `findings` array is valid) and resubmit.
