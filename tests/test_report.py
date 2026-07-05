import json
import pathlib

import pytest

from ai_review_ci.models import finding_fingerprint
from ai_review_ci.report import enforce_report_status, report_metadata
from tests.conftest import APP_FILE, general_candidate, general_finding


def test_report_metadata_emits_structured_findings(
    tmp_path: pathlib.Path, checkout: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    artifact = tmp_path / "artifact.json"
    artifact.write_text(json.dumps(general_candidate(findings=[general_finding()])))

    report_metadata(artifact)

    payload = json.loads(capsys.readouterr().out)
    assert payload["report_type"] == "general"
    assert payload["finding_count"] == 1
    assert payload["tier1_count"] == 1
    assert payload["findings"] == [
        {
            "fingerprint": finding_fingerprint("test-quality", APP_FILE),
            "tier": "tier1",
            "type": "general",
            "category": "test-quality",
            "label": "SUPPRESSED_ERROR",
            "path": APP_FILE,
            "line": 3,
            "end_line": 5,
            "status": "open",
        }
    ]


def test_enforce_report_status_fails_only_for_tier1(
    tmp_path: pathlib.Path, checkout: pathlib.Path
) -> None:
    tier1 = tmp_path / "tier1.json"
    tier1.write_text(
        json.dumps(general_candidate(findings=[general_finding(tier="tier1")]))
    )
    tier2 = tmp_path / "tier2.json"
    tier2.write_text(
        json.dumps(
            general_candidate(findings=[general_finding(tier="tier2", category="docs")])
        )
    )

    with pytest.raises(SystemExit):
        enforce_report_status(tier1)

    enforce_report_status(tier2)
