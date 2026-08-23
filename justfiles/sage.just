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
#   just test-push   — commit checks, the full Sage test suite, and the cheap
#                      deterministic gates (vulture, ast-grep, deptry, grain).
#   just test-ci     — push checks plus the threshold metrics (coverage,
#                      duplication) and the minutes-long import graph.

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
	@echo "     export SAGE_BIN=\"\${SAGE_BIN:-/path/to/sage-venv/bin/sage}\""
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
	@echo "     \"\$(dirname \"\$SAGE_BIN\")/python\" -m pip install pytest"
	@echo "   The package must be importable there (PYTHONPATH via .envrc, or"
	@echo "   installed into Sage's python)."
	@echo ""
	@echo "6. Gates: pre-commit runs 'just test-commit' (syntax and mypy);"
	@echo "   pre-push runs 'just test-push' (adds Sage tests and the cheap"
	@echo "   deterministic gates); CI runs 'just test-ci' (threshold metrics)."
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
	if rg --files \
		-g '*.sage' \
		-g '!*.sage.py' \
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
	# Repo-wide, like _sage-test-files beside it.  This read _python-qc-files,
	# which is diff-scoped by design — right for batching mypy over changed
	# files, wrong for deciding which tests exist.  On a clean tree it returned
	# nothing, so _sage-pytest saw no tests: a Sage project whose suite is all
	# .py ran pytest only when a test file happened to be in the diff, and
	# reported success when it ran nothing at all.
	exclude_dirs_output="$(uv run {{artifacts}}/scripts/read_qc_excludes.py {{configs}}/qc-excludes.toml)"
	exclude_dirs=()
	if [ -n "$exclude_dirs_output" ]; then
		mapfile -t exclude_dirs <<<"$exclude_dirs_output"
	fi
	exclude_args=()
	for dir in "${exclude_dirs[@]}"; do
		exclude_args+=(-g "!**/$dir/**")
	done
	if rg --files \
		-g 'tests/**/test_*.py' \
		-g 'tests/**/*_test.py' \
		-g '!*.sage.py' \
		"${exclude_args[@]}"; then
		:
	else
		status=$?
		[ "$status" -eq 1 ] || exit "$status"
	fi

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
		echo "         export SAGE_BIN=\"\${SAGE_BIN:-/path/to/sage-venv/bin/sage}\""
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
		echo "       .sage sources with the Sage environment's preparser; QC uses a tempdir, so"
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

_sage-python:
	#!/usr/bin/env bash
	set -euo pipefail
	sage_bin="$(just --justfile {{justfile()}} -d . _sage-bin)"
	sage_python="$(dirname "$sage_bin")/python"
	if [ ! -x "$sage_python" ]; then
		echo "ERROR: Sage virtual-environment Python is not executable: $sage_python" >&2
		"{{artifacts}}/scripts/emit-triage-directive.sh" >&2
		exit 1
	fi
	printf '%s\n' "$sage_python"

_sage-preparse-bin:
	#!/usr/bin/env bash
	set -euo pipefail
	sage_bin="$(just --justfile {{justfile()}} -d . _sage-bin)"
	sage_preparse="$(dirname "$sage_bin")/sage-preparse"
	if [ ! -x "$sage_preparse" ]; then
		echo "ERROR: Sage virtual-environment preparser is not executable: $sage_preparse" >&2
		"{{artifacts}}/scripts/emit-triage-directive.sh" >&2
		exit 1
	fi
	printf '%s\n' "$sage_preparse"

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

	sage_python="$(just --justfile {{justfile()}} -d . _sage-python)"
	sage_preparse="$(just --justfile {{justfile()}} -d . _sage-preparse-bin)"

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
		"$sage_python" "$sage_preparse" "${copied_sage_files[@]}" >/dev/null
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

	if ! "$sage_python" - "${compile_args[@]}" <<'PY'
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
	# Whole tree, never the diff. A symbol is dead only if nothing anywhere
	# calls it, so a file subset cannot answer the question: every definition
	# whose callers sit in an unchanged file reads as unused, and the false
	# positives grow as the diff shrinks.
	all_python_files_output="$(QC_TIER=ambient just -f {{justfiles}}/python.just -d . _python-qc-files)"
	all_python_files=()
	if [ -n "$all_python_files_output" ]; then
		mapfile -t all_python_files <<<"$all_python_files_output"
	fi
	all_sage_files_output="$(QC_TIER=ambient just --justfile {{justfile()}} -d . _sage-qc-files)"
	all_sage_files=()
	if [ -n "$all_sage_files_output" ]; then
		mapfile -t all_sage_files <<<"$all_sage_files_output"
	fi
	python_files_output="$(QC_TIER=ambient just -f {{justfiles}}/python.just -d . _python-vulture-files)"
	python_files=()
	if [ -n "$python_files_output" ]; then
		mapfile -t python_files <<<"$python_files_output"
	fi
	sage_files_output="$(QC_TIER=ambient just --justfile {{justfile()}} -d . _sage-vulture-files)"
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
		sage_python="$(just --justfile {{justfile()}} -d . _sage-python)"
		sage_preparse="$(just --justfile {{justfile()}} -d . _sage-preparse-bin)"

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
			"$sage_python" "$sage_preparse" "${copied_sage_files[@]}" >/dev/null
		)
		for generated_file in "${generated_sage_python_files[@]}"; do
			if [ ! -f "$generated_file" ]; then
				echo "ERROR: Sage preparse did not produce $generated_file"
				"{{artifacts}}/scripts/emit-triage-directive.sh"
				exit 1
			fi
		done
	fi

	uvx --python 3.14 --from vulture vulture \
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
	sage_python="$(just --justfile {{justfile()}} -d . _sage-python)"
	sage_preparse="$(just --justfile {{justfile()}} -d . _sage-preparse-bin)"

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
	if ! "$sage_python" -m pytest --version >/dev/null 2>&1; then
		echo "ERROR: pytest is not available in the Sage interpreter's Python."
		echo "       FIX: \"$sage_python\" -m pip install pytest"
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
			"$sage_python" "$sage_preparse" "${sage_test_files[@]}" >/dev/null
		)
		for sage_file in "${sage_test_files[@]}"; do
			generated="$sage_preparse_dir/${sage_file}.py"
			if [ ! -f "$generated" ]; then
				echo "ERROR: Sage preparser did not produce $generated for $sage_file"
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

	# The Sage virtual environment's Python has `sage` importable, but it is not
	# a Sage session: `sage.all` is absent from sys.modules there, while `sage -c`
	# has it. Every way a person runs Sage code goes through that startup
	# import, so a suite run without it is testing an environment no user
	# has -- and cannot exercise anything that depends on startup wiring.
	#
	# `sage -c` cannot carry the arguments (it reads trailing words as more
	# code), so do explicitly what a session does on startup.
	if "$sage_python" -c "import sage.all, sys, pytest; sys.exit(pytest.main(sys.argv[1:]))" "${pytest_args[@]}"; then
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
	sage_python="$(just --justfile {{justfile()}} -d . _sage-python)"
	sage_preparse="$(just --justfile {{justfile()}} -d . _sage-preparse-bin)"
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
	if ! "$sage_python" -m pytest --version >/dev/null 2>&1; then
		echo "ERROR: pytest is not available in the Sage interpreter's Python."
		echo "       FIX: \"$sage_python\" -m pip install pytest"
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
	fi
	if ! "$sage_python" -m coverage --version >/dev/null 2>&1; then
		echo "ERROR: coverage is not available in the Sage interpreter's Python."
		echo "       FIX: \"$sage_python\" -m pip install coverage"
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
			"$sage_python" "$sage_preparse" "${sage_test_files[@]}" >/dev/null
		)
		for sage_file in "${sage_test_files[@]}"; do
			generated="$sage_preparse_dir/${sage_file}.py"
			if [ ! -f "$generated" ]; then
				echo "ERROR: Sage preparser did not produce $generated for $sage_file"
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
	# The tests need sage.all, for the reason spelled out in _sage-pytest.
	# Importing it before `coverage run` would leave every module Sage's
	# startup touches -- the installed preparser among them -- already
	# imported when measurement begins, and reported as uncovered. So
	# coverage starts first and a driver does the startup import inside it.
	coverage_driver="$coverage_root/run-under-sage.py"
	cat >"$coverage_driver" <<'DRIVER'
	import sys

	import sage.all  # noqa: F401  (Sage's startup wiring; see _sage-pytest)
	import pytest

	sys.exit(pytest.main(sys.argv[1:]))
	DRIVER
	if "$sage_python" -m coverage run "$coverage_driver" "${pytest_args[@]}"; then
		:
	else
		ec=$?
		echo "ERROR: pytest failed."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi
	if "$sage_python" -m coverage xml -o "$coverage_root/coverage.xml"; then
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

_sage-mypy: _sage-qc-files
	#!/usr/bin/env bash
	set -euo pipefail
	echo "============================="
	echo "=== Running: mypy static type analysis (Sage-aware) ==="
	echo "# Type checks Python and preparsed Sage files"
	sage_python="$(just --justfile {{justfile()}} -d . _sage-python)"
	export MYPYPATH="{{infra}}/typings${MYPYPATH:+:$MYPYPATH}"
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
	mypy_targets=()
	for pf in "${python_files[@]}"; do
		[ -n "$pf" ] && mypy_targets+=("$pf")
	done
	if [ "${#sage_files[@]}" -gt 0 ]; then
		sage_preparse="$(just --justfile {{justfile()}} -d . _sage-preparse-bin)"
		sage_preparse_dir="$(mktemp -d "${TMPDIR:-/tmp}/qc-mypy-sage.XXXXXX")"
		trap 'if [ -e "$sage_preparse_dir" ]; then gio trash "$sage_preparse_dir"; fi' EXIT
		echo "# Preparsing ${#sage_files[@]} Sage file(s) for mypy"
		# The preparsed modules import each other and the package's plain .py
		# modules, and mypy resolves those imports statically: the tempdir must
		# be one coherent snapshot. Copy every tracked Python source and stub
		# (this also carries a repo's typings/ tree, keeping the config's
		# relative mypy_path resolvable), and rename each preparsed X.sage.py
		# to X.py -- the stem X.sage can never satisfy an import of pkg.X.
		git ls-files -z -- '*.py' '*.pyi' | xargs -0 --no-run-if-empty cp --parents -t "$sage_preparse_dir"
		copied_sage_files=()
		for sage_file in "${sage_files[@]}"; do
			target="$sage_preparse_dir/$sage_file"
			mkdir -p "$(dirname "$target")"
			cp "$sage_file" "$target"
			copied_sage_files+=("$sage_file")
		done
		(
			cd "$sage_preparse_dir"
			"$sage_python" "$sage_preparse" "${copied_sage_files[@]}" >/dev/null
		)
		for sage_file in "${copied_sage_files[@]}"; do
			mv "$sage_preparse_dir/$sage_file.py" "$sage_preparse_dir/${sage_file%.sage}.py"
			mypy_targets+=("${sage_file%.sage}.py")
		done
	fi
	if [ "${#mypy_targets[@]}" -eq 0 ]; then
		echo "mypy: no Python or Sage files to check."
		exit 0
	fi
	effective_config="{{configs}}/mypy-sage.ini"
	mypy_run_dir="."
	mypy_flags=()
	if [ -n "${sage_preparse_dir:-}" ]; then
		# Run from the snapshot so targets and every intra-package import
		# resolve inside it, ahead of the site-packages editable install.
		# The packages are namespace packages, so bases must be explicit.
		mypy_run_dir="$sage_preparse_dir"
		mypy_flags+=(--explicit-package-bases)
		if [ -d "$sage_preparse_dir/src" ]; then
			export MYPYPATH="$sage_preparse_dir/src${MYPYPATH:+:$MYPYPATH}"
		fi
		if [ -d "$sage_preparse_dir/typings" ]; then
			export MYPYPATH="$sage_preparse_dir/typings${MYPYPATH:+:$MYPYPATH}"
		fi
	fi
	if (cd "$mypy_run_dir" && "$sage_python" -m mypy \
		--config-file "$effective_config" \
		"${mypy_flags[@]}" \
		"${mypy_targets[@]}"); then
		:
	else
		ec=$?
		echo "ERROR: mypy found type errors in project code."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit $ec
	fi

# public: COMMIT gate — immediate, directly repairable feedback
test-commit:
	#!/usr/bin/env bash
	set -euo pipefail
	export AI_REVIEW_CI_FAILURE_MODE=direct
	just --justfile {{justfile()}} -d . _doctor-preflight _sage-preflight _normalize-common _sage-syntax _sage-mypy
	python_qc_repo="{{justfiles}}/python.just"
	python_qc_recipes=(_normalize _python-syntax)
	just -f "$python_qc_repo" -d . "${python_qc_recipes[@]}"
	just -f {{justfiles}}/shared.just -d . _no-bypass
	echo "Sage commit quality checks completed"

# public: PUSH gate — commit checks, the project-owned test suite, and the
# deterministic checks a developer can answer without leaving the local loop.
#
# A gate belongs here when it names a specific defect at a specific location and
# costs about a second: the duck-typing audit, banned patterns, missing
# dependencies, dead code and prose rules. Each reports the same verdict locally
# and in CI, so discovering it here costs one edit and discovering it there
# costs a CI round trip.
test-push:
	#!/usr/bin/env bash
	set -euo pipefail
	export AI_REVIEW_CI_FAILURE_MODE=direct
	just --justfile {{justfile()}} -d . test-commit _sage-pytest _vulture _sage-ast-grep
	just -f {{justfiles}}/python.just -d . _deptry _ast-grep _grain
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
		sage_python="$(just --justfile {{justfile()}} -d . _sage-python)"
		sage_preparse="$(just --justfile {{justfile()}} -d . _sage-preparse-bin)"

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
			"$sage_python" "$sage_preparse" "${copied_sage_files[@]}" >/dev/null
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
#
# What remains here earns it on one of two counts. Coverage, duplication and
# complexity are threshold metrics: run them in the local loop and they become
# a number to golf rather than a defect to fix. `_import-linter` builds the
# whole import graph and takes minutes, which no push gate can carry.
test-ci:
	#!/usr/bin/env bash
	set -euo pipefail
	export AI_REVIEW_CI_FAILURE_MODE=triage
	just --justfile {{justfile()}} -d . test-push
	python_qc_repo="{{justfiles}}/python.just"
	python_qc_recipes=(_import-linter _jscpd-python)
	just -f "$python_qc_repo" -d . "${python_qc_recipes[@]}"
	# CCN 15 (lizard's own default) for Sage projects: mathematical case
	# analysis is irreducibly branchy; see _lizard-python in python.just.
	just -f "$python_qc_repo" -d . _lizard-python 15
	# Coverage runs under the Sage interpreter (python-flavor coverage cannot
	# import sage.* or see preparsed .sage tests).
	just --justfile {{justfile()}} -d . _sage-diff-cover
	just -f {{justfiles}}/shared.just -d . _global-qc
	echo "Sage CI quality checks completed"
