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
	echo "============================="
	echo "=== Running: structured text formatting ==="
	echo "# Formats Markdown (flowmark), JSON, and YAML (prettier) before agents spend time on whitespace"
	prune_args=()
	while IFS= read -r dir; do
		prune_args+=(-path "./$dir" -o -path "*/$dir" -o -path "*/$dir/*" -o)
	done < <(uv run {{artifacts}}/scripts/read_qc_excludes.py {{configs}}/qc-excludes.toml)
	if [ "${#prune_args[@]}" -eq 0 ]; then
		echo "ERROR: qc-excludes.toml produced no exclusions for structured text formatting."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	unset 'prune_args[${#prune_args[@]}-1]'
	# Markdown is formatted by flowmark, NOT prettier. Prettier's CommonMark
	# formatter corrupts pandoc markdown: it escapes underscores in attribute
	# paths (path="_includes/x" -> path="\_includes/x"), rewrites emphasis
	# delimiters (*x* -> _x_), and reformats embedded code blocks. flowmark is
	# the canonical markdown formatter.
	md_files=()
	while IFS= read -r -d '' file; do
		md_files+=("$file")
	done < <(
		find . -type d \( "${prune_args[@]}" \) -prune -o \
			-type f \( -name '*.md' -o -name '*.markdown' \) \
			-print0
	)
	data_files=()
	while IFS= read -r -d '' file; do
		data_files+=("$file")
	done < <(
		find . -type d \( "${prune_args[@]}" \) -prune -o \
			-type f \( \
				-name '*.json' -o \
				-name '*.jsonc' -o \
				-name '*.yaml' -o \
				-name '*.yml' \
			\) \
			-print0
	)
	if [ "${#md_files[@]}" -eq 0 ] && [ "${#data_files[@]}" -eq 0 ]; then
		echo "No Markdown, JSON, or YAML files found"
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
	echo "# Applies Semgrep autofixes before later checks verify the post-fix tree"
	if uvx --from semgrep semgrep scan \
		--config={{configs}}/semgrep.yml \
		--config=p/ci \
		--exclude=codeql-db \
		--scan-unknown-extensions \
		--error \
		--autofix; then
		:
	else
		ec=$?
		echo ""
		echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
		echo "  ERROR: semgrep auto-fix left blocking pattern violations."
		echo "  Fix the project code, not the QC tooling."
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
	# 3. No .env files — they are env var definitions outside .envrc
	if find . -maxdepth 3 -name '.env*' -not -name '.envrc' -type f -not -path '*/.git/*' -not -path '*/node_modules/*' 2>/dev/null | grep -q .; then
		echo "ERROR: Found .env files — these are env var definitions that belong in .envrc."
		find . -maxdepth 3 -name '.env*' -not -name '.envrc' -type f -not -path '*/.git/*' -not -path '*/node_modules/*' 2>/dev/null
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
	if ! files=$(git diff --cached --name-only --diff-filter=ACM 2>/dev/null); then
		files=""
	fi
	[ -z "$files" ] && exit 0
	for file in $files; do
		if [ ! -f "$file" ]; then
			continue
		fi
		if grep -n "# pragma: no cover" "$file" 2>/dev/null; then
			echo "ERROR: $file contains '# pragma: no cover' — fix coverage, don't hide it"
			"{{artifacts}}/scripts/emit-triage-directive.sh"
			exit 1
		fi
		if grep -n "// istanbul ignore" "$file" 2>/dev/null; then
			echo "ERROR: $file contains '// istanbul ignore' — fix coverage, don't hide it"
			"{{artifacts}}/scripts/emit-triage-directive.sh"
			exit 1
		fi
		if grep -n "# noqa" "$file" 2>/dev/null; then
			echo "ERROR: $file contains '# noqa' — fix lint errors, don't hide them"
			"{{artifacts}}/scripts/emit-triage-directive.sh"
			exit 1
		fi
		if grep -n "# type: ignore" "$file" 2>/dev/null; then
			echo "ERROR: $file contains '# type: ignore' — fix type errors, don't hide them"
			"{{artifacts}}/scripts/emit-triage-directive.sh"
			exit 1
		fi
		if grep -nP 'as\s+(unknown|any|never)\s+as\s' "$file" 2>/dev/null; then
			echo "ERROR: $file contains a double-cast bypass (e.g., 'as unknown as') — use a proper type assertion or restructure the code"
			"{{artifacts}}/scripts/emit-triage-directive.sh"
			exit 1
		fi
		if grep -n "@ts-ignore" "$file" 2>/dev/null; then
			echo "ERROR: $file contains '@ts-ignore' — fix type errors, don't hide them"
			"{{artifacts}}/scripts/emit-triage-directive.sh"
			exit 1
		fi
		if grep -n "@ts-expect-error$" "$file" 2>/dev/null; then
			echo "ERROR: $file contains '@ts-expect-error' without justification — add a comment explaining why"
			"{{artifacts}}/scripts/emit-triage-directive.sh"
			exit 1
		fi
		if grep -n "// eslint-disable" "$file" 2>/dev/null; then
			echo "ERROR: $file contains '// eslint-disable' — fix lint errors, don't hide them"
			"{{artifacts}}/scripts/emit-triage-directive.sh"
			exit 1
		fi
	done
	echo "No bypass comments detected in staged files"

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

_semgrep:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: semgrep security pattern verification ==="
	echo "# Static analysis for code quality and fraud patterns after normalization"
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
		echo "  ERROR: semgrep found pattern violations in project code."
		echo "  Fix the project code, not the QC tooling."
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
		if npx -y ast-grep scan --config "$sg_config" .; then
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
	echo "============================="
	echo "=== Running: vibecheck anti-slop pattern detection ==="
	echo "# Runs qinnovates/vibecheck-slop-stopper via uvx against the project root"
	if uvx --from git+https://github.com/qinnovates/vibecheck-slop-stopper vibecheck . --severity high; then
		:
	else
		ec=$?
		echo ""
		echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
		echo "  ERROR: vibecheck found anti-slop pattern violations."
		echo "  Findings are in PROJECT CODE — fix the project code."
		echo ""
		echo "  PROBING GLOBAL QC IS REWARD-HACKING."
		echo "  Do NOT modify QC configs or tooling in ~/ai-review-ci/"
		echo "  to suppress these findings."
		echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
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

_global-qc: _check-envrc _no-bypass _check-no-local-qc-override _semgrep _ast-grep _vibecheck _slop
	#!/usr/bin/env bash
	set -euo pipefail
	echo "Global quality checks completed"

_global-qc-ci: _global-qc
	#!/usr/bin/env bash
	set -euo pipefail
	echo "Global CI quality checks completed"
