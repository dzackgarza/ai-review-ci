# Landing a green new project: bun-python with a Tauri crate

Every expectation below is enforced by a gate, and every gate reports one failure at a
time. This is the whole list, in the order that lands a fresh repository green on the
first CI run instead of the fifth. It was written from `dzackgarza/math-pdf-reader`
(Bun server, Vite web UI, WXT extension, Tauri window, Python plugin package) on
2026-09-23; the profile is `bun-python`, and the Rust-specific notes apply to any
Tauri crate in a repository on that profile.

## 1. Order of operations

The installer, the hooks and branch protection each assume a state the previous step
creates. Out of order, each refuses with a message that names only its own precondition.

1. Copy `scaffolds/bun-python/justfile` to the repository root **before** the first
   commit. The global pre-commit hook runs `just test-commit`; with no justfile the first
   commit fails with `error: no justfile found`. `install-qc-scaffold` and
   `ai-review-ci install` refuse to overwrite an existing justfile, so once you have one,
   later installer calls need `--skip-scaffold`.
2. Lay the repository out as in section 2 and make `just test-commit` pass locally.
3. Create the GitHub repository **public** (section 5 explains why) and push `main`.
4. Run `ai-review-ci install --skip-scaffold --target . --repo <owner>/<name> --branch
   main --profile bun-python`. It writes the two review workflows, `.aislop/config.yml`,
   the PR template, and the canonical `# Review Guidelines` section of `AGENTS.md`
   (`doctor` fails without that section). It also applies branch protection, which fails
   with `Branch not found` if `main` is not on GitHub yet. Once the workflows exist the
   installer refuses to run again (`already installed`), so any later protection or label
   work goes through `ai-review-ci protect-branch` and `ai-review-ci install-labels`.
5. Commit the installed files and push. From this point `main` accepts only pull requests
   with the seven required checks green; `enforce_admins` is on, so direct pushes are
   refused for everyone. The PR template requires a linked issue, so file the issue first.
   `gh pr checks` fails with the personal-token scope on these repos; read status with
   `gh run list --branch <branch>` and `gh run view <id> --log-failed`.
6. Before every push, run both CI-tier gates locally against the base branch. They are
   the same recipes CI runs and they take minutes, not a CI round trip:

   ```bash
   DIFF_COVER_BASE=origin/main just -f ~/ai-review-ci/justfiles/python.just -d . test-ci
   DIFF_COVER_BASE=origin/main just -f ~/ai-review-ci/justfiles/bun.just -d . test-ci
   ```

## 2. Layout the gates can see

The Bun and Python gates hard-code the single-package layout. Anything else is invisible
to some checks and fails others.

| Expectation | Enforced by | Failure text when violated |
| --- | --- | --- |
| One `package.json` and `bun.lock` at the root, no workspaces | `_check-ts-project` | "must use Bun — no bun.lock" |
| TypeScript under root `src/`, TypeScript tests under root `tests/` | `_biome`, `_eslint` check only those two directories | biome: "No files were processed in the specified paths" |
| Test files matching `*.test.ts` or under `tests/` | `_check-ts-project` | "TypeScript project must have tests" |
| A `tsconfig.json` at the root whose `include` covers every root-level `*.config.ts` (for example `wxt.config.ts`) | eslint's typed project service picks the nearest tsconfig per file | "was not found by the project service. Consider either including it in the tsconfig.json" |
| No local `biome.json`, `eslint.config.*`, `knip.*`, `lint-staged.*`, no `knip` or `lint-staged` keys in package.json | `_check-ts-project` | "Local QC override detected" |
| Python package under root `src/` | `tool-configs/coverage.ini` has `source = src` | pytest passes, then "CoverageWarning: No data was collected" and diff-cover fails |
| Python tests as `tests/test_*.py` | `_pytest` | "no test files found in a Python project" |
| `requires-python = ">=3.14"` in `pyproject.toml`; no `[tool.ruff]`, `[tool.mypy]`, `[tool.coverage]`, `[tool.deptry]`, `[tool.vulture]`, `[tool.import-linter]` sections | `_check-python-project` | "must target Python >=3.14" / "global QC owns this tool config" |
| A `py.typed` marker inside the Python package | `_mypy` analyzes the installed package from `tests/` | "module is installed, but missing library stubs or py.typed marker [import-untyped]" |
| `.envrc` at the root containing `source_up`, and `~/.envrc` exporting `DIRENV_CONFIGURED_CORRECTLY` | `_check-envrc`, CI tier only | "No .envrc file in project root" |

A Tauri crate does not fit under `src/`; put it in its own directory (`desktop/src-tauri`)
with no `package.json` of its own. Run the Tauri CLI through `bunx @tauri-apps/cli`
rather than a devDependency: knip reports a devDependency that only the justfile uses as
unused, and that blocks the CI tier.

## 3. Scripts the Bun gate calls

| Script | Called by | Contract |
| --- | --- | --- |
| `typecheck` | `_tsc`, commit tier | Runs on every commit. One `tsc --noEmit -p <dir>` per tsconfig; do not put `cargo check` in it (section 4). |
| `test` | `_bun-test`, push tier | `bun test`. |
| `coverage` | `_coverage`, CI tier | Must write `coverage/lcov.info`; the gate copies it to `lcov.info` and runs diff-cover. Without it: "diff-cover: lcov.info not produced". Use `bun test --coverage --coverage-reporter=lcov --coverage-dir=coverage`. Ignore `coverage/` and `lcov.info` in git. |

## 4. Rust and Tauri specifics

- **The generator names the crate after the directory.** `create-tauri-app apps/desktop`
  produces `name = "appsdesktop"` and `appsdesktop_lib` in `Cargo.toml` and
  `main.rs`. Rename both together or `cargo check` fails with an unresolved crate.
- **The generated `run()` ends in `.expect(...)`.** Return `tauri::Result<()>` from
  `run()` and `main()` instead; the error propagates and no policy on error discard is
  touched.
- **Lint silencing has a Rust-native gate.** Add to `Cargo.toml`:

  ```toml
  [lints.clippy]
  allow_attributes = "deny"
  allow_attributes_without_reason = "deny"
  ```

  This is the reference enforcement for the no-silencing policy in Rust; `#[expect(lint,
  reason = "...")]` remains available and rustc warns when the expectation is unfulfilled.
- **Nothing in `bun-python` gates Rust.** `cargo check` inside the `typecheck` script
  fails on the GitHub runner because Tauri's Linux inputs (WebKitGTK, GLib headers) are
  not installed: `failed to run custom build command for glib-sys`. Keep Rust out of the
  TypeScript script, and know that the crate is then unchecked in CI until a Rust gate
  exists (tracked as dzackgarza/math-pdf-reader#3; the runner needs
  `libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev patchelf`).
- **`frontendDist` must exist** even when the window loads a remote URL such as the local
  server; point it at a directory holding one placeholder `index.html`.
- **A window that loads `http://127.0.0.1:<port>`** needs `beforeDevCommand` to start the
  server from the crate's parent directory (`bun run --cwd .. dev`) and `devUrl` set to
  the same origin, so `tauri dev` waits for the server.
- **Semgrep's Rust attribute rules** were bare attribute patterns until #421 and matched
  every item in every Rust file. If a Rust file reports `NO_QC_SILENCING` and
  `RUNTIME_DEFAULT` on plain functions, the consumer is pinned to a QC ref older than
  that fix.

## 5. CI-tier gates that do not run at commit time

These pass or are silent locally at commit and push tier, then fail the PR.

- **Semgrep is base-relative in CI.** The commit tier prints `Blocking` findings and
  still exits 0; the CI tier compares findings on the changed files against
  `DIFF_COVER_BASE` and fails on any new one. Read every `Blocking` line at commit time
  as a CI failure.
- **`POLICY.NO_HIDDEN_CONFIG`** (regex, TypeScript): a top-level `const` whose upper-case
  name ends in `URL`, `URI`, `ENDPOINT`, `HOST`, `PORT`, `SERVER`, `DATABASE`,
  `COMMAND`, `CWD`, `PATH`, `DIR`, `DIRECTORY`, `TIMEOUT`, `RETRY`, `THRESHOLD`,
  `SECRET`, `TOKEN` and holds a literal, or any upper-case `const` holding an `http://`,
  `https://` or `file://` literal. Test files count. Files whose name matches `*config*`
  are exempt, which is the intended home: one JSON config file plus a `config.ts` loader
  with a strict schema, and tests that read the config rather than restating it.
- **aislop** blocks on `eslint/no-undef` and warns on `console.*` in production code.
  WXT's auto-imported globals (`defineBackground`, `browser`) are undefined to the global
  eslint: set `imports: false` in `wxt.config.ts` and import
  `defineBackground` from `wxt/utils/define-background`.
- **knip** blocks on unused devDependencies and unused exports.
- **The slop-review job uploads SARIF to GitHub code scanning.** A private repository
  without Advanced Security rejects the upload ("Code scanning is not enabled for this
  repository") and the required `slop / review` check fails. The code repositories under
  this account are public for that reason.
- **The scan-ai-slop bot** posts one "skipped, no paid plan" comment per PR. It is not a
  required check; ignore it.

## 6. Generator debris that the gates flag

Generators ship demo code. Delete it before the first gate run, or knip, aislop and biome
report it: WXT's `components/counter.ts`, `entrypoints/content.ts`, `entrypoints/popup/`,
`assets/`, `public/wxt.svg`; Vite's `src/assets/`, `public/icons.svg`, `.oxlintrc.json`
and the `oxlint` devDependency; Tauri's `src/assets`, `main.js`, `styles.css`, `.vscode`;
Hono's per-package `bun.lock`, `.gitignore` and `README.md`. `create-hono` needs
`--template bun --pm bun --install` to run non-interactively. Each generator writes its own
`.gitignore`; replace them with one root `.gitignore`.

## 7. Hooks rewrite files after staging

The commit hook runs flowmark, prettier and biome on staged Markdown, JSON and
TypeScript and leaves the reformatted files unstaged. The commit contains the
pre-format content; the working tree holds the formatted one. Run `just test-commit`
before `git add`, or expect a second formatting-only commit.
