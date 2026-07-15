"""Compile executable QC tripwires into a maintainer-only audit index.

Authored tripwires declare one policy and never a remediation. This module
joins each rule through the canonical policy record, then derives overlap and
analysis-capability views without making a detector the owner of a policy.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal, NoReturn

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ai_review_ci.gates import BYPASS_DIFF_RULES, DIFF_RULES, DiffRule
from ai_review_ci.policy_index import PolicyIndex, load_policy_index

EngineClass = Literal["python-re", "semgrep", "ast-grep"]
AnalysisCapability = Literal["line-regex", "syntax-tree-query"]
ExecutionScope = Literal["pr-added-lines", "staged-added-lines", "repository"]

_CAPABILITY_RANK: dict[AnalysisCapability, int] = {
    "line-regex": 1,
    "syntax-tree-query": 2,
}

_POLICY_CODE_RE = re.compile(r"POLICY\.[A-Z0-9_]+")
_REMEDIATION_CODE_RE = re.compile(r"REMEDIATE\.[A-Z0-9_]+")
_POLICY_INTERNAL_PATTERNS = (
    re.compile(r"\bdetector\b", re.IGNORECASE),
    re.compile(r"\bsemgrep\b", re.IGNORECASE),
    re.compile(r"\bast-grep\b", re.IGNORECASE),
    re.compile(r"tool-configs/", re.IGNORECASE),
    re.compile(r"\bDIFF_RULES\b"),
    re.compile(r"\bDiffRule\b"),
    re.compile(r"\bqc_lane\b"),
    re.compile(r"\bqc_class\b"),
    re.compile(r"\bbounce_required\b"),
    re.compile(r"\blocal_fix_forbidden\b"),
    re.compile(r"\banalysis_capability\b"),
    re.compile(r"\bsignal_keys?\b"),
    re.compile(r"Mechanical QC Targets", re.IGNORECASE),
)
_SEMANTIC_SEMGREP_KEYS = frozenset(
    {
        "metavariable-pattern",
        "pattern",
        "pattern-inside",
        "pattern-not",
        "pattern-not-inside",
    }
)


class TripwireIndexError(ValueError):
    """Raised when an authored tripwire violates the registry contract."""

    def __init__(self, message: str, *, error_code: str) -> None:
        super().__init__(message)
        self.error_code = error_code


class _RuleMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_code: str


class _SemgrepRule(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    id: str
    message: str
    languages: tuple[str, ...] = Field(min_length=1)
    severity: Literal["ERROR"]
    metadata: _RuleMetadata


class _SemgrepConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rules: tuple[_SemgrepRule, ...] = Field(min_length=1)


class _AstGrepRule(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    id: str
    language: str
    message: str
    severity: Literal["error"]
    metadata: _RuleMetadata


class _AstGrepConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ruleDirs: tuple[str, ...] = Field(min_length=1)


class TripwireRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str
    source: str
    engine_class: EngineClass
    analysis_capability: AnalysisCapability
    execution_scope: ExecutionScope
    language_scope: tuple[str, ...] = Field(min_length=1)
    signal_keys: tuple[str, ...] = Field(min_length=1)
    policy_code: str
    remediation_code: str


class TripwireReference(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str
    source: str
    engine_class: EngineClass
    analysis_capability: AnalysisCapability
    execution_scope: ExecutionScope


class OverlapCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    signal_key: str
    policy_code: str
    tripwires: tuple[TripwireReference, ...]


class InferiorToolCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    signal_key: str
    policy_code: str
    inferior_tripwires: tuple[TripwireReference, ...]
    stronger_tripwires: tuple[TripwireReference, ...]


class PolicyCoverage(BaseModel):
    model_config = ConfigDict(frozen=True)

    policy_code: str
    remediation_code: str
    tripwires: tuple[TripwireReference, ...]


class TripwireIndex(BaseModel):
    model_config = ConfigDict(frozen=True)

    tripwires: tuple[TripwireRecord, ...]
    policies: tuple[PolicyCoverage, ...]
    overlap_candidates: tuple[OverlapCandidate, ...]
    inferior_tool_candidates: tuple[InferiorToolCandidate, ...]
    uncovered_policy_codes: tuple[str, ...]


def _fail(message: str, *, error_code: str) -> NoReturn:
    raise TripwireIndexError(message, error_code=error_code)


def _display_path(path: Path, root: Path) -> str:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    if resolved_path.is_relative_to(resolved_root):
        return resolved_path.relative_to(resolved_root).as_posix()
    return resolved_path.as_posix()


def _load_yaml(path: Path) -> object:
    if not path.is_file():
        _fail(f"missing tripwire source: {path}", error_code="MISSING_TRIPWIRE_SOURCE")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        _fail(f"{path}: invalid YAML: {exc}", error_code="INVALID_RULE_SOURCE")


def _mapping(value: object, *, source: Path, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        _fail(f"{source}: {label} must be a string-keyed mapping", error_code="INVALID_RULE_SOURCE")
    return {str(key): item for key, item in value.items()}


def _sequence(value: object, *, source: Path, label: str) -> tuple[object, ...]:
    if not isinstance(value, list):
        _fail(f"{source}: {label} must be a sequence", error_code="INVALID_RULE_SOURCE")
    return tuple(value)


def _reject_authored_remediation(rule: dict[str, object], *, rule_id: str, source: Path) -> None:
    if "remediation_code" in rule:
        _fail(
            f"{source}: rule {rule_id} declares remediation_code; rules declare only policy_code",
            error_code="RULE_OWNS_REMEDIATION",
        )
    metadata = _mapping(rule["metadata"], source=source, label=f"{rule_id}.metadata")
    if "remediation_code" in metadata:
        _fail(
            f"{source}: rule {rule_id} declares remediation_code; rules declare only policy_code",
            error_code="RULE_OWNS_REMEDIATION",
        )


def _validate_policy(
    *,
    policy_code: str,
    rule_id: str,
    source: Path,
    policy_index: PolicyIndex,
) -> str:
    if policy_code not in policy_index.policies:
        _fail(
            f"{source}: rule {rule_id} references unknown policy {policy_code}",
            error_code="UNKNOWN_RULE_POLICY",
        )
    return policy_index.remediation_for_policy(policy_code).code


def _scope_from_rule(rule: dict[str, object], *, source: Path, languages: tuple[str, ...]) -> tuple[str, ...]:
    scope = [f"language:{language}" for language in languages]
    if "paths" not in rule:
        scope.append("paths:repository")
        return tuple(scope)
    paths = _mapping(rule["paths"], source=source, label="paths")
    for key in ("include", "exclude"):
        if key not in paths:
            continue
        entries = _sequence(paths[key], source=source, label=f"paths.{key}")
        for entry in entries:
            if not isinstance(entry, str):
                _fail(f"{source}: paths.{key} entries must be strings", error_code="INVALID_RULE_SOURCE")
            scope.append(f"path-{key}:{entry}")
    return tuple(scope)


def _has_semantic_pattern(value: object) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _SEMANTIC_SEMGREP_KEYS:
                return True
            if _has_semantic_pattern(item):
                return True
    if isinstance(value, list):
        return any(_has_semantic_pattern(item) for item in value)
    return False


def _tripwire_reference(tripwire: TripwireRecord) -> TripwireReference:
    return TripwireReference(
        rule_id=tripwire.rule_id,
        source=tripwire.source,
        engine_class=tripwire.engine_class,
        analysis_capability=tripwire.analysis_capability,
        execution_scope=tripwire.execution_scope,
    )


def _collect_semgrep_rules(config_path: Path, root: Path, policy_index: PolicyIndex) -> tuple[TripwireRecord, ...]:
    raw_config = _mapping(_load_yaml(config_path), source=config_path, label="config")
    if "rules" not in raw_config:
        _fail(f"{config_path}: missing rules", error_code="INVALID_RULE_SOURCE")
    raw_rules = _sequence(raw_config["rules"], source=config_path, label="rules")
    for position, raw_rule in enumerate(raw_rules):
        raw_rule_mapping = _mapping(raw_rule, source=config_path, label=f"rules[{position}]")
        rule_id_value = raw_rule_mapping["id"] if "id" in raw_rule_mapping else f"rules[{position}]"
        rule_id = str(rule_id_value)
        if "metadata" not in raw_rule_mapping:
            _fail(f"{config_path}: rule {rule_id} has no policy metadata", error_code="RULE_WITHOUT_POLICY")
        _reject_authored_remediation(raw_rule_mapping, rule_id=rule_id, source=config_path)
    try:
        config = _SemgrepConfig.model_validate(raw_config)
    except ValidationError as exc:
        _fail(f"{config_path}: invalid Semgrep rule contract: {exc}", error_code="INVALID_RULE_SOURCE")

    records: list[TripwireRecord] = []
    for raw_rule, semgrep_rule in zip(raw_rules, config.rules, strict=True):
        raw_mapping = _mapping(raw_rule, source=config_path, label=semgrep_rule.id)
        if semgrep_rule.message != semgrep_rule.metadata.policy_code:
            _fail(
                f"{config_path}: rule {semgrep_rule.id} message must equal its policy_code",
                error_code="POLICY_MESSAGE_MISMATCH",
            )
        remediation_code = _validate_policy(
            policy_code=semgrep_rule.metadata.policy_code,
            rule_id=semgrep_rule.id,
            source=config_path,
            policy_index=policy_index,
        )
        capability: AnalysisCapability = "syntax-tree-query" if _has_semantic_pattern(raw_mapping) else "line-regex"
        records.append(
            TripwireRecord(
                rule_id=semgrep_rule.id,
                source=_display_path(config_path, root),
                engine_class="semgrep",
                analysis_capability=capability,
                execution_scope="repository",
                language_scope=_scope_from_rule(raw_mapping, source=config_path, languages=semgrep_rule.languages),
                signal_keys=(semgrep_rule.id,),
                policy_code=semgrep_rule.metadata.policy_code,
                remediation_code=remediation_code,
            )
        )
    return tuple(records)


def collect_semgrep_rules(config_path: Path, root: Path) -> tuple[TripwireRecord, ...]:
    """Collect one Semgrep config against the canonical policy index."""
    return _collect_semgrep_rules(config_path, root, load_policy_index())


def _registered_ast_grep_rule_files(root: Path) -> tuple[Path, ...]:
    config_paths = sorted((root / "tool-configs").rglob("*sgconfig.yml"))
    if not config_paths:
        _fail("no registered ast-grep configs found", error_code="MISSING_TRIPWIRE_SOURCE")
    rule_files: set[Path] = set()
    for config_path in config_paths:
        try:
            config = _AstGrepConfig.model_validate(_load_yaml(config_path))
        except ValidationError as exc:
            _fail(f"{config_path}: invalid ast-grep config: {exc}", error_code="INVALID_RULE_SOURCE")
        for directory in config.ruleDirs:
            rule_dir = (config_path.parent / directory).resolve()
            if not rule_dir.is_dir():
                _fail(f"{config_path}: missing rule directory {rule_dir}", error_code="MISSING_TRIPWIRE_SOURCE")
            rule_files.update(rule_dir.glob("*.yml"))
    return tuple(sorted(rule_files))


def _collect_ast_grep_rules(root: Path, policy_index: PolicyIndex) -> tuple[TripwireRecord, ...]:
    records: list[TripwireRecord] = []
    for path in _registered_ast_grep_rule_files(root):
        raw_rule = _mapping(_load_yaml(path), source=path, label="rule")
        rule_id_value = raw_rule["id"] if "id" in raw_rule else path.stem
        rule_id = str(rule_id_value)
        if "metadata" not in raw_rule:
            _fail(f"{path}: rule {rule_id} has no policy metadata", error_code="RULE_WITHOUT_POLICY")
        _reject_authored_remediation(raw_rule, rule_id=rule_id, source=path)
        try:
            rule = _AstGrepRule.model_validate(raw_rule)
        except ValidationError as exc:
            _fail(f"{path}: invalid ast-grep rule contract: {exc}", error_code="INVALID_RULE_SOURCE")
        if rule.message != rule.metadata.policy_code:
            _fail(
                f"{path}: rule {rule.id} message must equal its policy_code",
                error_code="POLICY_MESSAGE_MISMATCH",
            )
        remediation_code = _validate_policy(
            policy_code=rule.metadata.policy_code,
            rule_id=rule.id,
            source=path,
            policy_index=policy_index,
        )
        records.append(
            TripwireRecord(
                rule_id=rule.id,
                source=_display_path(path, root),
                engine_class="ast-grep",
                analysis_capability="syntax-tree-query",
                execution_scope="repository",
                language_scope=(f"language:{rule.language}", "paths:repository"),
                signal_keys=(rule.id,),
                policy_code=rule.metadata.policy_code,
                remediation_code=remediation_code,
            )
        )
    return tuple(records)


def _diff_scope(rule: DiffRule) -> tuple[str, ...]:
    scope = [f"suffix:{suffix}" for suffix in rule.suffixes]
    if not scope:
        scope.append("suffix:any")
    scope.extend(f"exclude-suffix:{suffix}" for suffix in rule.excluded_suffixes)
    if rule.exclude_config_paths:
        scope.append("exclude:config-paths")
    return tuple(scope)


def _collect_diff_rules(
    rules: tuple[DiffRule, ...],
    *,
    execution_scope: Literal["pr-added-lines", "staged-added-lines"],
    root: Path,
    policy_index: PolicyIndex,
) -> tuple[TripwireRecord, ...]:
    source = root / "src/ai_review_ci/gates.py"
    records: list[TripwireRecord] = []
    for rule in rules:
        remediation_code = _validate_policy(
            policy_code=rule.policy_code,
            rule_id=rule.rule_id,
            source=source,
            policy_index=policy_index,
        )
        records.append(
            TripwireRecord(
                rule_id=rule.rule_id,
                source=_display_path(source, root),
                engine_class="python-re",
                analysis_capability="line-regex",
                execution_scope=execution_scope,
                language_scope=_diff_scope(rule),
                signal_keys=rule.signal_keys,
                policy_code=rule.policy_code,
                remediation_code=remediation_code,
            )
        )
    return tuple(records)


def audit_policy_isolation(root: Path) -> tuple[str, ...]:
    """Return policy/remediation knowledge leaks into the wrong authored surface."""
    findings: list[str] = []
    policy_dir = root / "skills/policy-index"
    policy_paths = sorted(policy_dir.rglob("*.md"))
    remediation_path = root / "skills/style-guide/references/style-guide-index.md"
    for path in (*policy_paths, remediation_path):
        text = path.read_text(encoding="utf-8")
        for pattern in _POLICY_INTERNAL_PATTERNS:
            match = pattern.search(text)
            if match:
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"{_display_path(path, root)}:{line}: QC implementation detail {match.group(0)!r}")
        if path == remediation_path:
            match = _POLICY_CODE_RE.search(text)
            if match:
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"{_display_path(path, root)}:{line}: inverse policy mapping in remediation index")

    canonical_policy_path = root / "skills/policy-index/references/policies.md"
    for path in sorted((root / "skills").rglob("*.md")):
        if path == canonical_policy_path:
            continue
        text = path.read_text(encoding="utf-8")
        if _POLICY_CODE_RE.search(text) and _REMEDIATION_CODE_RE.search(text):
            findings.append(f"{_display_path(path, root)}: scattered policy-to-remediation mapping")
    return tuple(sorted(set(findings)))


def _validate_unique_tripwires(tripwires: tuple[TripwireRecord, ...]) -> None:
    seen: set[tuple[str, str, str]] = set()
    for tripwire in tripwires:
        identity = (tripwire.source, tripwire.execution_scope, tripwire.rule_id)
        if identity in seen:
            _fail(f"duplicate tripwire identity: {identity}", error_code="DUPLICATE_TRIPWIRE")
        seen.add(identity)


def build_tripwire_index(root: Path) -> TripwireIndex:
    """Build the deterministic maintainer audit for all registered tripwires."""
    isolation_findings = audit_policy_isolation(root)
    if isolation_findings:
        _fail("policy isolation audit failed:\n" + "\n".join(isolation_findings), error_code="POLICY_CONTAMINATION")

    policy_index = load_policy_index()
    tripwires = (
        *_collect_semgrep_rules(root / "tool-configs/semgrep.yml", root, policy_index),
        *_collect_ast_grep_rules(root, policy_index),
        *_collect_diff_rules(DIFF_RULES, execution_scope="pr-added-lines", root=root, policy_index=policy_index),
        *_collect_diff_rules(BYPASS_DIFF_RULES, execution_scope="staged-added-lines", root=root, policy_index=policy_index),
    )
    ordered_tripwires = tuple(
        sorted(
            tripwires,
            key=lambda tripwire: (
                tripwire.policy_code,
                tripwire.rule_id,
                tripwire.engine_class,
                tripwire.execution_scope,
                tripwire.source,
            ),
        )
    )
    _validate_unique_tripwires(ordered_tripwires)

    by_signal: dict[str, list[TripwireRecord]] = {}
    by_policy: dict[str, list[TripwireRecord]] = {code: [] for code in policy_index.policies}
    for tripwire in ordered_tripwires:
        by_policy[tripwire.policy_code].append(tripwire)
        for signal_key in tripwire.signal_keys:
            by_signal.setdefault(signal_key, []).append(tripwire)

    overlaps: list[OverlapCandidate] = []
    inferior: list[InferiorToolCandidate] = []
    for signal_key, records in sorted(by_signal.items()):
        if len(records) < 2:
            continue
        policy_codes = {record.policy_code for record in records}
        if len(policy_codes) != 1:
            _fail(
                f"signal {signal_key} maps to conflicting policies: {sorted(policy_codes)}",
                error_code="SIGNAL_POLICY_CONFLICT",
            )
        policy_code = next(iter(policy_codes))
        references = tuple(_tripwire_reference(record) for record in records)
        overlaps.append(OverlapCandidate(signal_key=signal_key, policy_code=policy_code, tripwires=references))
        strongest_rank = max(_CAPABILITY_RANK[record.analysis_capability] for record in records)
        inferior_records = tuple(_tripwire_reference(record) for record in records if _CAPABILITY_RANK[record.analysis_capability] < strongest_rank)
        if inferior_records:
            stronger_records = tuple(_tripwire_reference(record) for record in records if _CAPABILITY_RANK[record.analysis_capability] == strongest_rank)
            inferior.append(
                InferiorToolCandidate(
                    signal_key=signal_key,
                    policy_code=policy_code,
                    inferior_tripwires=inferior_records,
                    stronger_tripwires=stronger_records,
                )
            )

    coverage = tuple(
        PolicyCoverage(
            policy_code=policy_code,
            remediation_code=policy_index.remediation_for_policy(policy_code).code,
            tripwires=tuple(_tripwire_reference(tripwire) for tripwire in by_policy[policy_code]),
        )
        for policy_code in sorted(policy_index.policies)
    )
    uncovered = tuple(policy.policy_code for policy in coverage if not policy.tripwires)
    return TripwireIndex(
        tripwires=ordered_tripwires,
        policies=coverage,
        overlap_candidates=tuple(overlaps),
        inferior_tool_candidates=tuple(inferior),
        uncovered_policy_codes=uncovered,
    )


def tripwire_index() -> None:
    """Print the derived maintainer-only tripwire inventory as deterministic JSON."""
    root = Path(__file__).resolve().parents[2]
    print(build_tripwire_index(root).model_dump_json(indent=2))


def check_tripwire_index() -> None:
    """Validate tripwire, policy, remediation, overlap, and isolation integrity."""
    root = Path(__file__).resolve().parents[2]
    inventory = build_tripwire_index(root)
    print(f"Tripwire index valid: {len(inventory.tripwires)} rules, {len(inventory.overlap_candidates)} overlap candidates.")
