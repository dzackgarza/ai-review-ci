infra := justfile_directory() / ".."
configs := infra / "tool-configs"
artifacts := infra / "tool-artifacts"
justfiles := infra / "justfiles"
biome_package := "@biomejs/biome@2.6.4"

local_qc_config_files := "biome.json biome.jsonc .biome.json .biome.jsonc " + \
	"eslint.config.js eslint.config.mjs eslint.config.cjs eslint.config.ts eslint.config.mts eslint.config.cts " + \
	"knip.json knip.jsonc .knip.json .knip.jsonc knip.ts knip.js knip.config.ts knip.config.js " + \
	"lint-staged.config.js lint-staged.config.cjs lint-staged.config.mjs " + \
	".lintstagedrc .lintstagedrc.js .lintstagedrc.cjs .lintstagedrc.mjs .lintstagedrc.json .lintstagedrc.yaml .lintstagedrc.yml"
local_qc_manifest_keys := "knip lint-staged"


_qc-excludes:
	#!/usr/bin/env bash
	set -euo pipefail
	uv run {{artifacts}}/scripts/read_qc_excludes.py {{configs}}/qc-excludes.toml

_eslint-deps:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{configs}}"
	flock --exclusive . bun install --frozen-lockfile

_normalize-common:
	#!/usr/bin/env bash
	set -euo pipefail
	just -f {{justfiles}}/shared.just -d . _normalize-common

_bun-test:
	#!/usr/bin/env bash
	set -euo pipefail
	source "{{artifacts}}/scripts/heavy-gate-lock.sh"
	echo "============================="
	echo "=== Running: bun test (push tier — no coverage gate) ==="
	echo "# Runs the project's own test suite; coverage is enforced in CI."
	unset NODE_ENV
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
	source "{{artifacts}}/scripts/heavy-gate-lock.sh"
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
	source "{{artifacts}}/scripts/heavy-gate-lock.sh"
	unset NODE_ENV
	if [ -f playwright.config.ts ]; then
		echo "Playwright project: coverage is proven by the app-boot e2e run; unit lcov is not applicable."
		exec just --justfile {{justfile()}} -d . _bun-test
	fi
	if jq -e '.scripts["test:ci"] // empty' package.json >/dev/null 2>&1; then
		bun run test:ci
		exit 0
	fi
	if jq -e '.scripts.coverage // empty' package.json >/dev/null 2>&1; then
		status=0
		bun run coverage || status=$?
		if [ -f coverage/lcov.info ]; then
			cp coverage/lcov.info lcov.info
		fi
		exit "$status"
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

_diff-cover:
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
	"{{artifacts}}/scripts/with-central-biome-config.sh" {{configs}}/biome.json bun x --package {{biome_package}} biome check "${dirs[@]}"

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
	source "{{artifacts}}/scripts/heavy-gate-lock.sh"
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
	if [[ ${QC_TIER:-} != ambient ]]; then
		base_ref="${DIFF_COVER_BASE:-}"
		if [[ -z "$base_ref" ]]; then
			for candidate in origin/HEAD origin/main main; do
				if git rev-parse --verify "$candidate^{commit}" >/dev/null 2>&1; then
					base_ref="$candidate"
					break
				fi
			done
			if [[ -z "$base_ref" ]]; then
				echo "ERROR: lizard: no local comparison ref resolves (origin/HEAD, origin/main, main); set DIFF_COVER_BASE." >&2
				exit 2
			fi
		elif ! git rev-parse --verify "$base_ref^{commit}" >/dev/null 2>&1; then
			echo "ERROR: lizard: DIFF_COVER_BASE does not resolve: $base_ref" >&2
			exit 2
		fi
		if ! base_commit="$(git merge-base "$base_ref" HEAD)"; then
			echo "ERROR: lizard: no common ancestor with $base_ref." >&2
			exit 2
		fi
		echo "# Comparing against $base_ref at $base_commit"
		scratch="$(mktemp -d)"
		base_tree="$scratch/base"
		head_output="$scratch/head.txt"
		base_output="$scratch/base.txt"
		changed_manifest="$scratch/changed"
		cleanup_lizard_diff() {
			if [[ -d "$base_tree" ]]; then
				git worktree remove --force "$base_tree" >/dev/null 2>&1 || rm -rf "$base_tree"
			fi
			rm -rf "$scratch"
		}
		trap cleanup_lizard_diff EXIT
		git diff --name-only --diff-filter=ACMRT -z "$base_commit" -- . > "$changed_manifest"
		git ls-files --others --exclude-standard -z -- . >> "$changed_manifest"
		files=()
		while IFS= read -r -d '' file; do
			[[ -f "$file" ]] || continue
			is_lizard_source "$file" || continue
			is_excluded_qc_path "$file" && continue
			files+=("$file")
		done < "$changed_manifest"
		if [ ${#files[@]} -eq 0 ]; then
			echo "lizard: no changed authored JavaScript, TypeScript, or Vue files."
			exit 0
		fi
		: > "$base_output"
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
		git worktree add --detach "$base_tree" "$base_commit" >/dev/null
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
		if [ "$status" -ne 1 ]; then
			exit "$status"
		fi
	fi

_slop-scan:
	#!/usr/bin/env bash
	set -euo pipefail
	source "{{artifacts}}/scripts/heavy-gate-lock.sh"
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
	source "{{artifacts}}/scripts/heavy-gate-lock.sh"
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
	if [ ! -f "package.json" ]; then
		echo "ERROR: TypeScript project must have a package.json file."
		failed=1
	fi
	if [ ! -f "bun.lock" ] && [ ! -f "bun.lockb" ]; then
		echo "ERROR: TypeScript project must use Bun — no bun.lock or bun.lockb found."
		failed=1
	fi
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
	if [ -f "tsconfig.json" ]; then
		if grep -qP '"strict"\s*:\s*false' tsconfig.json 2>/dev/null; then
			echo "ERROR: tsconfig.json has 'strict: false' — TypeScript strict mode is required by global QC."
			failed=1
		fi
	fi
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
	exclude_dirs_output="$(uv run {{artifacts}}/scripts/read_qc_excludes.py {{configs}}/qc-excludes.toml)"
	exclude_pathspecs=()
	if [ -n "$exclude_dirs_output" ]; then
		while IFS= read -r dir; do
			exclude_pathspecs+=(":(exclude,glob)**/$dir/**")
		done <<< "$exclude_dirs_output"
	fi
	staged_manifest="$(mktemp)"
	trap 'rm -f "$staged_manifest"' EXIT
	git diff --cached --name-only --diff-filter=ACMR -z -- . "${exclude_pathspecs[@]}" > "$staged_manifest"
	files=()
	while IFS= read -r -d '' file; do
		case "$file" in
			*.js|*.jsx|*.mjs|*.cjs|*.ts|*.tsx|*.mts|*.cts|*.vue) files+=("$file") ;;
		esac
	done < "$staged_manifest"
	if [ ${#files[@]} -eq 0 ]; then
		echo "No staged JavaScript, TypeScript, or Vue files found"
		exit 0
	fi
	if "{{artifacts}}/scripts/with-central-biome-config.sh" {{configs}}/biome.json bun x --package {{biome_package}} biome check --write --unsafe "${files[@]}"; then
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

[doc("Validate staged source syntax.")]
test-commit:
    @just -f {{justfiles}}/shared.just -d . _local-check staged

[doc("Validate syntax of outgoing committed changes.")]
test-push:
    @just -f {{justfiles}}/shared.just -d . _local-check push

_ci-checks:
	#!/usr/bin/env bash
	set -euo pipefail
	export AI_REVIEW_CI_FAILURE_MODE=triage
	just --justfile {{justfile()}} -d . test-commit _coverage _diff-cover _knip _biome _ast-grep _eslint _jscpd-bun _lizard-bun _slop-scan

[doc("Collect Bun test and quality diagnostics.")]
test-ci:
    @python3 "{{justfile_directory()}}/../scripts/ci-triage.py" bun


_ambient-bun-debt:
	#!/usr/bin/env bash
	set -euo pipefail
	export QC_TIER=ambient
	just --justfile {{justfile()}} -d . _knip _jscpd-bun _lizard-bun _slop-scan

[doc("Collect whole-tree Bun maintenance diagnostics.")]
ambient:
    @python3 "{{justfile_directory()}}/../scripts/ci-triage.py" bun --tier ambient
