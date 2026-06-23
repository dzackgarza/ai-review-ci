# Global QC and Review Doctrine

`ai-review-ci` exists to make agent-produced work auditable at the boundary where downstream users and repositories can observe it.
Its job is not to maximize checks.
Its job is to make green mean something precise.

## False Green Is A System Failure

A downstream repo can pass tests, collect reviews, and still ship broken behavior if the proof path does not cross the real boundary.

Rules:

- Treat a green suite followed by user-boundary failure as a defect in the QC design.
- Add or repair the gate that would have crossed the missed boundary.
- Prefer deterministic gates for mandatory merge criteria.
  LLM review is signal and diagnosis unless paired with a deterministic resolution gate.
- Do not replace proof with a score.
  If unresolved review threads or missing evidence remain, the gate should name that state directly.

The `zotero-gui` PR #7 startup failure is the calibration case: mocked network tests and bypassable local hooks produced a green path while the app crashed at startup.

## Target Boundary First

Central QC must prove behavior in the target repository, not in the QC repository.

Rules:

- Every central justfile call from a downstream repo must preserve the caller root with `-d .`.
- Nested central calls must preserve the caller root as well.
- Prove central QC changes with repo-owned target fixtures or temporary target repos that fail for the intended target-specific reason.
- Self-scanning `~/ai-review-ci` is not proof of a downstream gate unless the gate explicitly owns this repository as its target.

## Mandatory But Precise

Strict QC is mandatory.
False positives and overbroad rules are central defects, not reasons for downstream bypasses.

Rules:

- Fix rule precision upstream rather than adding generic downstream suppressions.
- Do not weaken runtime-default, fallback, type-escape, mock, skip, or source-policing policies to reduce noise.
- If a correct fail-loud implementation is blocked by contradictory or overbroad rules, repair the rule contract in `ai-review-ci`.
- Never create pressure toward `--no-verify` as the normal path.
  If hooks are too heavy or too noisy, fix the tiering or precision.

## Signal Tiers

Put each proof at the tier where it gives useful signal without forcing bypasses.

Rules:

- Commit tier: fast correctness and normalization checks.
- Push/PR tier: full slop, style, coverage, dependency, and project-boundary checks.
- PR deterministic gates: diff determinism, delegation conformance, review-thread resolution, branch protection, and app boot where the profile requires it.
- Scheduled or ambient audits: broad debt scans that should not block unrelated clean diffs.
- Deferred debt must be tracked explicitly.
  Moving a broad scan out of a PR gate is not permission to forget it.

## User-Observable App Proof

GUI and app repositories need proof that exercises their actual boot and entrypoint configuration.

Rules:

- For Bun/Playwright profiles, global app-boot gates must run the target repo's real Playwright boot configuration.
- If a repository adds `playwright.actual.config.ts`, the global gate must treat it as an additional actual-entrypoint proof, not a replacement for the primary config.
- The local repo delegates app-boot to global QC. It must not hand-roll a local Playwright invocation that hides from the shared proof contract.
- Boundary mocks can support unit tests, but they cannot satisfy app-start, browser, native-wrapper, network, or live-integration proof obligations.

## Review State And Convergence

Review must be blocking, stateful, and deduplicated.

Rules:

- Findings need stable fingerprints and runner-attached provenance.
- Re-emitting the same finding across pushes should carry state forward, not create a fresh triage burden.
- Review threads are resolved only by commit evidence or a visible disposition ledger.
- A reviewer omission is not a disposition.
  Dismissed, fixed, and rejected findings must remain available as do-not-reraise context.
- PR readiness is evidence-linked contract completeness, not a large checklist with unchecked semantics.

## Empirical Reviewer Improvement

Reviewer, prompt, and policy changes need behavioral evidence.

Rules:

- Use accepted and rejected historical findings as evaluation corpora when available.
- Cover true positives, true negatives, false positives, and false negatives.
- Do not treat prompt wording, policy restatement, or a cleaner report format as proof that reviewer behavior improved.
- If a change is meant to alter subagent disposition or triage behavior, evaluate that exact behavior.

## Owned Surface Reduction

Shared QC should use known solutions where the domain does not require bespoke ownership.

Rules:

- Prefer typed models for GitHub API data, TOML/YAML configuration, SARIF, and review-state records.
- Prefer mature diff parsers, schema validators, and official CLIs over custom string extraction.
- Keep downstream trigger workflows thin.
  Schedules, branches, thresholds, and `with:` inputs are downstream-owned; review behavior, gates, validators, prompts, and scaffolds are upstream-owned here.
- When custom glue remains, name its obligation and fixture coverage.

## Bounded External Loops

QC and review pipelines that touch external sources must be bounded and dispositioned.

Rules:

- Use per-source timeouts and item/batch budgets.
- Represent disabled, quota-dead, unreachable, and exhausted source states explicitly.
- Emit `needs_review` only after the intended source search space is exhausted or a named blocker prevents safe completion.
- Make long loops resumable from explicit state, not terminal scrollback.
