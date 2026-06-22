# Global QC signal-chain & gating redesign

Starting point for the QC gating redesign. Tracked by the epic and sub-issues linked in the PR.
Implementation has NOT started — this document is the plan a subsequent worker executes.

## Why
A complete mechanical global-QC run against a consumer repo (`zotero-gui`) produced 1,291 findings
whose signal is inverted: 59% from one rule that bans all `const` (`no-const-assignment`), ~12% from
a duplicate `??` rule, **zero** on the network-boundary mock that actually shipped a dead app, and a
clean `tsc`. Meanwhile the deterministic stack runs only in a bypassable local hook (absent from CI),
the only CI gate is the non-deterministic LLM reviewer with an invented health score, and consumer
`main` branches are unprotected. A noisy-but-blind gate is what drove a repo to route around global QC
entirely — disabling the (incomplete) real detection as a side effect.

## Design

### Two layers, neither using a fabricated score
1. **Deterministic mechanical QC** — semgrep/ast-grep/tsc/eslint/biome/jscpd/lizard/dead-code/slop-scan.
   Hard, binary, **required in CI on the PR unified diff**, and un-disableable from a local justfile.
2. **LLM review** — signal-only; always green unless the review process errors. The gate is
   **evidence-backed thread resolution** (zero unresolved reviewer threads; each resolution cites a
   commit or a disposition-ledger entry per `AGENTS.md`). The `_review.yml` health-score threshold is deleted.

### Gate placement
| Surface | Runs | Blocks? |
|---|---|---|
| pre-commit (local) | fast deterministic checks on changed files | local only (advisory; CI is authoritative) |
| pre-push (local)   | fuller deterministic stack | local only |
| PR / CI (diff scope) | deterministic stack + delegation-drift + app-boot + LLM threads | **required, un-bypassable** |
| ambient CI (repo scope / cron) | whole-repo backlog & trends | non-gating, visible |

PR gates evaluate the **unified diff only**; the pre-existing repo-wide backlog never blocks an unrelated PR.

### Signal fixes
- `no-const-assignment`: narrow to module-scope `const NAME = <bare literal>`; message → extract to config (not "use let"); reconcile with `eslint.config.js` (which permits `const`).
- Dedupe `no-nullish-coalescing` vs `ts-no-nullish-default` (identical `??` match).
- Extend TS mock vocabulary: `vi.stubGlobal`/`vi.fn`/`vi.spyOn`/`vi.stubEnv` (+ jest), alongside `ts-no-vi-mock`.

### New gates
- **Delegation-drift conformance**: fail when a consumer `test`/`test-ci` does not route through the global justfiles. Runs in CI.
- **App-boot/render**: build + serve real client against real server; assert it renders without the ErrorBoundary. Real-boundary proof, not a mocked smoke test.

### Enforcement
- Automate branch protection (`gh api .../branches/{b}/protection`) in the install path; mark the deterministic-QC, app-boot, drift, and thread-resolution checks as required. Apply to consumer repos.

## Execution order
Signal fixes → new gates → topology → enforcement. See the linked sub-issues for per-task evidence and acceptance criteria.
