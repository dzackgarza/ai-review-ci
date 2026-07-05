"""Load the canonical bridge-burning policy index.

The Markdown files under ``skills/policy-index`` are the canonical
database. This module parses only the stable ID-bearing contract in those
files; detector configs and report renderers must resolve policy text here
instead of copying local remediation prose.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

POLICY_INDEX_RELATIVE = Path("skills/policy-index")
POLICIES_FILE = "references/policies.md"
REMEDIATIONS_FILE = "references/remediations.md"

POLICY_RE = re.compile(r"^#### `(POLICY\.[A-Z0-9_]+)` — (.+)$")
FIELD_RE = re.compile(r"^([A-Z][A-Za-z ]+): (.+)$")
REMEDIATION_ROW_RE = re.compile(r"^\| `(REMEDIATE\.[A-Z0-9_]+)` \| (.+?) \| (.+) \|$")
CODE_RE = re.compile(r"`(POLICY\.[A-Z0-9_]+|REMEDIATE\.[A-Z0-9_]+)`")


class PolicyIndexError(ValueError):
    """Raised when the policy index or detector metadata is invalid."""


@dataclass(frozen=True)
class PolicyRecord:
    code: str
    name: str
    category: str
    rule: str
    invalid_local_fixes: str
    detection_handles: tuple[str, ...]
    remediation_code: str


@dataclass(frozen=True)
class RemediationRecord:
    code: str
    applies_to: tuple[str, ...]
    required_remediation: str


@dataclass(frozen=True)
class PolicyIndex:
    policies: dict[str, PolicyRecord]
    remediations: dict[str, RemediationRecord]

    def policy(self, code: str) -> PolicyRecord:
        try:
            return self.policies[code]
        except KeyError as exc:
            raise PolicyIndexError(f"unknown policy code: {code}") from exc

    def remediation(self, code: str) -> RemediationRecord:
        try:
            return self.remediations[code]
        except KeyError as exc:
            raise PolicyIndexError(f"unknown remediation code: {code}") from exc

    def remediation_for_policy(
        self, policy_code: str, remediation_code: str | None = None
    ) -> RemediationRecord:
        policy = self.policy(policy_code)
        code = remediation_code or policy.remediation_code
        remediation = self.remediation(code)
        if (
            policy_code not in remediation.applies_to
            and "Any slop finding" not in remediation.applies_to
        ):
            raise PolicyIndexError(
                f"remediation {code} does not apply to {policy_code}"
            )
        return remediation


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_policy_index_root() -> Path:
    return repo_root() / POLICY_INDEX_RELATIVE


def _fail(message: str) -> NoReturn:
    raise PolicyIndexError(message)


def _read_required(path: Path) -> str:
    if not path.is_file():
        _fail(f"missing policy-index file: {path}")
    return path.read_text()


def _parse_detection_handles(value: str) -> tuple[str, ...]:
    handles = tuple(re.findall(r"`([^`]+)`", value))
    if not handles:
        _fail("policy record missing detection handles")
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
        _fail(f"{code} missing required fields: {', '.join(missing)}")
    remediation_codes = CODE_RE.findall(fields["Related remediation"])
    if len(remediation_codes) != 1 or not remediation_codes[0].startswith("REMEDIATE."):
        _fail(f"{code} must name exactly one related remediation code")
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
                policies[current_code] = _parse_policy_block(
                    current_code, current_name, block
                )
            current_code, current_name = match.groups()
            block = []
            continue
        if current_code is not None:
            block.append(line)
    if current_code is not None:
        policies[current_code] = _parse_policy_block(current_code, current_name, block)
    if not policies:
        _fail("policies.md contained no POLICY records")
    return policies


def parse_remediations(text: str) -> dict[str, RemediationRecord]:
    remediations: dict[str, RemediationRecord] = {}
    for line in text.splitlines():
        match = REMEDIATION_ROW_RE.match(line)
        if not match:
            continue
        code, applies_to_text, required_remediation = match.groups()
        applies_to = tuple(CODE_RE.findall(applies_to_text))
        if not applies_to and "Any slop finding" in applies_to_text:
            applies_to = ("Any slop finding",)
        if not applies_to:
            _fail(f"{code} does not name any applicable policy")
        remediations[code] = RemediationRecord(
            code=code,
            applies_to=applies_to,
            required_remediation=required_remediation,
        )
    if not remediations:
        _fail("remediations.md contained no REMEDIATE records")
    return remediations


def load_policy_index(root: Path | None = None) -> PolicyIndex:
    index_root = root or default_policy_index_root()
    policies = parse_policies(_read_required(index_root / POLICIES_FILE))
    remediations = parse_remediations(_read_required(index_root / REMEDIATIONS_FILE))
    for policy in policies.values():
        if policy.remediation_code not in remediations:
            _fail(
                f"{policy.code} references missing remediation {policy.remediation_code}"
            )
        remediation = remediations[policy.remediation_code]
        if (
            policy.code not in remediation.applies_to
            and "Any slop finding" not in remediation.applies_to
        ):
            _fail(f"{policy.remediation_code} does not apply to {policy.code}")
    return PolicyIndex(policies=policies, remediations=remediations)


def canonical_guidance(
    policy_code: str,
    remediation_code: str | None = None,
    *,
    index: PolicyIndex | None = None,
) -> str:
    policy_index = index or load_policy_index()
    policy = policy_index.policy(policy_code)
    remediation = policy_index.remediation_for_policy(policy_code, remediation_code)
    return "\n".join(
        [
            f"Policy: `{policy.code}` — {policy.name}",
            f"Rule: {policy.rule}",
            f"Invalid local fixes: {policy.invalid_local_fixes}",
            f"Remediation: `{remediation.code}` — {remediation.required_remediation}",
        ]
    )
