from pathlib import Path

import pytest
import yaml

from ai_review_ci.policy_index import (
    PolicyIndexError,
    canonical_guidance,
    load_policy_index,
    parse_policies,
    parse_remediations,
)


def test_load_policy_index_resolves_policy_to_canonical_remediation() -> None:
    index = load_policy_index()

    policy = index.policy("POLICY.NO_HIDDEN_CONFIG")
    remediation = index.remediation_for_policy("POLICY.NO_HIDDEN_CONFIG")

    assert policy.name == "No hidden behavioral config in code"
    assert policy.remediation_code == "REMEDIATE.TOTAL_CONFIG_MODEL"
    assert remediation.required_remediation.startswith(
        "Put required configuration in the declared config surface"
    )


def test_canonical_guidance_uses_policy_and_remediation_records() -> None:
    guidance = canonical_guidance("POLICY.NO_MOCK_PROOF")

    assert "Policy: `POLICY.NO_MOCK_PROOF`" in guidance
    assert "Rule: Mocks, fakes, stubs" in guidance
    assert "Remediation: `REMEDIATE.REAL_PROOF_LOOP`" in guidance


def test_unknown_policy_code_fails_loudly() -> None:
    index = load_policy_index()

    with pytest.raises(PolicyIndexError, match="unknown policy code"):
        index.policy("POLICY.DOES_NOT_EXIST")


def test_policy_parser_rejects_missing_related_remediation() -> None:
    text = """#### `POLICY.BAD_RECORD` — Bad record

Category: Runtime, Config, and State

Rule: A policy record without a remediation is malformed.

Invalid local fixes: Copying prose into detector messages.

Detection handles: `BAD-HANDLE`
"""

    with pytest.raises(PolicyIndexError, match="Related remediation"):
        parse_policies(text)


def test_load_policy_index_rejects_missing_canonical_file(tmp_path: Path) -> None:
    with pytest.raises(PolicyIndexError, match="missing policy-index file"):
        load_policy_index(tmp_path)


def test_policy_parser_rejects_empty_policy_source() -> None:
    with pytest.raises(PolicyIndexError, match="contained no POLICY records"):
        parse_policies("# No policies here\n")


def test_remediation_parser_rejects_empty_remediation_source() -> None:
    with pytest.raises(PolicyIndexError, match="contained no REMEDIATE records"):
        parse_remediations("# No remediation rows here\n")


def test_semgrep_rules_use_id_only_messages_and_valid_metadata() -> None:
    index = load_policy_index()
    data = yaml.safe_load(Path("tool-configs/semgrep.yml").read_text())

    for rule in data["rules"]:
        policy_code = rule["message"]
        metadata = rule["metadata"]
        remediation_code = metadata["remediation_code"]
        assert policy_code == metadata["policy_code"]
        assert policy_code.startswith("POLICY.")
        assert " " not in policy_code
        index.remediation_for_policy(policy_code, remediation_code)


def test_ast_grep_policy_rules_use_id_only_messages() -> None:
    index = load_policy_index()

    for path in Path("tool-configs/ast-grep/rules").glob("*.yml"):
        rule = yaml.safe_load(path.read_text())
        policy_code = rule["message"]
        assert policy_code.startswith("POLICY.")
        assert " " not in policy_code
        index.remediation_for_policy(policy_code, rule["metadata"]["remediation_code"])


def test_test_semgrep_fixture_uses_policy_id_metadata() -> None:
    index = load_policy_index()
    data = yaml.safe_load(Path("tool-configs/test-semgrep.yml").read_text())

    for rule in data["rules"]:
        assert rule["message"] == rule["metadata"]["policy_code"]
        index.remediation_for_policy(
            rule["metadata"]["policy_code"], rule["metadata"]["remediation_code"]
        )


def test_review_manifests_reference_canonical_skills_policy_index() -> None:
    for path in (
        Path("reviews/general/manifest.txt"),
        Path("reviews/slop/manifest.txt"),
    ):
        manifest = path.read_text()
        assert "vendor/" not in manifest
        assert "../skills/policy-index/SKILL.md" in manifest
        assert "../skills/policy-index/references/policies.md" in manifest
