#!/usr/bin/env bash
set -euo pipefail

read_excludes_script="$1"
excludes_config="$2"
shift 2
if [ "${1:-}" != "--" ]; then
	echo "ERROR: semgrep-with-qc-ignores.sh expects -- before the semgrep argv" >&2
	exit 2
fi
shift

ignore_file=".semgrepignore"
had_preexisting=0
ignore_backup=""
if [ -e "$ignore_file" ]; then
	had_preexisting=1
	if ! ignore_backup="$(mktemp)" || ! cp "$ignore_file" "$ignore_backup"; then
		echo "ERROR: failed to back up the existing $ignore_file; aborting before the QC exclude set overwrites it." >&2
		exit 1
	fi
fi

restore_semgrepignore() {
	if [ "$had_preexisting" -eq 1 ]; then
		mv -f "$ignore_backup" "$ignore_file"
	else
		rm -f "$ignore_file"
	fi
}
trap restore_semgrepignore EXIT

uv run "$read_excludes_script" "$excludes_config" >"$ignore_file"
printf '%s\n' '*.html' '**/*.html' '.pnp.cjs' '.pnp.loader.mjs' >>"$ignore_file"

"$@"
