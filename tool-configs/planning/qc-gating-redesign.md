# Global QC signal-chain & gating redesign

Starting point for the QC gating redesign.
Tracked by the epic and sub-issues linked in the PR. Implementation has NOT started — this document is the plan a subsequent worker executes.

## Why

A complete mechanical global-QC run against a consumer repo (`zotero-gui`) produced 1,291 findings whose signal is **misdirected** (not "mostly junk"). 59% come from one rule (`no-const-assignment`) that enforces a **real policy** — *no hardcoded config constants in source* (config-as-data) — but via an **over-broad implementation**: it fires on every `const` (~640/763 are not config constants) and ships a **laundering** remediation message ("use `let`", which renames the binding without extracting the constant to config).
~12% are a **duplicate `??` rule** (the no-fallback policy is real; only the duplication is the defect).
**Zero** findings on the network-boundary mock that actually shipped a dead app, and a clean `tsc`.

So real policies are enforced imprecisely and at volume while the actual defect goes undetected — and that volume plausibly drove the repo to route around global QC entirely, disabling the (incomplete) real detection as a side effect.
The remedy is signal **precision** — make the real policies fire exactly, add the missing detectors — **without weakening strictness**. Real policies are never deleted or demoted to ignorable "advisory"; the question for each noisy rule is whether its *implementation* matches its *policy*.

## Design

### Two layers, neither using a fabricated score

1. **Deterministic mechanical QC** — semgrep/ast-grep/tsc/eslint/biome/jscpd/lizard/dead-code/slop-scan.
   Hard, binary, **required in CI on the PR unified diff**, and un-disableable from a local justfile.
2. **LLM review** — signal-only; always green unless the review process errors.
   The gate is **evidence-backed thread resolution** (zero unresolved reviewer threads; each resolution cites a commit or a disposition-ledger entry per `AGENTS.md`). The `_review.yml` health-score threshold is deleted.

### Gate placement

| Surface | Runs | Blocks? |
| --- | --- | --- |
| pre-commit (local) | fast deterministic checks on changed files | local only (CI is authoritative) |
| pre-push (local) | fuller deterministic stack | local only |
| PR / CI (diff scope) | deterministic stack + delegation-drift + app-boot + LLM threads | **required, un-bypassable** |
| ambient CI (repo scope / cron) | whole-repo backlog & trends | **non-gating but non-suppressible** (tracked/surfaced, never silently ignorable) |

PR gates evaluate the **unified diff only**; the pre-existing repo-wide backlog never blocks an unrelated PR. "Non-gating" is *not* "advisory/ignorable" — anything that can be silently ignored gets suppressed (exactly what happened to the slop report's mock policy).

### Signal fixes (make real policies fire precisely — do NOT delete policy)

- `no-const-assignment`: the policy (no hardcoded config constants in source) is real.
  Fix the *implementation*: narrow to module-scope `const NAME = <hardcoded config-shaped literal>`; message → "extract to config" (never "use `let`", which is laundering); reconcile with `eslint.config.js` (which permits `const`).
- Dedupe `no-nullish-coalescing` vs `ts-no-nullish-default` (identical `??` match).
  The no-fallback policy stays.
- Extend TS mock vocabulary: `vi.stubGlobal`/`vi.fn`/`vi.spyOn`/`vi.stubEnv` (+ jest), alongside `ts-no-vi-mock`.

### New gates

- **Delegation-drift conformance**: fail when a consumer `test`/`test-ci` does not route through the global justfiles.
  Runs in CI.
- **App-boot/render**: build + serve real client against real server; assert it renders without the ErrorBoundary.
  Real-boundary proof, not a mocked smoke test.

### Enforcement

- Automate branch protection (`gh api .../branches/{b}/protection`) in the install path; mark the deterministic-QC, app-boot, drift, and thread-resolution checks as required.
  Apply to consumer repos.

## Execution order

Signal fixes → new gates → topology → enforcement.
See the linked sub-issues for per-task evidence and acceptance criteria.
