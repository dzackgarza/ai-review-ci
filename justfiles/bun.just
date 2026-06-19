# justfile-bun — TypeScript-specific quality control
#
# Imports cross-language QC recipes from `justfile` (shared) and adds
# TypeScript-specific recipes. TypeScript projects delegate to this file:
#   just -f ~/ai-review-ci/justfiles/bun.just test
#
# Shared recipes (imported from justfile):
#   _no-bypass, _semgrep, _vibecheck, _slop
#
# TypeScript-specific recipes:
#   _coverage, _diff-cover, _knip, _biome, _eslint, _tsc,
#   _normalize (biome + eslint), _ast-grep, _jscpd, _lizard,
#   _codeql, _slop-scan, _lint-staged
#
# WORKFLOW (two-tier):
#   just test     — COMMIT gate: correctness + normalization only (preflight,
#                   biome/eslint auto-fix, tsc, plain bun test, bypass check).
#   just test-ci  — PUSH/CI gate: test + the full style/slop/coverage stack
#                   (coverage + diff-cover, knip, biome/eslint verify, ast-grep,
#                   jscpd, lizard, slop-scan, semgrep, vibecheck, ai-slop).
#
# HOOKS: pre-commit blocks on `just test`; pre-push blocks on `just test-ci`.
#   Run `just install-global-hooks` from ~/ai-review-ci to activate them globally.
#
# CONFIG: this justfile resolves configs and artifacts from the ai-review-ci repo.

infra := justfile_directory() / ".."
configs := infra / "tool-configs"
artifacts := infra / "tool-artifacts"
justfiles := infra / "justfiles"

# private recipes (prefix with _ — never run individually)

# QC file-scope excludes (directories to skip), sourced from qc-excludes.toml.
_qc-excludes:
	#!/usr/bin/env bash
	set -euo pipefail
	uv run {{artifacts}}/scripts/read_qc_excludes.py {{configs}}/qc-excludes.toml

_eslint-deps:
	#!/usr/bin/env bash
	set -euo pipefail
	# ESLint plugins must be installed LOCAL to the tool-configs directory.
	# ESLint flat config uses ES module imports that resolve relative to the
	# config file's location — NODE_PATH is ignored for ESM. Global installs
	# are invisible to the config loader.
	# All other tools run ephemerally via bun x (see tool-provisioning-and-environment-hygiene).
	cd {{configs}}
	bun install --frozen-lockfile

_normalize-common:
	#!/usr/bin/env bash
	set -euo pipefail
	just -f {{justfiles}}/shared.just -d . _normalize-common

_bun-test:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: bun test (commit tier — no coverage gate) ==="
	echo "# Runs the project's own test suite; must pass. Coverage is enforced at push (test-ci)."
	if jq -e '.scripts.test // empty' package.json >/dev/null 2>&1; then
		bun run test
		exit 0
	fi
	if [ ! -d tests ] && [ ! -d __tests__ ]; then
		echo "ERROR: no test script and no tests directory found."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	bun test

_coverage:
	#!/usr/bin/env bash
	set -euo pipefail
	if jq -e '.scripts.test // empty' package.json >/dev/null 2>&1; then
		bun run test
		exit 0
	fi
	if [ ! -d tests ] && [ ! -d __tests__ ]; then
		echo "ERROR: no test script and no tests directory found — 0% coverage"
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	bun test --coverage --coverage-reporter=lcov --coverage-dir=.

_diff-cover: _coverage
	#!/usr/bin/env bash
	set -euo pipefail
	if [ ! -f lcov.info ]; then
		echo "ERROR: diff-cover: lcov.info not produced — coverage step did not produce output."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	bun x diff-cover lcov.info --compare-branch ${DIFF_COVER_BASE:-main}

_knip:
	#!/usr/bin/env bash
	set -euo pipefail
	bun x knip --config {{configs}}/knip.json --no-config-hints

_biome:
	#!/usr/bin/env bash
	set -euo pipefail
	dirs=()
	[ -d src ] && dirs+=(src)
	[ -d tests ] && dirs+=(tests)
	[ ${#dirs[@]} -eq 0 ] && dirs=(.)
	bun x biome check --config-path {{configs}}/biome.json "${dirs[@]}"

_ast-grep:
	#!/usr/bin/env bash
	set -euo pipefail
	bun x ast-grep scan --config {{configs}}/sgconfig.yml

_eslint: _eslint-deps
	#!/usr/bin/env bash
	set -euo pipefail
	# Invoke via absolute path to quality-control's local eslint binary.
	# This keeps CWD = project dir (so files/**/*.ts matches project files)
	# while Node.js resolves the flat config's ES module imports from the
	# config file's directory (tool-configs/node_modules).
	"{{configs}}/node_modules/.bin/eslint" \
		--config {{configs}}/eslint.config.js \
		. --max-warnings 0

_tsc:
	#!/usr/bin/env bash
	set -euo pipefail
	if jq -e '.scripts.types // empty' package.json >/dev/null 2>&1; then
		bun run types
	elif [ -f tsconfig.json ] \
		&& jq -e '.compilerOptions.jsxImportSource == "ags/gtk4" or ((.compilerOptions.paths // {}) | has("gi://Astal?version=4.0"))' tsconfig.json >/dev/null; then
		if ags types 'Astal*' --ignore Gtk3 --ignore Astal3 --update; then
			:
		else
			ec=$?
			"{{artifacts}}/scripts/emit-triage-directive.sh"
			exit $ec
		fi
	fi
	if jq -e '.scripts.typecheck // empty' package.json >/dev/null 2>&1; then
		output="$(mktemp)"
		trap 'if [ -e "$output" ]; then gio trash "$output"; fi' EXIT
		if ! bun run typecheck >"$output" 2>&1; then
			if grep -vE '/usr/share/ags/js/|\.\./.*usr/share/ags/js/|gi://' "$output" | grep -q 'error TS'; then
				cat "$output"
				"{{artifacts}}/scripts/emit-triage-directive.sh"
				exit 1
			fi
			cat "$output"
			echo "Only system AGS/Gnim TypeScript diagnostics were reported; project-owned TypeScript passed."
			exit 0
		fi
		cat "$output"
	elif [ -f tsconfig.json ]; then
		output="$(mktemp)"
		trap 'if [ -e "$output" ]; then gio trash "$output"; fi' EXIT
		if [ -x node_modules/.bin/tsc ]; then
			tsc_cmd=(node_modules/.bin/tsc --noEmit --skipLibCheck -p tsconfig.json)
		else
			tsc_cmd=(tsc --noEmit --skipLibCheck -p tsconfig.json)
		fi
		if "${tsc_cmd[@]}" >"$output" 2>&1; then
			cat "$output"
			exit 0
		fi
		cat "$output"
		if grep -vE '/usr/share/ags/js/|\.\./.*usr/share/ags/js/|gi://' "$output" | grep -q 'error TS'; then
			"{{artifacts}}/scripts/emit-triage-directive.sh"
			exit 1
		fi
		echo "Only system AGS/Gnim TypeScript diagnostics were reported; project-owned TypeScript passed."
	else
		echo "ERROR: no package typecheck script and no tsconfig.json found"
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi

_jscpd-bun:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: jscpd copy-paste detection ==="
	echo "# Finds duplicate code blocks across JS/TS files"
	mapfile -t js_files < <(just --justfile {{justfile()}} -d . _js-qc-files)
	if [ "${#js_files[@]}" -eq 0 ]; then
		echo "ERROR: jscpd: no JS/TS files found."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	npx -y jscpd --config {{configs}}/jscpd.json \
		--format typescript \
		"${js_files[@]}"

_lizard-bun:
	#!/usr/bin/env bash
	set -euo pipefail
	lizard_excludes=()
	while IFS= read -r dir; do
		lizard_excludes+=(-x "*/$dir/*")
	done < <(uv run {{artifacts}}/scripts/read_qc_excludes.py {{configs}}/qc-excludes.toml)
	uvx lizard . -l typescript -C 8 -L 200 -a 7 -i 0 \
		"${lizard_excludes[@]}"

_js-qc-files:
	#!/usr/bin/env bash
	set -euo pipefail
	exclude_args=()
	while IFS= read -r dir; do
		exclude_args+=(-g "!**/$dir/**")
	done < <(just --justfile {{justfile()}} -d . _qc-excludes)
	rg --files \
		-g '*.ts' \
		-g '*.tsx' \
		-g '*.js' \
		-g '*.jsx' \
		-g '*.mjs' \
		-g '*.cjs' \
		"${exclude_args[@]}"

_slop-scan:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: slop-scan JS/TS anti-pattern detection ==="
	echo "# Scans JS/TS files for AI-associated slop patterns (error-swallowing, duplicate signatures, generic casts, etc.)"
	mapfile -t js_files < <(just --justfile {{justfile()}} -d . _js-qc-files)
	if [ "${#js_files[@]}" -eq 0 ]; then
		echo "ERROR: slop-scan: no JS/TS files found in a TypeScript project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	# slop-scan scan has no --fail-on flag (only delta does).
	# Run with --json (stdout) and post-process to enforce findings as failures.
	# Stderr from npx/slop-scan passes through to terminal.
	# Place QC-owned slop-scan config in the scan root (tool auto-discovers it).
	config_src="{{configs}}/slop-scan.config.json"
	config_dst="./slop-scan.config.json"
	if [ -f "$config_dst" ]; then
		if cmp -s "$config_src" "$config_dst"; then
			: # already has the QC config — leave it
		else
			echo "ERROR: Local QC override detected: $config_dst — global QC owns this tool config."
			echo "       DELETE this file. The global config already exists in"
			echo "       ~/ai-review-ci/ and is authoritative for all projects."
			"{{artifacts}}/scripts/emit-triage-directive.sh"
			exit 1
		fi
	else
		cp "$config_src" "$config_dst"
		trap 'if [ -e "$config_dst" ]; then gio trash "$config_dst"; fi' EXIT
	fi
	output=$(npx -y slop-scan scan . --json)
	count=$(echo "$output" | jq -r '.summary.findingCount // 0')
	if [ "$count" -gt 0 ]; then
		echo "$output" | jq -r '
			.findings[] | "  [" + (.severity // "?") + "] " +
			(.ruleId // "?") + " — " +
			(.path // "?") + ":" +
			((.location.line // 0) | tostring)
		'
		echo ""
		echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
		echo "  ERROR: slop-scan found $count finding(s)."
		echo "  All findings are in PROJECT CODE and must be fixed in PROJECT CODE."
		echo ""
		echo "  PROBING GLOBAL QC IS REWARD-HACKING."
		echo "  Do NOT modify QC configs, thresholds, ignore patterns, or any file"
		echo "  in ~/ai-review-ci/ to suppress these findings."
		echo "  Do NOT probe or edit QC tooling to mask the signal."
		echo ""
		echo "  The only acceptable response: fix the project code."
		echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	echo "slop-scan: 0 findings — clean."

_codeql:
	#!/usr/bin/env bash
	set -euo pipefail
	trap 'if [ -e codeql-db ]; then gio trash codeql-db; fi; if [ -e codeql-report.sarif ]; then gio trash codeql-report.sarif; fi' EXIT
	codeql database create codeql-db --overwrite --language=typescript --source-root=. --search-path=/dev/null
	codeql database analyze codeql-db --format=sarif-latest --output=codeql-report.sarif

_lint-staged:
	#!/usr/bin/env bash
	set -euo pipefail
	bun x lint-staged --config {{configs}}/lintstagedrc.json

_check-ts-project:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: TypeScript project preflight check ==="
	echo "# Validates project structure, Bun alignment, test presence, and QC config isolation"
	failed=0
	# 1. package.json must exist
	if [ ! -f "package.json" ]; then
		echo "ERROR: TypeScript project must have a package.json file."
		failed=1
	fi
	# 2. Must use Bun
	if [ ! -f "bun.lock" ] && [ ! -f "bun.lockb" ]; then
		echo "ERROR: TypeScript project must use Bun — no bun.lock or bun.lockb found."
		failed=1
	fi
	# 3. Check for local QC tool config overrides.
	#    Global QC owns these tool configs — projects must not set them locally.
	for config in biome.json eslint.config.js knip.json .lintstagedrc.json; do
		if [ -f "$config" ]; then
			echo "ERROR: Local QC override detected: $config — global QC owns this tool config."
			echo "       DELETE this file. The global config for this tool already exists in"
			echo "       ~/ai-review-ci/ and is authoritative for all projects."
			echo "       Do NOT copy or move this file to ~/ai-review-ci/ — that violates"
			echo "       QC isolation policy. If the global config needs to change, contact"
			echo "       the QC owner (dzack) to update it centrally."
			failed=1
		fi
	done
	# 4. tsconfig.json must not disable strict mode
	if [ -f "tsconfig.json" ]; then
		if grep -qP '"strict"\s*:\s*false' tsconfig.json 2>/dev/null; then
			echo "ERROR: tsconfig.json has 'strict: false' — TypeScript strict mode is required by global QC."
			failed=1
		fi
	fi
	# 5. Tests must exist
	if ! rg --files -g '*.test.ts' -g '*.test.tsx' -g '*.spec.ts' -g '*.spec.tsx' -g 'tests/' >/dev/null 2>&1; then
		echo "ERROR: TypeScript project must have tests. No test files found with patterns: *.test.ts, *.test.tsx, *.spec.ts, *.spec.tsx, tests/"
		"{{artifacts}}/scripts/emit-test-writing-directive.sh"
		exit 1
	fi
	if [ "$failed" -ne 0 ]; then
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	echo "TypeScript project configuration OK"

_normalize: _eslint-deps
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: biome format, lint, and import sorting (auto-fix) ==="
	echo "# Auto-applies safe and unsafe fixes, formatting, and import sorting"
	dirs=()
	[ -d src ] && dirs+=(src)
	[ -d tests ] && dirs+=(tests)
	[ ${#dirs[@]} -eq 0 ] && dirs=(.)
	if bun x biome check --write --unsafe --config-path {{configs}}/biome.json "${dirs[@]}"; then
		:
	else
		ec=$?
		echo "ERROR: biome auto-fix left blocking TypeScript/JavaScript issues."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi
	echo "=== Running: eslint auto-fix ==="
	if "{{configs}}/node_modules/.bin/eslint" \
		--config {{configs}}/eslint.config.js \
		--fix \
		.; then
		:
	else
		ec=$?
		echo "ERROR: eslint auto-fix left blocking TypeScript/JavaScript issues."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi

# public: COMMIT gate — correctness + normalization, plus bypass detection
test: _check-ts-project _normalize-common _normalize _tsc _bun-test
	#!/usr/bin/env bash
	set -euo pipefail
	just -f {{justfiles}}/shared.just _no-bypass
	echo "Commit-tier quality checks completed"

# public: PUSH/CI gate — test + the full style/slop/coverage stack
test-ci: test _coverage _diff-cover _knip _biome _ast-grep _eslint _jscpd-bun _lizard-bun _slop-scan
	#!/usr/bin/env bash
	set -euo pipefail
	just -f {{justfiles}}/shared.just _global-qc
	echo "Push/CI quality checks completed"
