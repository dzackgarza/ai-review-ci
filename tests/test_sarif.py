"""SARIF ledger tests for carried-forward code-scanning alerts."""

import os
from typing import Any

from ai_review_ci.models import finding_fingerprint
from ai_review_ci.sarif import build_sarif
from tests.conftest import APP_FILE, general_candidate, general_finding

JsonDict = dict[str, Any]


def existing_alert(
    *, category: str = "carried-forward", path: str = APP_FILE, state: str = "open"
) -> JsonDict:
    return {
        "tool_name": "ai-review/general",
        "alert": {
            "state": state,
            "rule": {
                "id": category,
                "name": "CARRIED_FORWARD",
                "description": "Existing finding that remains open",
            },
            "most_recent_instance": {
                "message": {"text": "Existing invariant violation"},
                "location": {
                    "path": path,
                    "start_line": 2,
                    "end_line": 4,
                    "properties": {
                        "label": "CARRIED_FORWARD",
                        "tier": "tier1",
                        "category": category,
                    },
                },
            },
        },
    }


def result_fingerprints(sarif: JsonDict) -> list[str]:
    return [
        result["partialFingerprints"]["reviewFindingKey"]
        for result in sarif["runs"][0]["results"]
    ]


def test_build_sarif_carries_existing_open_alerts(checkout) -> None:
    os.environ["GITHUB_SHA"] = "abc123"
    os.environ["GITHUB_SERVER_URL"] = "https://github.com"
    os.environ["GITHUB_REPOSITORY"] = "owner/repo"

    artifact = general_candidate(
        findings=[
            general_finding(
                category="new-review-finding",
                label="NEW_FINDING",
                location={"path": "tests/test_app.py", "start_line": 1, "end_line": 2},
            )
        ]
    )

    sarif = build_sarif(
        artifact,
        report_type="general",
        category="ai-general-review",
        carried_alerts=[existing_alert()],
    )

    fingerprints = result_fingerprints(sarif)
    assert finding_fingerprint("carried-forward", APP_FILE) in fingerprints
    assert finding_fingerprint("new-review-finding", "tests/test_app.py") in fingerprints


def test_new_finding_replaces_matching_carried_alert(checkout) -> None:
    os.environ["GITHUB_SHA"] = "abc123"
    os.environ["GITHUB_SERVER_URL"] = "https://github.com"
    os.environ["GITHUB_REPOSITORY"] = "owner/repo"

    artifact = general_candidate(
        findings=[
            general_finding(
                category="carried-forward",
                label="UPDATED_FINDING",
                violated_invariant="Updated reviewer evidence for the same ledger item",
            )
        ]
    )

    sarif = build_sarif(
        artifact,
        report_type="general",
        category="ai-general-review",
        carried_alerts=[existing_alert()],
    )

    fingerprints = result_fingerprints(sarif)
    assert fingerprints.count(finding_fingerprint("carried-forward", APP_FILE)) == 1
    messages = [result["message"]["text"] for result in sarif["runs"][0]["results"]]
    assert "Updated reviewer evidence for the same ledger item" in messages
    assert "Existing invariant violation" not in messages
