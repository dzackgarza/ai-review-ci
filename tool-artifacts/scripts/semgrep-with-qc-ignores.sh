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

exec {ignore_lock}<.
flock -x "$ignore_lock"

ignore_file=".semgrepignore"
had_preexisting=0
backup_dir=""
if [ -e "$ignore_file" ] || [ -L "$ignore_file" ]; then
	if [ ! -f "$ignore_file" ] && [ ! -L "$ignore_file" ]; then
		echo "ERROR: $ignore_file is not a regular file or symlink; original is untouched." >&2
		exit 1
	fi
	had_preexisting=1
	if ! backup_dir="$(mktemp -d)"; then
		echo "ERROR: failed to allocate a backup for $ignore_file; original is untouched." >&2
		exit 1
	fi
	if ! cp -a -- "$ignore_file" "$backup_dir/original"; then
		rm -rf -- "$backup_dir"
		echo "ERROR: failed to back up the existing $ignore_file; aborting before the QC exclude set overwrites it." >&2
		exit 1
	fi
fi

restore_semgrepignore() {
	if [ "$had_preexisting" -eq 1 ]; then
		mv -fT -- "$backup_dir/original" "$ignore_file"
		rmdir -- "$backup_dir"
	else
		rm -f -- "$ignore_file"
	fi
}
trap restore_semgrepignore EXIT

if [ "$had_preexisting" -eq 1 ]; then
	rm -f -- "$ignore_file"
fi
uv run "$read_excludes_script" "$excludes_config" >"$ignore_file"
printf '%s\n' '*.html' '**/*.html' '.pnp.cjs' '.pnp.loader.mjs' >>"$ignore_file"

"$@"
