"""Slop torture suite (#41, was #62): detector regression tests.

Runs the *real* shipped detectors against deliberately noncompliant
fixtures in tests/fixtures/slop-torture/, mixed with compliant
counterparts, and asserts both directions:

- true positives: every annotated slop line is flagged (no false negatives);
- true negatives: no compliant line is flagged (no flag-theater noise).

Three groupings from the #41 epic (was #62): runtime control flow and
defensiveness, mocking and proof-laundering (semgrep rules parsed out of
the shipped tool-configs/semgrep.yml), and complexity gaps (the real
lizard gate with the -C/-L thresholds from justfiles/python.just).
"""

import pathlib
import subprocess

from tests.test_semgrep_rules import _assert_rules_match_annotations

TORTURE = pathlib.Path(__file__).resolve().parent / "fixtures" / "slop-torture"

RUNTIME_CONTROL_FLOW_RULES = (
    "py-no-getenv-default",
    "py-no-dict-get-default",
    "py-no-getattr-default",
    "py-no-defaultdict",
    "py-no-optional-type",
    "py-no-try-import",
    "py-no-bare-except",
    "py-no-suppress",
)

PROOF_LAUNDERING_RULES = (
    "py-no-mock-import",
    "py-no-magicmock",
    "py-no-monkeypatch",
    "py-no-skip-test",
    "py-xfail-without-open-issue-gate",
)

# The gate thresholds shipped in justfiles/python.just `_lizard-python`.
LIZARD_GATE = ("-C", "7", "-L", "100", "-i", "0")


def test_runtime_control_flow_and_defensiveness_torture() -> None:
    """Swallowed errors, permissive defaults, optional state, try-import."""
    _assert_rules_match_annotations(
        RUNTIME_CONTROL_FLOW_RULES, "runtime_control_flow.py", fixtures_dir=TORTURE
    )


def test_mocking_and_proof_laundering_torture() -> None:
    """Mock-as-proof, masked tests, and the sanctioned red-proof xfail gate."""
    _assert_rules_match_annotations(
        PROOF_LAUNDERING_RULES, "proof_laundering.py", fixtures_dir=TORTURE
    )


def _lizard(path: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uvx", "--from", "lizard", "lizard", "-l", "python", *LIZARD_GATE, str(path)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_lizard_gate_flags_tangled_complexity() -> None:
    proc = _lizard(TORTURE / "complexity_tangled.py")
    assert proc.returncode != 0, f"lizard passed the tangled fixture:\n{proc.stdout}"
    assert "classify_finding" in proc.stdout


def test_lizard_gate_passes_dispatch_table_shape() -> None:
    proc = _lizard(TORTURE / "complexity_clean.py")
    assert proc.returncode == 0, f"lizard flagged the compliant fixture:\n{proc.stdout}\n{proc.stderr}"
