# QC Delegation Scaffolds

These scaffolds are copied into target repositories by `just install-qc-scaffold <profile> <target>`.

They contain only repo-local command surfaces that delegate to the global QC stack in `~/ai-review-ci`. They must not carry generic QC tool configs, tool pins, hook scripts, or replacement lint/type/test implementations.

Use `bun-playwright` for Bun repositories that must instantiate a real browser GUI through the central Playwright gate.
Those repositories must keep `package.json`, `bun.lock` or `bun.lockb`, and primary Playwright configuration at `playwright.config.ts` in the repository root.
Add `playwright.actual.config.ts` when the project also needs to prove a real app entrypoint outside fixture-backed GUI coverage; the central app-boot gate runs it automatically when present.
Plain TypeScript packages use `bun`.
