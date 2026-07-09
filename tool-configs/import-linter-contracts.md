# Import-linter contract ownership — decision record

Closes the #183 obligation carried by the #211 policy-index work unit: *decide
whether project-specific import-linter layer contracts are supported under global
QC, and document the decision.*

## Decision

**Global QC provides only universal, auto-derived import-linter contracts.
Project-specific `layers` contracts are not supported** — neither as downstream
`[tool.importlinter]` overrides (already rejected) nor as per-repo blocks in the
central surface.

## What the central mechanism actually does

Import-linter is centrally owned (`POLICY.GLOBAL_QC_AUTHORITY`). The `_import-linter`
recipe does not read the target repo's `[tool.importlinter]`; it builds the config
centrally:

- `tool-artifacts/scripts/python_qc_metadata.py import-linter-config <target>`
  discovers the target's first-party modules and emits, when there is more than one
  first-party package, a single universal `independence` contract
  ("First-party packages are independent").
- `justfiles/python.just` preflight rejects any local `[tool.import-linter]` /
  `[tool.importlinter]` section in a downstream `pyproject.toml`.

The generator's only input is the set of first-party module *names*. A `layers`
contract encodes an intended dependency *ordering* — e.g. MathRead's removed
`__main__ -> cli -> server -> ... -> models` — which is a fact only the owning repo
knows. The generator has no channel to receive that ordering, so a layer contract has
no representation today and is rejected downstream.

## Why universal-only, not a per-repo channel

1. **Ownership boundary.** A universal contract (first-party independence; the
   `ai_review_ci.models` no-I/O purity contract in this repo's own `pyproject.toml`)
   is a QC invariant ai-review-ci owns and every consumer must satisfy. A single
   repo's internal layer ordering is a project architecture *preference*, not a
   cross-repo invariant. Centralizing it would either couple the hub to every
   consumer's module graph or require a repo-owned layer-declaration channel.

2. **No speculative infrastructure (`POLICY.NO_HYPOTHETICAL_PATH` / YAGNI).** Building
   a repo-owned-contract channel for one consumer's layering is machinery ahead of
   demonstrated need. MathRead's contract has already been removed downstream; one
   removed contract does not justify a general channel.

3. **Consistent with the vulture-whitelist triage** (AGENTS.md → *False-Positive
   Triage*). External-framework facts are declared centrally once; a downstream repo's
   own facts are the downstream repo's responsibility. A positive layer contract is
   *added* enforcement a repo asks for itself, so unlike a suppression it carries no
   self-service-silence hazard — the reason not to support it is cost, not policy risk.

## Consequences

- MathRead's layer contract stays removed. No downstream repo carries a local
  import-linter override; the preflight rejection is correct and stays.
- The central contract set remains universal and auto-derived.
- This repo keeps its own `ai_review_ci.models` forbidden-imports contract in
  `pyproject.toml` — that is ai-review-ci enforcing an invariant on its *own* package,
  which is exactly what a repo owning a universal-shaped contract looks like, not a
  project-specific override of a downstream contract.

## Revisit trigger

If two or more downstream repos independently need enforced internal layer
architecture, add a repo-owned layer-declaration channel that the central generator
reads (central invocation and tool version; repo-owned architecture facts), modeled on
the vulture-whitelist precedent. Not before.
