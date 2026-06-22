# QC Delegation Scaffolds

These scaffolds are copied into target repositories by `just install-qc-scaffold <language> <target>`.

They contain only repo-local command surfaces that delegate to the global QC stack in `~/ai-review-ci`. They must not carry generic QC tool configs, tool pins, hook scripts, or replacement lint/type/test implementations.

Use `bun-playwright` only for Bun repositories that must instantiate a real browser GUI through the central Playwright gate.
Those repositories must keep Playwright configuration at `playwright.config.ts` in the repository root; the scaffold delegates `app-boot` to `~/ai-review-ci/justfiles/bun.just`.
Plain TypeScript packages should use `bun`.
