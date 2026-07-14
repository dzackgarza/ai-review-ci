# justfile-rust — Rust-specific quality control
#
# Imports cross-language QC recipes from `justfile` (shared) and adds
# Rust-specific recipes. Rust projects delegate to this file:
#   just -f ~/ai-review-ci/justfiles/rust.just -d . test-commit
#
# Shared recipes (imported from justfile):
#   _no-bypass, _semgrep, _ast-grep, _jscpd, _vibecheck, _slop
#
# Rust-specific recipes:
#   _clippy, _rustfmt, _cargo-test, _lizard, _codeql
#
# WORKFLOW (three-tier):
#   just test-commit — preflight, formatting, clippy, bypass check.
#   just test-push   — commit checks plus the full Cargo test suite.
#   just test-ci     — push checks plus policy, complexity, and security gates.
#
# HOOKS: pre-commit blocks on `just test-commit`; pre-push blocks on `just test-push`.
#   Run `just install-global-hooks` from ~/ai-review-ci to activate them globally.

infra := justfile_directory() / ".."
configs := infra / "tool-configs"
artifacts := infra / "tool-artifacts"
justfiles := infra / "justfiles"

default:
	@just test-commit

_rust-qc-files:
	#!/usr/bin/env bash
	set -euo pipefail
	exclude_dirs_output="$(uv run {{artifacts}}/scripts/read_qc_excludes.py {{configs}}/qc-excludes.toml)"
	exclude_dirs=()
	if [ -n "$exclude_dirs_output" ]; then
		mapfile -t exclude_dirs <<<"$exclude_dirs_output"
	fi
	exclude_args=()
	for dir in "${exclude_dirs[@]}"; do
		exclude_args+=(-not -path "*/$dir/*")
	done
	find . -name '*.rs' "${exclude_args[@]}"

_rust-cargo-manifests:
	#!/usr/bin/env bash
	set -euo pipefail
	exclude_dirs_output="$(uv run {{artifacts}}/scripts/read_qc_excludes.py {{configs}}/qc-excludes.toml)"
	exclude_dirs=()
	if [ -n "$exclude_dirs_output" ]; then
		mapfile -t exclude_dirs <<<"$exclude_dirs_output"
	fi
	exclude_args=()
	for dir in "${exclude_dirs[@]}"; do
		exclude_args+=(-not -path "*/$dir/*")
	done
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
	cargo_manifests_output="$(just --justfile {{justfile()}} -d . _rust-cargo-manifests)"
	cargo_manifests=()
	if [ -n "$cargo_manifests_output" ]; then
		mapfile -t cargo_manifests <<<"$cargo_manifests_output"
	fi
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
	cargo_manifests_output="$(just --justfile {{justfile()}} -d . _rust-cargo-manifests)"
	cargo_manifests=()
	if [ -n "$cargo_manifests_output" ]; then
		mapfile -t cargo_manifests <<<"$cargo_manifests_output"
	fi
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
	rust_files_output="$(just --justfile {{justfile()}} -d . _rust-qc-files)"
	rust_files=()
	if [ -n "$rust_files_output" ]; then
		mapfile -t rust_files <<<"$rust_files_output"
	fi
	if [ "${#rust_files[@]}" -eq 0 ]; then
		echo "ERROR: clippy: no Rust files found in a Rust project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	cargo_manifests_output="$(just --justfile {{justfile()}} -d . _rust-cargo-manifests)"
	cargo_manifests=()
	if [ -n "$cargo_manifests_output" ]; then
		mapfile -t cargo_manifests <<<"$cargo_manifests_output"
	fi
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
	rust_files_output="$(just --justfile {{justfile()}} -d . _rust-qc-files)"
	rust_files=()
	if [ -n "$rust_files_output" ]; then
		mapfile -t rust_files <<<"$rust_files_output"
	fi
	if [ "${#rust_files[@]}" -eq 0 ]; then
		echo "ERROR: rustfmt: no Rust files found in a Rust project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	cargo_manifests_output="$(just --justfile {{justfile()}} -d . _rust-cargo-manifests)"
	cargo_manifests=()
	if [ -n "$cargo_manifests_output" ]; then
		mapfile -t cargo_manifests <<<"$cargo_manifests_output"
	fi
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
	cargo_manifests_output="$(just --justfile {{justfile()}} -d . _rust-cargo-manifests)"
	cargo_manifests=()
	if [ -n "$cargo_manifests_output" ]; then
		mapfile -t cargo_manifests <<<"$cargo_manifests_output"
	fi
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
	cargo_manifests_output="$(just --justfile {{justfile()}} -d . _rust-cargo-manifests)"
	cargo_manifests=()
	if [ -n "$cargo_manifests_output" ]; then
		mapfile -t cargo_manifests <<<"$cargo_manifests_output"
	fi
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
	rust_files_output="$(just --justfile {{justfile()}} -d . _rust-qc-files)"
	rust_files=()
	if [ -n "$rust_files_output" ]; then
		mapfile -t rust_files <<<"$rust_files_output"
	fi
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
	rust_files_output="$(just --justfile {{justfile()}} -d . _rust-qc-files)"
	rust_files=()
	if [ -n "$rust_files_output" ]; then
		mapfile -t rust_files <<<"$rust_files_output"
	fi
	if [ "${#rust_files[@]}" -eq 0 ]; then
		echo "ERROR: lizard: no Rust files found in a Rust project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	exclude_dirs_output="$(uv run {{artifacts}}/scripts/read_qc_excludes.py {{configs}}/qc-excludes.toml)"
	exclude_dirs=()
	if [ -n "$exclude_dirs_output" ]; then
		mapfile -t exclude_dirs <<<"$exclude_dirs_output"
	fi
	lizard_excludes=()
	for dir in "${exclude_dirs[@]}"; do
		lizard_excludes+=(-x "*/$dir/*")
	done
	uvx --from lizard lizard -l rust -C 7 -L 150 -a 5 -i 0 \
		"${lizard_excludes[@]}" \
		"${rust_files[@]}"

_doctor-preflight:
	#!/usr/bin/env bash
	set -euo pipefail
	uv run --project {{infra}} ai-review-ci doctor-preflight --target .

# public: COMMIT gate — immediate, directly repairable feedback
test-commit:
	#!/usr/bin/env bash
	set -euo pipefail
	export AI_REVIEW_CI_FAILURE_MODE=direct
	just --justfile {{justfile()}} -d . _doctor-preflight _check-rust-project _normalize-common _normalize _clippy _rustfmt
	just -f {{justfiles}}/shared.just -d . _no-bypass
	echo "Commit quality checks completed"

# public: PUSH gate — commit checks plus the full project-owned test suite
test-push:
	#!/usr/bin/env bash
	set -euo pipefail
	export AI_REVIEW_CI_FAILURE_MODE=direct
	just --justfile {{justfile()}} -d . test-commit _cargo-test
	echo "Push quality checks completed"

# public: CI gate — push checks plus gameable and long-running acceptance gates
test-ci:
	#!/usr/bin/env bash
	set -euo pipefail
	export AI_REVIEW_CI_FAILURE_MODE=triage
	just --justfile {{justfile()}} -d . test-push _jscpd _lizard _codeql
	just -f {{justfiles}}/shared.just -d . _global-qc
	echo "CI quality checks completed"
