"""Convert a validated review report artifact to SARIF 2.1.0.

The SARIF file is uploaded as GitHub code scanning alerts. The ``category``
argument is written to ``run.automationDetails.id`` — use
"ai-general-review" or "ai-slop-review" to match GitHub category
expectations from upload-sarif's category parameter.

Each finding becomes one SARIF result. The partialFingerprint is the
deterministic ``finding_fingerprint`` hash of (category, path) — stable
across line shifts so the same finding maps to the same code scanning
alert across runs.

Inputs are artifacts produced by ``validate-report``: the model-required
keys are indexed directly, so feeding an unvalidated file fails loudly.
Keys that are report-type-specific (symptom/consequence for general,
pattern/why_it_matters for slop) or agent-supplied extras (remedy) are
forwarded by presence.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

from ai_review_ci.models import finding_fingerprint

JsonDict = dict[str, Any]

SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/"
    "master/Schemata/sarif-schema-2.1.0.json"
)

CATEGORY_PREFIX = "ai-review"

_OPTIONAL_PROPERTY_KEYS = (
    ("symptom", "symptom"),
    ("consequence", "consequence"),
    ("remedy", "remedy"),
    ("proof_command", "proof_command"),
    ("pattern", "slop_pattern"),
    ("why_it_matters", "why_it_matters"),
)


def _tool_name(report_type: str) -> str:
    return f"{CATEGORY_PREFIX}/{report_type}"


def _tier_to_level(tier: str) -> str:
    return "error" if tier == "tier1" else "warning"


def _rule_for(finding: JsonDict) -> JsonDict:
    """SARIF rule entry seeded from the first finding of its category."""
    return {
        "id": finding["category"],
        "name": finding["label"],
        "shortDescription": {"text": finding["violated_invariant"][:200]},
        "defaultConfiguration": {"level": _tier_to_level(finding["tier"])},
    }


def _region(start_line: int, end_line: int) -> JsonDict:
    region: JsonDict = {"startLine": start_line}
    if end_line != start_line:
        region["endLine"] = end_line
    return region


def _result_properties(finding: JsonDict) -> JsonDict:
    properties: JsonDict = {
        "label": finding["label"],
        "tier": finding["tier"],
        "category": finding["category"],
    }
    for key, prop_name in _OPTIONAL_PROPERTY_KEYS:
        if key in finding:
            properties[prop_name] = finding[key]
    return properties


def _sarif_result(finding: JsonDict, rule_index: int) -> JsonDict:
    loc = finding["location"]
    return {
        "ruleId": finding["category"],
        "ruleIndex": rule_index,
        "level": _tier_to_level(finding["tier"]),
        "message": {"text": finding["violated_invariant"]},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": loc["path"],
                        "uriBaseId": "%ROOT%",
                    },
                    "region": _region(loc["start_line"], loc["end_line"]),
                }
            }
        ],
        "partialFingerprints": {
            "reviewFindingKey": finding_fingerprint(finding["category"], loc["path"])
        },
        "properties": _result_properties(finding),
    }


def build_sarif(artifact: JsonDict, report_type: str, category: str) -> JsonDict:
    """Build the full SARIF document from a validated artifact."""
    findings: list[JsonDict] = artifact["findings"]
    run_sha = os.environ["GITHUB_SHA"]

    seen_rules: dict[str, int] = {}
    rules: list[JsonDict] = []
    results: list[JsonDict] = []

    for finding in findings:
        finding_category = finding["category"]
        if finding_category not in seen_rules:
            seen_rules[finding_category] = len(rules)
            rules.append(_rule_for(finding))
        results.append(_sarif_result(finding, seen_rules[finding_category]))

    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": _tool_name(report_type),
                        "informationUri": f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}",
                        "rules": rules,
                    }
                },
                "automationDetails": {
                    "id": category,
                },
                "results": results,
                "originalUriBaseIds": {
                    "%ROOT%": {"uri": "file:///github/workspace/"},
                },
                "properties": {
                    "repo_sha": run_sha,
                    "report_type": report_type,
                },
            }
        ],
    }


def to_sarif(artifact: Path, output: Path, category: str) -> None:
    """Convert a validated review report artifact to SARIF 2.1.0.

    Args:
        artifact: Path to validated .review-report-artifact.json.
        output: Path to write .review-report.sarif.
        category: run.automationDetails.id (e.g. ai-general-review or ai-slop-review).
    """
    if not artifact.is_file():
        print(f"FATAL: artifact not found: {artifact}", file=sys.stderr)
        sys.exit(1)

    data: JsonDict = json.loads(artifact.read_text())

    report_type = data.get("report_type", "")
    if report_type not in ("general", "slop"):
        print(
            f"FATAL: unknown report_type '{report_type}' in artifact",
            file=sys.stderr,
        )
        sys.exit(1)

    sarif = build_sarif(data, report_type, category=category)

    output.write_text(json.dumps(sarif, indent=2))

    n = len(sarif["runs"][0]["results"])
    print(f"SARIF written to {output} ({n} findings)")
