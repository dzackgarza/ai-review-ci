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
from typing import Any, NoReturn

from sarif_pydantic import (
    ArtifactLocation,
    Location,
    Message,
    PhysicalLocation,
    Region,
    ReportingConfiguration,
    ReportingDescriptor,
    Result,
    Run,
    Sarif,
    Tool,
    ToolDriver,
)

from ai_review_ci.models import finding_fingerprint
from ai_review_ci.policy_index import canonical_guidance, load_policy_index

JsonDict = dict[str, Any]

SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json"

CATEGORY_PREFIX = "ai-review"
REVIEW_AGENT = "opencode-ai"
REVIEW_PROMPT_VERSION = "1"

_OPTIONAL_PROPERTY_KEYS = (
    ("policy_code", "policy_code"),
    ("remediation_code", "remediation_code"),
    ("symptom", "symptom"),
    ("consequence", "consequence"),
    ("proof_command", "proof_command"),
    ("pattern", "slop_pattern"),
    ("why_it_matters", "why_it_matters"),
)

CARRY_FORWARD_SCHEMA_VERSION = 1


def _die(message: str) -> NoReturn:
    print(f"FATAL: {message}", file=sys.stderr)
    sys.exit(1)


def _mapping(value: object, label: str) -> JsonDict:
    if not isinstance(value, dict):
        _die(f"invalid JSON payload: {label} must be an object")
    mapping: JsonDict = {}
    for key, item in value.items():
        if not isinstance(key, str):
            _die(f"invalid JSON payload: {label} keys must be strings")
        mapping[key] = item
    return mapping


def _mapping_list(value: object, label: str) -> list[JsonDict]:
    if not isinstance(value, list):
        _die(f"invalid JSON payload: {label} must be a list")
    entries: list[JsonDict] = []
    for index, entry in enumerate(value):
        entries.append(_mapping(entry, f"{label}[{index}]"))
    return entries


def _string(mapping: JsonDict, key: str, label: str) -> str:
    value: object = mapping.get(key)
    if not isinstance(value, str) or not value:
        _die(f"invalid carry-forward alert: {label}.{key} must be a non-empty string")
    return value


def _integer(mapping: JsonDict, key: str, label: str) -> int:
    value: object = mapping.get(key)
    if not isinstance(value, int):
        _die(f"invalid carry-forward alert: {label}.{key} must be an integer")
    return value


def _tool_name(report_type: str) -> str:
    return f"{CATEGORY_PREFIX}/{report_type}"


def _reviewer_identity(report_type: str) -> JsonDict:
    return {
        "type": report_type,
        "agent": REVIEW_AGENT,
        "prompt_id": f"reviews/{report_type}",
        "prompt_version": REVIEW_PROMPT_VERSION,
    }


def _tier_to_level(tier: str) -> str:
    return "error" if tier == "tier1" else "warning"


def _level_to_tier(level: str) -> str:
    if level == "error":
        return "tier1"
    if level in {"warning", "note"}:
        return "tier2"
    _die(f"invalid carry-forward alert: alert.rule.severity is unsupported: {level}")


def _rule_for(finding: JsonDict) -> ReportingDescriptor:
    """SARIF rule entry seeded from the first finding of its category."""
    policy_code = finding.get("policy_code")
    if isinstance(policy_code, str):
        policy = load_policy_index().policy(policy_code)
        return ReportingDescriptor(
            id=finding["category"],
            name=finding["label"],
            shortDescription=Message(text=f"{policy.code}: {policy.name}"[:200]),
            defaultConfiguration=ReportingConfiguration(level=_tier_to_level(finding["tier"])),
            properties={
                "policy_code": policy.code,
                "remediation_code": policy.remediation_code,
            },
        )
    return ReportingDescriptor(
        id=finding["category"],
        name=finding["label"],
        shortDescription=Message(text=finding["violated_invariant"][:200]),
        defaultConfiguration=ReportingConfiguration(level=_tier_to_level(finding["tier"])),
    )


def _rule_for_alert(alert: JsonDict) -> ReportingDescriptor:
    rule = _mapping(alert.get("rule"), "alert.rule")
    return ReportingDescriptor(
        id=_string(rule, "id", "alert.rule"),
        name=_string(rule, "name", "alert.rule"),
        shortDescription=Message(text=_string(rule, "description", "alert.rule")[:200]),
        defaultConfiguration=ReportingConfiguration(level=_string(rule, "severity", "alert.rule")),
    )


def _region(start_line: int, end_line: int) -> Region:
    return Region(startLine=start_line, endLine=end_line if end_line != start_line else None)


def _result_properties(finding: JsonDict, report_type: str) -> JsonDict:
    properties: JsonDict = {
        "label": finding["label"],
        "tier": finding["tier"],
        "category": finding["category"],
        "reviewer": _reviewer_identity(report_type),
    }
    policy_code = finding.get("policy_code")
    if isinstance(policy_code, str):
        policy = load_policy_index().policy(policy_code)
        properties["policy_code"] = policy.code
        remediation_code = finding.get("remediation_code")
        properties["remediation_code"] = remediation_code if isinstance(remediation_code, str) else policy.remediation_code
    for key, prop_name in _OPTIONAL_PROPERTY_KEYS:
        if prop_name in properties:
            continue
        if key in finding:
            properties[prop_name] = finding[key]
    return properties


def _sarif_result(finding: JsonDict, rule_index: int, report_type: str) -> Result:
    loc = finding["location"]
    message_text = finding["violated_invariant"]
    policy_code = finding.get("policy_code")
    if isinstance(policy_code, str):
        remediation_code = finding.get("remediation_code")
        message_text = f"{message_text}\n\n{canonical_guidance(policy_code, remediation_code if isinstance(remediation_code, str) else None)}"
    return Result(
        ruleId=finding["category"],
        ruleIndex=rule_index,
        level=_tier_to_level(finding["tier"]),
        message=Message(text=message_text),
        locations=[
            Location(
                physicalLocation=PhysicalLocation(
                    artifactLocation=ArtifactLocation(
                        uri=loc["path"],
                        uriBaseId="%ROOT%",
                    ),
                    region=_region(loc["start_line"], loc["end_line"]),
                )
            )
        ],
        partialFingerprints={"reviewFindingKey": finding_fingerprint(finding["category"], loc["path"])},
        properties=_result_properties(finding, report_type),
    )


def _alert_fingerprint(alert: JsonDict) -> str:
    rule = _mapping(alert.get("rule"), "alert.rule")
    instance = _mapping(alert.get("most_recent_instance"), "alert.most_recent_instance")
    loc = _mapping(instance.get("location"), "alert.most_recent_instance.location")
    return finding_fingerprint(
        _string(rule, "id", "alert.rule"),
        _string(loc, "path", "alert.most_recent_instance.location"),
    )


def _alert_region(location: JsonDict) -> Region:
    start_line = _integer(location, "start_line", "alert.most_recent_instance.location")
    end_line = location.get("end_line")
    if end_line is None:
        end_line = start_line
    if not isinstance(end_line, int):
        _die("invalid carry-forward alert: location.end_line must be an integer")
    return _region(start_line, end_line)


def _sarif_result_for_alert(alert: JsonDict, rule_index: int) -> Result:
    rule = _mapping(alert.get("rule"), "alert.rule")
    instance = _mapping(alert.get("most_recent_instance"), "alert.most_recent_instance")
    message = _mapping(instance.get("message"), "alert.most_recent_instance.message")
    loc = _mapping(instance.get("location"), "alert.most_recent_instance.location")
    category = _string(rule, "id", "alert.rule")
    label = _string(rule, "name", "alert.rule")
    level = _string(rule, "severity", "alert.rule")
    path = _string(loc, "path", "alert.most_recent_instance.location")
    return Result(
        ruleId=category,
        ruleIndex=rule_index,
        level=level,
        message=Message(text=_string(message, "text", "alert.most_recent_instance.message")),
        locations=[
            Location(
                physicalLocation=PhysicalLocation(
                    artifactLocation=ArtifactLocation(
                        uri=path,
                        uriBaseId="%ROOT%",
                    ),
                    region=_alert_region(loc),
                )
            )
        ],
        partialFingerprints={"reviewFindingKey": finding_fingerprint(category, path)},
        properties={
            "label": label,
            "tier": _level_to_tier(level),
            "category": category,
        },
    )


def _result_fingerprint(finding: JsonDict) -> str:
    loc = finding["location"]
    return finding_fingerprint(finding["category"], loc["path"])


def _append_result(
    seen_rules: dict[str, int],
    rules: list[ReportingDescriptor],
    results: list[Result],
    rule_id: str,
    rule: ReportingDescriptor,
    result: Result,
) -> None:
    if rule_id not in seen_rules:
        seen_rules[rule_id] = len(rules)
        rules.append(rule)
    result.rule_index = seen_rules[rule_id]
    results.append(result)


def _carried_open_alerts(carried_alerts: list[JsonDict], report_type: str) -> list[JsonDict]:
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
    findings = _mapping_list(artifact.get("findings"), "artifact.findings")
    run_sha = os.environ["GITHUB_SHA"]
    new_fingerprints = {_result_fingerprint(finding) for finding in findings}

    seen_rules: dict[str, int] = {}
    rules: list[ReportingDescriptor] = []
    results: list[Result] = []

    for alert in _carried_open_alerts(carried_alerts or [], report_type):
        if _alert_fingerprint(alert) in new_fingerprints:
            continue
        rule = _rule_for_alert(alert)
        _append_result(
            seen_rules,
            rules,
            results,
            rule.id,
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
            _sarif_result(finding, 0, report_type),
        )

    sarif = Sarif(
        schema_uri=SARIF_SCHEMA,
        version=SARIF_VERSION,
        runs=[
            Run(
                tool=Tool(
                    driver=ToolDriver(
                        name=_tool_name(report_type),
                        informationUri=f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}",
                        rules=rules,
                    )
                ),
                automationDetails={"id": category},
                results=results,
                originalUriBaseIds={
                    "%ROOT%": ArtifactLocation(uri="file:///github/workspace/"),
                },
                properties={
                    "repo_sha": run_sha,
                    "report_type": report_type,
                },
            )
        ],
    )
    return sarif.model_dump(by_alias=True, exclude_none=True)


def _load_carried_alerts(path: Path | None) -> list[JsonDict]:
    if path is None:
        return []
    if not path.is_file():
        _die(f"carry-forward alerts file not found: {path}")
    payload = _mapping(json.loads(path.read_text()), "carry_forward")
    if payload.get("schema_version") != CARRY_FORWARD_SCHEMA_VERSION:
        _die(f"unsupported carry-forward alerts schema in {path}")
    return _mapping_list(payload.get("alerts"), "carry_forward.alerts")


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

    data = _mapping(json.loads(artifact.read_text()), "artifact")

    report_type = _string(data, "report_type", "artifact")
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
