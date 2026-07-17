from pathlib import Path

import pytest

from ai_review_ci.policy_index import canonical_route
from ai_review_ci.tripwire_index import (
    TripwireIndexError,
    audit_policy_isolation,
    build_tripwire_index,
    collect_semgrep_rules,
)

ROOT = Path(__file__).parent.parent


def test_inventory_derives_remediation_and_reports_cross_capability_overlap() -> None:
    inventory = build_tripwire_index(ROOT)

    or_tripwires = [tripwire for tripwire in inventory.tripwires if tripwire.rule_id == "ts-no-or-default"]
    expected_remediation = canonical_route("POLICY.RUNTIME_DEFAULT").remediation_code
    assert {tripwire.remediation_code for tripwire in or_tripwires} == {expected_remediation}
    assert {tripwire.engine_class for tripwire in or_tripwires} == {
        "python-re",
        "semgrep",
    }

    overlap = next(candidate for candidate in inventory.overlap_candidates if candidate.signal_key == "ts-no-or-default")
    assert {tripwire.engine_class for tripwire in overlap.tripwires} == {
        "python-re",
        "semgrep",
    }

    weaker = next(candidate for candidate in inventory.inferior_tool_candidates if candidate.signal_key == "ts-no-or-default")
    assert {tripwire.analysis_capability for tripwire in weaker.inferior_tripwires} == {"line-regex"}
    assert {tripwire.analysis_capability for tripwire in weaker.stronger_tripwires} == {"syntax-tree-query"}


def test_inventory_includes_staged_bypass_rules_from_their_executable_registry() -> None:
    inventory = build_tripwire_index(ROOT)

    staged_double_cast = [tripwire for tripwire in inventory.tripwires if tripwire.rule_id == "no-double-cast" and tripwire.execution_scope == "staged-added-lines"]
    assert len(staged_double_cast) == 1
    assert staged_double_cast[0].policy_code == "POLICY.NO_TYPE_ESCAPE"


def test_rule_local_remediation_is_rejected_even_when_it_matches_policy(tmp_path: Path) -> None:
    config = tmp_path / "semgrep.yml"
    remediation_code = canonical_route("POLICY.RUNTIME_DEFAULT").remediation_code
    config.write_text(
        f"""rules:
  - id: copied-remediation
    message: POLICY.RUNTIME_DEFAULT
    languages: [python]
    severity: ERROR
    pattern: os.getenv($KEY, $DEFAULT)
    metadata:
      policy_code: POLICY.RUNTIME_DEFAULT
      remediation_code: {remediation_code}
"""
    )

    with pytest.raises(TripwireIndexError) as exc_info:
        collect_semgrep_rules(config, ROOT)

    assert exc_info.value.error_code == "RULE_OWNS_REMEDIATION"
    assert "copied-remediation" in str(exc_info.value)
    assert str(config) in str(exc_info.value)


def test_top_level_rule_remediation_is_rejected(tmp_path: Path) -> None:
    config = tmp_path / "semgrep.yml"
    config.write_text(
        """rules:
  - id: copied-remediation
    message: POLICY.RUNTIME_DEFAULT
    languages: [python]
    severity: ERROR
    pattern: os.getenv($KEY, $DEFAULT)
    remediation_code: REMEDIATE.REQUIRE_EXPLICIT_INPUT
    metadata:
      policy_code: POLICY.RUNTIME_DEFAULT
""",
        encoding="utf-8",
    )

    with pytest.raises(TripwireIndexError) as exc_info:
        collect_semgrep_rules(config, ROOT)

    assert exc_info.value.error_code == "RULE_OWNS_REMEDIATION"


def test_malformed_rule_yaml_fails_with_tripwire_error(tmp_path: Path) -> None:
    config = tmp_path / "semgrep.yml"
    config.write_text("rules: [\n", encoding="utf-8")

    with pytest.raises(TripwireIndexError) as exc_info:
        collect_semgrep_rules(config, ROOT)

    assert exc_info.value.error_code == "INVALID_RULE_SOURCE"
    assert str(config) in str(exc_info.value)


@pytest.mark.parametrize(
    "operator, clause",
    [
        ("pattern", "'os.getenv($KEY, $DEFAULT)'"),
        ("pattern-inside", "'def $FUNC(...): ...'"),
        ("pattern-not", "'os.getenv($KEY)'"),
        ("pattern-not-inside", "'if $COND: ...'"),
        ("metavariable-pattern", "{metavariable: '$VALUE', pattern: '$DEFAULT'}"),
    ],
)
def test_semgrep_semantic_operators_are_classified_as_syntax_tree_queries(
    tmp_path: Path,
    operator: str,
    clause: str,
) -> None:
    config = tmp_path / "semgrep.yml"
    config.write_text(
        f"""rules:
  - id: semantic-rule
    message: POLICY.RUNTIME_DEFAULT
    languages: [python]
    severity: ERROR
    {operator}: {clause}
    metadata:
      policy_code: POLICY.RUNTIME_DEFAULT
""",
        encoding="utf-8",
    )

    (rule,) = collect_semgrep_rules(config, ROOT)

    assert rule.analysis_capability == "syntax-tree-query"


def test_semgrep_regex_only_rule_is_classified_as_line_regex(tmp_path: Path) -> None:
    config = tmp_path / "semgrep.yml"
    config.write_text(
        """rules:
  - id: regex-rule
    message: POLICY.RUNTIME_DEFAULT
    languages: [regex]
    severity: ERROR
    pattern-regex: getenv
    metadata:
      policy_code: POLICY.RUNTIME_DEFAULT
""",
        encoding="utf-8",
    )

    (rule,) = collect_semgrep_rules(config, ROOT)

    assert rule.analysis_capability == "line-regex"


def test_unknown_rule_policy_identifies_rule_and_source(tmp_path: Path) -> None:
    config = tmp_path / "semgrep.yml"
    config.write_text(
        """rules:
  - id: unknown-policy-rule
    message: POLICY.DOES_NOT_EXIST
    languages: [python]
    severity: ERROR
    pattern: os.getenv($KEY, $DEFAULT)
    metadata:
      policy_code: POLICY.DOES_NOT_EXIST
"""
    )

    with pytest.raises(TripwireIndexError) as exc_info:
        collect_semgrep_rules(config, ROOT)

    assert exc_info.value.error_code == "UNKNOWN_RULE_POLICY"
    assert "unknown-policy-rule" in str(exc_info.value)
    assert str(config) in str(exc_info.value)


def test_policies_without_tripwires_are_reported_not_reclassified_as_errors() -> None:
    inventory = build_tripwire_index(ROOT)

    assert "POLICY.NO_EXCEPTION_CONTROL_FLOW" in inventory.uncovered_policy_codes


def test_policy_material_is_isolated_from_tripwire_implementation_and_mapping_copies() -> None:
    assert audit_policy_isolation(ROOT) == ()
