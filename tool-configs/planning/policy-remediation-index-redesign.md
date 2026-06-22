# Policy + remediation index redesign

Issue #40 tracks the implementation work. This document is the execution plan for a fresh worker.
Implementation has NOT started here.

## Why

Global QC currently carries policy and remediation text in the individual detector configs.
`tool-configs/semgrep.yml` has 56 `message:` entries, the ast-grep rules have 3 more, and
`tool-configs/test-semgrep.yml` has 1. Those messages are uncontrolled copies of policy guidance, so
they can drift from the real policy index and teach laundering fixes. The canonical failure was the
old `no-const-assignment` instruction to "use let": it changed the binding shape without moving hidden
config into a declared config surface.

The real policy registry now lives upstream in `dzackgarza/ai` under
`opencode/skills/policy-index/`, and it already has stable `POLICY.*` and `REMEDIATE.*` codes. This
repo has only a flattened, stale `reviews/vendor/policy-index.md`, plus detector-local prose. The fix
is to make `ai-review-ci` resolve detector findings through vendored policy/remediation IDs at report
time, not to keep authoring local prose in each rule.

## Researched current state

### Upstream source

Vendor source:

- `/home/dzack/gitclones/ai/opencode/skills/policy-index/SKILL.md`
- `/home/dzack/gitclones/ai/opencode/skills/policy-index/references/policies.md`
- `/home/dzack/gitclones/ai/opencode/skills/policy-index/references/remediations.md`
- `/home/dzack/gitclones/ai/opencode/skills/policy-index/references/red-flags.md`
- `/home/dzack/gitclones/ai/opencode/skills/policy-index/references/runtime-control-flow.md`
- `/home/dzack/gitclones/ai/opencode/skills/policy-index/references/test-proof-rules.md`

The upstream checkout inspected for planning was commit
`ec54f33ed97ebfc36914685cc63417e8a295307b`, but that checkout was dirty and ahead of
`origin/main`. Implementation must either pin a clean upstream ref or explicitly decide to vendor the
current local work by first making it a clean upstream commit.

### Local vendor surface

Current local vendor references:

- `reviews/vendor/policy-index.md` is a flattened routing document, not an ID-addressable database.
- `reviews/general/manifest.txt` and `reviews/slop/manifest.txt` include `vendor/policy-index.md`.
- `reviews/general/template.md` and `reviews/slop/template.md` explicitly keep reviewer output
  diagnosis-only and forbid reviewer-authored remediation.

That firewall is correct. The new renderer can append canonical policy/remediation text after validation,
but reviewer agents should still produce diagnosis plus policy IDs, not bespoke fixes.

### Rule prose inventory

Current detector-local prose carriers:

| File | Count | Notes |
| --- | ---: | --- |
| `tool-configs/semgrep.yml` | 56 `message:` entries | Main migration surface. No policy/remediation metadata exists yet. |
| `tool-configs/ast-grep/rules/no-boolean-param.yml` | 1 `message:` entry | Includes policy prose and direct doc links. |
| `tool-configs/ast-grep/rules/no-field-default.yml` | 1 `message:` entry | Embeds runtime-default remediation prose. |
| `tool-configs/ast-grep/rules/no-dynamic-import.yml` | 1 `message:` entry | Embeds local design advice. |
| `tool-configs/test-semgrep.yml` | 1 `message:` entry | Test fixture needs the same schema discipline or explicit fixture exemption. |

Analogous explanatory text in `tool-configs/eslint.config.js`, `tool-configs/slop-scan.config.json`,
and `tool-configs/slopconfig.yaml` must be audited during implementation even though those files do not
currently use `message:` keys.

### Report surfaces

Relevant code surfaces:

- `src/ai_review_ci/models.py` has finding schemas with `violated_invariant`, `category`, `label`, and
  related diagnostic fields, but no first-class `policy_code` or `remediation_code`.
- `src/ai_review_ci/sarif.py` currently uses `violated_invariant` for SARIF rule descriptions and result
  messages. It also forwards an optional `remedy` property even though current review prompts forbid
  remediation.
- `src/ai_review_ci/threads.py` says thread bodies are diagnosis-only and renders the reviewer finding
  directly. It does not resolve canonical policy/remediation text from an index.

## Target architecture

### Canonical vendor tree

Create an auditable vendor tree, replacing the flattened `reviews/vendor/policy-index.md` surface:

```text
reviews/vendor/policy-index/
  VENDOR.toml
  SKILL.md
  references/
    policies.md
    remediations.md
    red-flags.md
    runtime-control-flow.md
    test-proof-rules.md
```

`VENDOR.toml` records the source repository, source ref, source paths, copied file hashes, and sync time.
The sync path must be reproducible from a `just` recipe or script, not manual copy/paste.

### Detector metadata contract

Every policy detector carries only detection structure, severity, and stable IDs. Tool-required diagnostic
fields may exist only as ID carriers, not prose.

Example target for tools that support metadata:

```yaml
metadata:
  qc_lane: blocker
  qc_class: bridge_burning
  policy_code: POLICY.NO_HIDDEN_CONFIG
  remediation_code: REMEDIATE.TOTAL_CONFIG_MODEL
  failure_mode: hidden_config
  local_fix_forbidden: true
```

Implementation must settle each detector's carrier constraints before migration. If a tool requires a
syntactic `message` field, the only acceptable content is an ID-only token or generated short label such as
`POLICY.NO_HIDDEN_CONFIG`; it must not contain remediation prose.

### Runtime resolver

Add a policy-index loader that parses the vendored database and exposes:

- known `POLICY.*` records with canonical name, category, rule, invalid local fixes, detection handles, and
  related remediation code;
- known `REMEDIATE.*` records with the short remediation summary;
- validation that every detector ID exists and every finding ID resolves.

The loader should be deterministic and local-only. It should not read from `/home/dzack/gitclones/ai` at
runtime.

### Rendering split

Keep reviewer generation diagnosis-only. Then deterministic post-processing resolves:

- SARIF rule metadata and alert text from `policy_code` / `remediation_code`;
- PR thread policy/remediation sections from the vendored index;
- report properties that retain the raw IDs for downstream filtering.

This preserves the reviewer/fixer firewall while satisfying #40's requirement that humans see canonical,
actionable guidance in alerts and threads.

## Phases

### Phase 1: Vendor contract and source pin

- Decide the clean upstream ref to vendor from.
- Add the vendor tree and manifest.
- Add `just`/script sync that copies only the approved policy-index files and verifies hashes.
- Replace `reviews/vendor/policy-index.md` manifest references with the new tree entry point.

Exit criteria: a clean checkout can regenerate or verify the vendored policy-index from the pinned source.

### Phase 2: Index parser and validation API

- Implement the local policy/remediation loader.
- Add schema tests for all `POLICY.*` and `REMEDIATE.*` records.
- Fail on duplicate IDs, missing related remediation codes, unknown remediation references, or malformed
  records.

Exit criteria: `ai-review-ci` can load and validate the vendored database without consulting upstream.

### Phase 3: Detector metadata migration

- Migrate Semgrep rules from prose messages to policy/remediation metadata.
- Migrate ast-grep rules to the same ID contract.
- Audit eslint and slop configs for any explanatory policy/remediation prose and replace it with IDs or
  comments that point to the canonical index.
- Add guard tests that reject detector prose and unknown IDs.

Exit criteria: adding or editing a policy detector without valid IDs fails locally and in CI.

### Phase 4: Finding schema and renderer integration

- Add first-class policy/remediation ID fields to reviewer finding models or a deterministic enrichment layer.
- Update SARIF rendering to use canonical policy/remediation text and properties.
- Update PR thread rendering to append canonical policy/remediation guidance resolved from the index.
- Remove ad hoc `remedy` forwarding from SARIF unless it is replaced by canonical index output.

Exit criteria: a fixture finding renders the same canonical guidance in SARIF and PR-thread output, with raw
IDs preserved.

### Phase 5: Drift enforcement

- Add checks that every detector with policy meaning carries valid IDs.
- Add checks that detector-local `message:` values, comments, or config text cannot contain remediation prose.
- Add checks that vendored policy files match `VENDOR.toml`.
- Wire these checks into the repo's normal `just test` / `just test-ci` path.

Exit criteria: policy drift, stale vendoring, missing IDs, and reintroduced inline prose are mechanical failures.

### Phase 6: Cleanup and issue handoff

- Remove or subsume the old flattened `reviews/vendor/policy-index.md`.
- Update manifests/templates/docs to point at the canonical vendor tree.
- Leave #30/#32 rule implementation work carrying IDs, not bespoke prose.
- Keep #40 open until implementation and proof land; this planning PR should reference it, not close it.

Exit criteria: no live code path depends on the stale flattened policy-index document.

## Parallelization

Phases 1 and 2 are foundation work and should land before broad detector migration. After the loader and
metadata schema exist, Semgrep, ast-grep, eslint/slop audit, and SARIF/thread rendering can fan out in
parallel, provided each branch uses the same policy/remediation ID contract.
