from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from ai_review_ci.policy_index import (
    PolicyIndexError,
    canonical_guidance,
    load_policy_index,
    load_vendor_manifest,
    parse_policies,
)


def test_load_policy_index_resolves_policy_to_canonical_remediation() -> None:
    index = load_policy_index()

    policy = index.policy("POLICY.NO_HIDDEN_CONFIG")
    remediation = index.remediation_for_policy("POLICY.NO_HIDDEN_CONFIG")

    assert policy.name == "No hidden behavioral config in code"
    assert policy.remediation_code == "REMEDIATE.TOTAL_CONFIG_MODEL"
    assert remediation.required_remediation.startswith("Put required configuration in the declared config surface")


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


def test_vendor_manifest_pins_clean_source_ref_and_file_hashes() -> None:
    manifest = load_vendor_manifest()
    source = cast(dict[str, Any], manifest["source"])
    copied_files = cast(dict[str, dict[str, str]], manifest["copied_files"])

    assert source["repo"] == "dzackgarza/ai"
    assert source["ref"]
    assert copied_files["SKILL.md"]["sha256"]
    assert copied_files["references/policies.md"]["sha256"]


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
        index.remediation_for_policy(rule["metadata"]["policy_code"], rule["metadata"]["remediation_code"])


def test_detector_policy_and_remediation_ids_resolve_for_all_policy_surfaces() -> None:
    index = load_policy_index()
    detector_pairs: list[tuple[Path, str, str]] = []

    for path in (Path("tool-configs/semgrep.yml"), Path("tool-configs/test-semgrep.yml")):
        for rule in yaml.safe_load(path.read_text())["rules"]:
            detector_pairs.append((path, rule["metadata"]["policy_code"], rule["metadata"]["remediation_code"]))

    for path in Path("tool-configs/ast-grep/rules").glob("*.yml"):
        rule = yaml.safe_load(path.read_text())
        detector_pairs.append((path, rule["metadata"]["policy_code"], rule["metadata"]["remediation_code"]))

    assert detector_pairs, "expected policy-bearing detector metadata"
    for path, policy_code, remediation_code in detector_pairs:
        assert policy_code.startswith("POLICY."), f"{path}: non-policy id {policy_code}"
        assert remediation_code.startswith("REMEDIATE."), f"{path}: non-remediation id {remediation_code}"
        index.remediation_for_policy(policy_code, remediation_code)


def test_remediation_catalog_contains_before_after_examples() -> None:
    text = Path("reviews/vendor/policy-index/references/remediations.md").read_text()

    for heading in ("[FALLBACK-HEDGE]", "[SWALLOW-CATCH]", "[PARTIAL-RESULT]"):
        section = text.split(f"### {heading}", 1)[1].split("\n### ", 1)[0]
        assert "BAD:" in section, f"{heading} is missing a bad example"
        assert "Remediation:" in section, f"{heading} is missing a remediation example"


def test_review_manifests_do_not_reference_flattened_policy_index() -> None:
    for path in (Path("reviews/general/manifest.txt"), Path("reviews/slop/manifest.txt")):
        manifest = path.read_text()
        assert "vendor/policy-index.md" not in manifest
        assert "vendor/policy-index/SKILL.md" in manifest
        assert "vendor/policy-index/references/policies.md" in manifest
