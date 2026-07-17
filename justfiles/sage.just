# justfile-sage — SageMath-specific quality control
#
# Imports shared and Python QC recipes and adds Sage-specific checks.
# Sage projects delegate to this file:
#   just -f ~/ai-review-ci/justfiles/sage.just -d . test-commit
#
# Shared + Python recipes (imported transitively via justfile-python):
#   All cross-language (justfile) and Python (justfile-python) recipes.
#
# Sage-specific recipes:
#   _sage-qc-files, _sage-syntax, _vulture, _sage-ast-grep (Sage-aware preparse)
#
# WORKFLOW (three-tier):
#   just test-commit — Sage/Python syntax, normalization, mypy, bypass check.
#   just test-push   — commit checks plus the full Sage test suite.
#   just test-ci     — push checks plus coverage and policy-sensitive gates.

infra := justfile_directory() / ".."
configs := infra / "tool-configs"
artifacts := infra / "tool-artifacts"
justfiles := infra / "justfiles"

default:
	@just test-commit

# public: print the wiring contract for putting a Sage project on this QC
setup:
	@echo "Sage QC wiring contract (what _sage-preflight enforces):"
	@echo ""
	@echo "1. Delegate the project justfile to this file:"
	@echo "     test-commit:"
	@echo "         @just -f ~/ai-review-ci/justfiles/sage.just -d . test-commit"
	@echo "     test-push:"
	@echo "         @just -f ~/ai-review-ci/justfiles/sage.just -d . test-push"
	@echo "     test-ci:"
	@echo "         @just -f ~/ai-review-ci/justfiles/sage.just -d . test-ci"
	@echo ""
	@echo "2. Export the Sage executable from a tracked .envrc (path, not a secret):"
	@echo "     export SAGE_BIN=\"\${SAGE_BIN:-\$(command -v sage)}\""
	@echo "   then: direnv allow"
	@echo ""
	@echo "3. Provide a pyproject.toml (mypy installs the project editable):"
	@echo "     [project]"
	@echo "     name = \"<project-name>\""
	@echo "     version = \"0.0.1\""
	@echo "     requires-python = \">=3.14\""
	@echo ""
	@echo "4. Write tests as .sage files (test_*.sage / *_test.sage) so the"
	@echo "   preparser converts integer literals to Sage Integer/Rational."
	@echo "   NEVER commit generated *.sage.py preparse artifacts; add"
	@echo "   '*.sage.py' to .gitignore. QC preparses into a tempdir itself."
	@echo ""
	@echo "5. Tests run under the Sage interpreter's own Python. It needs pytest:"
	@echo "     \"\$SAGE_BIN\" -pip install pytest"
	@echo "   The package must be importable there (PYTHONPATH via .envrc, or"
	@echo "   installed into Sage's python)."
	@echo ""
	@echo "6. Gates: pre-commit runs 'just test-commit' (syntax and mypy);"
	@echo "   pre-push runs 'just test-push' (adds Sage tests); CI runs 'just test-ci'."
	@echo "   Commit/push failures are direct repair; CI policy findings are triaged."

_sage-qc-files:
	#!/usr/bin/env bash
	set -euo pipefail
	exclude_dirs_output="$(uv run {{artifacts}}/scripts/read_qc_excludes.py {{configs}}/qc-excludes.toml)"
	exclude_dirs=()
	if [ -n "$exclude_dirs_output" ]; then
		mapfile -t exclude_dirs <<<"$exclude_dirs_output"
	fi
	exclude_args=()
	for dir in "${exclude_dirs[@]}"; do
		exclude_args+=(-g "!**/$dir/**")
	done
	rg --files \
		-g '*.sage' \
		-g '!*.sage.py' \
		"${exclude_args[@]}"

_sage-vulture-files:
	#!/usr/bin/env bash
	set -euo pipefail
	if ! mapfile -t sage_files < <(just --justfile {{justfile()}} -d . _sage-qc-files 2>/dev/null); then :; fi
	for sage_file in "${sage_files[@]}"; do
		case "$sage_file" in
			scripts/*|*/scripts/*) continue ;;
		esac
		printf '%s\n' "$sage_file"
	done

_sage-test-files:
	#!/usr/bin/env bash
	set -euo pipefail
	sage_files_output="$(just --justfile {{justfile()}} -d . _sage-qc-files)"
	sage_files=()
	if [ -n "$sage_files_output" ]; then
		mapfile -t sage_files <<<"$sage_files_output"
	fi
	for sage_file in "${sage_files[@]}"; do
		case "${sage_file##*/}" in
			test_*.sage|*_test.sage) printf '%s\n' "$sage_file" ;;
		esac
	done

_sage-python-test-files:
	#!/usr/bin/env bash
	set -euo pipefail
	python_files_output="$(just -f {{justfiles}}/python.just -d . _python-qc-files)"
	python_files=()
	if [ -n "$python_files_output" ]; then
		mapfile -t python_files <<<"$python_files_output"
	fi
	for python_file in "${python_files[@]}"; do
		case "$python_file" in
			tests/test_*.py|tests/*_test.py|tests/*/test_*.py|tests/*/*_test.py) printf '%s\n' "$python_file" ;;
		esac
	done

# Wiring preflight: every failure prints the exact remediation so a
# misconfigured repo converges to correct QC wiring instead of guessing.
_sage-preflight:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: Sage QC wiring preflight ==="
	echo "# Validates SAGE_BIN, pyproject.toml, and absence of committed preparse artifacts"
	failed=0
	if [ "${SAGE_BIN+x}" != x ] || [ ! -x "${SAGE_BIN:-}" ]; then
		echo "ERROR: SAGE_BIN is unset or not executable (current: '${SAGE_BIN:-<unset>}')."
		echo "       FIX: export it from the repo's tracked .envrc (it is a path, not a secret):"
		echo "         export SAGE_BIN=\"\${SAGE_BIN:-\$(command -v sage)}\""
		echo "       then run: direnv allow"
		failed=1
	fi
	if [ ! -f pyproject.toml ]; then
		echo "ERROR: no pyproject.toml in the Sage project root ($(pwd -P))."
		echo "       QC installs the project editable for mypy/pytest. FIX: create a minimal one:"
		echo "         [project]"
		echo "         name = \"<project-name>\""
		echo "         version = \"0.0.1\""
		echo "         requires-python = \">=3.14\""
		failed=1
	fi
	tracked_generated="$(git ls-files -- '*.sage.py' 2>/dev/null || true)"
	if [ -n "$tracked_generated" ]; then
		echo "ERROR: git-tracked *.sage.py preparse artifacts found. These are generated from"
		echo "       .sage sources by 'sage --preparse'; QC preparses into a tempdir itself, so"
		echo "       committed copies are duplicate state that pollutes Python QC."
		echo "       FIX: git rm --cached -- '*.sage.py'  and add '*.sage.py' to .gitignore"
		printf '%s\n' "$tracked_generated" | sed 's/^/         /'
		failed=1
	fi
	if [ "$failed" -ne 0 ]; then
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	echo "Sage QC wiring OK"

_doctor-preflight:
	#!/usr/bin/env bash
	set -euo pipefail
	uv run --project {{infra}} ai-review-ci doctor-preflight --target .

_sage-bin:
	#!/usr/bin/env bash
	set -euo pipefail
	if [ "${SAGE_BIN+x}" != x ]; then
		echo "ERROR: SAGE_BIN must be set to the Sage executable path." >&2
		"{{artifacts}}/scripts/emit-triage-directive.sh" >&2
		exit 1
	fi
	if [ ! -x "$SAGE_BIN" ]; then
		echo "ERROR: configured SAGE_BIN is not executable: $SAGE_BIN" >&2
		"{{artifacts}}/scripts/emit-triage-directive.sh" >&2
		exit 1
	fi
	printf '%s\n' "$SAGE_BIN"

_sage-syntax:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: Sage syntax validation ==="
	echo "# Preparses .sage files and byte-compiles the generated Python to catch syntax errors early"
	sage_files_output="$(just --justfile {{justfile()}} -d . _sage-qc-files)"
	sage_files=()
	if [ -n "$sage_files_output" ]; then
		mapfile -t sage_files <<<"$sage_files_output"
	fi
	if [ "${#sage_files[@]}" -eq 0 ]; then
		echo "ERROR: Sage syntax validation: no .sage files found in a Sage project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi

	sage_bin="$(just --justfile {{justfile()}} -d . _sage-bin)"

	sage_preparse_dir="$(mktemp -d "${TMPDIR:-/tmp}/qc-sage-syntax.XXXXXX")"
	trap 'if [ -e "$sage_preparse_dir" ]; then gio trash "$sage_preparse_dir"; fi' EXIT
	echo "# Preparsing and compiling ${#sage_files[@]} Sage file(s)"
	copied_sage_files=()
	compile_args=()
	failed=0
	for sage_file in "${sage_files[@]}"; do
		target="$sage_preparse_dir/$sage_file"
		mkdir -p "$(dirname "$target")"
		cp "$sage_file" "$target"
		generated_file="$target.py"
		copied_sage_files+=("$sage_file")
		compile_args+=("$sage_file" "$generated_file")
	done

	(
		cd "$sage_preparse_dir"
		"$SAGE_BIN" --preparse "${copied_sage_files[@]}" >/dev/null
	)

	for sage_file in "${sage_files[@]}"; do
		generated_file="$sage_preparse_dir/$sage_file.py"
		if [ ! -f "$generated_file" ]; then
			echo "ERROR: Sage preparse did not produce $generated_file for $sage_file"
			failed=1
		fi
	done
	if [ "$failed" -ne 0 ]; then
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi

	if ! "$SAGE_BIN" -python - "${compile_args[@]}" <<'PY'
	import py_compile
	import sys

	args = sys.argv[1:]
	failed = False
	for index in range(0, len(args), 2):
	    original = args[index]
	    generated = args[index + 1]
	    try:
	        py_compile.compile(generated, doraise=True)
	    except py_compile.PyCompileError as exc:
	        print(exc.msg, file=sys.stderr, end="" if exc.msg.endswith("\n") else "\n")
	        print(f"ERROR: Sage syntax validation failed for {original}", file=sys.stderr)
	        failed = True

	raise SystemExit(1 if failed else 0)
	PY
	then
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi

_normalize-common:
	#!/usr/bin/env bash
	set -euo pipefail
	just -f {{justfiles}}/shared.just -d . _normalize-common

_vulture: _sage-qc-files
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: vulture dead code detection (Sage-aware) ==="
	echo "# Finds unused code in Python and Sage files"
	all_python_files_output="$(just -f {{justfiles}}/python.just -d . _python-qc-files)"
	all_python_files=()
	if [ -n "$all_python_files_output" ]; then
		mapfile -t all_python_files <<<"$all_python_files_output"
	fi
	all_sage_files_output="$(just --justfile {{justfile()}} -d . _sage-qc-files)"
	all_sage_files=()
	if [ -n "$all_sage_files_output" ]; then
		mapfile -t all_sage_files <<<"$all_sage_files_output"
	fi
	python_files_output="$(just -f {{justfiles}}/python.just -d . _python-vulture-files)"
	python_files=()
	if [ -n "$python_files_output" ]; then
		mapfile -t python_files <<<"$python_files_output"
	fi
	sage_files_output="$(just --justfile {{justfile()}} -d . _sage-vulture-files)"
	sage_files=()
	if [ -n "$sage_files_output" ]; then
		mapfile -t sage_files <<<"$sage_files_output"
	fi
	generated_sage_python_files=()
	whitelist_file="{{artifacts}}/vulture_whitelist.py"
	if [ "${#all_python_files[@]}" -eq 0 ] && [ "${#all_sage_files[@]}" -eq 0 ]; then
		echo "ERROR: vulture: no Python or Sage files found in a Sage project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	if [ "${#python_files[@]}" -eq 0 ] && [ "${#sage_files[@]}" -eq 0 ]; then
		echo "# No Python or Sage files eligible for vulture after excluding scripts/."
		exit 0
	fi

	if [ "${#sage_files[@]}" -gt 0 ]; then
		sage_bin="$(just --justfile {{justfile()}} -d . _sage-bin)"

		sage_preparse_dir="$(mktemp -d "${TMPDIR:-/tmp}/qc-vulture-sage.XXXXXX")"
		trap 'if [ -e "$sage_preparse_dir" ]; then gio trash "$sage_preparse_dir"; fi' EXIT
		echo "# Preparsing ${#sage_files[@]} Sage file(s) for vulture"
		copied_sage_files=()
		for sage_file in "${sage_files[@]}"; do
			target="$sage_preparse_dir/$sage_file"
			mkdir -p "$(dirname "$target")"
			cp "$sage_file" "$target"
			copied_sage_files+=("$sage_file")
			generated_sage_python_files+=("$target.py")
		done
		(
			cd "$sage_preparse_dir"
			"$SAGE_BIN" --preparse "${copied_sage_files[@]}" >/dev/null
		)
		for generated_file in "${generated_sage_python_files[@]}"; do
			if [ ! -f "$generated_file" ]; then
				echo "ERROR: Sage preparse did not produce $generated_file"
				"{{artifacts}}/scripts/emit-triage-directive.sh"
				exit 1
			fi
		done
	fi

	uvx --from vulture vulture \
		--config {{configs}}/pyproject.toml \
		"${python_files[@]}" \
		"${generated_sage_python_files[@]}" \
		"$whitelist_file"

_sage-pytest:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: pytest on Sage test files (preparsed) ==="
	echo "# Preparses .sage test files so integer literals become Sage Integer/Rational,"
	echo "# then runs pytest on the generated .py files."
	sage_bin="$(just --justfile {{justfile()}} -d . _sage-bin)"

	# Collect only files owned by this repository; the shared discovery boundary
	# excludes gitlinks and independently initialized nested repositories.
	sage_test_files_output="$(just --justfile {{justfile()}} -d . _sage-test-files)"
	sage_test_files=()
	if [ -n "$sage_test_files_output" ]; then
		mapfile -t sage_test_files <<<"$sage_test_files_output"
	fi
	# Also collect any .py test files (mixed projects).
	py_test_files_output="$(just --justfile {{justfile()}} -d . _sage-python-test-files)"
	py_test_files=()
	if [ -n "$py_test_files_output" ]; then
		mapfile -t py_test_files <<<"$py_test_files_output"
	fi

	if [ "${#sage_test_files[@]}" -eq 0 ] && [ "${#py_test_files[@]}" -eq 0 ]; then
		echo "ERROR: pytest: no test files found (.sage or .py)."
		"{{artifacts}}/scripts/emit-test-writing-directive.sh"
		exit 1
	fi
	# Sage tests can only run under the Sage interpreter: sage.* is not
	# pip-installable into a uvx CPython environment. The project must be
	# importable there (PYTHONPATH via envrc, or installed into Sage's python).
	if ! "$sage_bin" -python -m pytest --version >/dev/null 2>&1; then
		echo "ERROR: pytest is not available in the Sage interpreter's Python."
		echo "       FIX: \"$sage_bin\" -pip install pytest"
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi

	pytest_args=()

	if [ "${#sage_test_files[@]}" -gt 0 ]; then
		sage_preparse_dir="$(mktemp -d "${TMPDIR:-/tmp}/qc-sage-pytest.XXXXXX")"
		trap 'if [ -e "$sage_preparse_dir" ]; then gio trash "$sage_preparse_dir"; fi' EXIT

		echo "# Preparsing ${#sage_test_files[@]} .sage test file(s)"
		for sage_file in "${sage_test_files[@]}"; do
			target="$sage_preparse_dir/$sage_file"
			mkdir -p "$(dirname "$target")"
			cp "$sage_file" "$target"
		done
		(
			cd "$sage_preparse_dir"
			"$sage_bin" --preparse "${sage_test_files[@]}" >/dev/null
		)
		for sage_file in "${sage_test_files[@]}"; do
			generated="$sage_preparse_dir/${sage_file}.py"
			if [ ! -f "$generated" ]; then
				echo "ERROR: sage --preparse did not produce $generated for $sage_file"
				"{{artifacts}}/scripts/emit-triage-directive.sh"
				exit 1
			fi
			# foo.sage.py is not an importable module name for pytest
			# (the extra dot breaks module resolution); strip the .sage.
			importable="${generated%.sage.py}.py"
			mv "$generated" "$importable"
			pytest_args+=("$importable")
		done
	fi

	# Add .py test files directly
	for py_file in "${py_test_files[@]:-}"; do
		[ -n "$py_file" ] && pytest_args+=("$py_file")
	done

	if "$sage_bin" -python -m pytest "${pytest_args[@]}"; then
		:
	else
		ec=$?
		echo "ERROR: pytest failed."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi

_sage-pytest-coverage:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: pytest with coverage under the Sage interpreter ==="
	echo "# Same preparse flow as _sage-pytest, run under coverage.py inside Sage's"
	echo "# Python (uvx CPython cannot import sage.*); emits coverage.xml for diff-cover."
	sage_bin="$(just --justfile {{justfile()}} -d . _sage-bin)"
	sage_test_files_output="$(just --justfile {{justfile()}} -d . _sage-test-files)"
	sage_test_files=()
	if [ -n "$sage_test_files_output" ]; then
		mapfile -t sage_test_files <<<"$sage_test_files_output"
	fi
	py_test_files_output="$(just --justfile {{justfile()}} -d . _sage-python-test-files)"
	py_test_files=()
	if [ -n "$py_test_files_output" ]; then
		mapfile -t py_test_files <<<"$py_test_files_output"
	fi
	if [ "${#sage_test_files[@]}" -eq 0 ] && [ "${#py_test_files[@]}" -eq 0 ]; then
		echo "ERROR: pytest/coverage: no test files found (.sage or .py)."
		"{{artifacts}}/scripts/emit-test-writing-directive.sh"
		exit 1
	fi
	if ! "$sage_bin" -python -m pytest --version >/dev/null 2>&1; then
		echo "ERROR: pytest is not available in the Sage interpreter's Python."
		echo "       FIX: \"$sage_bin\" -pip install pytest"
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	if ! "$sage_bin" -python -m coverage --version >/dev/null 2>&1; then
		echo "ERROR: coverage is not available in the Sage interpreter's Python."
		echo "       FIX: \"$sage_bin\" -pip install coverage"
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	pytest_args=()
	if [ "${#sage_test_files[@]}" -gt 0 ]; then
		sage_preparse_dir="$(mktemp -d "${TMPDIR:-/tmp}/qc-sage-cov.XXXXXX")"
		trap 'if [ -e "$sage_preparse_dir" ]; then gio trash "$sage_preparse_dir"; fi' EXIT
		echo "# Preparsing ${#sage_test_files[@]} .sage test file(s)"
		for sage_file in "${sage_test_files[@]}"; do
			target="$sage_preparse_dir/$sage_file"
			mkdir -p "$(dirname "$target")"
			cp "$sage_file" "$target"
		done
		(
			cd "$sage_preparse_dir"
			"$sage_bin" --preparse "${sage_test_files[@]}" >/dev/null
		)
		for sage_file in "${sage_test_files[@]}"; do
			generated="$sage_preparse_dir/${sage_file}.py"
			if [ ! -f "$generated" ]; then
				echo "ERROR: sage --preparse did not produce $generated for $sage_file"
				"{{artifacts}}/scripts/emit-triage-directive.sh"
				exit 1
			fi
			importable="${generated%.sage.py}.py"
			mv "$generated" "$importable"
			pytest_args+=("$importable")
		done
	fi
	for py_file in "${py_test_files[@]:-}"; do
		[ -n "$py_file" ] && pytest_args+=("$py_file")
	done
	project_root="$(pwd -P)"
	project_slug="$(printf '%s' "$project_root" | sed 's#[^A-Za-z0-9._-]#_#g')"
	coverage_root="${XDG_CACHE_HOME:-$HOME/.cache}/quality-control/coverage/$project_slug"
	mkdir -p "$coverage_root"
	export COVERAGE_FILE="$coverage_root/.coverage"
	export COVERAGE_RCFILE="{{configs}}/coverage-sage.ini"
	if "$sage_bin" -python -m coverage run -m pytest "${pytest_args[@]}"; then
		:
	else
		ec=$?
		echo "ERROR: pytest failed."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi
	if "$sage_bin" -python -m coverage xml -o "$coverage_root/coverage.xml"; then
		:
	else
		ec=$?
		echo "ERROR: coverage XML generation failed."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi
	echo "Coverage XML report: $coverage_root/coverage.xml"

_sage-diff-cover: _sage-pytest-coverage
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: diff-cover against main branch (Sage flavor) ==="
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

# public: COMMIT gate — immediate, directly repairable feedback
test-commit:
	#!/usr/bin/env bash
	set -euo pipefail
	export AI_REVIEW_CI_FAILURE_MODE=direct
	just --justfile {{justfile()}} -d . _doctor-preflight _sage-preflight _normalize-common _sage-syntax
	python_qc_repo="{{justfiles}}/python.just"
	python_qc_recipes=(_normalize _python-syntax _mypy)
	just -f "$python_qc_repo" -d . "${python_qc_recipes[@]}"
	just -f {{justfiles}}/shared.just -d . _no-bypass
	echo "Sage commit quality checks completed"

# public: PUSH gate — commit checks plus the full project-owned test suite
test-push:
	#!/usr/bin/env bash
	set -euo pipefail
	export AI_REVIEW_CI_FAILURE_MODE=direct
	just --justfile {{justfile()}} -d . test-commit _sage-pytest
	echo "Sage push quality checks completed"

_sage-ast-grep:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: ast-grep duck-typing audit (Sage-aware) ==="
	echo "# Bans runtime type introspection (hasattr/getattr/setattr/delattr, type(x) comparisons,"
	echo "# __class__/__dict__ probing). Sage research code must declare the mathematical objects it"
	echo "# expects through the type system, not discover them at runtime."
	python_files_output="$(just -f {{justfiles}}/python.just -d . _python-qc-files)"
	python_files=()
	if [ -n "$python_files_output" ]; then
		mapfile -t python_files <<<"$python_files_output"
	fi
	sage_files_output="$(just --justfile {{justfile()}} -d . _sage-qc-files)"
	sage_files=()
	if [ -n "$sage_files_output" ]; then
		mapfile -t sage_files <<<"$sage_files_output"
	fi
	scan_files=("${python_files[@]}")
	if [ "${#python_files[@]}" -eq 0 ] && [ "${#sage_files[@]}" -eq 0 ]; then
		echo "ERROR: ast-grep duck-typing audit: no Python or Sage files found in a Sage project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi

	if [ "${#sage_files[@]}" -gt 0 ]; then
		sage_bin="$(just --justfile {{justfile()}} -d . _sage-bin)"

		sage_preparse_dir="$(mktemp -d "${TMPDIR:-/tmp}/qc-astgrep-sage.XXXXXX")"
		trap 'if [ -e "$sage_preparse_dir" ]; then gio trash "$sage_preparse_dir"; fi' EXIT
		echo "# Preparsing ${#sage_files[@]} Sage file(s) for ast-grep"
		copied_sage_files=()
		for sage_file in "${sage_files[@]}"; do
			target="$sage_preparse_dir/$sage_file"
			mkdir -p "$(dirname "$target")"
			cp "$sage_file" "$target"
			copied_sage_files+=("$sage_file")
		done
		(
			cd "$sage_preparse_dir"
			"$SAGE_BIN" --preparse "${copied_sage_files[@]}" >/dev/null
		)
		for sage_file in "${sage_files[@]}"; do
			generated_file="$sage_preparse_dir/$sage_file.py"
			if [ ! -f "$generated_file" ]; then
				echo "ERROR: Sage preparse did not produce $generated_file"
				"{{artifacts}}/scripts/emit-triage-directive.sh"
				exit 1
			fi
			scan_files+=("$generated_file")
		done
	fi

	findings_file=$(mktemp)
	trap 'if [ -e "$findings_file" ]; then rm -f "$findings_file"; fi; if [ -e "${sage_preparse_dir:-}" ]; then gio trash "$sage_preparse_dir"; fi' EXIT
	npx -y --package @ast-grep/cli ast-grep scan \
		--config {{configs}}/sage-sgconfig.yml \
		--report-style short \
		"${scan_files[@]}" | tee "$findings_file"
	if [ -s "$findings_file" ]; then
		echo "Blocking just test-ci: POLICY.NO_TYPE_ESCAPE"
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi

# public: CI gate — push checks plus gameable and long-running acceptance gates
test-ci:
	#!/usr/bin/env bash
	set -euo pipefail
	export AI_REVIEW_CI_FAILURE_MODE=triage
	just --justfile {{justfile()}} -d . test-push _vulture _sage-ast-grep
	python_qc_repo="{{justfiles}}/python.just"
	python_qc_recipes=(_deptry _import-linter _ast-grep _jscpd-python _grain)
	just -f "$python_qc_repo" -d . "${python_qc_recipes[@]}"
	# CCN 15 (lizard's own default) for Sage projects: mathematical case
	# analysis is irreducibly branchy; see _lizard-python in python.just.
	just -f "$python_qc_repo" -d . _lizard-python 15
	# Coverage runs under the Sage interpreter (python-flavor coverage cannot
	# import sage.* or see preparsed .sage tests).
	just --justfile {{justfile()}} -d . _sage-diff-cover
	just -f {{justfiles}}/shared.just -d . _global-qc
	echo "Sage CI quality checks completed"
