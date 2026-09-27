#!/usr/bin/env bash
set -euo pipefail

# This integration proof requires the real Sage installation and category plugin.
# Run through just _test-sage-mypy-launch with SAGE_BIN configured by the caller.
: "${SAGE_BIN:?Configure the real Sage launcher before running this proof}"
repo_root="$(cd "$(dirname "$0")/.." && pwd -P)"
target="$(mktemp -d)"
trap 'gio trash "$target"' EXIT
git -C "$target" init --quiet
cat >"$target/pyproject.toml" <<'TOML'
[project]
name = "sage-launch-proof"
version = "0.0.0"
[tool.sage-mypy-category-plugin]
packages = ["sage.categories.sets_cat"]
TOML
printf 'value: int = 1\n' >"$target/example.py"
git -C "$target" add pyproject.toml example.py
just -f "$repo_root/justfiles/sage.just" -d "$target" _sage-mypy

printf 'value: int = "wrong"\n' >"$target/example.py"
if just -f "$repo_root/justfiles/sage.just" -d "$target" _sage-mypy >"$target/invalid.log" 2>&1; then
    cat "$target/invalid.log"
    echo "ERROR: Sage mypy accepted an invalid typed assignment." >&2
    exit 1
fi
cat "$target/invalid.log"
rg 'example.py:1: error: Incompatible types in assignment.*\[assignment\]' "$target/invalid.log"
