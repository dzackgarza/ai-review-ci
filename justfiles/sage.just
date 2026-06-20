# justfile-sage — SageMath-specific quality control
#
# Imports shared and Python QC recipes and adds Sage-specific checks.
# Sage projects delegate to this file:
#   just -f ~/ai-review-ci/justfiles/sage.just -d . test
#
# Shared + Python recipes (imported transitively via justfile-python):
#   All cross-language (justfile) and Python (justfile-python) recipes.
#
# Sage-specific recipes:
#   _sage-qc-files, _sage-syntax, _vulture (Sage-aware preparse)
#
# WORKFLOW (two-tier):
#   just test     — COMMIT gate: Sage syntax + Python correctness/normalize
#                   (normalize, syntax, mypy, plain pytest, bypass check).
#   just test-ci  — PUSH/CI gate: test + the full style/slop/coverage stack
#                   (vulture, deptry, import-linter, jscpd, lizard, ast-grep,
#                   grain, coverage + diff-cover, semgrep, vibecheck, ai-slop).

infra := justfile_directory() / ".."
configs := infra / "tool-configs"
artifacts := infra / "tool-artifacts"
justfiles := infra / "justfiles"

default:
	@just test

_sage-qc-files:
	#!/usr/bin/env bash
	set -euo pipefail
	exclude_args=()
	while IFS= read -r dir; do
		exclude_args+=(-g "!**/$dir/**")
	done < <(uv run {{artifacts}}/scripts/read_qc_excludes.py {{configs}}/qc-excludes.toml)
	rg --files \
		-g '*.sage' \
		-g '!*.sage.py' \
		"${exclude_args[@]}"

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
	mapfile -t sage_files < <(just --justfile {{justfile()}} -d . _sage-qc-files)
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
	mapfile -t python_files < <(just -f {{justfiles}}/python.just -d . _python-qc-files)
	mapfile -t sage_files < <(just --justfile {{justfile()}} -d . _sage-qc-files)
	generated_sage_python_files=()
	whitelist_file="{{artifacts}}/vulture_whitelist.py"
	if [ "${#python_files[@]}" -eq 0 ] && [ "${#sage_files[@]}" -eq 0 ]; then
		echo "ERROR: vulture: no Python or Sage files found in a Sage project."
		"{{artifacts}}/scripts/emit-triage-directive.sh"
		exit 1
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

# public: COMMIT gate — Sage syntax + Python correctness/normalization
test: _normalize-common _sage-syntax
	#!/usr/bin/env bash
	set -euo pipefail
	python_qc_repo="{{justfiles}}/python.just"
	python_qc_recipes=(_normalize _python-syntax _mypy _pytest)
	just -f "$python_qc_repo" -d . "${python_qc_recipes[@]}"
	just -f {{justfiles}}/shared.just -d . _no-bypass
	echo "Sage commit-tier quality checks completed"

# public: PUSH/CI gate — test + the full style/slop/coverage stack
test-ci: test _vulture
	#!/usr/bin/env bash
	set -euo pipefail
	python_qc_repo="{{justfiles}}/python.just"
	python_qc_recipes=(_deptry _import-linter _ast-grep _jscpd-python _lizard-python _grain _pytest_with_coverage _diff-cover)
	just -f "$python_qc_repo" -d . "${python_qc_recipes[@]}"
	just -f {{justfiles}}/shared.just -d . _global-qc
	echo "Sage push/CI quality checks completed"
