from pathlib import Path

import pytest
import yaml

from ai_review_ci.policy_index import (
    PolicyIndexError,
    canonical_route,
    load_policy_index,
    load_policy_index_from_paths,
    parse_policies,
    parse_remediations,
)


def test_load_policy_index_resolves_policy_to_canonical_remediation() -> None:
    index = load_policy_index()

    policy = index.policy("POLICY.NO_HIDDEN_CONFIG")
    remediation = index.remediation_for_policy("POLICY.NO_HIDDEN_CONFIG")

    assert remediation.code == policy.remediation_code


def test_canonical_route_contains_only_catalogue_identifiers() -> None:
    index = load_policy_index()
    route = canonical_route("POLICY.NO_MOCK_PROOF")

    assert route.policy_code == "POLICY.NO_MOCK_PROOF"
    assert route.remediation_code == index.policy(route.policy_code).remediation_code


def test_dependency_reinvention_routes_through_policy_catalogue() -> None:
    index = load_policy_index()
    policy = index.policy("POLICY.NO_BESPOKE_REINVENTION")
    route = canonical_route(policy.code, index=index)

    assert route.remediation_code == policy.remediation_code
    assert index.remediation(route.remediation_code) == index.remediation_for_policy(policy.code)


def test_every_remediation_route_is_owned_by_a_policy_record() -> None:
    index = load_policy_index()

    owned_routes = {policy.remediation_code for policy in index.policies.values()}
    assert set(index.remediations) == owned_routes


def test_unknown_policy_code_fails_loudly() -> None:
    index = load_policy_index()

    with pytest.raises(PolicyIndexError) as exc_info:
        index.policy("POLICY.DOES_NOT_EXIST")
    assert exc_info.value.error_code == "UNKNOWN_POLICY"


def test_policy_parser_rejects_missing_related_remediation() -> None:
    text = """#### `POLICY.BAD_RECORD` — Bad record

Category: Runtime, Config, and State

Rule: A policy record without a remediation is malformed.

Invalid local fixes: Copying prose into detector messages.

Detection handles: `BAD-HANDLE`
"""

    with pytest.raises(PolicyIndexError) as exc_info:
        parse_policies(text)
    assert exc_info.value.error_code == "MISSING_FIELDS"


def test_load_policy_index_rejects_missing_canonical_file(tmp_path: Path) -> None:
    with pytest.raises(PolicyIndexError) as exc_info:
        load_policy_index_from_paths(tmp_path / "policies.md", tmp_path / "style-guide-index.md")
    assert exc_info.value.error_code == "MISSING_INDEX_FILE"


def test_policy_parser_rejects_empty_policy_source() -> None:
    with pytest.raises(PolicyIndexError) as exc_info:
        parse_policies("# No policies here\n")
    assert exc_info.value.error_code == "EMPTY_SOURCE"


def test_remediation_parser_rejects_empty_remediation_source() -> None:
    with pytest.raises(PolicyIndexError) as exc_info:
        parse_remediations("# No remediation rows here\n")
    assert exc_info.value.error_code == "EMPTY_SOURCE"


def test_remediation_parser_rejects_duplicate_codes() -> None:
    text = """| `REMEDIATE.EXAMPLE` | First construction. |
| `REMEDIATE.EXAMPLE` | Conflicting construction. |
"""

    with pytest.raises(PolicyIndexError) as exc_info:
        parse_remediations(text)

    assert exc_info.value.error_code == "DUPLICATE_REMEDIATION"


def test_semgrep_rules_use_id_only_messages_and_valid_metadata() -> None:
    index = load_policy_index()
    data = yaml.safe_load(Path("tool-configs/semgrep.yml").read_text())

    for rule in data["rules"]:
        policy_code = rule["message"]
        metadata = rule["metadata"]
        assert policy_code == metadata["policy_code"]
        assert policy_code.startswith("POLICY.")
        assert " " not in policy_code
        assert "remediation_code" not in metadata
        index.remediation_for_policy(policy_code)


def test_ast_grep_policy_rules_use_id_only_messages() -> None:
    index = load_policy_index()

    rule_files = [
        *Path("tool-configs/ast-grep/rules").glob("*.yml"),
        *Path("tool-configs/ast-grep/sage-rules").glob("*.yml"),
    ]
    assert rule_files
    for path in rule_files:
        rule = yaml.safe_load(path.read_text())
        policy_code = rule["message"]
        assert policy_code.startswith("POLICY.")
        assert " " not in policy_code
        assert "remediation_code" not in rule["metadata"]
        index.remediation_for_policy(policy_code)


def test_policy_bearing_rules_are_blocking_tier() -> None:
    # Every central rule routes to a POLICY.* code and thence to a remediation
    # (enforced by test_ast_grep_policy_rules_use_id_only_messages and
    # test_semgrep_rules_use_id_only_messages_and_valid_metadata) — there are no
    # non-policy rules. A bridge-burning policy BANS its pattern rather than
    # emitting an ignorable warning, so every rule must sit at the tool's
    # blocking tier: unconditionally, with no exemption. ast-grep blocks on
    # `error`; semgrep blocks on `ERROR`.
    ast_grep_files = [
        *Path("tool-configs/ast-grep/rules").glob("*.yml"),
        *Path("tool-configs/ast-grep/sage-rules").glob("*.yml"),
    ]
    assert ast_grep_files
    for path in ast_grep_files:
        rule = yaml.safe_load(path.read_text())
        assert rule["severity"] == "error", f"{path}: {rule['severity']}"

    semgrep = yaml.safe_load(Path("tool-configs/semgrep.yml").read_text())
    for rule in semgrep["rules"]:
        assert rule["severity"] == "ERROR", f"{rule['id']}: {rule['severity']}"


def test_test_semgrep_fixture_uses_policy_id_metadata() -> None:
    index = load_policy_index()
    data = yaml.safe_load(Path("tool-configs/test-semgrep.yml").read_text())

    for rule in data["rules"]:
        assert rule["message"] == rule["metadata"]["policy_code"]
        assert "remediation_code" not in rule["metadata"]
        index.remediation_for_policy(rule["metadata"]["policy_code"])


def test_remediation_index_contains_constructions_not_inverse_policy_mapping() -> None:
    text = Path("skills/style-guide/references/style-guide-index.md").read_text()

    assert "Policy findings" not in text
    assert "POLICY." not in text


def test_review_manifests_reference_canonical_skills_policy_index() -> None:
    for path in (Path("reviews/general/manifest.txt"), Path("reviews/slop/manifest.txt")):
        manifest = path.read_text()
        assert "vendor/" not in manifest
        assert "../skills/policy-index/SKILL.md" in manifest
        assert "../skills/policy-index/references/policies.md" in manifest
