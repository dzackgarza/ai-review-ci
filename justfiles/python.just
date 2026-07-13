# justfile-python — Python-specific quality control
#
# Imports cross-language QC recipes from `justfile` (shared) and adds
# Python-specific recipes. Python projects delegate to this file:
#   just -f ~/ai-review-ci/justfiles/python.just -d . test
#
# Shared recipes (imported from justfile):
#   _no-bypass, _semgrep, _vibecheck, _slop
#
# Python-specific recipes:
#   _python-qc-files, _python-syntax, _mypy, _normalize (ruff),
#   _pytest_with_coverage, _diff-cover, _vulture, _deptry,
#   _import-linter, _grain, _ast-grep, _jscpd, _lizard, _codeql
#
# WORKFLOW (two-tier):
#   just test     — COMMIT gate: correctness + normalization only (preflight,
#                   normalize/auto-fix, syntax, mypy, plain pytest, bypass check).
#   just test-ci  — PUSH/CI gate: test + changed-line coverage and deterministic
#                   dependency/import/AST/duplication gates. Broad debt scans
#                   stay available through _ambient-python-debt.
#
# HOOKS: pre-commit blocks on `just test`; pre-push blocks on `just test-ci`.
#   Run `just install-global-hooks` from ~/ai-review-ci to activate them globally.
#
# CONFIG: this justfile resolves configs and artifacts from the ai-review-ci repo.

infra := justfile_directory() / ".."
configs := infra / "tool-configs"
artifacts := infra / "tool-artifacts"
justfiles := infra / "justfiles"

# public: print the wiring contract for putting a Python project on this QC
setup:
	@echo "Python QC wiring contract (what _check-python-project enforces):"
	@echo ""
	@echo "1. Delegate the project justfile to this file:"
	@echo "     test:"
	@echo "         @just -f ~/ai-review-ci/justfiles/python.just -d . test"
	@echo "     test-ci:"
	@echo "         @just -f ~/ai-review-ci/justfiles/python.just -d . test-ci"
	@echo ""
	@echo "2. Provide a pyproject.toml with requires-python = \">=3.14\"."
	@echo "   QC installs the project editable for mypy and pytest."
	@echo ""
	@echo "3. Do NOT add local QC tool configs — ruff/mypy/coverage/deptry/"
	@echo "   vulture/import-linter sections in pyproject.toml, or standalone"
	@echo "   files (ruff.toml, mypy.ini, .coveragerc, ...). Global QC owns"
	@echo "   these; the preflight rejects local overrides."
	@echo ""
	@echo "4. Tests must exist (test_*.py / *_test.py / tests/*.py)."
	@echo ""
	@echo "5. Gates: pre-commit hook runs 'just test' (syntax, mypy, pytest);"
	@echo "   pre-push runs 'just test-ci' (adds style/slop/coverage stack)."
	@echo "   Run 'just test' locally first — every failure prints its own fix."
	@echo ""
	@echo "Sage projects: use sage.just instead ('just -f ~/ai-review-ci/justfiles/sage.just setup')."

# private recipes (prefix with _ — never run individually)
_python-qc-files:
	#!/usr/bin/env bash
	set -euo pipefail
	exclude_args=()
	while IFS= read -r dir; do
		exclude_args+=(-g "!**/$dir/**")
	done < <(uv run {{artifacts}}/scripts/read_qc_excludes.py {{configs}}/qc-excludes.toml)
	rg --files \
		-g '*.py' \
		-g '!*.sage.py' \
		-g '!tool-artifacts/vulture_whitelist.py' \
		"${exclude_args[@]}"

_python-syntax:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: Python syntax validation ==="
	echo "# Compiles Python source with the configured target interpreter before linting or analysis"
	if ! mapfile -t python_files < <(just --justfile {{justfile()}} -d . _python-qc-files 2>/dev/null); then :; fi
	if [ "${#python_files[@]}" -eq 0 ]; then
		echo "ERROR: Python syntax validation: no Python files found in a Python project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	uv run --python 3.14 --no-project python - "${python_files[@]}" <<'PY'
	import sys
	import tokenize
	import warnings

	warnings.simplefilter("error", SyntaxWarning)
	failed = False
	for file_name in sys.argv[1:]:
	    try:
	        with tokenize.open(file_name) as source_file:
	            source = source_file.read()
	        compile(source, file_name, "exec", dont_inherit=True)
	    except SyntaxError as exc:
	        line = exc.lineno or 0
	        column = exc.offset or 0
	        print(f"ERROR: Python syntax validation failed for {file_name}:{line}:{column}: {exc.msg}", file=sys.stderr)
	        if exc.text:
	            print(exc.text.rstrip(), file=sys.stderr)
	            if column > 0:
	                print(f"{' ' * (column - 1)}^", file=sys.stderr)
	        failed = True
	    except (OSError, UnicodeError) as exc:
	        print(f"ERROR: Python syntax validation could not read {file_name}: {exc}", file=sys.stderr)
	        failed = True

	raise SystemExit(1 if failed else 0)
	PY

_venv:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: uvx/npx tool runners setup ==="
	echo "# Provides access to ruff, coverage, semgrep, and other Python/JS tools via uvx/npx without local installation"

_install-tools: _venv
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: tool installation ==="
	echo "# Installs Python/JS tool dependencies to local cache for faster subsequent runs"

_normalize-common:
	#!/usr/bin/env bash
	set -euo pipefail
	just -f {{justfiles}}/shared.just -d . _normalize-common

_doctor-preflight:
	#!/usr/bin/env bash
	set -euo pipefail
	uv run --project {{infra}} ai-review-ci doctor-preflight --target .

_mypy: _install-tools
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: mypy type checking ==="
	echo "# Checks static typing after syntax validation and before lint/style normalization"
	python_files_output="$(just --justfile {{justfile()}} -d . _python-qc-files)"
	python_files=()
	if [ -n "$python_files_output" ]; then
		mapfile -t python_files <<<"$python_files_output"
	fi
	if [ "${#python_files[@]}" -eq 0 ]; then
		echo "ERROR: mypy: no Python files found in a Python project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	effective_config="{{configs}}/mypy-global.ini"
	with_args=(--with-editable .)
	dependency_requirements_output="$(uv run --no-project python "{{artifacts}}/scripts/python_qc_metadata.py" dependency-group-requirements .)"
	if [ -n "$dependency_requirements_output" ]; then
		mapfile -t dependency_requirements <<<"$dependency_requirements_output"
		for requirement in "${dependency_requirements[@]}"; do
			with_args+=(--with "$requirement")
		done
	fi
	pep723_requirements_output="$(uv run --no-project python "{{artifacts}}/scripts/python_qc_metadata.py" pep723-requirements "${python_files[@]}")"
	if [ -n "$pep723_requirements_output" ]; then
		mapfile -t pep723_requirements <<<"$pep723_requirements_output"
		for requirement in "${pep723_requirements[@]}"; do
			with_args+=(--with "$requirement")
		done
	fi
	if uvx --python 3.14 --from mypy \
		"${with_args[@]}" \
		mypy \
		--config-file "$effective_config" \
		"${python_files[@]}"; then
		:
	else
		ec=$?
		echo "ERROR: mypy found type errors in project code."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi

_check-python-project:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: Python project preflight check ==="
	echo "# Validates project structure, Python version target, test presence, and QC config isolation"
	failed=0
	# 1. pyproject.toml must exist
	if [ ! -f "pyproject.toml" ]; then
		echo "ERROR: Python project must have a pyproject.toml file."
		failed=1
	else
		# 2. must target Python >=3.14
		if ! grep -qP 'requires-python\s*=\s*"[^"]*3\.14' pyproject.toml 2>/dev/null; then
			echo "ERROR: pyproject.toml must target Python >=3.14 (requires-python string)."
			echo "       Add: requires-python = \">=3.14\""
			failed=1
		fi
		# 3. Check for local QC tool overrides in pyproject.toml sections.
		#    These tools' configs are owned by global QC — projects must not set them locally.
		for section in \
			'\[tool\.ruff' \
			'\[tool\.mypy' \
			'\[tool\.coverage' \
			'\[tool\.deptry' \
			'\[tool\.vulture' \
			'\[tool\.import-linter' \
			'\[tool\.importlinter'; do
			if grep -qP "$section" pyproject.toml 2>/dev/null; then
				echo "ERROR: pyproject.toml contains section matching '$section' — global QC owns this tool config."
				echo "       DELETE this section from pyproject.toml. The global config for this tool"
				echo "       already exists in ~/ai-review-ci/ and is authoritative for all projects."
				echo "       Do NOT copy the section contents to ~/ai-review-ci/ — that violates"
				echo "       QC isolation policy. If the global config needs to change, contact"
				echo "       the QC owner (dzack) to update it centrally."
				failed=1
			fi
		done
	fi
	# 4. Check for standalone Python tool config files (also QC overrides)
	for config in ruff.toml .ruff.toml mypy.ini .mypy.ini grain.toml .coveragerc .importlinter; do
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
	# 5. Tests must exist
	if ! rg --files -g 'test_*.py' -g '*_test.py' -g 'tests/*.py' -g '!*.sage.py' >/dev/null 2>&1; then
		echo "ERROR: Python project must have tests. No test files found with patterns: test_*.py, *_test.py, tests/*.py"
		"{{artifacts}}/scripts/emit-test-writing-directive.sh"
		exit 1
	fi
	if [ "$failed" -ne 0 ]; then
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	echo "Python project configuration OK"

_normalize: _install-tools
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: ruff format and check (auto-fix) ==="
	echo "# Enforces PEP 8 style + auto-fixes common issues (import sorting, unused imports, pyupgrade patterns)"
	if ! mapfile -t python_files < <(just --justfile {{justfile()}} -d . _python-qc-files 2>/dev/null); then :; fi
	if [ "${#python_files[@]}" -eq 0 ]; then
		echo "ERROR: ruff normalization: no Python files found in a Python project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	if ! uvx --from ruff ruff check --fix \
		--config {{configs}}/ruff-global.toml \
		"${python_files[@]}"; then
		ec=$?
		echo "ERROR: ruff check found issues in project code."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi
	if ! uvx --from ruff ruff format \
		--config {{configs}}/ruff-global.toml \
		"${python_files[@]}"; then
		ec=$?
		echo "ERROR: ruff format found issues in project code."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi

_pytest: _install-tools
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: pytest (commit tier — no coverage gate) ==="
	echo "# Runs the project's own test suite; must pass. Coverage thresholds are enforced at push (test-ci)."
	if ! rg --files tests -g 'test_*.py' -g '*_test.py' -g '!*.sage.py' >/dev/null 2>&1; then
		echo "ERROR: pytest: no test files found in a Python project."
		"{{artifacts}}/scripts/emit-test-writing-directive.sh"
		exit 1
	fi
	if [ ! -f pyproject.toml ]; then
		echo "ERROR: pytest: no pyproject.toml found — cannot install project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	with_args=(--with-editable .)
	dependency_requirements_output="$(uv run --no-project python "{{artifacts}}/scripts/python_qc_metadata.py" dependency-group-requirements .)"
	if [ -n "$dependency_requirements_output" ]; then
		mapfile -t dependency_requirements <<<"$dependency_requirements_output"
		for requirement in "${dependency_requirements[@]}"; do
			with_args+=(--with "$requirement")
		done
	fi
	if uvx --python 3.14 --from pytest "${with_args[@]}" pytest; then
		:
	else
		ec=$?
		echo "ERROR: pytest failed."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi

_pytest_with_coverage: _install-tools
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: pytest with coverage measurement ==="
	echo "# Runs pytest with coverage.py and generates coverage.xml for diff-cover"
	if ! rg --files tests -g 'test_*.py' -g '*_test.py' -g '!*.sage.py' >/dev/null 2>&1; then
		echo "ERROR: pytest/coverage: no test files found in a Python project."
		"{{artifacts}}/scripts/emit-test-writing-directive.sh"
		exit 1
	fi
	if [ ! -f pyproject.toml ]; then
		echo "ERROR: pytest/coverage: no pyproject.toml found — cannot install project or measure coverage."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	project_root="$(pwd -P)"
	project_slug="$(printf '%s' "$project_root" | sed 's#[^A-Za-z0-9._-]#_#g')"
	coverage_root="${XDG_CACHE_HOME:-$HOME/.cache}/quality-control/coverage/$project_slug"
	coverage_data="$coverage_root/.coverage"
	coverage_xml="$coverage_root/coverage.xml"
	coverage_config="{{configs}}/coverage.ini"
	mkdir -p "$coverage_root"
	export COVERAGE_FILE="$coverage_data"
	export COVERAGE_RCFILE="$coverage_config"
	with_args=(--with pytest --with-editable .)
	dependency_requirements_output="$(uv run --no-project python "{{artifacts}}/scripts/python_qc_metadata.py" dependency-group-requirements .)"
	if [ -n "$dependency_requirements_output" ]; then
		mapfile -t dependency_requirements <<<"$dependency_requirements_output"
		for requirement in "${dependency_requirements[@]}"; do
			with_args+=(--with "$requirement")
		done
	fi
	if uvx --python 3.14 --from coverage "${with_args[@]}" coverage run -m pytest; then
		:
	else
		ec=$?
		echo "ERROR: pytest failed."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi
	if uvx --python 3.14 --from coverage coverage xml -o "$coverage_xml"; then
		:
	else
		ec=$?
		echo "ERROR: coverage XML generation failed."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi
	echo "Coverage XML report: $coverage_xml"

_diff-cover: _pytest_with_coverage
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: diff-cover against main branch ==="
	echo "# Reports coverage gaps on code changed since main branch to ensure new code is tested"
	project_root="$(pwd -P)"
	project_slug="$(printf '%s' "$project_root" | sed 's#[^A-Za-z0-9._-]#_#g')"
	coverage_xml="${XDG_CACHE_HOME:-$HOME/.cache}/quality-control/coverage/$project_slug/coverage.xml"
	if [ ! -f "$coverage_xml" ]; then
		echo "ERROR: diff-cover: no coverage.xml at $coverage_xml — coverage step did not produce output."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	if uvx --from diff-cover diff-cover "$coverage_xml" --compare-branch ${DIFF_COVER_BASE:-main}; then
		:
	else
		ec=$?
		echo "ERROR: diff-cover found coverage gaps in changed code."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi

_vulture: _install-tools
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: vulture dead code detection ==="
	echo "# Finds unused code (functions, classes, variables) that can be safely removed"
	if ! mapfile -t python_files < <(just --justfile {{justfile()}} -d . _python-qc-files 2>/dev/null); then :; fi
	whitelist_file="{{artifacts}}/vulture_whitelist.py"
	if [ "${#python_files[@]}" -eq 0 ]; then
		echo "ERROR: vulture: no Python files found in a Python project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi

	if uvx --from vulture vulture \
		--config {{configs}}/pyproject.toml \
		"${python_files[@]}" \
		"$whitelist_file"; then
		:
	else
		ec=$?
		echo "ERROR: vulture found dead code in project code."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi

_deptry: _install-tools
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: deptry import dependency linting ==="
	echo "# Checks for missing/import dependency failures in pyproject.toml; unused declared dependencies are maintenance-only and do not block global QC"
	if [ ! -f pyproject.toml ]; then
		echo "ERROR: deptry: no pyproject.toml found — Python project must have one."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	python_files_output="$(just --justfile {{justfile()}} -d . _python-qc-files)"
	python_files=()
	if [ -n "$python_files_output" ]; then
		mapfile -t python_files <<<"$python_files_output"
	fi
	package_module_name_map="$(uv run --no-project python "{{artifacts}}/scripts/deptry_package_module_name_map.py" "{{configs}}/pyproject.toml")"
	# DEP001 sage/fpylll: provided by the Sage interpreter environment, not pip
	# dependency definitions (sage.just wiring contract runs projects under
	# SAGE_BIN; fpylll ships inside the Sage distribution — extend on first use).
	# Harmless for pure-Python repos, which do not import them.
	deptry_args=(. --package-module-name-map "$package_module_name_map" --ignore DEP002 --per-rule-ignores "DEP001=sage|fpylll")
	# qc-excludes.toml is the single source of truth for never-scanned
	# directories; deptry takes path regexes, so literal dots are escaped
	# and glob stars widen to `.*`.
	while IFS= read -r exclude_dir; do
		exclude_regex="${exclude_dir//./\\.}"
		deptry_args+=(--extend-exclude "(^|.*/)${exclude_regex//\*/.*}")
	done < <(uv run --no-project python "{{artifacts}}/scripts/read_qc_excludes.py" "{{configs}}/qc-excludes.toml")
	first_party_modules_output="$(uv run --no-project python "{{artifacts}}/scripts/python_qc_metadata.py" first-party-modules .)"
	if [ -n "$first_party_modules_output" ]; then
		mapfile -t first_party_modules <<<"$first_party_modules_output"
		for first_party_module in "${first_party_modules[@]}"; do
			deptry_args+=(--known-first-party "$first_party_module")
		done
	fi
	pep723_scripts_output="$(uv run --no-project python "{{artifacts}}/scripts/python_qc_metadata.py" pep723-scripts "${python_files[@]}")"
	if [ -n "$pep723_scripts_output" ]; then
		mapfile -t pep723_scripts <<<"$pep723_scripts_output"
		for script in "${pep723_scripts[@]}"; do
			deptry_args+=(--extend-exclude "$script")
		done
	fi
	if uvx --from deptry deptry "${deptry_args[@]}"; then
		:
	else
		ec=$?
		echo "ERROR: deptry found missing/import dependency issues in project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi

_ast-grep: _install-tools
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: ast-grep code quality audit ==="
	echo "# Custom AST rules for fraud detection (boolean assignment, loops without asserts, numeric bounds, self-reinforcing prints)"
	if ! mapfile -t python_files < <(just --justfile {{justfile()}} -d . _python-qc-files 2>/dev/null); then :; fi
	if [ "${#python_files[@]}" -eq 0 ]; then
		echo "ERROR: ast-grep: no Python files found in a Python project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	findings_file=$(mktemp)
	trap 'if [ -e "$findings_file" ]; then rm -f "$findings_file"; fi' EXIT
	npx -y --package @ast-grep/cli ast-grep scan \
		--config {{configs}}/sgconfig.yml \
		--report-style short \
		"${python_files[@]}" | tee "$findings_file"
	# Fail on error-severity findings. Every central rule routes to a POLICY.*
	# code and thence to a remediation (enforced in tests/test_policy_index.py);
	# there are no non-policy rules. A bridge-burning policy BANS its pattern
	# rather than emitting an ignorable warning, so every rule is error-tier and
	# blocks here — `error[` matches all of them.
	if grep -q "error\[" "$findings_file"; then
		echo "Blocking just test: error-severity findings must be resolved against repository audit guidelines."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi

_jscpd-python:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: jscpd copy-paste detection ==="
	echo "# Finds duplicate code blocks across the codebase that may indicate copypaste or missing refactoring"
	if ! mapfile -t python_files < <(just --justfile {{justfile()}} -d . _python-qc-files 2>/dev/null); then :; fi
	if [ "${#python_files[@]}" -eq 0 ]; then
		echo "ERROR: jscpd: no Python files found in a Python project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	if ! npx -y jscpd \
		--config {{configs}}/jscpd.json \
		--format python \
		"${python_files[@]}"; then
		ec=$?
		echo "ERROR: jscpd found code duplication in project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi

# ccn: cyclomatic-complexity threshold. Sage projects pass 15 (lizard's own
# default): mathematical case analysis (axiom stratification, decision
# procedures) is irreducibly branchy; 7 stays the pure-Python default.
_lizard-python ccn="7": _install-tools
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: lizard complexity analysis ==="
	echo "# Computes cyclomatic complexity number (CCN) and line count to flag overly complex functions"
	if ! mapfile -t python_files < <(just --justfile {{justfile()}} -d . _python-qc-files 2>/dev/null); then :; fi
	if [ "${#python_files[@]}" -eq 0 ]; then
		echo "ERROR: lizard: no Python files found in a Python project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	# lexicon subtrees are declared Sage reflection boundaries; their stub
	# verifiers are recursive AST dispatch (dev tooling), not product code.
	# Filter the array: lizard -x does not apply to explicitly passed files.
	scan_files=()
	for python_file in "${python_files[@]}"; do
		case "$python_file" in */lexicon/*|lexicon/*) continue ;; esac
		scan_files+=("$python_file")
	done
	if [ "${#scan_files[@]}" -eq 0 ]; then
		echo "# lizard: all Python files are lexicon boundary files; nothing to scan"
	elif uvx --from lizard lizard -l python -C {{ccn}} -L 100 -i 0 -W "{{configs}}/lizard-whitelist.txt" "${scan_files[@]}"; then
		:
	else
		ec=$?
		echo "ERROR: lizard found excessive complexity in project code."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi

_import-linter: _install-tools
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: import-linter dependency rules ==="
	echo "# Enforces layer-based import rules (e.g., core cannot import from plugins, data cannot import from domain)"
	config="$(mktemp "${TMPDIR:-/tmp}/ai-review-ci-importlinter.XXXXXX.toml")"
	trap 'rm -f "$config"' EXIT
	if uv run --no-project python "{{artifacts}}/scripts/python_qc_metadata.py" import-linter-config . > "$config"; then
		:
	else
		ec=$?
		if [ "$ec" -eq 3 ]; then
			echo "import-linter: skipped — no first-party packages (single-file modules only; #249)."
			exit 0
		fi
		echo "ERROR: import-linter could not build the central config for this project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	if uvx --python 3.14 --from import-linter --with-editable . lint-imports --config "$config"; then
		:
	else
		ec=$?
		echo "ERROR: import-linter found import rule violations in project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi

_grain:
	#!/usr/bin/env bash
	set -euo pipefail
	# Strip git env vars the pre-commit hook inherits from `git commit`; left
	# set, they redirect uvx's git-sourced tool fetch (grain) at the host
	# project's .git and it fails with "Git operation failed".
	unset GIT_DIR GIT_INDEX_FILE GIT_WORK_TREE GIT_PREFIX GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR
	echo "============================="
	echo "=== Running: grain unused code detection ==="
	echo "# Finds unused imports and variables that can be safely removed"
	cp {{configs}}/grain.toml .grain.toml
	if uvx --from git+https://github.com/mmartoccia/grain grain check --all; then
		:
	else
		ec=$?
		[ -e .grain.toml ] && rm -f -- .grain.toml
		echo "ERROR: grain found unused code in project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi
	[ -e .grain.toml ] && rm -f -- .grain.toml

_codeql:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: codeql security analysis ==="
	echo "# GitHub's static analysis engine for code quality and security vulnerabilities"
	project_root="$(pwd -P)"
	project_slug="$(printf '%s' "$project_root" | sed 's#[^A-Za-z0-9._-]#_#g')"
	codeql_root="${XDG_CACHE_HOME:-$HOME/.cache}/quality-control/codeql/$project_slug"
	db="$codeql_root/codeql-db"
	report="$codeql_root/codeql-report.sarif"
	mkdir -p "$codeql_root"
	if codeql database create "$db" --overwrite --language=python --source-root="$project_root"; then
		:
	else
		ec=$?
		echo "ERROR: CodeQL database creation failed."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi
	if codeql database analyze "$db" --format=sarif-latest --output="$report"; then
		:
	else
		ec=$?
		echo "ERROR: CodeQL analysis failed."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi
	echo "CodeQL SARIF report: $report"
	python3 - "$report" <<'PY'
	import json
	import sys
	from pathlib import Path

	report = Path(sys.argv[1])
	if not report.exists():
		print(f"CodeQL summary unavailable: report not found at {report}")
		raise SystemExit(0)

	data = json.loads(report.read_text())
	rule_levels = {}
	for run in data.get("runs", []):
		for rule in run.get("tool", {}).get("driver", {}).get("rules", []):
			level = rule.get("defaultConfiguration", {}).get("level")
			if level:
				rule_levels[rule.get("id")] = level

	findings = []
	for run in data.get("runs", []):
		for result in run.get("results", []):
			rule_id = result.get("ruleId", "unknown-rule")
			level = result.get("level") or rule_levels.get(rule_id, "note")
			message = result.get("message", {}).get("text", "").replace("\n", " ").strip()
			location = result.get("locations", [{}])[0].get("physicalLocation", {})
			artifact = location.get("artifactLocation", {})
			uri = artifact.get("uri", "unknown-file")
			region = location.get("region", {})
			line = region.get("startLine")
			file_ref = f"{uri}:{line}" if line else uri
			findings.append((level, rule_id, file_ref, message))

	print(f"CodeQL findings: {len(findings)}")
	for level, rule_id, file_ref, message in findings[:50]:
		print(f"- [{level}] {rule_id} {file_ref}: {message}")
	if len(findings) > 50:
		print(f"- ... {len(findings) - 50} more findings omitted; see SARIF report above.")
	PY

# public: COMMIT gate — correctness + normalization, plus bypass detection
test: _doctor-preflight _check-python-project _normalize-common _normalize _python-syntax _mypy _pytest
	#!/usr/bin/env bash
	set -euo pipefail
	just -f {{justfiles}}/shared.just -d . _no-bypass
	echo "Commit-tier quality checks completed"

# private: ambient broad-debt audit — not push-blocking for unrelated diffs
_ambient-python-debt: _lizard-python _vulture _grain

# public: PUSH/CI gate — test + changed-line coverage and deterministic project gates
test-ci: test _pytest_with_coverage _diff-cover _deptry _import-linter _ast-grep _jscpd-python
	#!/usr/bin/env bash
	set -euo pipefail
	just -f {{justfiles}}/shared.just -d . _global-qc
	echo "Push/CI quality checks completed"
