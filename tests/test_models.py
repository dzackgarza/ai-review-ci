"""Red/green validation tests for the report models against a real checkout.

Every rejection asserts on the exact FIX-guidance message the reviewing
agent receives, and every acceptance asserts the model preserved the
agent-supplied analysis verbatim.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_review_ci.models import (
    GeneralReport,
    SlopReport,
    finding_fingerprint,
)
from ai_review_ci.policy_index import canonical_route
from tests.conftest import (
    APP_FILE,
    APP_LINES,
    general_candidate,
    general_finding,
    slop_candidate,
    slop_finding,
)

FINGERPRINT_GENERAL = "98c020b740c04d14dd944241910818377b3bb114a9712807565890682c9f67d2"


def test_out_of_range_lines_rejected_with_true_file_length(checkout: Path) -> None:
    bad = general_candidate(
        findings=[
            general_finding(
                location={"path": APP_FILE, "start_line": 10, "end_line": 99},
                evidence=[{"kind": "file-read", "path": APP_FILE, "lines": [1, 2]}],
            )
        ]
    )
    with pytest.raises(ValidationError) as exc:
        GeneralReport.model_validate(bad)
    message = str(exc.value)
    assert f"exceed the length of '{APP_FILE}' ({APP_LINES} lines)" in message
    assert "FIX: use line numbers that exist in the file" in message

    corrected = general_candidate(findings=[general_finding(location={"path": APP_FILE, "start_line": 10, "end_line": APP_LINES})])
    report = GeneralReport.model_validate(corrected)
    assert report.findings[0].location.end_line == APP_LINES


def test_evidence_lines_out_of_range_rejected(checkout: Path) -> None:
    bad = general_candidate(findings=[general_finding(evidence=[{"kind": "file-read", "path": APP_FILE, "lines": [1, 999]}])])
    with pytest.raises(ValidationError) as exc:
        GeneralReport.model_validate(bad)
    assert f"exceed the length of '{APP_FILE}' ({APP_LINES} lines)" in str(exc.value)


def test_nonexistent_paths_rejected(checkout: Path) -> None:
    with pytest.raises(ValidationError) as scope_exc:
        GeneralReport.model_validate(general_candidate(review_scope=["src/ghost.py"]))
    assert "review_scope[0] path 'src/ghost.py' does not exist" in str(scope_exc.value)

    with pytest.raises(ValidationError) as loc_exc:
        GeneralReport.model_validate(
            general_candidate(
                findings=[
                    general_finding(
                        location={
                            "path": "src/ghost.py",
                            "start_line": 1,
                            "end_line": 1,
                        }
                    )
                ]
            )
        )
    assert "location path 'src/ghost.py' does not exist" in str(loc_exc.value)


def test_workflow_path_can_be_reviewed_when_it_is_in_scope(checkout: Path) -> None:
    wf = checkout / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "x.yml").write_text("name: x\n")
    report = SlopReport.model_validate(
        slop_candidate(
            review_scope=[".github/workflows/x.yml"],
            findings=[
                slop_finding(
                    location={
                        "path": ".github/workflows/x.yml",
                        "start_line": 1,
                        "end_line": 1,
                    },
                    evidence=[
                        {
                            "kind": "diff-snippet",
                            "path": ".github/workflows/x.yml",
                            "lines": [1, 1],
                        }
                    ],
                )
            ],
        )
    )
    assert str(report.findings[0].location.path) == ".github/workflows/x.yml"


def test_slop_report_rejects_note_label(checkout: Path) -> None:
    with pytest.raises(ValidationError) as exc:
        SlopReport.model_validate(slop_candidate(findings=[slop_finding(label="NOTE")]))
    assert "SLOP" in str(exc.value)


def test_slop_report_does_not_accept_review_theater_fields(checkout: Path) -> None:
    theatrical = slop_candidate(
        checked_surfaces=[
            {
                "path": APP_FILE,
                "reason": "high-churn",
                "lines_read": [1, APP_LINES],
                "result": "finding",
            }
        ],
        rejected_easy_wins=["long lines in tests/test_app.py — line-length only"],
    )
    with pytest.raises(ValidationError) as exc:
        SlopReport.model_validate(theatrical)
    assert "checked_surfaces" in str(exc.value)
    assert "rejected_easy_wins" in str(exc.value)

    stripped = slop_candidate()
    report = SlopReport.model_validate(stripped)
    assert report.findings[0].label == "SLOP"


def test_slop_report_rejects_clean_report_language(checkout: Path) -> None:
    bad = slop_candidate()
    bad["findings"] = [
        slop_finding(
            label="SLOP SUSPECT",
            pattern="clean delegation",
            slop_narrative="The diff is clean and no slop was found.",
        )
    ]
    with pytest.raises(ValidationError) as exc:
        SlopReport.model_validate(bad)
    assert "clean-report language" in str(exc.value)


def test_workflow_category_can_be_reviewed(checkout: Path) -> None:
    report = SlopReport.model_validate(slop_candidate(findings=[slop_finding(category="workflow")]))
    assert report.findings[0].category == "workflow"


def test_low_signal_category_cannot_be_tier1(checkout: Path) -> None:
    with pytest.raises(ValidationError) as exc:
        GeneralReport.model_validate(general_candidate(findings=[general_finding(category="naming", tier="tier1")]))
    assert "is low-signal, must be tier2" in str(exc.value)

    accepted = GeneralReport.model_validate(
        general_candidate(
            findings=[
                general_finding(category="naming", tier="tier2"),
                general_finding(),
            ]
        )
    )
    assert accepted.findings[0].tier == "tier2"


def test_report_of_only_low_signal_findings_rejected(checkout: Path) -> None:
    with pytest.raises(ValidationError) as exc:
        SlopReport.model_validate(slop_candidate(findings=[slop_finding(category="formatting", tier="tier2")]))
    assert "at least one finding must be substantive" in str(exc.value)


def test_empty_findings_report_accepted(checkout: Path) -> None:
    # An honest empty report must be valid: requiring >=1 finding structurally
    # pressures every run to invent debt. The substantive-finding rule only
    # rejects padding in non-empty reports.
    general = GeneralReport.model_validate(general_candidate(findings=[]))
    assert general.findings == []

    slop = SlopReport.model_validate(slop_candidate(findings=[]))
    assert slop.findings == []


def test_forbidden_score_and_report_fields_rejected(checkout: Path) -> None:
    with pytest.raises(ValidationError):
        GeneralReport.model_validate(general_candidate(score=95))
    with pytest.raises(ValidationError):
        GeneralReport.model_validate(general_candidate(report="all good"))


def test_general_review_accepts_ci_categories(checkout: Path) -> None:
    report = GeneralReport.model_validate(general_candidate(findings=[general_finding(category="ci-pipeline")]))
    assert report.findings[0].category == "ci-pipeline"


def test_blanket_invariant_claims_rejected(checkout: Path) -> None:
    with pytest.raises(ValidationError) as exc:
        SlopReport.model_validate(slop_candidate(findings=[slop_finding(violated_invariant="everything looks good in this module overall")]))
    assert "contains prohibited pattern" in str(exc.value)


def test_descending_line_ranges_rejected(checkout: Path) -> None:
    with pytest.raises(ValidationError) as loc_exc:
        GeneralReport.model_validate(general_candidate(findings=[general_finding(location={"path": APP_FILE, "start_line": 5, "end_line": 3})]))
    assert "start_line must not exceed end_line" in str(loc_exc.value)

    with pytest.raises(ValidationError) as ev_exc:
        GeneralReport.model_validate(general_candidate(findings=[general_finding(evidence=[{"kind": "file-read", "path": APP_FILE, "lines": [5, 3]}])]))
    assert "not an ascending" in str(ev_exc.value)


def test_schema_version_pinned_to_one(checkout: Path) -> None:
    with pytest.raises(ValidationError):
        GeneralReport.model_validate(general_candidate(schema_version=2))
    report = GeneralReport.model_validate(general_candidate(schema_version=1, report_type="general"))
    assert report.schema_version == 1
    assert report.report_type == "general"


def test_report_type_mismatch_rejected(checkout: Path) -> None:
    with pytest.raises(ValidationError):
        SlopReport.model_validate(slop_candidate(report_type="general"))


def test_validation_preserves_agent_analysis_verbatim(checkout: Path) -> None:
    candidate = slop_candidate(report_type="slop", schema_version=1)
    report = SlopReport.model_validate(candidate)
    raw = candidate["findings"][0]
    f = report.findings[0]
    assert f.label == raw["label"]
    assert f.category == raw["category"]
    assert f.violated_invariant == raw["violated_invariant"]
    assert f.proof_command == raw["proof_command"]
    assert f.pattern == raw["pattern"]
    assert f.task_narrative == raw["task_narrative"]
    assert f.slop_narrative == raw["slop_narrative"]
    assert f.why_it_matters == raw["why_it_matters"]
    assert f.user_surprise == raw["user_surprise"]
    assert f.existential_justification == raw["existential_justification"]
    assert f.failure_mode == raw["failure_mode"]
    assert f.evidence[0].kind == raw["evidence"][0]["kind"]
    assert f.evidence[0].lines == raw["evidence"][0]["lines"]
    assert f.location.start_line == raw["location"]["start_line"]
    assert [str(p) for p in report.review_scope] == candidate["review_scope"]


def test_general_finding_narrative_fields_preserved(checkout: Path) -> None:
    raw = general_finding()
    report = GeneralReport.model_validate(general_candidate())
    f = report.findings[0]
    assert f.symptom == raw["symptom"]
    assert f.source == raw["source"]
    assert f.consequence == raw["consequence"]


def test_general_report_rejects_unknown_policy_code(checkout: Path) -> None:
    raw = general_candidate(findings=[general_finding(policy_code="POLICY.DOES_NOT_EXIST")])

    with pytest.raises(ValidationError, match="unknown policy code"):
        GeneralReport.model_validate(raw)


def test_slop_report_rejects_finding_authored_remediation(checkout: Path) -> None:
    remediation_code = canonical_route("POLICY.NO_MOCK_PROOF").remediation_code
    raw = slop_candidate(
        findings=[
            slop_finding(
                policy_code="POLICY.NO_MOCK_PROOF",
                remediation_code=remediation_code,
            )
        ]
    )

    with pytest.raises(ValidationError, match="remediation_code"):
        SlopReport.model_validate(raw)


def test_finding_fingerprint_is_pinned_and_line_independent(checkout: Path) -> None:
    assert finding_fingerprint("test-quality", APP_FILE) == FINGERPRINT_GENERAL
    assert finding_fingerprint("test-quality", APP_FILE) == finding_fingerprint("test-quality", APP_FILE)
    assert finding_fingerprint("naming", APP_FILE) != FINGERPRINT_GENERAL


def test_nonexistent_evidence_path_rejected(checkout: Path) -> None:
    bad = general_candidate(findings=[general_finding(evidence=[{"kind": "file-read", "path": "src/ghost.py", "lines": [1, 2]}])])
    with pytest.raises(ValidationError) as exc:
        GeneralReport.model_validate(bad)
    assert "evidence[0] path 'src/ghost.py' does not exist" in str(exc.value)
