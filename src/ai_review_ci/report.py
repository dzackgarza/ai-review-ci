"""Validate candidate report JSON against the pydantic report models.

``validate_report`` is the single admission gate for review reports: it
stamps the tool-owned identification fields (``report_type``,
``schema_version``) when the candidate omits them, validates the candidate
against the model selected by ``report_type``, and writes the validated
artifact. Agent-supplied values for the stamped fields are admitted only
when they match exactly — the models pin them with ``Literal`` types.

The report contains analysis only — findings, scope, surfaces. All run
provenance (commit, ref, repo) is owned by the CI environment and attached
at SARIF conversion/upload, never by the agent or this tool.

Exit codes: 0 on valid, 1 on any validation failure with diagnostic
messages carrying FIX guidance.
"""

import json
import sys
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from ai_review_ci.models import MODEL_BY_TYPE

ReportType = Literal["general", "slop"]

SCHEMA_VERSION = 1


def validate_report(path: Path, report_type: ReportType, output: Path) -> None:
    """Validate a candidate report and write the artifact.

    The report contains analysis only — findings, scope, surfaces. All
    run provenance (commit, ref, repo) is owned by the CI environment and
    attached at SARIF conversion/upload, never by the agent or this tool.

    Args:
        path: Path to the candidate report JSON file.
        report_type: Type of report — "general" or "slop".
        output: Where to write the validated artifact.
    """
    if not path.is_file():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    try:
        data: dict[str, object] = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        print(
            f"Report validation FAILED:\n  invalid JSON in {path}: {exc}\n"
            f"  FIX: the candidate must be a single valid JSON document."
        )
        sys.exit(1)

    if "report_type" not in data:
        data["report_type"] = report_type
    if "schema_version" not in data:
        data["schema_version"] = SCHEMA_VERSION

    try:
        MODEL_BY_TYPE[report_type].model_validate(data)
    except ValidationError as exc:
        print(f"Report validation FAILED:\n  {exc}")
        sys.exit(1)

    output.write_text(json.dumps(data, indent=2) + "\n")
    print("Report validation PASSED")


def report_schema(report_type: ReportType) -> None:
    """Dump JSON Schema for a report type.

    Args:
        report_type: Which report schema to dump — "general" or "slop".
    """
    print(json.dumps(MODEL_BY_TYPE[report_type].model_json_schema(), indent=2))


def report_metadata(path: Path) -> None:
    """Print machine-parseable metadata from a validated artifact.

    Args:
        path: Path to the validated artifact JSON file.
    """
    if not path.is_file():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(path.read_text())

    findings = data["findings"]
    result = {
        "report_type": data["report_type"],
        "finding_count": len(findings),
        "tier1_count": sum(1 for f in findings if f["tier"] == "tier1"),
        "tier2_count": sum(1 for f in findings if f["tier"] == "tier2"),
    }
    print(json.dumps(result))
