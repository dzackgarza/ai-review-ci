# justfile — Cross-language (shared) quality control recipes
#
# This file contains QC recipes that are language-agnostic.
# Language-specific justfiles call this file explicitly and compose its
# recipes into their `test` chain alongside language-specific recipes.
#
# Language justfiles:
#   python.just  — Python QC (calls this file)
#   bun.just     — TypeScript QC (calls this file)
#   rust.just    — Rust QC (calls this file)
#   sage.just    — SageMath QC (calls this file, delegates to Python)
#
# CONFIGS:
#   tool-configs/semgrep.yml       → semgrep local rules (--config flag)
#   tool-configs/jscpd.json        → jscpd (--config flag)
#   tool-configs/slopconfig.yaml   → ai-slop-detector (--config flag)

infra := justfile_directory() / ".."
configs := infra / "tool-configs"
artifacts := infra / "tool-artifacts"

# ── Cross-language recipes ────────────────────────────────────────

_format-structured-text:
	#!/usr/bin/env bash
	set -euo pipefail
	# Strip git env vars the pre-commit hook inherits from `git commit`; left
	# set, they redirect uvx's git-sourced tool fetch (flowmark) at the host
	# project's .git and it fails with "Git operation failed".
	unset GIT_DIR GIT_INDEX_FILE GIT_WORK_TREE GIT_PREFIX GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR
	echo "============================="
	echo "=== Running: structured text formatting ==="
	echo "# Formats Markdown (flowmark), JSON, and YAML (prettier) before agents spend time on whitespace"
	# Markdown is formatted by flowmark, NOT prettier. Prettier's CommonMark
	# formatter corrupts pandoc markdown: it escapes underscores in attribute
	# paths (path="_includes/x" -> path="\_includes/x"), rewrites emphasis
	# delimiters (*x* -> _x_), and reformats embedded code blocks. flowmark is
	# the canonical markdown formatter.
	md_files=()
	data_files=()
	while IFS= read -r -d '' file; do
		case "$file" in
			AGENTS.md|*/AGENTS.md) ;;
			*.md|*.markdown) md_files+=("$file") ;;
			*.json|*.jsonc|*.yaml|*.yml) data_files+=("$file") ;;
		esac
	done < <(git diff --cached --name-only --diff-filter=ACMR -z)
	if [ "${#md_files[@]}" -eq 0 ] && [ "${#data_files[@]}" -eq 0 ]; then
		echo "No staged Markdown, JSON, or YAML files found"
		exit 0
	fi
	if [ "${#md_files[@]}" -gt 0 ]; then
		uvx --from 'git+https://github.com/dzackgarza/flowmark.git' flowmark \
			--inplace --nobackup --semantic --no-respect-gitignore "${md_files[@]}"
	fi
	if [ "${#data_files[@]}" -gt 0 ]; then
		npx -y prettier --write --config {{configs}}/prettier-global.json "${data_files[@]}"
	fi

_semgrep-autofix:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: semgrep auto-fix ==="
	echo "# Applies Semgrep autofixes; CI-tier Semgrep verification owns remaining findings"
	exclude_dirs_output="$(uv run {{artifacts}}/scripts/read_qc_excludes.py {{configs}}/qc-excludes.toml)"
	exclude_dirs=()
	if [ -n "$exclude_dirs_output" ]; then
		mapfile -t exclude_dirs <<<"$exclude_dirs_output"
	fi
	exclude_args=()
	for dir in "${exclude_dirs[@]}"; do
		exclude_args+=("--exclude=$dir")
	done
	exclude_args+=("--exclude=*.html")
	exclude_args+=("--exclude=**/*.html")
	if uvx --from semgrep semgrep scan \
		--config={{configs}}/semgrep.yml \
		--config=p/ci \
		--exclude=codeql-db \
		"${exclude_args[@]}" \
		--scan-unknown-extensions \
		--autofix; then
		:
	else
		ec=$?
		echo ""
		echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
		echo "  ERROR: semgrep auto-fix failed to run."
		echo "  Fix the QC tooling or Semgrep invocation before rerunning project checks."
		echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi

_normalize-common: _format-structured-text _semgrep-autofix
	#!/usr/bin/env bash
	set -euo pipefail
	echo "Common normalization completed"

_check-envrc:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: environment config check ==="
	echo "# Validates .envrc presence and env var hygiene"
	failed=0
	# 1. .envrc must exist
	if [ ! -f ".envrc" ]; then
		echo "ERROR: No .envrc file in project root."
		echo "       Create an .envrc with all required environment variables,"
		echo "       then run 'direnv allow' to load it."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	# 2. DIRENV_CONFIGURED_CORRECTLY must be set
	if [ -z "${DIRENV_CONFIGURED_CORRECTLY:-}" ]; then
		echo "ERROR: DIRENV_CONFIGURED_CORRECTLY is not set."
		echo "       The repo's .envrc must either use 'source_up' to inherit"
		echo "       the parent environment (which sources ~/.envrc), or explicitly"
		echo "       source \$HOME/.envrc to make the global env vars available."
		echo "       Then run 'direnv allow' to load the configuration."
		echo ""
		echo "       The justfile must NEVER define env vars via 'export'."
		echo "       All environment variables must be defined in .envrc files."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	# 3. No .env files except *.example templates — real env var definitions belong in .envrc
	if find . -maxdepth 3 -name '.env*' -not -name '.envrc' -not -name '*.example' -type f -not -path '*/.git/*' -not -path '*/node_modules/*' 2>/dev/null | grep -q .; then
		echo "ERROR: Found .env files — these are env var definitions that belong in .envrc."
		find . -maxdepth 3 -name '.env*' -not -name '.envrc' -not -name '*.example' -type f -not -path '*/.git/*' -not -path '*/node_modules/*' 2>/dev/null
		echo "       Move these variables to .envrc and delete the .env files."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	# 4. Shell scripts must not define env vars via 'export VAR=value'
	for script in $(find . -maxdepth 3 -name '*.sh' -type f -not -path '*/.git/*' -not -path '*/node_modules/*' 2>/dev/null); do
		if grep -n '^[[:space:]]*export [A-Za-z_][A-Za-z0-9_]*=' "$script" 2>/dev/null; then
			echo "ERROR: $script defines environment variables via 'export VAR=value'."
			echo "       All env vars must be centralized in .envrc."
			echo "       Move these exports to .envrc and run 'direnv allow'."
			"{{artifacts}}/scripts/emit-triage-directive.sh"
			exit 1
		fi
	done
	# 5. Justfile must not define env vars — they belong in .envrc
	for jf in "justfile" "Justfile"; do
		[ ! -f "$jf" ] && continue
		if grep -n '^export ' "$jf" 2>/dev/null; then
			echo "ERROR: $jf defines environment variables via 'export'."
			echo "       All env vars must be centralized in .envrc."
			echo "       Move these exports to .envrc and run 'direnv allow'."
			"{{artifacts}}/scripts/emit-triage-directive.sh"
			exit 1
		fi
		break
	done
	echo "Environment configuration OK"

_no-bypass:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: bypass comment detection ==="
	echo "# Blocks staged changes from hiding QC issues via bypass comments"
	if ! uv run --project {{infra}} ai-review-ci check-staged-bypass; then
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi

_check-no-local-qc-override:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: local QC override detection ==="
	echo "# Detects local config files that would override or duplicate global QC"
	failed=0
	# Shared tool configs that must NOT exist in project root.
	# Global QC owns these tool configs — local copies are forbidden overrides.
	for config in \
		semgrep.yml \
		.jscpd.json \
		.slopconfig.yaml \
		sgconfig.yml; do
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
	if [ "$failed" -ne 0 ]; then
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	echo "No local QC overrides detected"

_ensure-qc-repo-current:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: QC repo freshness check ==="
	qc_root="{{infra}}"
	qc_branch="$(git -C "$qc_root" branch --show-current)"
	if [ -z "$qc_branch" ]; then
		echo "ERROR: QC repo is in detached HEAD mode; cannot auto-update deterministically."
		echo "       Update ~/ai-review-ci manually and rerun."
		echo "       Command: git -C ~/ai-review-ci pull"
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	if ! git -C "$qc_root" fetch --quiet --prune --tags origin; then
		echo "ERROR: QC repo auto-update check failed."
		echo "  Cannot fetch from origin for ~/ai-review-ci."
		echo "  UPDATE THE QC REPO FIRST before running project QC:"
		echo "  git -C ~/ai-review-ci pull"
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	if ! git -C "$qc_root" show-ref --verify --quiet "refs/remotes/origin/$qc_branch"; then
		echo "ERROR: No remote-tracking branch found: origin/$qc_branch"
		echo "  UPDATE THE QC REPO FIRST before running project QC:"
		echo "  git -C ~/ai-review-ci pull"
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	behind_count="$(git -C "$qc_root" rev-list --count "HEAD..origin/$qc_branch")"
	if [ "$behind_count" -gt 0 ]; then
		echo "Global QC is behind by $behind_count commit(s) on origin/$qc_branch."
		echo "Attempting auto-update: git -C ~/ai-review-ci pull"
		if ! git -C "$qc_root" pull --ff-only; then
			echo "ERROR: Global QC auto-update failed (non-fast-forward or local changes)."
			echo "  UPDATE THE QC REPO FIRST before rerunning project checks:"
			echo "  git -C ~/ai-review-ci pull"
			"{{artifacts}}/scripts/emit-triage-directive.sh"
			exit 1
		fi
	fi
	echo "Global QC repo is current with origin/$qc_branch."

_semgrep:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: semgrep security pattern verification ==="
	echo "# Static analysis for code quality and fraud patterns after normalization"
	# #214: with no project .semgrepignore, semgrep falls back to its bundled
	# default template, which excludes tests/ — silently killing the
	# test-antipattern rules (py-no-monkeypatch and its NO_MOCK_PROOF /
	# NO_SKIP_MASK siblings) that are designed to fire IN test files. Ship the
	# QC-authoritative ignore set from the single-source-of-truth exclusion list
	# (vendor/generated dirs only — it does NOT list tests/) so tests/ is scanned.
	# This also overrides any repo-committed .semgrepignore for the scan
	# (no-repo-writable-QC-suppression). Restore prior state on exit.
	# "a tracked file pre-existed" and "we made a backup" are DISTINCT facts.
	# The restore trap must never conflate them: an empty backup handle must
	# not license rm-ing a tracked file we did not create. Back up BEFORE the
	# overwrite below and fail loud if the backup cannot be made, rather than
	# proceeding into a trap that could delete the user's tracked file.
	ignore_file=".semgrepignore"
	had_preexisting=0
	ignore_backup=""
	if [ -e "$ignore_file" ]; then
		had_preexisting=1
		if ! ignore_backup="$(mktemp)" || ! cp "$ignore_file" "$ignore_backup"; then
			echo ""
			echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
			echo "  ERROR: failed to back up the existing $ignore_file."
			echo "  Aborting before the QC exclude set overwrites it — the tracked file is untouched."
			echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
			"{{artifacts}}/scripts/emit-triage-directive.sh"
			exit 1
		fi
	fi
	restore_semgrepignore() {
		if [ "$had_preexisting" -eq 1 ]; then
			# A tracked file pre-existed: restore it, never remove it.
			mv -f "$ignore_backup" "$ignore_file"
		else
			# We created it ourselves; removing it is safe.
			rm -f "$ignore_file"
		fi
	}
	trap restore_semgrepignore EXIT
	uv run {{artifacts}}/scripts/read_qc_excludes.py {{configs}}/qc-excludes.toml > "$ignore_file"
	printf '%s\n' '*.html' '**/*.html' >> "$ignore_file"
	if [[ ${QC_TIER:-} != ambient && -n ${DIFF_COVER_BASE:-} ]] && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
		if ! git rev-parse --verify "${DIFF_COVER_BASE}^{commit}" >/dev/null 2>&1; then
			echo "ERROR: semgrep: DIFF_COVER_BASE does not resolve: $DIFF_COVER_BASE" >&2
			exit 2
		fi
		exclude_dirs_output="$(uv run {{artifacts}}/scripts/read_qc_excludes.py {{configs}}/qc-excludes.toml)"
		is_excluded_qc_path() {
			local file="$1"
			local exclude_dir
			while IFS= read -r exclude_dir; do
				[ -n "$exclude_dir" ] || continue
				exclude_dir="${exclude_dir%/}"
				[[ "$file" == "$exclude_dir" || "$file" == "$exclude_dir"/* ]] && return 0
			done <<< "$exclude_dirs_output"
			return 1
		}
		is_semgrep_pr_target() {
			local file="$1"
			case "$file" in
				justfile|Justfile|*.just)
					return 1
					;;
			esac
			return 0
		}
		changed_files=()
		while IFS= read -r -d '' file; do
			[[ -f "$file" ]] || continue
			is_excluded_qc_path "$file" && continue
			is_semgrep_pr_target "$file" || continue
			changed_files+=("$file")
		done < <(git diff --name-only --diff-filter=ACMR -z "${DIFF_COVER_BASE}...HEAD" -- .)
		if [ ${#changed_files[@]} -eq 0 ]; then
			echo "semgrep: no changed authored files."
			exit 0
		fi
		head_json="$(mktemp)"
		base_json="$(mktemp)"
		base_tree="$(mktemp -d)"
		cleanup_semgrep_diff() {
			rm -f "$head_json" "$base_json"
			git worktree remove --force "$base_tree" >/dev/null 2>&1 || rm -rf "$base_tree"
			restore_semgrepignore
		}
		trap cleanup_semgrep_diff EXIT
		uvx --from semgrep semgrep scan \
			--json \
			--config={{configs}}/semgrep.yml \
			--config=p/ci \
			--exclude=codeql-db \
			--scan-unknown-extensions \
			"${changed_files[@]}" > "$head_json"
		git worktree add --detach "$base_tree" "$DIFF_COVER_BASE" >/dev/null
		base_files=()
		for file in "${changed_files[@]}"; do
			[ -f "$base_tree/$file" ] && base_files+=("$file")
		done
		if [ ${#base_files[@]} -gt 0 ]; then
			(
				cd "$base_tree"
				uvx --from semgrep semgrep scan \
					--json \
					--config={{configs}}/semgrep.yml \
					--config=p/ci \
					--exclude=codeql-db \
					--scan-unknown-extensions \
					"${base_files[@]}" > "$base_json"
			)
		else
			printf '{"results":[]}\n' > "$base_json"
		fi
		uv run {{artifacts}}/scripts/semgrep_diff_gate.py --base-json "$base_json" --head-json "$head_json"
		exit 0
	fi
	if uvx --from semgrep semgrep scan \
		--config={{configs}}/semgrep.yml \
		--config=p/ci \
		--exclude=codeql-db \
		--scan-unknown-extensions \
		--error; then
		:
	else
		ec=$?
		echo ""
		echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
		echo "  ERROR: semgrep found policy violations in project code."
		echo "  Review the Semgrep finding snippets above; they identify the target file, line, rule id, and offending source."
		echo "  Route POLICY.RUNTIME_DEFAULT and other POLICY.* findings through the QC triage directive below; do not silence or locally weaken QC."
		echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi

_ast-grep:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: ast-grep structural pattern scanning ==="
	echo "# Structural code pattern analysis for bridge-burning policy violations"
	sg_config="{{configs}}/ast-grep/sgconfig.yml"
	if [ -f "$sg_config" ]; then
		exclude_dirs_output="$(uv run {{artifacts}}/scripts/read_qc_excludes.py {{configs}}/qc-excludes.toml)"
		exclude_dirs=()
		if [ -n "$exclude_dirs_output" ]; then
			mapfile -t exclude_dirs <<<"$exclude_dirs_output"
		fi
		ast_grep_globs=()
		for dir in "${exclude_dirs[@]}"; do
			ast_grep_globs+=(--globs "!**/$dir/**")
		done
		if npx -y --package @ast-grep/cli ast-grep scan --config "$sg_config" "${ast_grep_globs[@]}" .; then
			:
		else
			ec=$?
			echo ""
			echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
			if [ "$ec" -eq 1 ]; then
				echo "  ERROR: ast-grep found pattern violations in project code."
				echo "  Fix the project code, not the QC tooling."
			else
				echo "  ERROR: ast-grep FAILED TO RUN (exit $ec). This is a QC TOOLING failure,"
				echo "  NOT a project-code violation. ast-grep did not complete a scan, so no"
				echo "  finding has been made about the project. Fix the QC tooling/environment"
				echo "  (e.g. ast-grep missing from PATH, broken npx resolution, or an invalid"
				echo "  ast-grep config at $sg_config). Do NOT edit project code in response to this."
			fi
			echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
			"{{artifacts}}/scripts/emit-triage-directive.sh"
			exit $ec
		fi
	fi

_vibecheck:
	#!/usr/bin/env bash
	set -euo pipefail
	# Strip git env vars the pre-commit hook inherits from `git commit`; left
	# set, they redirect uvx's git-sourced tool fetch (vibecheck) at the host
	# project's .git and it fails with "Git operation failed".
	unset GIT_DIR GIT_INDEX_FILE GIT_WORK_TREE GIT_PREFIX GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR
	echo "============================="
	echo "=== Running: vibecheck anti-slop pattern detection ==="
	echo "# Runs qinnovates/vibecheck-slop-stopper via uvx against the project root"
	# vibecheck delegates file discovery to ripgrep. Install the QC-owned
	# exclusions as a temporary project-root .ignore file so ripgrep excludes
	# user-authored research scripts and notebooks before it parses them.
	ignore_file=".ignore"
	had_preexisting_ignore=0
	ignore_backup=""
	if [ -L "$ignore_file" ]; then
		echo "ERROR: cannot temporarily install QC exclusions: $ignore_file is a symlink."
		echo "       Refusing to follow a user-owned symlink while configuring vibecheck."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	if [ -e "$ignore_file" ]; then
		had_preexisting_ignore=1
		if ! ignore_backup="$(mktemp)" || ! cp "$ignore_file" "$ignore_backup"; then
			echo "ERROR: failed to back up existing $ignore_file before running vibecheck."
			"{{artifacts}}/scripts/emit-triage-directive.sh"
			exit 1
		fi
	fi
	restore_ignore() {
		if [ "$had_preexisting_ignore" -eq 1 ]; then
			cat "$ignore_backup" > "$ignore_file"
			rm -f "$ignore_backup"
		else
			rm -f "$ignore_file"
		fi
	}
	trap restore_ignore EXIT
	if [ "$had_preexisting_ignore" -eq 1 ]; then
		cat "$ignore_backup" > "$ignore_file"
	fi
	printf '\n' >> "$ignore_file"
	uv run {{artifacts}}/scripts/read_qc_excludes.py {{configs}}/qc-excludes.toml >> "$ignore_file"
	if raw_output=$(uvx --from git+https://github.com/qinnovates/vibecheck-slop-stopper vibecheck . --severity high --json); then
		ec=0
	else
		ec=$?
	fi
	if ! echo "$raw_output" | jq -e . >/dev/null; then
		echo "$raw_output"
		echo ""
		echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
		echo "  ERROR: vibecheck FAILED TO RUN (exit $ec). This is a QC TOOLING failure,"
		echo "  NOT a project-code violation. vibecheck did not return parseable JSON,"
		echo "  so no finding has been made about the project."
		echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit "$ec"
	fi
	head_vibecheck_json=$(mktemp)
	base_vibecheck_json=""
	base_worktree=""
	cleanup_vibecheck() {
		rm -f -- "$head_vibecheck_json"
		if [ -n "$base_vibecheck_json" ]; then
			rm -f -- "$base_vibecheck_json"
		fi
		if [ -n "$base_worktree" ]; then
			git worktree remove --force "$base_worktree" >/dev/null 2>&1 || true
		fi
		restore_ignore
	}
	trap cleanup_vibecheck EXIT
	printf '%s\n' "$raw_output" > "$head_vibecheck_json"
	base_args=()
	if [ "${QC_TIER:-}" = "test-ci" ] && [ -n "${DIFF_COVER_BASE:-}" ] && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
		base_worktree=$(mktemp -d)
		rmdir "$base_worktree"
		git worktree add --detach "$base_worktree" "$DIFF_COVER_BASE" >/dev/null
		(
			cd "$base_worktree"
			if [ -L ".ignore" ]; then
				echo "ERROR: cannot temporarily install QC exclusions in base worktree: .ignore is a symlink."
				exit 1
			fi
			printf '\n' >> ".ignore"
			uv run {{artifacts}}/scripts/read_qc_excludes.py {{configs}}/qc-excludes.toml >> ".ignore"
			if raw_base_output=$(uvx --from git+https://github.com/qinnovates/vibecheck-slop-stopper vibecheck . --severity high --json); then
				base_ec=0
			else
				base_ec=$?
			fi
			if ! echo "$raw_base_output" | jq -e . >/dev/null; then
				echo "$raw_base_output"
				echo ""
				echo "ERROR: base vibecheck failed to produce parseable JSON (exit $base_ec)."
				exit "$base_ec"
			fi
			printf '%s\n' "$raw_base_output"
		) > "$base_worktree/vibecheck-base.json"
		base_vibecheck_json=$(mktemp)
		cp "$base_worktree/vibecheck-base.json" "$base_vibecheck_json"
		base_args=(--base-json "$base_vibecheck_json" --base-root "$base_worktree")
	fi
	if ! uv run {{artifacts}}/scripts/vibecheck_gate.py --head-json "$head_vibecheck_json" --head-root "$PWD" "${base_args[@]}"; then
		echo ""
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi

_slop:
	#!/usr/bin/env bash
	set -euo pipefail
	# Preflight: verify the ML model file exists (centrally owned artifact)
	model_file="{{artifacts}}/models/slop_classifier.pkl"
	if [ ! -f "$model_file" ]; then
		echo "ERROR: ai-slop-detector ML model not found: $model_file"
		echo "  Run: uv run scripts/train_slop_model.py"
		echo "  (from the ai-review-ci repo root)"
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	echo "============================="
	echo "=== Running: ai-slop-detector ML-based quality check ==="
	echo "# ML classifier for detecting AI-generated code patterns and low-quality implementations"
	if ! uvx ai-slop-detector "$(pwd -P)" \
		--project \
		--js \
		--config {{configs}}/slopconfig.yaml \
		--verbose \
		--ci-mode hard \
		--ci-claims-strict \
		--ci-report \
		--no-color; then
		ec=$?
		echo ""
		echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
		echo "  ERROR: ai-slop-detector found slop pattern violations."
		echo "  Findings are in PROJECT CODE — fix the project code."
		echo ""
		echo "  PROBING GLOBAL QC IS REWARD-HACKING."
		echo "  Do NOT modify QC configs, thresholds, ignore patterns, or"
		echo "  ML model files in ~/ai-review-ci/ to suppress findings."
		echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi

_aislop:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: aislop AI-slop quality scan ==="
	echo "# Runs scanaislop.com's aislop scanner; blocks on error-severity findings (warnings surface but do not block)"
	exclude_dirs_output="$(uv run {{artifacts}}/scripts/read_qc_excludes.py {{configs}}/qc-excludes.toml)"
	exclude_dirs=()
	if [ -n "$exclude_dirs_output" ]; then
		mapfile -t exclude_dirs <<<"$exclude_dirs_output"
	fi
	aislop_exclude_patterns=()
	for dir in "${exclude_dirs[@]}"; do
		if [[ "$dir" == *,* ]]; then
			echo "ERROR: aislop cannot represent an exclusion path containing a comma: $dir"
			"{{artifacts}}/scripts/emit-triage-directive.sh"
			exit 1
		fi
		aislop_exclude_patterns+=("**/$dir/**")
	done
	aislop_exclude_csv="$(IFS=,; printf '%s' "${aislop_exclude_patterns[*]}")"
	if raw_output=$(npx -y aislop@latest scan --json --exclude "$aislop_exclude_csv" .); then
		:
	else
		ec=$?
		if ! printf '%s' "$raw_output" | jq -e . >/dev/null 2>&1; then
			printf '%s\n' "$raw_output"
			echo ""
			echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
			echo "  ERROR: aislop FAILED TO RUN (exit $ec). This is a QC TOOLING failure,"
			echo "  NOT a project-code violation. aislop did not return parseable JSON,"
			echo "  so no finding has been made about the project."
			echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
			"{{artifacts}}/scripts/emit-triage-directive.sh"
			exit "$ec"
		fi
	fi
	if ! printf '%s' "$raw_output" | jq -e . >/dev/null 2>&1; then
		printf '%s\n' "$raw_output"
		echo ""
		echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
		echo "  ERROR: aislop did not return parseable JSON. This is a QC TOOLING failure,"
		echo "  NOT a project-code violation."
		echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	# Fail closed on an unexpected-but-parseable schema: if summary.errors /
	# summary.warnings are not numbers, or diagnostics is not an array, the
	# numeric guards below would silently fall through and treat the scan as
	# clean. Treat a schema mismatch as a QC TOOLING failure, not a pass.
	if ! printf '%s' "$raw_output" | jq -e '(.summary.errors | type == "number") and (.summary.warnings | type == "number") and (.diagnostics | type == "array")' >/dev/null 2>&1; then
		printf '%s\n' "$raw_output"
		echo ""
		echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
		echo "  ERROR: aislop returned JSON without the expected schema (numeric"
		echo "  summary.errors and summary.warnings, array diagnostics). This is a QC"
		echo "  TOOLING failure — failing closed rather than assuming the scan passed."
		echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	head_aislop_json=$(mktemp)
	base_aislop_json=""
	base_worktree=""
	cleanup_aislop() {
		rm -f -- "$head_aislop_json"
		if [ -n "$base_aislop_json" ]; then
			rm -f -- "$base_aislop_json"
		fi
		if [ -n "$base_worktree" ]; then
			git worktree remove --force "$base_worktree" >/dev/null 2>&1 || true
		fi
	}
	trap cleanup_aislop EXIT
	printf '%s\n' "$raw_output" > "$head_aislop_json"
	base_args=()
	if [ "${QC_TIER:-}" = "test-ci" ] && [ -n "${DIFF_COVER_BASE:-}" ] && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
		base_worktree=$(mktemp -d)
		rmdir "$base_worktree"
		git worktree add --detach "$base_worktree" "$DIFF_COVER_BASE" >/dev/null
		(
			cd "$base_worktree"
			base_exclude_patterns=()
			while IFS= read -r dir; do
				if [[ "$dir" == *,* ]]; then
					echo "ERROR: aislop cannot represent an exclusion path containing a comma in base worktree: $dir"
					exit 1
				fi
				base_exclude_patterns+=("**/$dir/**")
			done < <(uv run {{artifacts}}/scripts/read_qc_excludes.py {{configs}}/qc-excludes.toml)
			base_exclude_csv="$(IFS=,; printf '%s' "${base_exclude_patterns[*]}")"
			if raw_base_output=$(npx -y aislop@latest scan --json --exclude "$base_exclude_csv" .); then
				base_ec=0
			else
				base_ec=$?
			fi
			if ! printf '%s' "$raw_base_output" | jq -e . >/dev/null 2>&1; then
				printf '%s\n' "$raw_base_output"
				echo ""
				echo "ERROR: base aislop failed to produce parseable JSON (exit $base_ec)."
				exit "$base_ec"
			fi
			if ! printf '%s' "$raw_base_output" | jq -e '(.summary.errors | type == "number") and (.summary.warnings | type == "number") and (.diagnostics | type == "array")' >/dev/null 2>&1; then
				printf '%s\n' "$raw_base_output"
				echo ""
				echo "ERROR: base aislop returned JSON without the expected schema."
				exit 1
			fi
			printf '%s\n' "$raw_base_output"
		) > "$base_worktree/aislop-base.json"
		base_aislop_json=$(mktemp)
		cp "$base_worktree/aislop-base.json" "$base_aislop_json"
		base_args=(--base-json "$base_aislop_json" --base-root "$base_worktree")
	fi
	if ! uv run {{artifacts}}/scripts/aislop_gate.py --head-json "$head_aislop_json" --head-root "$PWD" "${base_args[@]}"; then
		echo ""
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi

# ── Config Sync ───────────────────────────────────────────────────
# Sync qc-excludes.toml into every tool config (biome, eslint, knip,
# jscpd, slop-scan, pyright, grain, and justfile-rust _rust-qc-files).

# Run this whenever qc-excludes.toml changes.
_sync-qc-excludes:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "=== Syncing qc-excludes.toml into tool configs ==="
	uv run {{artifacts}}/scripts/sync_qc_excludes.py {{configs}}/qc-excludes.toml
	echo "Done. Commit the updated configs."

# ── Entry Points ──────────────────────────────────────────────────

# Push/CI-tier cross-language stack. `_no-bypass` is NOT here — it is a
# commit-tier check invoked directly by each language's `test-commit` recipe.
_global-qc: _ensure-qc-repo-current _check-envrc _check-no-local-qc-override _semgrep _ast-grep _vibecheck _slop _aislop
	#!/usr/bin/env bash
	set -euo pipefail
	echo "Global quality checks completed"
