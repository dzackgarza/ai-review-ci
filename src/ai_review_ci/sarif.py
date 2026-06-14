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

CARRY_FORWARD_SCHEMA_VERSION = 1


def _die(message: str) -> None:
    print(f"FATAL: {message}", file=sys.stderr)
    sys.exit(1)


def _mapping(value: object, label: str) -> JsonDict:
    if not isinstance(value, dict):
        _die(f"invalid carry-forward alert: {label} must be an object")
    return value


def _string(mapping: JsonDict, key: str, label: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        _die(f"invalid carry-forward alert: {label}.{key} must be a non-empty string")
    return value


def _integer(mapping: JsonDict, key: str, label: str) -> int:
    value = mapping.get(key)
    if not isinstance(value, int):
        _die(f"invalid carry-forward alert: {label}.{key} must be an integer")
    return value


def _tool_name(report_type: str) -> str:
    return f"{CATEGORY_PREFIX}/{report_type}"


def _tier_to_level(tier: str) -> str:
    return "error" if tier == "tier1" else "warning"


def _level_to_tier(level: str) -> str:
    if level == "error":
        return "tier1"
    if level in {"warning", "note"}:
        return "tier2"
    _die(f"invalid carry-forward alert: alert.rule.severity is unsupported: {level}")


def _rule_for(finding: JsonDict) -> JsonDict:
    """SARIF rule entry seeded from the first finding of its category."""
    return {
        "id": finding["category"],
        "name": finding["label"],
        "shortDescription": {"text": finding["violated_invariant"][:200]},
        "defaultConfiguration": {"level": _tier_to_level(finding["tier"])},
    }


def _rule_for_alert(alert: JsonDict) -> JsonDict:
    rule = _mapping(alert.get("rule"), "alert.rule")
    return {
        "id": _string(rule, "id", "alert.rule"),
        "name": _string(rule, "name", "alert.rule"),
        "shortDescription": {
            "text": _string(rule, "description", "alert.rule")[:200]
        },
        "defaultConfiguration": {
            "level": _string(rule, "severity", "alert.rule")
        },
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


def _alert_fingerprint(alert: JsonDict) -> str:
    rule = _mapping(alert.get("rule"), "alert.rule")
    instance = _mapping(alert.get("most_recent_instance"), "alert.most_recent_instance")
    loc = _mapping(instance.get("location"), "alert.most_recent_instance.location")
    return finding_fingerprint(
        _string(rule, "id", "alert.rule"),
        _string(loc, "path", "alert.most_recent_instance.location"),
    )


def _alert_region(location: JsonDict) -> JsonDict:
    start_line = _integer(location, "start_line", "alert.most_recent_instance.location")
    end_line = location.get("end_line")
    if end_line is None:
        end_line = start_line
    if not isinstance(end_line, int):
        _die("invalid carry-forward alert: location.end_line must be an integer")
    return _region(start_line, end_line)


def _sarif_result_for_alert(alert: JsonDict, rule_index: int) -> JsonDict:
    rule = _mapping(alert.get("rule"), "alert.rule")
    instance = _mapping(alert.get("most_recent_instance"), "alert.most_recent_instance")
    message = _mapping(instance.get("message"), "alert.most_recent_instance.message")
    loc = _mapping(instance.get("location"), "alert.most_recent_instance.location")
    category = _string(rule, "id", "alert.rule")
    label = _string(rule, "name", "alert.rule")
    level = _string(rule, "severity", "alert.rule")
    path = _string(loc, "path", "alert.most_recent_instance.location")
    return {
        "ruleId": category,
        "ruleIndex": rule_index,
        "level": level,
        "message": {
            "text": _string(message, "text", "alert.most_recent_instance.message")
        },
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": path,
                        "uriBaseId": "%ROOT%",
                    },
                    "region": _alert_region(loc),
                }
            }
        ],
        "partialFingerprints": {
            "reviewFindingKey": finding_fingerprint(category, path)
        },
        "properties": {
            "label": label,
            "tier": _level_to_tier(level),
            "category": category,
        },
    }


def _result_fingerprint(finding: JsonDict) -> str:
    loc = finding["location"]
    return finding_fingerprint(finding["category"], loc["path"])


def _append_result(
    seen_rules: dict[str, int],
    rules: list[JsonDict],
    results: list[JsonDict],
    rule_id: str,
    rule: JsonDict,
    result: JsonDict,
) -> None:
    if rule_id not in seen_rules:
        seen_rules[rule_id] = len(rules)
        rules.append(rule)
    result["ruleIndex"] = seen_rules[rule_id]
    results.append(result)


def _carried_open_alerts(
    carried_alerts: list[JsonDict], report_type: str
) -> list[JsonDict]:
    target_tool = _tool_name(report_type)
    alerts: list[JsonDict] = []
    for entry in carried_alerts:
        tool_name = _string(entry, "tool_name", "carry_forward_entry")
        if tool_name != target_tool:
            continue
        alert = _mapping(entry.get("alert"), "carry_forward_entry.alert")
        state = _string(alert, "state", "carry_forward_entry.alert")
        if state == "open":
            alerts.append(alert)
        elif state not in ("dismissed", "fixed", "closed"):
            _die(f"invalid carry-forward alert state: {state}")
    return alerts


def build_sarif(
    artifact: JsonDict,
    report_type: str,
    category: str,
    carried_alerts: list[JsonDict] | None = None,
) -> JsonDict:
    """Build the full SARIF document from a validated artifact."""
    findings: list[JsonDict] = artifact["findings"]
    run_sha = os.environ["GITHUB_SHA"]
    new_fingerprints = {_result_fingerprint(finding) for finding in findings}

    seen_rules: dict[str, int] = {}
    rules: list[JsonDict] = []
    results: list[JsonDict] = []

    for alert in _carried_open_alerts(carried_alerts or [], report_type):
        if _alert_fingerprint(alert) in new_fingerprints:
            continue
        rule = _rule_for_alert(alert)
        _append_result(
            seen_rules,
            rules,
            results,
            rule["id"],
            rule,
            _sarif_result_for_alert(alert, 0),
        )

    for finding in findings:
        finding_category = finding["category"]
        _append_result(
            seen_rules,
            rules,
            results,
            finding_category,
            _rule_for(finding),
            _sarif_result(finding, 0),
        )

    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": _tool_name(report_type),
                        "informationUri": (
                            f"{os.environ['GITHUB_SERVER_URL']}/"
                            f"{os.environ['GITHUB_REPOSITORY']}"
                        ),
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


def _load_carried_alerts(path: Path | None) -> list[JsonDict]:
    if path is None:
        return []
    if not path.is_file():
        _die(f"carry-forward alerts file not found: {path}")
    payload = json.loads(path.read_text())
    if payload.get("schema_version") != CARRY_FORWARD_SCHEMA_VERSION:
        _die(f"unsupported carry-forward alerts schema in {path}")
    alerts = payload.get("alerts")
    if not isinstance(alerts, list):
        _die(f"invalid carry-forward alerts file: {path}")
    for entry in alerts:
        _mapping(entry, "carry_forward_entry")
    return alerts


def to_sarif(
    artifact: Path,
    output: Path,
    category: str,
    carry_forward_alerts: Path | None = None,
) -> None:
    """Convert a validated review report artifact to SARIF 2.1.0.

    Args:
        artifact: Path to validated .review-report-artifact.json.
        output: Path to write .review-report.sarif.
        category: run.automationDetails.id (e.g. ai-general-review or ai-slop-review).
        carry_forward_alerts: JSON sidecar of existing open alerts to keep in
            the uploaded ledger snapshot.
    """
    if not artifact.is_file():
        _die(f"artifact not found: {artifact}")

    data: JsonDict = json.loads(artifact.read_text())

    report_type = data.get("report_type", "")
    if report_type not in ("general", "slop"):
        _die(f"unknown report_type '{report_type}' in artifact")

    sarif = build_sarif(
        data,
        report_type,
        category=category,
        carried_alerts=_load_carried_alerts(carry_forward_alerts),
    )

    output.write_text(json.dumps(sarif, indent=2))

    n = len(sarif["runs"][0]["results"])
    print(f"SARIF written to {output} ({n} findings)")
