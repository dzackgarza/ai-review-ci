#!/usr/bin/env bash
set -euo pipefail

: "${SAGE_BIN:?Configure the real Sage launcher before running this proof}"
repo_root="$(cd "$(dirname "$0")/.." && pwd -P)"
target="$(mktemp -d)"
trap 'gio trash "$target"' EXIT
mkdir -p "$target/tests"
cat >"$target/engine.py" <<'PY'
from sage.all import ZZ


def factor_twelve():
    return list(ZZ(12).factor())
PY
cat >"$target/tests/test_engine.sage" <<'PY'
from engine import factor_twelve


def test_factorization():
    assert factor_twelve() == [(2, 2), (3, 1)]
PY
git -C "$target" init --quiet
git -C "$target" add engine.py tests
for recipe in _sage-pytest _sage-pytest-coverage; do
    just -f "$repo_root/justfiles/sage.just" -d "$target" "$recipe"
done
target_slug="$(printf '%s' "$target" | sed 's#[^A-Za-z0-9._-]#_#g')"
coverage_xml="${XDG_CACHE_HOME:-$HOME/.cache}/quality-control/coverage/$target_slug/coverage.xml"
"$SAGE_BIN" -python - "$coverage_xml" <<'PY'
import sys
from xml.etree import ElementTree

report = ElementTree.parse(sys.argv[1])
classes = report.findall(".//class[@filename='engine.py']")
assert len(classes) == 1
lines = classes[0].findall("./lines/line")
assert lines
assert all(int(line.attrib["hits"]) > 0 for line in lines)
PY
sed -i 's/(3, 1)/(5, 1)/' "$target/tests/test_engine.sage"
for recipe in _sage-pytest _sage-pytest-coverage; do
    if just -f "$repo_root/justfiles/sage.just" -d "$target" "$recipe" >"$target/invalid.log" 2>&1; then
        cat "$target/invalid.log"
        echo "ERROR: Sage test gate accepted an incorrect factorization." >&2
        exit 1
    fi
    cat "$target/invalid.log"
    rg 'FAILED tests/test_engine.sage::test_factorization' "$target/invalid.log"
done
