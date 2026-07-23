# Policy Database

This file is the canonical database of named bridge-burning policies.
Other skills may teach review, testing, debugging, or remediation workflows, but policy identity and policy text live here.

Disposition and reviewer agents load this file to classify the source and inspect adjacent obligations.
Fixer agents follow the assigned policy's exact route into `../../style-guide/references/style-guide-index.md`.

## Record Schema

Each policy record contains:

- `Category`: the policy family used for routing and reporting.
- `Rule`: the canonical obligation.
- `Invalid local fixes`: local edits that preserve the violation.
- `Detection handles`: red-flag or banned-shape labels that map to the policy.
- `Related remediation`: the exact fixer-side route owned by this policy.
  The named construction is defined in `../../style-guide/references/style-guide-index.md`.

## Policy Records

### Runtime, Config, and State

#### `POLICY.RUNTIME_DEFAULT` — No defaults in runtime logic

Category: Runtime, Config, and State

Rule: Runtime values must be supplied explicitly and validated at the owned boundary.
Config, env, CLI, schema, serde, Pydantic, dict, and option defaults are banned when they let missing data become success-shaped execution.

Invalid local fixes: Replacing one default syntax with another; moving the default to a constant; adding a comment that the default is harmless.

Detection handles: `RUNTIME-DEFAULTS`, `DEFAULTS-OPTIONALITY`, `RUNTIME-DEFAULTS-FALLBACKS`, `CONFIG-DEFAULTING`, `NULLISH-DEFAULT`, `UNWRAP-OR`, `CONFIG-SCHEMA`

Related remediation: `REMEDIATE.TOTAL_CONFIG_MODEL`

#### `POLICY.TOTAL_CORE_STATE` — No optional core state

Category: Runtime, Config, and State

Rule: Normalize required state once at the boundary.
Inside owned core logic, required data is total and non-optional.

Invalid local fixes: Sprinkling null checks; using `Optional`, `Partial`, `Any`, sentinel fields, or "maybe initialized" state in core paths.

Detection handles: `OPTIONAL-STATE`, `OPTIONAL-UI-FAILOPEN`, `OPTION-CORE-STATE`, `IFLET-INITIALIZED`, `NESTED-IF-CHAIN`

Related remediation: `REMEDIATE.TOTAL_CONFIG_MODEL`

#### `POLICY.NO_UNJUSTIFIED_OPTIONALITY` — No unjustified optionality for absent data

Category: Runtime, Config, and State

Rule: An optional, nullable, or defaulted field declared to tolerate absent data is invalid by default.
The required move is to require the field and fix the producer so the data is always present, handling true absence as a narrow sliced-off case at the boundary.
Optionality is admissible only when absence is a genuine irreducible domain state — a fact about the domain, not a convenience for a producer that sometimes omits the value — and that justification must be stated at the point of declaration.
Do not push optionality up into a shared interface to tolerate one absent case; that weakens the field for every consumer.
"Genuinely optional" claimed from priors, without a declaration-site justification, resolves against the optional.

Invalid local fixes: Defending the optional as "genuinely optional" in review or triage without a declaration-site justification; widening a shared interface field to optional; adding null checks or sentinel stand-ins at consumers; moving the default value elsewhere.

Detection handles: `UNJUSTIFIED-OPTIONAL`, `OPTIONAL-STATE`, `DEFAULTS-OPTIONALITY`, `OPTIONAL-UI-FAILOPEN`

Related remediation: `REMEDIATE.TOTAL_CONFIG_MODEL`

#### `POLICY.NO_HIDDEN_CONFIG` — No hidden behavioral config in code

Category: Runtime, Config, and State

Rule: Behavioral parameters, thresholds, paths, provider choices, retries, feature flags, and policy decisions belong in the declared config surface as required values.

Invalid local fixes: Moving to `constants.*`; using `const`/`static`/top-level literals; calling it a true invariant without applying the invariant test.

Detection handles: `GLOBAL-STATE`, `CONFIG-SCHEMA`, `IMPLICIT-STATE`

Related remediation: `REMEDIATE.TOTAL_CONFIG_MODEL`

#### `POLICY.NO_AMBIENT_DISCOVERY` — No ambient discovery as source of truth

Category: Runtime, Config, and State

Rule: Behavior must not be inferred from installed tools, current directory, shell profiles, caches, home-directory artifacts, or multi-location search chains unless that is the explicit product contract.

Invalid local fixes: Env-then-config-then-default chains; installed-tool probing; local snooping; "works because it found something else".

Detection handles: `AMBIENT-DISCOVERY`, `GLOBAL-STATE`, `SILENT-PROBING`, `command -v`

Related remediation: `REMEDIATE.FAIL_LOUD_BOUNDARY`

#### `POLICY.NO_DEFENSIVE_HOTPATH` — No defensive validation inside trusted hot paths

Category: Runtime, Config, and State

Rule: Validate once at the owned boundary, then use total types internally.
Core code should not repeatedly defend against impossible malformed state.

Invalid local fixes: Every function checking null/missing/impossible variants; tests for impossible branches; defensive guards in trusted core paths.

Detection handles: `DEFENSIVE-GUARDS`, `DEFENSIVE-EXCESS`, `IF-REQUIRED-INVARIANT`

Related remediation: `REMEDIATE.FAIL_LOUD_BOUNDARY`

### Fail-Loud Execution

#### `POLICY.FAIL_OPEN` — No fallbacks

Category: Fail-Loud Execution

Rule: Required work fails loudly.
Do not continue with substitute data, empty collections, placeholder output, cached guesses, "best effort", or alternate branches that preserve a success signal after the obligation failed.

Invalid local fixes: Catching and logging; returning `None`, `[]`, `{}`, `false`, or a placeholder; adding another fallback layer.

Detection handles: `FALLBACK-CHAINS`, `FAIL-OPEN-BAN`, `LAUNDER-EMPTY-LIST`, `EMPTY-ARRAY-FAILED`, `VECTOR-LAUNDERING`, `FALSEY-RESULT`, `EMPTY-OUTPUT-FAILURE`, `STATUS-LAUNDERING`

Related remediation: `REMEDIATE.FAIL_LOUD_BOUNDARY`

#### `POLICY.CRITICAL_DEPENDENCY` — No optional critical dependencies

Category: Fail-Loud Execution

Rule: A dependency, binary, service, model, config file, or generated artifact required for the operation is mandatory.
Its absence is a setup error, not a branch in product logic.

Invalid local fixes: `try import`; `command -v` fallback; "skip if missing"; vendoring a weaker substitute.

Detection handles: `OPTIONAL-DEPS`, `TRY-IMPORT`, `FALLBACK-HEDGE`

Related remediation: `REMEDIATE.FAIL_LOUD_BOUNDARY`

#### `POLICY.NO_PARTIAL_SUCCESS` — No partial success

Category: Fail-Loud Execution

Rule: Owned operations either complete the claimed operation or fail with a hard error.
Do not return success-shaped results with warnings, missing fields, skipped substeps, or hidden data loss.

Invalid local fixes: Returning `ok: true` with warnings; empty arrays on error; rendering with missing pieces; best-effort modes.

Detection handles: `PARTIAL-SUCCESS`, `PARTIAL-RESULT`, `WARNING-CONTINUE`

Related remediation: `REMEDIATE.FAIL_LOUD_BOUNDARY`

#### `POLICY.NO_ERROR_DISCARD` — No swallowed errors

Category: Fail-Loud Execution

Rule: Errors and failed results must be propagated, handled immediately as a real domain alternative, or converted into structured failure.
They must not be discarded.

Invalid local fixes: `.ok()`, `let _ =`, `filter_map(Result::ok)`, `except: pass`, `catch(() => default)`, `|| true`, stderr suppression.

Detection handles: `SWALLOWED-ERRORS`, `OK-DISCARD`, `SUPPRESSION-FALLBACK`, `PIPE-TRUE`, `NO_ERROR_DISCARD`

Related remediation: `REMEDIATE.FAIL_LOUD_BOUNDARY`

#### `POLICY.NO_EXCEPTION_CONTROL_FLOW` — No exception-driven ordinary control flow

Category: Fail-Loud Execution

Rule: Expected domain states, legal transitions, and routine alternatives must be represented explicitly before effects execute.
Do not deliberately provoke and catch failures to discover state, select ordinary behavior, probe an API or object shape, or drive fallback and retry trees.
Exceptions mean that the current computation cannot fulfill its contract; retries are admissible only for a classified transient failure when the operation is safe to repeat, the attempt count is bounded, backoff is explicit, and every attempt remains observable.

Canonical rationale: [Error Handling as Control Flow](error-handling-as-control-flow.md).

Invalid local fixes: Reordering catches; narrowing a catch while retaining exception-selected routine behavior; moving the probing loop into a helper; renaming retries as resilience; catching an exception only to return a domain sentinel; adding preflight attempts that still mutate state; retrying without a typed transient-failure class and idempotency proof.

Detection handles: `EXCEPTION-CONTROL-FLOW`, `TRY-EXCEPT-FALLBACK`, `SWALLOWED-ERRORS`, `ASSERTION-CATCH`

Related remediation: `REMEDIATE.EXPLICIT_STATE_MODEL`

### Proof and Test Integrity

#### `POLICY.NO_SMOKE_PROOF` — No proof-free smoke paths

Category: Proof and Test Integrity

Rule: Tests and QC paths must prove owned behavior through real boundaries.
Smoke, diagnostic, import, constructor, coverage-only, no-crash, and status-only checks carry no proof burden.

Invalid local fixes: Renaming a fake test to smoke; keeping non-proof checks in proof paths; citing coverage as correctness.

Detection handles: `NON-PROOF-TESTS`, `SMOKE-TEST`, `LA-NO-THROW`, `LA-IMPORT`, `NO-CRASH-PROOF`

Related remediation: `REMEDIATE.REAL_PROOF_LOOP`

#### `POLICY.NO_MOCK_PROOF` — No mocks as proof

Category: Proof and Test Integrity

Rule: Mocks, fakes, stubs, spies, monkeypatching, synthetic providers, and mocked IPC do not prove owned behavior when real boundaries are available.

Invalid local fixes: Asserting a mock was called; swapping one mock framework for another; labeling a mocked test as non-proof while leaving it in QC.

Detection handles: `MOCK-STUB`, `MOCK-TEST-POISON`, `MOCKED-IPC`, `TS-MOCKED-BOUNDARY`, `MOCK-AS-PROOF`

Related remediation: `REMEDIATE.REAL_PROOF_LOOP`

#### `POLICY.NO_SKIP_MASK` — No skipped or masked tests

Category: Proof and Test Integrity

Rule: `skip`, `xfail`, `todo`, `only`, ignored tests, conditional test gating, and hidden test exclusions mask runtime reality and are not acceptable proof surfaces.

Sanctioned exception (user grant 2026-07-09) — **open-issue red proof gates**: a committed red proof test for an OPEN tracked issue may carry `@pytest.mark.xfail(reason="... #<issue-number> ...", strict=True)`. The reason string must cite the open issue; `strict=True` is mandatory so the suite goes red the moment the gap closes (the marker must then be removed in the fixing commit).
This is the coexistence mechanism between the all-green commit gate and the red-test-first bug workflow — nothing else is exempted: `skip`/`skipif`, non-strict xfail, and xfail without an open-issue citation remain violations, and citing a CLOSED issue is a violation (reviewers audit issue state).

Invalid local fixes: Moving the skip; adding a reason string without an open-issue red-proof-gate grant; filing an issue while leaving the proof gap masked with `skip` or non-strict `xfail`.

Detection handles: `TEST-GATING`, `NO MASKING`

Related remediation: `REMEDIATE.REAL_PROOF_LOOP`

#### `POLICY.NO_HELPER_PROOF` — No helper-level proof for boundary obligations

Category: Proof and Test Integrity

Rule: A finding about startup, config, persistence, IPC, subprocess, API, or UI behavior must be proved at that boundary.
Helper tests are supplementary and cannot resolve boundary feedback.

Invalid local fixes: Extracting a helper after review; testing branch behavior instead of product behavior; proving code the app may stop calling.

Detection handles: `HELPER-BOUNDARY`, `HELPER-PATCH`, `STOPPED-HELPER`, `HELPER-BRANCH-PROOF`, `PY-HELPER-BRANCH`, `BOUNDARY-BYPASS`

Related remediation: `REMEDIATE.REAL_PROOF_LOOP`

#### `POLICY.NO_EXACT_STRING_PROOF` — No exact string assertions unless public contract

Category: Proof and Test Integrity

Rule: Tests assert structured error kinds, semantic values, or public text contracts.
Exact string assertions on internal diagnostics usually prove only the test's copied literal.

Invalid local fixes: Asserting copied error messages; matching implementation wording; replacing string errors with different strings.

Detection handles: `EXACT-STRING`, `TEST-EXACT-STRING`, `STRINGLY-ERRORS`, `LA-STRING`, `PY-STRINGS`, `TS-STRINGS`, `RS-STRING-ERRORS`

Related remediation: `REMEDIATE.REAL_PROOF_LOOP`

### Type and Interface Integrity

#### `POLICY.NO_BOOLEAN_MODE` — No boolean mode flags in owned APIs

Category: Type and Interface Integrity

Rule: Boolean parameters that select behavior hide multiple operations behind one call surface.
Use separate functions or an explicit domain variant with exhaustive dispatch.

Invalid local fixes: Renaming `flag` to `mode`; replacing `bool` with an enum without splitting obligations; testing both branches directly instead of constructing real state.

Detection handles: `BOOLEAN-FLAGS`, `BOOLEAN-MODE`, `LA-BOOLEAN-FORCING`, `RS-BOOLEAN-FORCING`

Related remediation: `REMEDIATE.API_SPLIT_OR_VARIANT`

#### `POLICY.NO_TYPE_ESCAPE` — No type-system escape hatches

Category: Type and Interface Integrity

Rule: Owned code must not bypass static guarantees with `Any`, casts, double casts, `as any`, `unknown as`, broad `Partial`, stringly errors, untyped blobs for structured state, or runtime duck-typing introspection (`hasattr`, dynamic `getattr`/`setattr`/`delattr`, `vars()`, `type(x) ==`/`is` comparisons, `__class__`/`__dict__` probing) in place of declared types.
Sage research code in particular must declare exactly which mathematical objects it expects rather than discovering their capabilities at runtime.

Invalid local fixes: Adding a narrower cast without proving the boundary; asserting type shape in tests; hiding data in JSON/dicts; replacing `hasattr` with `try`/`except AttributeError`.

Detection handles: `TYPE-PROOF-ESCAPE`, `TYPE-ESCAPE`, `TSAnyKeyword`, `Any`, `Partial<T>`, `sage-no-hasattr`, `sage-no-dynamic-attr`, `sage-no-type-identity`, `sage-no-dunder-introspection`

Related remediation: `REMEDIATE.STRUCTURED_TYPES`

#### `POLICY.NO_UNTYPED_IMPORT_LEAK` — No untyped dependency leakage

Category: Type and Interface Integrity

Rule: Untyped third-party libraries may not leak `Any` into owned code.
A mypy `import-untyped` diagnostic means the dependency boundary lacks stubs or a `py.typed` marker; owned code must restore a typed boundary before using that library broadly.

Invalid local fixes: Replacing the library solely to satisfy mypy; hand-rolling library behavior; adding `ignore_missing_imports`; adding `# type: ignore[import-untyped]`; casting imported values to expected types; exposing untyped library objects from a wrapper; adding local QC config or excludes.

Detection handles: `UNTYPED-IMPORT`, `IMPORT-UNTYPED`, `MISSING-STUBS`, `MISSING-PY-TYPED`, `ANY-INGRESS`, `TYPE-FIREWALL`

Related remediation: `REMEDIATE.TYPED_DEPENDENCY_BOUNDARY`

### Architecture Ownership

#### `POLICY.NO_BESPOKE_REINVENTION` — No bespoke reinvention of available capabilities

Category: Architecture Ownership

Rule: Before implementing a capability, inspect the language, framework, installed dependencies, and project-owned component inventory.
When an existing surface owns the capability, use it.
Custom implementation is admissible only after a concrete contract gap is established.

Invalid local fixes: Calling the available surface too abstract or complex without comparing its contract; wrapping a bespoke implementation in an adapter; retaining both implementations; removing the dependency because the reinvention left it unused.

Detection handles: `DEPENDENCY-AVERSION`, `BESPOKE-DEP`, `COMPLEXITY-SIGNAL`

Related remediation: `REMEDIATE.USE_EXISTING_CAPABILITY`

#### `POLICY.NO_UNGROUNDED_MATH_NAME` — Mathematical surfaces name standard referents

Category: Architecture Ownership

Rule: Every declaration on a mathematical surface names a standard mathematical object at its natural generality.
Engineering shims graduated to mathematical placement are banned: predicate wrappers around total constructions, record nouns standing where a governing object, diagram, or fiber belongs, propositional truncation of mandatory coherence data, unconstrained `Prop` fields, epistemic states as fiber values, and convention-violating imports on mathematical surfaces.
Fixing a shim means retiring the name and stating the real object — never reframing, rehoming, or deriving notation from it.

Invalid local fixes: Renaming the wrapper while keeping its shape; reframing the shim as "derived notation" for the real object; moving the record to another module; tethering it to a standard declaration with an equivalence and keeping both; widening an engineering-path exclusion to cover it.

Detection handles: `REFERENT-SHIM`, `HAS-WRAPPER`, `PROP-TRUNCATION`, `UNCONSTRAINED-PROP-FIELD`, `EPISTEMIC-FIBER`, `ISOTROPY-AS-TORSION`, `TRUNCATING-DIVISION`, `CONVENTION-IMPORT`

Related remediation: `REMEDIATE.USE_EXISTING_CAPABILITY`

#### `POLICY.NO_MYOPIC_PATCHING` — No token-local repair of architectural violations

Category: Architecture Ownership

Rule: Treat a finding as evidence of a weakened obligation, not as a token to silence.
Inspect the owning boundary, adjacent callers, tests, configuration, and repeated instances of the same failure process.
Repair the complete obligation rather than only the cited line.

Invalid local fixes: Replacing only the matched syntax; adding a guard, special case, adapter, suppression, or parallel helper around the reported site; fixing one call site while the same failure process remains elsewhere.

Detection handles: `MYOPIC-PATCHING`, `BLAST-RADIUS`, `PATCH-ACCUMULATION`, `WHACK-A-MOLE`

Related remediation: `REMEDIATE.BLAST_RADIUS_REPAIR`

### QC Authority

#### `POLICY.NO_QC_SILENCING` — No validator bypass

Category: QC Authority

Rule: Suppression comments, allow attributes, ignore globs, disabled rules, lowered thresholds, local QC overrides, and broad excludes convert validator failure into validator silence.

Invalid local fixes: Narrowing the suppression while keeping the violation; adding post-hoc prose; weakening the rule or threshold.

Detection handles: `BYPASS-COMMENTS`, `ATTRIBUTE-BYPASSES`, `CONFIG-QC`, `VALIDATOR-BYPASS`

Related remediation: `REMEDIATE.REMOVE_SUPPRESSION_WITH_EXCEPTION_PROTOCOL`

#### `POLICY.GLOBAL_QC_AUTHORITY` — No local QC authority

Category: QC Authority

Rule: Generic lint, type, format, coverage, dead-code, duplication, slop, and tool-config behavior belong to global QC. Repos delegate; they do not reimplement or override.

Invalid local fixes: Adding local `lint`/`typecheck` recipes; copying global configs downstream; running narrower local checks as proof.

Detection handles: `LOCAL-QC`, `QC-TARGETS`

Related remediation: `REMEDIATE.DELEGATE_GLOBAL_QC`

### Artifact Ownership

#### `POLICY.NO_DYNAMIC_ARTIFACTS` — No owned static artifacts generated from code

Category: Artifact Ownership

Rule: Configs, prompts, scripts, static data, and templates owned by the project must be tracked reviewable artifacts, not strings or dicts emitted from runtime code.

Invalid local fixes: Heredocs; embedded cross-language code; inline prompt strings; generated config assembled from literals.

Detection handles: `DYNAMIC-FILE`, `INLINE-STRINGS-DATA`, `CODE-IN-CODE`, `DYNAMIC-FILE-CREATION`, `INLINE-STRINGS`, `CODE-WITHIN-CODE`

Related remediation: `REMEDIATE.TRACK_STATIC_ARTIFACT`

### Migration and Remediation Integrity

#### `POLICY.NO_LEGACY_SHIM` — No compatibility shims in pre-launch bespoke software

Category: Migration and Remediation Integrity

Rule: Replace wrong paths, migrate callers, and remove old interfaces after transferring their burden.
Do not preserve legacy branches without external consumers.

Invalid local fixes: Deprecated wrappers; compat mode; old parser retained "just in case"; feature flags for obsolete paths.

Detection handles: `LEGACY-SHIMS`, `LEGACY-SHIM`

Related remediation: `REMEDIATE.REPLACE_LEGACY_PATH`

#### `POLICY.NO_QUARANTINE_REMEDIATION` — No quarantine as remediation

Category: Migration and Remediation Integrity

Rule: Quarantine labels such as smoke, non-proof, legacy, diagnostic-only, temporary, compatibility, fallback, scaffold, or out-of-scope require burden disposition.
They do not make slop acceptable.

Invalid local fixes: Keeping proof-shaped artifacts under disclaimer labels; moving slop to "future-owned"; renaming rather than resolving burden.

Detection handles: `QUARANTINE-LANG`, `ADMIN-ARTIFACT`

Related remediation: `REMEDIATE.BURDEN_DISPOSITION`

#### `POLICY.NO_ADMIN_COMPLETION` — No administrative artifact as completion

Category: Migration and Remediation Integrity

Rule: Issues, comments, docs, labels, review replies, and status fields can preserve truth but do not satisfy implementation or proof obligations.

Invalid local fixes: Marking as future work; documenting a limitation; closing a thread without code/proof; resolving by metadata.

Detection handles: `ADMIN-COMPLETION`, `ADMIN-ARTIFACT`

Related remediation: `REMEDIATE.BURDEN_DISPOSITION`

#### `POLICY.NO_DELETION_LAUNDERING` — No deletion or relabeling without burden disposition

Category: Migration and Remediation Integrity

Rule: Slop artifacts are forensic evidence of an unmet need.
Removing or renaming them is valid only after the original burden is solved, invalidated, transferred, or recorded unresolved.

Invalid local fixes: Deleting the evidence; renaming to smoke/basic/legacy; "cleaning up" without reconstructing intent.

Detection handles: `DELETION-BURDEN`, `DELETION-LAUNDERING`

Related remediation: `REMEDIATE.BURDEN_DISPOSITION`

### Anti-Speculation

#### `POLICY.NO_HYPOTHETICAL_PATH` — No hypothetical failure-path code

Category: Anti-Speculation

Rule: Do not add branches for failure modes that have not been observed, tested, or reported.
Assert invariants now; handle real incidents when they exist.
Converting an existing `assert` into `if/raise` to defend against `python -O` stripping assertions is itself a hypothetical-path fix: `-O` is an unobserved failure mode in bespoke software that is never run with it.
Keep the assertion.
See `POLICY.PREFER_ASSERTION`.

Invalid local fixes: "What if" guards; speculative fallback code; enterprise deployment branches for bespoke local tools; replacing `assert` with `if/raise` on a generic "asserts are disabled under `-O`" argument that names no observed failure.

Detection handles: `HYPOTHETICAL-PATH`, `NO-PREEMPTIVE-PATH`, `UNOBSERVED-FAILURE`, `ASSERT-TO-RAISE-O-STRIP`

Related remediation: `REMEDIATE.OBSERVE_BEFORE_BRANCHING`

#### `POLICY.PREFER_ASSERTION` — Prefer assertions over `if/raise` for invariants

Category: Anti-Speculation

Rule: Assertions are the strongly-preferred idiom for invariants, preconditions, and type-narrowing in owned code.
An `assert` records what the author believes must be provably true at that point — it forces the writer to engage with the data, enumerate real (observed) failure modes, name them, narrow types for the checker, and short-circuit early so later logic can rely on a proven condition.
Code should be littered with assertions.
Catching `AssertionError` is the same category error in the other direction: it turns a provable claim about code state into runtime logic, error handling, retry behavior, or product contract.
Assertions are claims to preserve and strengthen, not exceptions to recover from.
`if/raise` (especially `raise ValueError`/`RuntimeError`) on what is actually an invariant is the red flag, not the assertion: it is adjacent to timid, fail-open, splat-guessing slop and removes the auditable proof an assertion provides.
The threat model is slop and unproven logic, not someone running the app under `-O`; protecting downstream users who pass optimization flags is not an owned obligation.
If assertion cost ever becomes a real measured problem, the fix is a dedicated optimization pass (cython/rust/library change), never pre-emptively swapping asserts for raises.

Invalid local fixes: Replacing an `assert` with `if/raise`/`ValueError`/`RuntimeError` to satisfy a reviewer or a `python -O` argument; adding a raise-based guard where an assertion would document the precondition; weakening an assertion into a tolerant branch; catching `AssertionError` or an equivalent invariant-failure exception; converting assertion failure into fallback, retry, warning, user-facing error, or partial success.

Detection handles: `RAISE-FOR-INVARIANT`, `ASSERT-TO-RAISE-O-STRIP`, `ASSERT-WEAKENING`, `ASSERTION-CATCH`, `ASSERTION-AS-RUNTIME-ERROR`

Related remediation: `REMEDIATE.PREFER_ASSERTION`

#### `POLICY.NO_UNVERIFIED_CONVENTION_CLAIMS` — Reviewer convention-claims are untrusted priors

Category: Anti-Speculation

Rule: Any claim that an external dependency's name, namespace, API shape, or convention is X — whether emitted by an agent or an automated reviewer — is an untrusted prior until verified against the pinned checkout or live source.
A building usage against the pinned dependency outranks every prior.
A review suggestion justified by convention-alignment ("the standard namespace is …", "for easier upstreaming …", "X is a LinearEquiv") that fails that one verification is slop: rejected wholesale, with the verifying file:line evidence recorded in the thread reply and the disposition ledger.
One falsified convention-claim in a review batch drops the confidence prior on the reviewer's remaining unsourced convention-claims — each still receives its single verification; none receives accommodation.

Invalid local fixes: Partially adopting the suggested rename; adding an alias or `open` so both spellings resolve; renaming "toward" the claimed convention; resolving the thread as accepted-with-modification without checkout evidence; deferring the claim to a follow-up instead of verifying it once.

Detection handles: `STALE-CONVENTION-SUGGESTION`, `REVIEWER-PRIOR-RENAME`, `UNSOURCED-CONVENTION-CLAIM`, `DEPRECATED-NAMESPACE-SUGGESTION`, `CONVENTION-ALIGNMENT-JUSTIFICATION`

Related remediation: `REMEDIATE.VERIFY_CONVENTION_CLAIM`
