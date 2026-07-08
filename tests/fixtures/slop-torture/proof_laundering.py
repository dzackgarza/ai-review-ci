"""Slop-torture fixtures: mocking and proof-laundering (#41, was #62).

Test-shaped code exercising the shipped semgrep rules for mock-as-proof,
masked tests, and the sanctioned open-issue red-proof xfail gate, mixed
with compliant real-boundary counterparts.

Annotation convention: ``# ruleid: <id>`` / ``# ok: <id>`` mark the line
below. Run by tests/test_slop_torture.py against the real rules parsed out
of tool-configs/semgrep.yml. Not collected by pytest (filename does not
match test_*.py); excluded from the repo's own QC surface via
tool-configs/qc-excludes.toml.
"""

# ruleid: py-no-mock-import
from unittest.mock import MagicMock

import pytest


def test_mocked_boundary_as_proof() -> None:
    # ruleid: py-no-magicmock
    client = MagicMock()
    client.fetch.return_value = {"ok": True}
    assert client.fetch() == {"ok": True}


def test_real_boundary(tmp_path) -> None:
    # ok: py-no-magicmock
    report = tmp_path / "report.json"
    report.write_text("{}")
    assert report.read_text() == "{}"


def test_patched_boundary_as_proof(monkeypatch) -> None:
    # ruleid: py-no-monkeypatch
    monkeypatch.setattr("os.environ", {})


# ruleid: py-no-skip-test
@pytest.mark.skip(reason="flaky, revisit later")
def test_masked_by_skip() -> None:
    raise AssertionError("never runs")


# ruleid: py-xfail-without-open-issue-gate
@pytest.mark.xfail(reason="broken sometimes")
def test_masked_by_loose_xfail() -> None:
    raise AssertionError("masked without an issue grant")


# ok: py-xfail-without-open-issue-gate
@pytest.mark.xfail(reason="red proof gate for #41", strict=True)
def test_red_proof_gate() -> None:
    raise AssertionError("committed red proof, strict, cites the open issue")
