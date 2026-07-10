"""Behavioral tests for the custom ast-grep rules in ``tool-configs/ast-grep``.

These run the *real* shipped rule file (not a copy) against an annotated
fixture, so a rule edit that changes what fires is caught here rather than only
in a downstream repo's gate. The annotation convention (``# ruleid:`` for an
expected match, ``# ok:`` for an expected non-match) is shared with the semgrep
behavioral suite in test_semgrep_rules.py.
"""

import json
import pathlib
import subprocess

from tests.test_semgrep_rules import ROOT, _expected

AST_GREP_RULES = ROOT / "tool-configs" / "ast-grep" / "rules"
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "ast-grep"


def _ast_grep_matches(rule_file: pathlib.Path, files: list[pathlib.Path]) -> set[tuple[str, int]]:
    proc = subprocess.run(
        [
            "npx",
            "-y",
            "--package",
            "@ast-grep/cli",
            "ast-grep",
            "scan",
            "--rule",
            str(rule_file),
            "--json",
            *(str(f) for f in files),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.stdout, f"ast-grep produced no output (rc={proc.returncode}):\n{proc.stderr}"
    # ast-grep reports 0-indexed lines; the annotation convention is 1-indexed.
    return {(pathlib.Path(m["file"]).name, m["range"]["start"]["line"] + 1) for m in json.loads(proc.stdout)}


def test_no_dynamic_import_python_flags_only_static_literals() -> None:
    """#219: fire on a dependency-hiding static literal, never on a name that
    is data (variable, attribute, f-string) — dynamic import by design."""
    fixture = FIXTURES / "dynamic_import.py"
    expected_flag, expected_clean = _expected([fixture])
    assert expected_flag and expected_clean, "fixture must annotate both ruleid and ok cases"

    matched = _ast_grep_matches(AST_GREP_RULES / "no-dynamic-import-python.yml", [fixture])

    false_negatives = sorted(expected_flag - matched)
    false_positives = sorted(matched - expected_flag)
    assert not false_negatives, f"expected-flag line(s) not flagged: {false_negatives}"
    assert not false_positives, f"expected-clean line(s) wrongly flagged: {false_positives}"
