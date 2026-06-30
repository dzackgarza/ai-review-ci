"""SARIF ledger tests for carried-forward code-scanning alerts."""

import json
import os
from pathlib import Path
from typing import Any

import pytest
from sarif_pydantic import Message, ReportingDescriptor, Result

from ai_review_ci.models import finding_fingerprint
from ai_review_ci.sarif import (
    CARRY_FORWARD_SCHEMA_VERSION,
    _append_result,
    build_sarif,
    to_sarif,
)
from tests.conftest import APP_FILE, general_candidate, general_finding, slop_candidate, slop_finding

JsonDict = dict[str, Any]


def existing_alert(*, category: str = "carried-forward", path: str = APP_FILE, state: str = "open") -> JsonDict:
    return {
        "tool_name": "ai-review/general",
        "alert": {
            "state": state,
            "rule": {
                "id": category,
                "name": "CARRIED_FORWARD",
                "description": "Existing finding that remains open",
                "severity": "error",
            },
            "most_recent_instance": {
                "message": {"text": "Existing invariant violation"},
                "location": {
                    "path": path,
                    "start_line": 2,
                    "end_line": 4,
                },
            },
        },
    }


def result_fingerprints(sarif: JsonDict) -> list[str]:
    return [result["partialFingerprints"]["reviewFindingKey"] for result in sarif["runs"][0]["results"]]


def configure_github_env() -> None:
    os.environ["GITHUB_SHA"] = "abc123"
    os.environ["GITHUB_SERVER_URL"] = "https://github.com"
    os.environ["GITHUB_REPOSITORY"] = "owner/repo"


def test_build_sarif_carries_existing_open_alerts(checkout: Path) -> None:
    configure_github_env()

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


def test_build_sarif_results_reference_rule_table_indexes(checkout: Path) -> None:
    configure_github_env()

    artifact = general_candidate(
        findings=[
            general_finding(
                category="first-review-finding",
                label="FIRST_FINDING",
                location={"path": APP_FILE, "start_line": 1, "end_line": 2},
            ),
            general_finding(
                category="second-review-finding",
                label="SECOND_FINDING",
                location={"path": "tests/test_app.py", "start_line": 3, "end_line": 4},
            ),
        ]
    )

    sarif = build_sarif(
        artifact,
        report_type="general",
        category="ai-general-review",
    )

    run = sarif["runs"][0]
    rule_index_by_id = {rule["id"]: index for index, rule in enumerate(run["tool"]["driver"]["rules"])}
    for result in run["results"]:
        assert result["ruleIndex"] == rule_index_by_id[result["ruleId"]]


def test_build_sarif_resolves_policy_guidance_from_vendored_index(checkout: Path) -> None:
    configure_github_env()

    artifact = general_candidate(
        findings=[
            general_finding(
                category="hidden-config",
                label="HIDDEN_CONFIG",
                policy_code="POLICY.NO_HIDDEN_CONFIG",
            )
        ]
    )

    sarif = build_sarif(
        artifact,
        report_type="general",
        category="ai-general-review",
    )

    result = sarif["runs"][0]["results"][0]
    rule = sarif["runs"][0]["tool"]["driver"]["rules"][0]
    assert result["properties"]["policy_code"] == "POLICY.NO_HIDDEN_CONFIG"
    assert result["properties"]["remediation_code"] == "REMEDIATE.TOTAL_CONFIG_MODEL"
    assert "Policy: `POLICY.NO_HIDDEN_CONFIG`" in result["message"]["text"]
    assert "Remediation: `REMEDIATE.TOTAL_CONFIG_MODEL`" in result["message"]["text"]
    assert rule["properties"] == {
        "policy_code": "POLICY.NO_HIDDEN_CONFIG",
        "remediation_code": "REMEDIATE.TOTAL_CONFIG_MODEL",
    }


def test_build_sarif_embeds_structured_reviewer_identity(checkout: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_github_env()
    monkeypatch.setenv("AI_REVIEW_AGENT", "codex-reviewer")

    artifact = general_candidate(findings=[general_finding()])

    sarif = build_sarif(
        artifact,
        report_type="general",
        category="ai-general-review",
    )

    assert sarif["runs"][0]["results"][0]["properties"]["reviewer"] == {
        "type": "general",
        "agent": "codex-reviewer",
        "prompt_id": "reviews/general",
        "prompt_version": "1.0.0",
    }


def test_build_sarif_routes_reviewer_identity_by_report_type(checkout: Path) -> None:
    configure_github_env()

    artifact = slop_candidate(findings=[slop_finding()])

    sarif = build_sarif(
        artifact,
        report_type="slop",
        category="ai-slop-review",
    )

    assert sarif["runs"][0]["results"][0]["properties"]["reviewer"] == {
        "type": "slop",
        "agent": "opencode-ai",
        "prompt_id": "reviews/slop",
        "prompt_version": "1.0.0",
    }


def test_append_result_updates_runtime_rule_index_field() -> None:
    seen_rules = {"existing-rule": 0}
    rules = [ReportingDescriptor(id="existing-rule")]
    results: list[Result] = []
    result = Result(
        rule_id="new-rule",
        rule_index=0,
        message=Message(text="Rule index must be assigned through the model field"),
    )

    _append_result(
        seen_rules,
        rules,
        results,
        "new-rule",
        ReportingDescriptor(id="new-rule"),
        result,
    )

    assert result.rule_index == 1
    assert not hasattr(result, "ruleIndex")
    assert results == [result]


def test_new_finding_replaces_matching_carried_alert(checkout: Path) -> None:
    configure_github_env()

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


def test_to_sarif_writes_artifact_with_optional_carried_alert_sidecar(
    checkout: Path,
    tmp_path: Path,
) -> None:
    configure_github_env()
    artifact_path = tmp_path / "artifact.json"
    sidecar_path = tmp_path / "carry-forward.json"
    first_output = tmp_path / "first.sarif"
    second_output = tmp_path / "second.sarif"
    carried_alert = existing_alert()
    del carried_alert["alert"]["most_recent_instance"]["location"]["end_line"]
    artifact_path.write_text(json.dumps(general_candidate(findings=[])))
    sidecar_path.write_text(
        json.dumps(
            {
                "schema_version": CARRY_FORWARD_SCHEMA_VERSION,
                "alerts": [carried_alert],
            }
        )
    )

    to_sarif(artifact_path, first_output, "ai-general-review")
    to_sarif(artifact_path, second_output, "ai-general-review", sidecar_path)

    first_sarif = json.loads(first_output.read_text())
    second_sarif = json.loads(second_output.read_text())
    assert first_sarif["runs"][0]["results"] == []
    carried_result = second_sarif["runs"][0]["results"][0]
    assert carried_result["partialFingerprints"]["reviewFindingKey"] == (finding_fingerprint("carried-forward", APP_FILE))
    assert carried_result["locations"][0]["physicalLocation"]["region"] == {"startLine": 2}


def test_build_sarif_carries_github_rest_alert_without_location_properties(
    checkout: Path,
) -> None:
    configure_github_env()
    carried_alert = existing_alert()

    sarif = build_sarif(
        general_candidate(findings=[]),
        report_type="general",
        category="ai-general-review",
        carried_alerts=[carried_alert],
    )

    carried_result = sarif["runs"][0]["results"][0]
    assert carried_result["ruleId"] == "carried-forward"
    assert carried_result["level"] == "error"
    assert carried_result["properties"] == {
        "category": "carried-forward",
        "label": "CARRIED_FORWARD",
        "tier": "tier1",
    }


def test_build_sarif_ignores_non_target_and_resolved_carried_alerts(
    checkout: Path,
) -> None:
    configure_github_env()
    other_tool = existing_alert()
    other_tool["tool_name"] = "ai-review/slop"

    sarif = build_sarif(
        general_candidate(findings=[]),
        report_type="general",
        category="ai-general-review",
        carried_alerts=[
            other_tool,
            existing_alert(state="dismissed"),
            existing_alert(state="fixed"),
            existing_alert(state="closed"),
        ],
    )

    assert sarif["runs"][0]["results"] == []


@pytest.mark.parametrize(
    ("carried_alert", "broken_location_key"),
    [
        ({"tool_name": "ai-review/general", "alert": []}, None),
        ({"tool_name": "ai-review/general", "alert": {"state": ""}}, None),
        (existing_alert(state="unexpected"), None),
        (existing_alert(), "start_line"),
        (existing_alert(), "end_line"),
    ],
)
def test_build_sarif_rejects_malformed_carried_alerts(
    checkout: Path,
    carried_alert: JsonDict,
    broken_location_key: str | None,
) -> None:
    configure_github_env()
    if broken_location_key is not None:
        location = carried_alert["alert"]["most_recent_instance"]["location"]
        location[broken_location_key] = str(location[broken_location_key])

    with pytest.raises(SystemExit):
        build_sarif(
            general_candidate(findings=[]),
            report_type="general",
            category="ai-general-review",
            carried_alerts=[carried_alert],
        )


@pytest.mark.parametrize(
    "sidecar_payload",
    [
        {"schema_version": CARRY_FORWARD_SCHEMA_VERSION + 1, "alerts": []},
        {"schema_version": CARRY_FORWARD_SCHEMA_VERSION, "alerts": {}},
    ],
)
def test_to_sarif_rejects_invalid_carry_forward_sidecars(
    checkout: Path,
    tmp_path: Path,
    sidecar_payload: JsonDict,
) -> None:
    configure_github_env()
    artifact_path = tmp_path / "artifact.json"
    sidecar_path = tmp_path / "carry-forward.json"
    artifact_path.write_text(json.dumps(general_candidate(findings=[])))
    sidecar_path.write_text(json.dumps(sidecar_payload))

    with pytest.raises(SystemExit):
        to_sarif(
            artifact_path,
            tmp_path / "out.sarif",
            "ai-general-review",
            sidecar_path,
        )


def test_to_sarif_rejects_missing_carry_forward_sidecar(
    checkout: Path,
    tmp_path: Path,
) -> None:
    configure_github_env()
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(json.dumps(general_candidate(findings=[])))

    with pytest.raises(SystemExit):
        to_sarif(
            artifact_path,
            tmp_path / "out.sarif",
            "ai-general-review",
            tmp_path / "missing.json",
        )


def test_to_sarif_rejects_missing_or_unknown_artifacts(
    checkout: Path,
    tmp_path: Path,
) -> None:
    configure_github_env()
    invalid_artifact = tmp_path / "invalid-artifact.json"
    invalid_artifact.write_text(json.dumps(general_candidate(report_type="unknown")))

    with pytest.raises(SystemExit):
        to_sarif(tmp_path / "missing-artifact.json", tmp_path / "missing.sarif", "x")

    with pytest.raises(SystemExit):
        to_sarif(invalid_artifact, tmp_path / "invalid.sarif", "x")
