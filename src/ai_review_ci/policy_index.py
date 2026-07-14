"""Load the canonical bridge-burning policy index.

The policy records under ``skills/policy-index`` own the policy-to-remediation
edge. The style guide owns remediation constructions but carries no inverse
policy mapping. Detector configs and report renderers resolve the edge here
instead of selecting or copying a remediation.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NoReturn

from pydantic import BaseModel, ConfigDict

POLICIES_RELATIVE = Path("skills/policy-index/references/policies.md")
REMEDIATIONS_RELATIVE = Path("skills/style-guide/references/style-guide-index.md")

POLICY_RE = re.compile(r"^#### `(POLICY\.[A-Z0-9_]+)` — (.+)$")
FIELD_RE = re.compile(r"^([A-Z][A-Za-z ]+): (.+)$")
REMEDIATION_ROW_RE = re.compile(r"^\| `(REMEDIATE\.[A-Z0-9_]+)` \| (.+) \|$")
CODE_RE = re.compile(r"`(POLICY\.[A-Z0-9_]+|REMEDIATE\.[A-Z0-9_]+)`")


class PolicyIndexError(ValueError):
    """Raised when the policy index or detector metadata is invalid.

    Attributes:
        error_code: Machine-readable error classification for structured
            assertion in tests (e.g. ``"UNKNOWN_POLICY"``).
    """

    def __init__(self, message: str, *, error_code: str = "UNKNOWN") -> None:
        super().__init__(message)
        self.error_code = error_code


class PolicyRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    name: str
    category: str
    rule: str
    invalid_local_fixes: str
    detection_handles: tuple[str, ...]
    remediation_code: str


class RemediationRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    required_remediation: str


class PolicyRoute(BaseModel):
    model_config = ConfigDict(frozen=True)

    policy_code: str
    remediation_code: str


class PolicyIndex(BaseModel):
    model_config = ConfigDict(frozen=True)

    policies: dict[str, PolicyRecord]
    remediations: dict[str, RemediationRecord]

    def policy(self, code: str) -> PolicyRecord:
        try:
            return self.policies[code]
        except KeyError as exc:
            raise PolicyIndexError(f"unknown policy code: {code}", error_code="UNKNOWN_POLICY") from exc

    def remediation(self, code: str) -> RemediationRecord:
        try:
            return self.remediations[code]
        except KeyError as exc:
            raise PolicyIndexError(f"unknown remediation code: {code}", error_code="UNKNOWN_REMEDIATION") from exc

    def remediation_for_policy(self, policy_code: str) -> RemediationRecord:
        policy = self.policy(policy_code)
        return self.remediation(policy.remediation_code)

    def route(self, policy_code: str) -> PolicyRoute:
        policy = self.policy(policy_code)
        self.remediation(policy.remediation_code)
        return PolicyRoute(
            policy_code=policy.code,
            remediation_code=policy.remediation_code,
        )


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _fail(message: str, *, error_code: str = "UNKNOWN") -> NoReturn:
    raise PolicyIndexError(message, error_code=error_code)


def _read_required(path: Path) -> str:
    if not path.is_file():
        _fail(f"missing policy-index file: {path}", error_code="MISSING_INDEX_FILE")
    return path.read_text()


def _parse_detection_handles(value: str) -> tuple[str, ...]:
    handles = tuple(re.findall(r"`([^`]+)`", value))
    if not handles:
        _fail("policy record missing detection handles", error_code="INVALID_DETECTION_HANDLES")
    return handles


def _parse_policy_block(code: str, name: str, block: list[str]) -> PolicyRecord:
    fields: dict[str, str] = {}
    for line in block:
        match = FIELD_RE.match(line)
        if match:
            fields[match.group(1)] = match.group(2)
    required = {
        "Category",
        "Rule",
        "Invalid local fixes",
        "Detection handles",
        "Related remediation",
    }
    missing = sorted(required - fields.keys())
    if missing:
        _fail(f"{code} missing required fields: {', '.join(missing)}", error_code="MISSING_FIELDS")
    remediation_codes = CODE_RE.findall(fields["Related remediation"])
    if len(remediation_codes) != 1 or not remediation_codes[0].startswith("REMEDIATE."):
        _fail(f"{code} must name exactly one related remediation code", error_code="MISSING_REMEDIATION")
    return PolicyRecord(
        code=code,
        name=name,
        category=fields["Category"],
        rule=fields["Rule"],
        invalid_local_fixes=fields["Invalid local fixes"],
        detection_handles=_parse_detection_handles(fields["Detection handles"]),
        remediation_code=remediation_codes[0],
    )


def parse_policies(text: str) -> dict[str, PolicyRecord]:
    policies: dict[str, PolicyRecord] = {}
    current_code: str | None = None
    current_name = ""
    block: list[str] = []
    for line in text.splitlines():
        match = POLICY_RE.match(line)
        if match:
            if current_code is not None:
                policies[current_code] = _parse_policy_block(current_code, current_name, block)
            current_code, current_name = match.groups()
            block = []
            continue
        if current_code is not None:
            block.append(line)
    if current_code is not None:
        policies[current_code] = _parse_policy_block(current_code, current_name, block)
    if not policies:
        _fail("policies.md contained no POLICY records", error_code="EMPTY_SOURCE")
    return policies


def parse_remediations(text: str) -> dict[str, RemediationRecord]:
    remediations: dict[str, RemediationRecord] = {}
    for line in text.splitlines():
        match = REMEDIATION_ROW_RE.match(line)
        if not match:
            continue
        code, required_remediation = match.groups()
        remediations[code] = RemediationRecord(
            code=code,
            required_remediation=required_remediation,
        )
    if not remediations:
        _fail("remediations.md contained no REMEDIATE records", error_code="EMPTY_SOURCE")
    return remediations


def load_policy_index_from_paths(policies_path: Path, remediations_path: Path) -> PolicyIndex:
    """Load an index from explicit canonical-source-shaped paths.

    This seam exists for parser tests. Runtime callers use
    :func:`load_policy_index`, whose two source locations are fixed.
    """
    policies = parse_policies(_read_required(policies_path))
    remediations = parse_remediations(_read_required(remediations_path))
    for policy in policies.values():
        if policy.remediation_code not in remediations:
            _fail(f"{policy.code} references missing remediation {policy.remediation_code}", error_code="MISSING_REMEDIATION")
    return PolicyIndex(policies=policies, remediations=remediations)


def load_policy_index() -> PolicyIndex:
    root = repo_root()
    return load_policy_index_from_paths(
        root / POLICIES_RELATIVE,
        root / REMEDIATIONS_RELATIVE,
    )


def canonical_route(policy_code: str, *, index: PolicyIndex | None = None) -> PolicyRoute:
    policy_index = index or load_policy_index()
    return policy_index.route(policy_code)
