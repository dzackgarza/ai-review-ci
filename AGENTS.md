# Agent Rules

## QC Delegation

- Treat `~/ai-review-ci` as the authoritative QC implementation.
  Downstream repositories carry only thin `test` and `test-ci` recipes that delegate to this repo.

- Every command that loads a central justfile from another repository must preserve the caller repository with `-d .`:

  ```justfile
  test:
      @just -f ~/ai-review-ci/justfiles/python.just -d . test

  test-ci:
      @just -f ~/ai-review-ci/justfiles/python.just -d . test-ci
  ```

- Apply the same caller-root rule to nested central calls.
  Language justfiles calling `shared.just`, and Sage calling Python QC, must include `-d .` on every nested `just -f` invocation.

- Do not patch a downstream repository first when a shared QC command runs in the wrong directory.
  Fix the central scaffold or central language justfile in this repository, then reinstall or recopy downstream only if the downstream file itself is stale.

- Prove caller-root fixes with a red test before editing the scaffold or justfile.
  Use a real temporary target repository whose target-specific preflight failure differs from the failure produced in `~/ai-review-ci/justfiles`.

## Semgrep Findings

- Separate Semgrep rule provenance from finding ownership.
  Paths under `~/ai-review-ci/tool-configs/` identify the rule config; the finding target path identifies the code being checked.

- Do not conclude that QC scanned its own files because output mentions `tool-configs/semgrep.yml`. Confirm the process cwd, the target paths, and the target count before diagnosing wrong-repo scanning.

- A downstream report that “Semgrep found issues about CI files” is a cwd/provenance triage problem until target paths prove otherwise.
  Reproduce the run from the target repository and inspect the exact reported paths before editing rules or suppressions.

## Hook Tiers

- The global hook split is intentional: `pre-commit` runs `just test`, and `pre-push` runs `just test-ci`.

- Slop/style/coverage findings during an ordinary commit indicate a hook-tier or delegation problem.
  Do not reinstall hooks or weaken QC until the active hook path, hook contents, and delegated cwd have been verified.
