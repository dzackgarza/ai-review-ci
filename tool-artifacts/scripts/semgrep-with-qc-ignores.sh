#!/usr/bin/env bash
# Run semgrep with the QC-authoritative ignore set in place.
#
# #214: with no project .semgrepignore, semgrep falls back to its bundled
# default template, which excludes tests/ — silently killing the
# test-antipattern rules (py-no-monkeypatch and its NO_MOCK_PROOF /
# NO_SKIP_MASK siblings) that are designed to fire IN test files. The
# single-source-of-truth exclusion list names vendor/generated dirs only and
# does NOT list tests/, so writing it makes tests/ scannable. It also
# overrides any repo-committed .semgrepignore for the duration of the scan
# (no-repo-writable-QC-suppression).
#
# "a tracked file pre-existed" and "we made a backup" are DISTINCT facts. The
# restore path must never conflate them: an empty backup handle must not
# license removing a tracked file we did not create. The backup is taken
# BEFORE the overwrite and a failure to take it aborts, rather than proceeding
# into a trap that could delete the user's tracked file.
#
# Usage: semgrep-with-qc-ignores.sh <read_qc_excludes.py> <qc-excludes.toml> -- <semgrep argv...>
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
		# A tracked file pre-existed: restore it, never remove it.
		mv -f "$ignore_backup" "$ignore_file"
	else
		# We created it ourselves; removing it is safe.
		rm -f "$ignore_file"
	fi
}
trap restore_semgrepignore EXIT

uv run "$read_excludes_script" "$excludes_config" >"$ignore_file"
printf '%s\n' '*.html' '**/*.html' >>"$ignore_file"

"$@"
