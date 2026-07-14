from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "pr-feedback-triage" / "scripts" / "triage_state.py"


def load_triage_state() -> ModuleType:
    spec = importlib.util.spec_from_file_location("triage_state", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def thread(
    finding: str,
    *replies: str,
    resolved: bool = False,
    path: str = "src/reader.py",
) -> dict[str, object]:
    comments = [
        {
            "id": f"comment-{index}",
            "databaseId": index,
            "url": f"https://github.com/owner/repo/pull/7#discussion_r{index}",
            "author": {"login": "reviewer" if index == 0 else "worker"},
            "body": body,
            "createdAt": "2026-07-15T00:00:00Z",
        }
        for index, body in enumerate((finding, *replies))
    ]
    return {
        "id": "PRRT_thread",
        "isResolved": resolved,
        "isOutdated": False,
        "path": path,
        "line": 12,
        "comments": {"nodes": comments},
    }


def test_stable_key_prefers_fingerprint_and_ignores_line_shifts() -> None:
    triage = load_triage_state()
    finding = "<!-- ai-review-fingerprint: " + "a" * 64 + " -->\n## Read failure"
    first = thread(finding)
    shifted = thread(finding)
    shifted["line"] = 900

    assert triage.stable_key(first) == "fp:" + "a" * 64
    assert triage.stable_key(shifted) == triage.stable_key(first)


def test_disposition_parser_requires_complete_thread_reply_not_root_text() -> None:
    triage = load_triage_state()
    accepted = """\
Disposition: Accepted as written
Policy basis: POLICY.NO_ERROR_DISCARD
Pre-filter: Gate 1 correctness defect -> current-PR remediation
Claim: Read failures are discarded.
Remediation: Propagate the read error.
Code/action taken or explicit non-change: Propagate the read error.
Proof: Boundary test rejects partial success.
Commit: 123456789abc
Audit anchor: tests/test_reader.py::test_failure
"""
    root_only = thread(accepted, resolved=True)
    incomplete_reply = thread(
        "Read failures are discarded.",
        """\
Disposition: Accepted as written
Policy basis: POLICY.NO_ERROR_DISCARD
Pre-filter: Gate 1 correctness defect -> current-PR remediation
Claim: Read failures are discarded.
Remediation: Propagate the read error.
Code/action taken or explicit non-change: Propagate the read error.
Proof: Boundary test rejects partial success.
Audit anchor: tests/test_reader.py::test_failure
""",
        resolved=True,
    )
    complete_reply = thread("Read failures are discarded.", accepted, resolved=True)

    assert triage.disposition_of(root_only) is None
    assert triage.disposition_of(incomplete_reply)["complete"] is False
    assert triage.classify(incomplete_reply, triage.disposition_of(incomplete_reply), None) == "OPEN-PENDING"
    assert triage.disposition_of(complete_reply)["complete"] is True
    assert triage.classify(complete_reply, triage.disposition_of(complete_reply), None) == "CLOSED"


def test_re_emitted_finding_uses_prior_complete_disposition_as_resume_state() -> None:
    triage = load_triage_state()
    finding = "<!-- ai-review-fingerprint: " + "b" * 64 + " -->\n## Missing proof"
    current = thread(finding)
    key = triage.stable_key(current)
    previous = {
        key: {
            "verdict": "rejected",
            "complete": True,
            "commit": None,
            "by": "worker",
            "url": "https://github.com/owner/repo/pull/7#discussion_r4",
        }
    }

    records = triage.build_records([current], previous)

    assert records[0]["state"] == "RE-RAISED"
    assert records[0]["key"] == key
