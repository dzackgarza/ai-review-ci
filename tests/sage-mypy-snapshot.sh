#!/usr/bin/env bash
set -euo pipefail

: "${SAGE_BIN:?Configure the real Sage launcher before running this proof}"
repo_root="$(cd "$(dirname "$0")/.." && pwd -P)"
target="$(mktemp -d)"
trap 'gio trash "$target"' EXIT
git -C "$target" init --quiet
mkdir -p "$target/src/snapshot_category"
cat >"$target/src/snapshot_category/__init__.py" <<'PY'
from sage.categories.sets_cat import Sets


class SnapshotSets(Sets):
    pass
PY
cat >"$target/pyproject.toml" <<'TOML'
[project]
name = "sage-snapshot-proof"
version = "0.0.0"
[tool.sage-mypy-category-plugin]
packages = ["snapshot_category"]
TOML
printf 'value: int = int(1)\n' >"$target/example.sage"
git -C "$target" add pyproject.toml example.sage src
just -f "$repo_root/justfiles/sage.just" -d "$target" _sage-mypy

printf 'value: int = "wrong"\n' >"$target/example.sage"
if just -f "$repo_root/justfiles/sage.just" -d "$target" _sage-mypy >"$target/invalid.log" 2>&1; then
    cat "$target/invalid.log"
    echo "ERROR: Sage mypy accepted an invalid typed assignment." >&2
    exit 1
fi
cat "$target/invalid.log"
rg 'example.py:[0-9]+: error: Incompatible types in assignment.*\[assignment\]' "$target/invalid.log"
