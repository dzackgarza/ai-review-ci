# Implementation Style Guide

Load this guide before implementing a design that reaches one of its pattern families.
It is also the canonical repair source after triage provides a policy code.

The route table is the remediation catalogue.
Style cards elaborate recurring bad shapes, rearchitecture, and proof burdens, but they do not select or override the route owned by the canonical policy record.

## Language Profiles

Select the language profile before applying a card.
The card owns the invariant and proof obligation; the profile owns the concrete construction and migration shape.

- [[style-guide/style-guide-python/SKILL|Python]] — Pydantic/dataclasses, enums, typed outcomes, and real Python boundaries.
- [[style-guide/style-guide-typescript/SKILL|TypeScript and Bun]] — Zod, discriminated unions, typed outcomes, and real TypeScript/Bun boundaries.
- [[style-guide/style-guide-bash/SKILL|Bash]] — explicit inputs, command boundaries, `case` modes, and observable command proof.
- [[style-guide/style-guide-sage/SKILL|SageMath]] — routing stub pending observed Sage-specific repairs.

## Remediation Routes

The canonical policy record names the route code.
This index defines only the construction named by that code; it does not repeat an inverse policy map.

| Route code | Preferred construction |
| --- | --- |
| `REMEDIATE.TOTAL_CONFIG_MODEL` | Put required configuration in the declared config surface. Validate once at startup into a total model. Missing, malformed, partial, or unknown config fails loudly. |
| `REMEDIATE.FAIL_LOUD_BOUNDARY` | Assert or check required resources at the owned boundary, then execute without fallback. Let unexpected errors propagate. At an external boundary, translate a specific observed exception once into a typed domain outcome; ordinary callers dispatch that outcome explicitly. |
| `REMEDIATE.EXPLICIT_STATE_MODEL` | Enumerate expected domain states and legal transitions, parse boundary input into typed outcomes, and dispatch exhaustively before effects execute. Unexpected failures propagate. Retry only a typed transient failure through a bounded, observable policy after proving the operation is safe to repeat. |
| `REMEDIATE.REAL_PROOF_LOOP` | Replace fake or masked proof with tests that cross the real boundary, use real fixtures/data/services available to the project, and assert semantic output or side effects. Commit red proof before green fixes for reported bugs. |
| `REMEDIATE.API_SPLIT_OR_VARIANT` | Split behavior into named functions when the modes are separate operations. Use an explicit enum/tagged variant only when the mode is domain data, and dispatch exhaustively. |
| `REMEDIATE.STRUCTURED_TYPES` | Replace casts, `Any`, broad `Partial`, string errors, and dict-shaped owned data with explicit domain types, schemas, enums, and structured errors. Replace runtime duck-typing introspection (`hasattr`, dynamic `getattr`/`setattr`/`delattr`, `vars()`, `type(x)` comparisons, `__class__`/`__dict__` probing) by declaring the exact expected type in the signature and, where narrowing is genuinely domain data, dispatching exhaustively on `isinstance` against declared types. Tests assert semantic variants, not string rendering or shape. |
| `REMEDIATE.TYPED_DEPENDENCY_BOUNDARY` | Preserve the correct library. Restore type information with stubs when practical; otherwise isolate the untyped import in one typed firewall module that returns project-owned typed values. |
| `REMEDIATE.USE_EXISTING_CAPABILITY` | Replace the bespoke implementation with the language, framework, installed dependency, or project-owned component that already owns the capability. Establish a concrete unmet contract before retaining custom code. |
| `REMEDIATE.REMOVE_SUPPRESSION_WITH_EXCEPTION_PROTOCOL` | Remove the suppression and fix the underlying invariant. If a validator is wrong, stop for explicit policy exception approval with policy code, justification, replacement invariant, boundary proof, and audit trail. |
| `REMEDIATE.DELEGATE_GLOBAL_QC` | Route public `test` and `test-ci` through `~/ai-review-ci/justfiles/<language>.just`. Keep project-specific semantic checks private and composed after the global gate. |
| `REMEDIATE.TRACK_STATIC_ARTIFACT` | Move owned prompts, scripts, configs, templates, and static data into tracked files. Runtime code loads the reviewed artifact rather than constructing it from inline strings. |
| `REMEDIATE.REPLACE_LEGACY_PATH` | Migrate all callers to the new path, prove the migrated behavior, then remove the obsolete interface with burden disposition. |
| `REMEDIATE.OBSERVE_BEFORE_BRANCHING` | Do not add code. Preserve the invariant as an assertion or fail-loud boundary. Add a branch only after a real observed incident establishes the domain case. |
| `REMEDIATE.PREFER_ASSERTION` | Reject suggestions to replace `assert` with `if/raise` (especially the `python -O` argument). Keep the assertion, make it ADDD-shaped, delete any `AssertionError` catch path, and strengthen it to the strongest provably-true invariant. See `[ASSERT-OVER-RAISE]`. |
| `REMEDIATE.BURDEN_DISPOSITION` | Reconstruct the original obligation, then mark it solved, invalidated, transferred to a real proof surface, or recorded unresolved. Do not treat labels, docs, deletion, or comments as resolution. |
| `REMEDIATE.BLAST_RADIUS_REPAIR` | Inspect the owning boundary, adjacent call sites, tests, config surface, and history for the same failure process. Fix the full damaged obligation, not only the matched token. |

## Selection Rule

Before implementation, select supplemental cards by the boundary and intended construction.
After triage, the fixer follows the remediation code named by the canonical policy record to the exact route here.

If more than one card applies, choose the one that restores the original obligation at the widest real boundary.
Do not pick the smallest local edit.

* * *

## Style Cards

- [`FALLBACK-HEDGE`](../cards/fallback-hedge.md) — Fallback / Optional-Dependency / File-Availability Hedge
- [`SWALLOW-CATCH`](../cards/swallow-catch.md) — try/catch That Swallows or Hedges
- [`EXPLICIT-STATE-MODEL`](../cards/explicit-state-model.md) — Exception-Driven Ordinary Control Flow
- [`DATA-PEEK`](../cards/data-peek.md) — Data-Peeking Inside Loops
- [`NESTED-CONDITIONAL`](../cards/nested-conditional.md) — Nested / Stacked Conditional Chains
- [`DYNAMIC-FILE-CREATION`](../cards/dynamic-file-creation.md) — Dynamic File / Config Creation from Code
- [`INLINE-STRINGS`](../cards/inline-strings.md) — Inline Large Strings / Prompts Embedded as Code
- [`IMPLICIT-STATE`](../cards/implicit-state.md) — Implicit / Defaulted / Discovered State
- [`PARTIAL-RESULT`](../cards/partial-result.md) — Partial / Sentinel Results
- [`BOOLEAN-MODE`](../cards/boolean-mode.md) — Boolean Mode Parameters
- [`UNTYPED-IMPORT-BOUNDARY`](../cards/untyped-import-boundary.md) — Untyped Third-Party Imports
- [`BOUNDARY-BYPASS`](../cards/boundary-bypass.md) — Boundary Test Bypass
- [`STRINGLY-ERROR`](../cards/stringly-error.md) — String-Based Error Types
- [`ADMIN-ARTIFACT`](../cards/admin-artifact.md) — Non-Proof / Administrative Artifacts
- [`QC-BYPASS`](../cards/qc-bypass.md) — Local QC Bypass
- [`VALIDATOR-BYPASS`](../cards/validator-bypass.md) — Validator Bypass Markers
- [`LEGACY-SHIM`](../cards/legacy-shim.md) — Compatibility / Legacy Shims
- [`UNOBSERVED-FAILURE`](../cards/unobserved-failure.md) — Unobserved-Failure Branches
- [`ASSERT-OVER-RAISE`](../cards/assert-over-raise.md) — `if/raise` Where an Assertion Belongs
- [`CODE-VERBOSITY`](../cards/code-verbosity.md) — Code Verbosity and Complexity
- [`CODE-WITHIN-CODE`](../cards/code-within-code.md) — Code Within Code / Embedded Cross-Language Programs
- [`EXISTENCE-AS-PROOF`](../cards/existence-as-proof.md) — Existence / Truthy / Shape as Proof
- [`NO-CRASH-PROOF`](../cards/no-crash-proof.md) — No-Throw / No-Crash as Proof
- [`MOCK-AS-PROOF`](../cards/mock-as-proof.md) — Mock/Spy/Call-Count as Proof
- [`SOURCE-POLICING`](../cards/source-policing.md) — Source Policing in Tests
- [`DELETION-LAUNDERING`](../cards/deletion-laundering.md) — Deletion Laundering / Proof-Burden Erasure
- [`BESPOKE-DEP`](../cards/bespoke-dep.md) — Bespoke Dependency Reinvention
