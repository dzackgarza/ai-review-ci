"""Slop-torture fixture: compliant code the lizard gate must NOT flag.

Counterpart to complexity_tangled.py: same job, dispatch-table shape,
complexity under the -C 7 gate. Proves the detector test rejects
flag-theater on clean code.
"""

_DISPOSITIONS = {
    ("SLOP", 1): "block",
    ("SLOP", 2): "note",
    ("SLOP SUSPECT", 1): "escalate",
    ("SLOP SUSPECT", 2): "review",
}


def classify_finding(label: str, tier: int) -> str:
    disposition = _DISPOSITIONS.get((label, tier))
    assert disposition is not None, (label, tier)
    return disposition
