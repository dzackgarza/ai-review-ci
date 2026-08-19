# justfile-bun — TypeScript-specific quality control
#
# Imports cross-language QC recipes from `justfile` (shared) and adds
# TypeScript-specific recipes. TypeScript projects delegate to this file:
#   just -f ~/ai-review-ci/justfiles/bun.just -d . test-commit
#
# Shared recipes (imported from justfile):
#   _no-bypass, _semgrep, _vibecheck, _slop
#
# TypeScript-specific recipes:
#   _coverage, _diff-cover, _knip, _biome, _eslint, _tsc,
#   _normalize (biome + eslint), _ast-grep, _jscpd, _lizard,
#   _codeql, _slop-scan, _lint-staged
#
# WORKFLOW (three-tier):
#   just test-commit — preflight, normalization, tsc, bypass check.
#   just test-push   — commit checks plus the full Bun test suite.
#   just test-ci     — push checks plus coverage and policy-sensitive gates.
#
# HOOKS: pre-commit blocks on `just test-commit`; pre-push blocks on `just test-push`.
#   Run `just install-global-hooks` from ~/ai-review-ci to activate them globally.
#
# CONFIG: this justfile resolves configs and artifacts from the ai-review-ci repo.

infra := justfile_directory() / ".."
configs := infra / "tool-configs"
artifacts := infra / "tool-artifacts"
justfiles := infra / "justfiles"

# Every config filename these QC tools discover on their own. A project that carries any
# of them diverges its local run from canonical CI (#292). Each list is the tool's own
# resolution order: biome ConfigName::BIOME_JSON (biome_fs/src/fs.rs), eslint
# FLAT_CONFIG_FILENAMES (lib/config/config-loader.js), knip.dev/overview/configuration,
# lint-staged CONFIG_FILE_NAMES (lib/loadConfig.js).
local_qc_config_files := "biome.json biome.jsonc .biome.json .biome.jsonc " + \
	"eslint.config.js eslint.config.mjs eslint.config.cjs eslint.config.ts eslint.config.mts eslint.config.cts " + \
	"knip.json knip.jsonc .knip.json .knip.jsonc knip.ts knip.js knip.config.ts knip.config.js " + \
	"lint-staged.config.js lint-staged.config.cjs lint-staged.config.mjs " + \
	".lintstagedrc .lintstagedrc.js .lintstagedrc.cjs .lintstagedrc.mjs .lintstagedrc.json .lintstagedrc.yaml .lintstagedrc.yml"
# knip and lint-staged also load config from a package.json key, with no config file present.
local_qc_manifest_keys := "knip lint-staged"

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
	echo "=== Running: bun test (push tier — no coverage gate) ==="
	echo "# Runs the project's own test suite; coverage is enforced in CI."
	unset NODE_ENV
	# A repo may declare a dedicated push-tier suite (e.g. units plus a browser
	# smoke subset) as scripts["test:push"]; the full suite then runs in CI via
	# scripts["test:ci"] (see _coverage).
	if jq -e '.scripts["test:push"] // empty' package.json >/dev/null 2>&1; then
		bun run test:push
		exit 0
	fi
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

app-boot:
	#!/usr/bin/env bash
	set -euo pipefail
	export AI_REVIEW_CI_FAILURE_MODE=triage
	if [ ! -f playwright.config.ts ]; then
		echo "ERROR: bun-playwright projects must define playwright.config.ts at the repository root."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	bunx playwright test --config playwright.config.ts

_coverage:
	#!/usr/bin/env bash
	set -euo pipefail
	unset NODE_ENV
	# Playwright (e2e-covered) projects prove coverage through the app-boot e2e run in
	# test-ci, not a unit lcov. Unit-lcov diff-cover does not apply to them.
	if [ -f playwright.config.ts ]; then
		echo "Playwright project: coverage is proven by the app-boot e2e run; unit lcov is not applicable."
		exit 0
	fi
	# A repo that split its suite into push/CI tiers runs the full suite here.
	# The script owns its coverage flags and must leave lcov.info at the repo root.
	if jq -e '.scripts["test:ci"] // empty' package.json >/dev/null 2>&1; then
		bun run test:ci
		exit 0
	fi
	if jq -e '.scripts.coverage // empty' package.json >/dev/null 2>&1; then
		bun run coverage
		if [ -f coverage/lcov.info ]; then
			cp coverage/lcov.info lcov.info
		fi
		exit 0
	fi
	if jq -e '(.devDependencies.vitest // .dependencies.vitest // empty)' package.json >/dev/null 2>&1; then
		bun run test -- --coverage --coverage.reporter=lcov
		cp coverage/lcov.info lcov.info
		exit 0
	fi
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
	if [ -f playwright.config.ts ]; then
		echo "Playwright project: diff-cover skipped; coverage is proven via the app-boot e2e run."
		exit 0
	fi
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
	js_files_output="$(just --justfile {{justfile()}} -d . _js-qc-files)"
	js_files=()
	if [ -n "$js_files_output" ]; then
		mapfile -t js_files <<<"$js_files_output"
	fi
	if [ "${#js_files[@]}" -eq 0 ]; then
		echo "ERROR: ast-grep: no JS/TS files found."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	npx -y --package @ast-grep/cli ast-grep scan --config {{configs}}/sgconfig.yml "${js_files[@]}"

_eslint: _eslint-deps
	#!/usr/bin/env bash
	set -euo pipefail
	dirs=()
	for candidate in src source tests test; do
		[ -d "$candidate" ] && dirs+=("$candidate")
	done
	[ ${#dirs[@]} -eq 0 ] && dirs=(.)
	"{{infra}}/scripts/run-eslint-batched.sh" \
		"{{configs}}/node_modules/.bin/eslint" \
		"{{configs}}/eslint.config.js" \
		"${dirs[@]}"

_tsc:
	#!/usr/bin/env bash
	set -euo pipefail
	if jq -e '.scripts.types // empty' package.json >/dev/null 2>&1; then
		bun run types
	elif [ -f tsconfig.json ] \
		&& rg -q '"jsxImportSource"\s*:\s*"ags/gtk4"|"gi://Astal\?version=4\.0"' tsconfig.json; then
		if ags types 'Astal*' --ignore Gtk3 --ignore Astal3 --update; then
			:
		else
			ec=$?
			"{{artifacts}}/scripts/emit-triage-directive.sh"
			exit $ec
		fi
	fi
	if jq -e '.scripts.typecheck // empty' package.json >/dev/null 2>&1; then
		output="$(mktemp -p "{{infra}}" .tsc-output.XXXXXX)"
		trap 'if [ -e "$output" ]; then rm -f -- "$output"; fi' EXIT
		if ! bun run typecheck >"$output" 2>&1; then
			if [ -f tsconfig.json ] \
				&& rg -q '"jsxImportSource"\s*:\s*"ags/gtk4"|"gi://Astal\?version=4\.0"' tsconfig.json \
				&& ! grep -vE '/usr/share/ags/js/|\.\./.*usr/share/ags/js/|gi://' "$output" | grep -q 'error TS'; then
				cat "$output"
				echo "Only system AGS/Gnim TypeScript diagnostics were reported; project-owned TypeScript passed."
				exit 0
			fi
			cat "$output"
			"{{artifacts}}/scripts/emit-triage-directive.sh"
			exit 1
		fi
		cat "$output"
	elif [ -f tsconfig.json ]; then
		output="$(mktemp -p "{{infra}}" .tsc-output.XXXXXX)"
		trap 'if [ -e "$output" ]; then rm -f -- "$output"; fi' EXIT
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
	js_files_output="$(just --justfile {{justfile()}} -d . _js-qc-files)"
	js_files=()
	if [ -n "$js_files_output" ]; then
		mapfile -t js_files <<<"$js_files_output"
	fi
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
	echo "============================="
	echo "=== Running: lizard complexity analysis ==="
	echo "# Finds excessive complexity in authored JS/TS/Vue files"
	exclude_dirs_output="$(uv run {{artifacts}}/scripts/read_qc_excludes.py {{configs}}/qc-excludes.toml)"
	exclude_dirs=()
	if [ -n "$exclude_dirs_output" ]; then
		mapfile -t exclude_dirs <<<"$exclude_dirs_output"
	fi
	is_lizard_source() {
		case "$1" in
			*.js|*.jsx|*.mjs|*.cjs|*.ts|*.tsx|*.mts|*.cts|*.vue) return 0 ;;
			*) return 1 ;;
		esac
	}
	is_excluded_qc_path() {
		local file=$1
		local dir
		for dir in "${exclude_dirs[@]}"; do
			[[ "$file" == "$dir"/* || "$file" == */"$dir"/* ]] && return 0
		done
		return 1
	}
	if [[ ${QC_TIER:-} != ambient && -n ${DIFF_COVER_BASE:-} ]]; then
		if ! git rev-parse --verify "${DIFF_COVER_BASE}^{commit}" >/dev/null 2>&1; then
			echo "ERROR: lizard: DIFF_COVER_BASE does not resolve: $DIFF_COVER_BASE" >&2
			exit 2
		fi
		files=()
		while IFS= read -r -d '' file; do
			[[ -f "$file" ]] || continue
			is_lizard_source "$file" || continue
			is_excluded_qc_path "$file" && continue
			files+=("$file")
		done < <(git diff --name-only --diff-filter=ACMR -z "${DIFF_COVER_BASE}...HEAD" -- .)
		if [ ${#files[@]} -eq 0 ]; then
			echo "lizard: no changed authored JavaScript, TypeScript, or Vue files."
			exit 0
		fi
		head_output="$(mktemp)"
		base_output="$(mktemp)"
		base_tree="$(mktemp -d)"
		cleanup_lizard_diff() {
			rm -f "$head_output" "$base_output"
			git worktree remove --force "$base_tree" >/dev/null 2>&1 || rm -rf "$base_tree"
		}
		trap cleanup_lizard_diff EXIT
		set +e
		uvx lizard -l typescript -C 8 -L 200 -a 7 -i 0 "${files[@]}" | tee "$head_output"
		head_status=${PIPESTATUS[0]}
		set -e
		if [ "$head_status" -eq 0 ]; then
			exit 0
		fi
		if [ "$head_status" -ne 1 ]; then
			exit "$head_status"
		fi
		git worktree add --detach "$base_tree" "$DIFF_COVER_BASE" >/dev/null
		base_files=()
		for file in "${files[@]}"; do
			[ -f "$base_tree/$file" ] && base_files+=("$file")
		done
		if [ ${#base_files[@]} -gt 0 ]; then
			(
				cd "$base_tree"
				set +e
				uvx lizard -l typescript -C 8 -L 200 -a 7 -i 0 "${base_files[@]}" > "$base_output"
				base_status=$?
				set -e
				if [ "$base_status" -ne 0 ] && [ "$base_status" -ne 1 ]; then
					exit "$base_status"
				fi
			)
		fi
		uv run {{artifacts}}/scripts/lizard_diff_gate.py --base-output "$base_output" --head-output "$head_output"
		exit 0
	fi
	lizard_excludes=()
	for dir in "${exclude_dirs[@]}"; do
		lizard_excludes+=(-x "*/$dir/*")
	done
	uvx lizard . -l typescript -C 8 -L 200 -a 7 -i 0 \
		"${lizard_excludes[@]}"

_js-qc-files:
	#!/usr/bin/env bash
	set -euo pipefail
	exclude_dirs_output="$(just --justfile {{justfile()}} -d . _qc-excludes)"
	exclude_dirs=()
	if [ -n "$exclude_dirs_output" ]; then
		mapfile -t exclude_dirs <<<"$exclude_dirs_output"
	fi
	exclude_args=()
	for dir in "${exclude_dirs[@]}"; do
		exclude_args+=(-g "!**/$dir/**")
	done
	if rg --files \
		-g '*.ts' \
		-g '*.tsx' \
		-g '*.js' \
		-g '*.jsx' \
		-g '*.mjs' \
		-g '*.cjs' \
		"${exclude_args[@]}"; then
		:
	else
		status=$?
		# rg uses 1 for an empty selection. Callers own the required-language
		# diagnostic; source-discovery errors still propagate.
		if [ "$status" -ne 1 ]; then
			exit "$status"
		fi
	fi

_slop-scan:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: slop-scan JS/TS anti-pattern detection ==="
	echo "# Scans JS/TS files for AI-associated slop patterns (error-swallowing, duplicate signatures, generic casts, etc.)"
	exclude_dirs_output="$(uv run {{artifacts}}/scripts/read_qc_excludes.py {{configs}}/qc-excludes.toml)"
	exclude_dirs=()
	if [ -n "$exclude_dirs_output" ]; then
		mapfile -t exclude_dirs <<<"$exclude_dirs_output"
	fi
	is_slop_scan_source() {
		case "$1" in
			*.js|*.jsx|*.mjs|*.cjs|*.ts|*.tsx|*.mts|*.cts|*.vue) return 0 ;;
			*) return 1 ;;
		esac
	}
	is_excluded_qc_path() {
		local file=$1
		local dir
		for dir in "${exclude_dirs[@]}"; do
			[[ "$file" == "$dir"/* || "$file" == */"$dir"/* ]] && return 0
		done
		return 1
	}
	js_files_output="$(just --justfile {{justfile()}} -d . _js-qc-files)"
	js_files=()
	if [ -n "$js_files_output" ]; then
		mapfile -t js_files <<<"$js_files_output"
	fi
	if [ "${#js_files[@]}" -eq 0 ]; then
		echo "ERROR: slop-scan: no JS/TS files found in a TypeScript project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	# slop-scan scan has no --fail-on flag (only delta does).
	# Run with --json (stdout) and post-process to enforce findings as failures.
	# Stderr from npx/slop-scan passes through to terminal.
	# Place QC-owned slop-scan config in the scan root (tool auto-discovers it).
	raw_output_file="$(mktemp)"
	output_file="$(mktemp)"
	copied_config=0
	config_src="{{configs}}/slop-scan.config.json"
	config_dst="./slop-scan.config.json"
	cleanup_slop_scan() {
		if [ "$copied_config" -eq 1 ] && [ -e "$config_dst" ]; then
			gio trash "$config_dst"
		fi
		rm -f "$raw_output_file" "$output_file"
	}
	trap cleanup_slop_scan EXIT
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
		copied_config=1
	fi

	changed_paths_json='null'
	if [[ ${QC_TIER:-} != ambient && -n ${DIFF_COVER_BASE:-} ]]; then
		if ! git rev-parse --verify "${DIFF_COVER_BASE}^{commit}" >/dev/null 2>&1; then
			echo "ERROR: slop-scan: DIFF_COVER_BASE does not resolve: $DIFF_COVER_BASE" >&2
			exit 2
		fi
		changed_files=()
		while IFS= read -r -d '' file; do
			[[ -f "$file" ]] || continue
			is_slop_scan_source "$file" || continue
			is_excluded_qc_path "$file" && continue
			changed_files+=("$file")
		done < <(git diff --name-only --diff-filter=ACMR -z "${DIFF_COVER_BASE}...HEAD" -- .)
		if [ ${#changed_files[@]} -eq 0 ]; then
			echo "slop-scan: no changed authored JavaScript, TypeScript, or Vue files."
			exit 0
		fi
		changed_paths_json="$(printf '%s\0' "${changed_files[@]}" | python3 -c 'import json, sys; print(json.dumps([p for p in sys.stdin.buffer.read().decode().split("\0") if p]))')"
	fi

	npx -y slop-scan scan . --json > "$raw_output_file"
	ignored_count=$(jq -r '
		[.findings[]? | select((.ruleId // "") == "structure.pass-through-wrappers" or (.ruleId // "") == "structure.directory-fanout-hotspot")]
		| length
	' "$raw_output_file")
	jq --argjson changed_paths "$changed_paths_json" '
		.findings = [
			.findings[]?
			| select((.ruleId // "") != "structure.pass-through-wrappers")
			| select((.ruleId // "") != "structure.directory-fanout-hotspot")
			| (.path // "") as $finding_path
			| select($changed_paths == null or ($changed_paths | index($finding_path)))
		]
		| .summary.findingCount = (.findings | length)
	' "$raw_output_file" > "$output_file"
	if [ "$ignored_count" -gt 0 ]; then
		echo "slop-scan: ignored $ignored_count non-gating structural heuristic finding(s)."
	fi
	count=$(jq -r '.summary.findingCount // 0' "$output_file")
	if [ "$count" -gt 0 ]; then
		jq -r '
			.findings[] | "  [" + (.severity // "?") + "] " +
			(.ruleId // "?") + " — " +
			(.path // "?") + ":" +
			((.location.line // 0) | tostring)
		' "$output_file"
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
	bun x lint-staged --config {{configs}}/lintstagedrc.mjs

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
	report_local_qc_override() {
		echo "ERROR: Local QC override detected: $1 — global QC owns this tool config."
		echo "       $2 The global config for this tool already exists in"
		echo "       ~/ai-review-ci/ and is authoritative for all projects."
		echo "       Do NOT copy or move this config to ~/ai-review-ci/ — that violates"
		echo "       QC isolation policy. If the global config needs to change, contact"
		echo "       the QC owner (dzack) to update it centrally."
		failed=1
	}
	for config in {{local_qc_config_files}}; do
		if [ -f "$config" ]; then
			report_local_qc_override "$config" "DELETE this file."
		fi
	done
	if [ -f "package.json" ]; then
		if ! jq -e 'type == "object"' package.json >/dev/null; then
			echo "ERROR: package.json is not a JSON object — cannot audit it for local QC config."
			failed=1
		else
			for key in {{local_qc_manifest_keys}}; do
				if jq -e --arg key "$key" 'has($key)' package.json >/dev/null; then
					report_local_qc_override "package.json#$key" "REMOVE this key."
				fi
			done
		fi
	fi
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
	files=()
	while IFS= read -r -d '' file; do
		case "$file" in
			*.js|*.jsx|*.mjs|*.cjs|*.ts|*.tsx|*.mts|*.cts|*.vue) files+=("$file") ;;
		esac
	done < <(git diff --cached --name-only --diff-filter=ACMR -z)
	if [ ${#files[@]} -eq 0 ]; then
		echo "No staged JavaScript, TypeScript, or Vue files found"
		exit 0
	fi
	if bun x biome check --write --unsafe --config-path {{configs}}/biome.json "${files[@]}"; then
		:
	else
		ec=$?
		echo "ERROR: biome auto-fix left blocking TypeScript/JavaScript issues."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi
	echo "=== Running: eslint auto-fix ==="
	if ESLINT_FIX=1 "{{infra}}/scripts/run-eslint-batched.sh" \
		"{{configs}}/node_modules/.bin/eslint" \
		"{{configs}}/eslint.config.js" \
		"${files[@]}"; then
		:
	else
		ec=$?
		echo "ERROR: eslint auto-fix left blocking TypeScript/JavaScript issues."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi

_doctor-preflight:
	#!/usr/bin/env bash
	set -euo pipefail
	uv run --project {{infra}} ai-review-ci doctor-preflight --target .

# public: COMMIT gate — immediate, directly repairable feedback
test-commit:
	#!/usr/bin/env bash
	set -euo pipefail
	export AI_REVIEW_CI_FAILURE_MODE=direct
	just --justfile {{justfile()}} -d . _doctor-preflight _check-ts-project _normalize-common _normalize _tsc
	just -f {{justfiles}}/shared.just -d . _no-bypass
	echo "Commit quality checks completed"

# public: PUSH gate — commit checks plus the full project-owned test suite
test-push:
	#!/usr/bin/env bash
	set -euo pipefail
	export AI_REVIEW_CI_FAILURE_MODE=direct
	just --justfile {{justfile()}} -d . test-commit _bun-test
	echo "Push quality checks completed"

# public: CI gate — push checks plus gameable and long-running acceptance gates
test-ci:
	#!/usr/bin/env bash
	set -euo pipefail
	export AI_REVIEW_CI_FAILURE_MODE=triage
	just --justfile {{justfile()}} -d . test-push _coverage _diff-cover _knip _biome _ast-grep _eslint _jscpd-bun _lizard-bun _slop-scan
	just -f {{justfiles}}/shared.just -d . _global-qc
	echo "CI quality checks completed"
