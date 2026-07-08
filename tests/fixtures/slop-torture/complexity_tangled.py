"""Slop-torture fixture: complexity the lizard gate must flag (#41, was #62).

``classify_finding`` is a deliberately tangled decision ladder whose
cyclomatic complexity exceeds the shipped lizard gate (-C 7). Run by
tests/test_slop_torture.py through the real lizard invocation shape from
justfiles/python.just. Excluded from the repo's own QC surface via
tool-configs/qc-excludes.toml.
"""


def classify_finding(
    label: str,
    policy_code: str,
    tier: int,
    evidence_count: int,
    age_days: int,
    author: str,
    area: str,
) -> str:
    if label == "SLOP":
        if policy_code:
            if tier == 1:
                if evidence_count > 0:
                    return "block"
                if age_days > 30:
                    return "stale-block"
                return "needs-evidence"
            if tier == 2:
                if area == "tests":
                    return "note-tests"
                return "note"
            return "untiered"
        if author == "bot":
            return "unattributed-bot"
        return "unattributed"
    if label == "SLOP SUSPECT":
        if evidence_count > 2:
            return "escalate"
        if age_days > 7 and area != "docs":
            return "review"
        return "hold"
    if label == "NOTE" or label == "":
        return "drop"
    return "unknown"
