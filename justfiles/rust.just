# justfile-rust — Rust-specific quality control
#
# Imports cross-language QC recipes from `justfile` (shared) and adds
# Rust-specific recipes. Rust projects delegate to this file:
#   just -f ~/ai-review-ci/justfiles/rust.just -d . test
#
# Shared recipes (imported from justfile):
#   _no-bypass, _semgrep, _ast-grep, _jscpd, _vibecheck, _slop
#
# Rust-specific recipes:
#   _clippy, _rustfmt, _cargo-test, _lizard, _codeql
#
# WORKFLOW (two-tier):
#   just test     — COMMIT gate: correctness + normalization only (preflight,
#                   cargo fmt, clippy, rustfmt --check, cargo test, bypass check).
#   just test-ci  — PUSH/CI gate: test + the full style/slop stack
#                   (jscpd, lizard, codeql, semgrep, ast-grep, vibecheck, ai-slop).
#
# HOOKS: pre-commit blocks on `just test`; pre-push blocks on `just test-ci`.
#   Run `just install-global-hooks` from ~/ai-review-ci to activate them globally.

infra := justfile_directory() / ".."
configs := infra / "tool-configs"
artifacts := infra / "tool-artifacts"
justfiles := infra / "justfiles"

default:
	@just test

_rust-qc-files:
	#!/usr/bin/env bash
	set -euo pipefail
	exclude_args=()
	while IFS= read -r dir; do
		exclude_args+=(-not -path "*/$dir/*")
	done < <(uv run {{artifacts}}/scripts/read_qc_excludes.py {{configs}}/qc-excludes.toml)
	find . -name '*.rs' "${exclude_args[@]}"

_rust-cargo-manifests:
	#!/usr/bin/env bash
	set -euo pipefail
	exclude_args=()
	while IFS= read -r dir; do
		exclude_args+=(-not -path "*/$dir/*")
	done < <(uv run {{artifacts}}/scripts/read_qc_excludes.py {{configs}}/qc-excludes.toml)
	find . -name 'Cargo.toml' "${exclude_args[@]}" | sort

_check-rust-project:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: Rust project preflight check ==="
	echo "# Validates project structure, test presence, and QC config isolation"
	failed=0
	missing_tests=0
	# 1. At least one Cargo.toml must exist in the repository.
	mapfile -t cargo_manifests < <(just --justfile {{justfile()}} -d . _rust-cargo-manifests)
	if [ "${#cargo_manifests[@]}" -eq 0 ]; then
		echo "ERROR: Rust project must have at least one Cargo.toml file."
		failed=1
	fi
	# 2. Tests must exist (either a tests/ directory or #[test] functions in source)
	if ! find . -type d -name tests -not -path '*/target/*' -not -path '*/.git/*' | grep -q .; then
		if ! rg -l '#\[test\]' --glob '*.rs' --glob '!**/target/**' >/dev/null 2>&1; then
			echo "ERROR: Rust project must have tests. No tests/ directory and no #[test] functions found."
			missing_tests=1
		fi
	fi
	if [ "$missing_tests" -ne 0 ]; then
		"{{artifacts}}/scripts/emit-test-writing-directive.sh"
		exit 1
	fi
	if [ "$failed" -ne 0 ]; then
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	echo "Rust project configuration OK"

_normalize-common:
	#!/usr/bin/env bash
	set -euo pipefail
	just -f {{justfiles}}/shared.just -d . _normalize-common

_normalize:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: cargo fmt auto-format ==="
	echo "# Formats Rust source before clippy, rustfmt --check, and tests run"
	mapfile -t cargo_manifests < <(just --justfile {{justfile()}} -d . _rust-cargo-manifests)
	if [ "${#cargo_manifests[@]}" -eq 0 ]; then
		echo "ERROR: cargo fmt: no Cargo.toml found anywhere in this Rust project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	for manifest in "${cargo_manifests[@]}"; do
		if cargo fmt --manifest-path "$manifest"; then
			:
		else
			ec=$?
			echo "ERROR: cargo fmt failed for $manifest."
			"{{artifacts}}/scripts/emit-triage-directive.sh"
			exit $ec
		fi
	done

_clippy:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: clippy Rust linting ==="
	echo "# Runs cargo clippy with deny-level warnings"
	mapfile -t rust_files < <(just --justfile {{justfile()}} -d . _rust-qc-files)
	if [ "${#rust_files[@]}" -eq 0 ]; then
		echo "ERROR: clippy: no Rust files found in a Rust project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	mapfile -t cargo_manifests < <(just --justfile {{justfile()}} -d . _rust-cargo-manifests)
	if [ "${#cargo_manifests[@]}" -eq 0 ]; then
		echo "ERROR: cargo clippy: no Cargo.toml found anywhere in this Rust project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	for manifest in "${cargo_manifests[@]}"; do
		cargo clippy --manifest-path "$manifest" --all-targets --all-features -- -D warnings
	done

_rustfmt:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: rustfmt formatting check ==="
	echo "# Checks Rust source formatting against rustfmt defaults"
	mapfile -t rust_files < <(just --justfile {{justfile()}} -d . _rust-qc-files)
	if [ "${#rust_files[@]}" -eq 0 ]; then
		echo "ERROR: rustfmt: no Rust files found in a Rust project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	mapfile -t cargo_manifests < <(just --justfile {{justfile()}} -d . _rust-cargo-manifests)
	if [ "${#cargo_manifests[@]}" -eq 0 ]; then
		echo "ERROR: cargo fmt: no Cargo.toml found anywhere in this Rust project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	for manifest in "${cargo_manifests[@]}"; do
		cargo fmt --manifest-path "$manifest" --check
	done

_cargo-test:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: cargo test ==="
	echo "# Runs Rust unit and integration tests"
	mapfile -t cargo_manifests < <(just --justfile {{justfile()}} -d . _rust-cargo-manifests)
	if [ "${#cargo_manifests[@]}" -eq 0 ]; then
		echo "ERROR: cargo test: no Cargo.toml found — Rust project must have one."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	for manifest in "${cargo_manifests[@]}"; do
		cargo test --manifest-path "$manifest" --all-features
	done

_codeql:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: codeql security analysis (Rust) ==="
	echo "# GitHub's static analysis engine for code quality and security vulnerabilities"
	mapfile -t cargo_manifests < <(just --justfile {{justfile()}} -d . _rust-cargo-manifests)
	if [ "${#cargo_manifests[@]}" -eq 0 ]; then
		echo "ERROR: codeql: no Cargo.toml found anywhere in this Rust project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	for manifest in "${cargo_manifests[@]}"; do
		cargo clean --manifest-path "$manifest"
	done
	project_root="$(pwd -P)"
	project_slug="$(printf '%s' "$project_root" | sed 's#[^A-Za-z0-9._-]#_#g')"
	codeql_root="${XDG_CACHE_HOME:-$HOME/.cache}/quality-control/codeql/$project_slug"
	db="$codeql_root/codeql-db"
	report="$codeql_root/codeql-report.sarif"
	mkdir -p "$codeql_root"
	codeql database create "$db" --overwrite --language=rust --source-root="$project_root"
	codeql database analyze "$db" --format=sarif-latest --output="$report"
	echo "CodeQL SARIF report: $report"

_jscpd:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: jscpd copy-paste detection ==="
	echo "# Finds duplicate code blocks across Rust files"
	mapfile -t rust_files < <(just --justfile {{justfile()}} -d . _rust-qc-files)
	if [ "${#rust_files[@]}" -eq 0 ]; then
		echo "ERROR: jscpd: no Rust files found."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	npx -y jscpd --config {{configs}}/jscpd.json \
		--format rust \
		"${rust_files[@]}"

_lizard:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: lizard complexity analysis (Rust) ==="
	echo "# Computes cyclomatic complexity number (CCN), line count, and parameter count"
	mapfile -t rust_files < <(just --justfile {{justfile()}} -d . _rust-qc-files)
	if [ "${#rust_files[@]}" -eq 0 ]; then
		echo "ERROR: lizard: no Rust files found in a Rust project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	lizard_excludes=()
	while IFS= read -r dir; do
		lizard_excludes+=(-x "*/$dir/*")
	done < <(uv run {{artifacts}}/scripts/read_qc_excludes.py {{configs}}/qc-excludes.toml)
	uvx --from lizard lizard -l rust -C 7 -L 150 -a 5 -i 0 \
		"${lizard_excludes[@]}" \
		"${rust_files[@]}"

# public: COMMIT gate — correctness + normalization, plus bypass detection
test: _check-rust-project _normalize-common _normalize _clippy _rustfmt _cargo-test
	#!/usr/bin/env bash
	set -euo pipefail
	just -f {{justfiles}}/shared.just -d . _no-bypass
	echo "Commit-tier quality checks completed"

# public: PUSH/CI gate — test + the full style/slop stack
test-ci: test _jscpd _lizard _codeql
	#!/usr/bin/env bash
	set -euo pipefail
	just -f {{justfiles}}/shared.just -d . _global-qc
	echo "Push/CI quality checks completed"
