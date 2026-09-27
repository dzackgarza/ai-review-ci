#!/usr/bin/env bash
set -euo pipefail

: "${SAGE_BIN:?Configure the real Sage launcher before running this proof}"
repo_root="$(cd "$(dirname "$0")/.." && pwd -P)"
target="$(mktemp -d)"
ambient="$(mktemp -d)"
trap 'gio trash "$target" "$ambient"' EXIT
git -C "$target" init --quiet
mkdir -p "$target/src/snapshot_category"
cat >"$target/src/snapshot_category/__init__.py" <<'PY'
from importlib.resources import files
from typing import override

from sage.categories.category import Category
from sage.categories.category_singleton import Category_singleton
from sage.categories.sets_cat import Sets

UNIT = files(__package__).joinpath("units.txt").read_text().strip()


class SnapshotBaseSets(Category_singleton):
    def super_categories(self) -> list[Category]:
        return [Sets()]

    def _repr_object_names(self) -> str:
        return UNIT

    class ParentMethods:
        def snapshot_unit(self) -> str:
            return UNIT


class SnapshotSets(Category_singleton):
    def super_categories(self) -> list[Category]:
        return [SnapshotBaseSets()]

    class ParentMethods:
        @override
        def snapshot_unit(self) -> str:
            return UNIT
PY
printf 'snapshot sets\n' >"$target/src/snapshot_category/units.txt"
# The ambient version predates the category inheritance used by the current
# provider's override. Importing it for projection must fail that override check.
cp -r "$target/src/snapshot_category" "$ambient/snapshot_category"
sed -i 's/return \[SnapshotBaseSets()\]/return [Sets()]/' "$ambient/snapshot_category/__init__.py"
export PYTHONPATH="$ambient${PYTHONPATH:+:$PYTHONPATH}"
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
