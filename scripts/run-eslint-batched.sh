#!/usr/bin/env bash
set -euo pipefail

if (( $# < 3 )); then
  echo "usage: run-eslint-batched.sh <eslint> <config> <target>..." >&2
  exit 2
fi

eslint_bin=$1
eslint_config=$2
shift 2

batch_size=${ESLINT_BATCH_SIZE:-5}
if [[ ! $batch_size =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: ESLINT_BATCH_SIZE must be a positive integer" >&2
  exit 2
fi

eslint_args=(--config "$eslint_config" --max-warnings 0 --no-warn-ignored)
if [[ ${ESLINT_FIX:-0} == 1 ]]; then
  eslint_args+=(--fix)
fi

is_eslint_source() {
  case "$1" in
    *.js|*.jsx|*.mjs|*.cjs|*.ts|*.tsx|*.mts|*.cts|*.vue) return 0 ;;
    *) return 1 ;;
  esac
}

files=()
if [[ ${QC_TIER:-} != ambient && -n ${DIFF_COVER_BASE:-} ]]; then
  if ! git rev-parse --verify "${DIFF_COVER_BASE}^{commit}" >/dev/null 2>&1; then
    echo "ERROR: eslint: DIFF_COVER_BASE does not resolve: $DIFF_COVER_BASE" >&2
    exit 2
  fi
  while IFS= read -r -d '' file; do
    [[ -f $file ]] && is_eslint_source "$file" && files+=("$file")
  done < <(
    git diff --name-only --diff-filter=ACMR -z \
      "${DIFF_COVER_BASE}...HEAD" -- "$@"
  )
  if (( ${#files[@]} == 0 )); then
    echo "eslint: no changed authored JavaScript, TypeScript, or Vue files."
    exit 0
  fi
else
  while IFS= read -r -d '' file; do
    files+=("$file")
  done < <(
    find "$@" -type f \
      \( -name '*.js' -o -name '*.jsx' -o -name '*.mjs' -o -name '*.cjs' \
        -o -name '*.ts' -o -name '*.tsx' -o -name '*.mts' -o -name '*.cts' \
        -o -name '*.vue' \) \
      -print0
  )
  if (( ${#files[@]} == 0 )); then
    echo "ERROR: eslint: no authored JavaScript, TypeScript, or Vue files found." >&2
    exit 1
  fi
fi

failed=0
for (( offset = 0; offset < ${#files[@]}; offset += batch_size )); do
  if ! "$eslint_bin" "${eslint_args[@]}" "${files[@]:offset:batch_size}"; then
    failed=1
  fi
done

exit "$failed"
