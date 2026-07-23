"""Behavioral tests for the custom semgrep rules in ``tool-configs/semgrep.yml``.

These run the *real* rule definitions (parsed out of the shipped config, not a
copy) against annotated fixtures, so a rule edit that changes what fires is
caught here rather than only in a downstream repo's gate.

Annotation convention (semgrep's own): a ``// ruleid: <id>`` comment (``#`` in
Python fixtures) marks the following line as an expected match; ``// ok: <id>``
marks it as an expected non-match. The test asserts the rules flag exactly the
``ruleid`` lines and none of the ``ok`` lines.

The annotation/run/assert helpers here are shared with the slop-torture suite
in test_slop_torture.py (#41).
"""

import json
import pathlib
import re
import subprocess
import tempfile

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
SEMGREP_CONFIG = ROOT / "tool-configs" / "semgrep.yml"
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "semgrep"

# The fail-soft-default rules whose precision #120 is about. Position, not the
# bare ``||`` / ``??`` operator, must be the signal.
RUNTIME_DEFAULT_RULES = ("ts-no-or-default", "no-nullish-coalescing")

_ANNOTATION = re.compile(r"(?://|#)\s*(ruleid|ok):\s*([\w-]+)")


def _rules_subset(ids: tuple[str, ...]) -> list[dict[str, object]]:
    rules = [r for r in yaml.safe_load(SEMGREP_CONFIG.read_text())["rules"] if r["id"] in ids]
    assert {r["id"] for r in rules} == set(ids), f"missing rules in {SEMGREP_CONFIG}: {set(ids) - {r['id'] for r in rules}}"
    return rules


def _expected(files: list[pathlib.Path]) -> tuple[set[tuple[str, int]], set[tuple[str, int]]]:
    """(expected-match, expected-clean) line sets, keyed by (filename, line).

    Each annotation refers to the line immediately below the comment.
    """
    flag: set[tuple[str, int]] = set()
    clean: set[tuple[str, int]] = set()
    for path in files:
        for i, line in enumerate(path.read_text().splitlines()):
            match = _ANNOTATION.search(line)
            if match:
                (flag if match.group(1) == "ruleid" else clean).add((path.name, i + 2))
    return flag, clean


def _semgrep_matches(rules: list[dict[str, object]], files: list[pathlib.Path]) -> set[tuple[str, int]]:
    with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as tmp:
        yaml.safe_dump({"rules": rules}, tmp)
        config = tmp.name
    proc = subprocess.run(
        [
            "uvx",
            "--from",
            "semgrep",
            "semgrep",
            "scan",
            f"--config={config}",
            "--scan-unknown-extensions",
            "--json",
            *(str(f) for f in files),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.stdout, f"semgrep produced no output (rc={proc.returncode}):\n{proc.stderr}"
    results = json.loads(proc.stdout)["results"]
    return {(pathlib.Path(r["path"]).name, r["start"]["line"]) for r in results}


def _assert_rules_match_annotations(rule_ids: tuple[str, ...], glob: str, fixtures_dir: pathlib.Path = FIXTURES) -> None:
    fixtures = sorted(fixtures_dir.glob(glob))
    assert fixtures, f"no fixtures match {glob} in {fixtures_dir}"

    expected_flag, expected_clean = _expected(fixtures)
    assert expected_flag and expected_clean, f"{glob}: fixtures must annotate both ruleid and ok cases"

    matched = _semgrep_matches(_rules_subset(rule_ids), fixtures)

    false_negatives = sorted(expected_flag - matched)
    false_positives = sorted(matched - expected_flag)
    assert not false_negatives, f"expected-flag line(s) not flagged: {false_negatives}"
    assert not false_positives, f"expected-clean line(s) wrongly flagged: {false_positives}"


def test_runtime_default_rules_flag_only_value_default_positions() -> None:
    """#120: ``||`` / ``??`` flag fail-soft defaults, not boolean connectives."""
    _assert_rules_match_annotations(RUNTIME_DEFAULT_RULES, "runtime_default.ts*")


def test_type_escape_rules_own_single_and_double_casts() -> None:
    _assert_rules_match_annotations(("ts-no-any-cast", "no-double-cast", "no-unproven-boundary-cast"), "no_double_cast.ts")


LEAN_REFERENT_RULES = (
    "lean-no-axiom",
    "lean-shim-suffix-decl",
    "lean-has-wrapper",
    "lean-nonempty-field",
    "lean-bare-prop-field",
    "lean-isotropy-as-torsion",
    "lean-truncating-division-on-forms",
    "lean-epistemic-on-math-surface",
)


def test_lean_referent_rules_flag_shims_and_conventions() -> None:
    """#309: engineering shims graduated to mathematical placement (lean-lattices referent audit)."""
    _assert_rules_match_annotations(LEAN_REFERENT_RULES, "*.lean")
