#!/usr/bin/env bash
set -euo pipefail

: "${SAGE_BIN:?Configure the real Sage launcher before running this proof}"
repo_root="$(cd "$(dirname "$0")/.." && pwd -P)"
target="$(mktemp -d)"
trap 'gio trash "$target"' EXIT
git -C "$target" init --quiet
# Sage generator syntax is invalid Python until the real preparser lowers it.
printf 'R.<x> = PolynomialRing(QQ)\n' >"$target/example.sage"
git -C "$target" add example.sage
just -f "$repo_root/justfiles/sage.just" -d "$target" _sage-syntax

printf 'def broken(:\n' >"$target/example.sage"
if just -f "$repo_root/justfiles/sage.just" -d "$target" _sage-syntax >"$target/invalid.log" 2>&1; then
    cat "$target/invalid.log"
    echo "ERROR: Sage syntax validation accepted invalid syntax." >&2
    exit 1
fi
cat "$target/invalid.log"
rg 'SyntaxError' "$target/invalid.log"
