import json
import pathlib
import subprocess
import sys
import tomllib
from typing import Any

import pytest
from pydantic import ValidationError

from ai_review_ci.doctor import (
    DoctorReport,
    QcManifest,
    _classify,
    _evaluate_label_alignment,
    _has_private_attribute,
    _justfile_recipes,
    _label_alignment_findings,
    doctor_report,
    manifest_text,
)
from ai_review_ci.install import _write_trigger_workflows
from ai_review_ci.labels import RemoteLabel, load_taxonomy
from ai_review_ci.review_guidelines import load_canonical_review_guidelines

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCTOR_SCHEMA = ROOT / "schemas" / "doctor-report.schema.json"
DOCTOR_EXAMPLE = ROOT / "schemas" / "examples" / "doctor-report-current-python.json"


def run_git(workdir: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(workdir), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def init_git_repo(project: pathlib.Path) -> None:
    assert run_git(project, "init", "-q").returncode == 0
    assert run_git(project, "config", "user.email", "doctor-test@example.invalid").returncode == 0
    assert run_git(project, "config", "user.name", "Doctor Test").returncode == 0
    (project / "README.md").write_text("# target\n")
    assert run_git(project, "add", "README.md").returncode == 0
    commit = run_git(project, "-c", "core.hooksPath=/dev/null", "commit", "-m", "baseline")
    assert commit.returncode == 0, commit.stdout + commit.stderr


def create_target(tmp_path: pathlib.Path, profile: str) -> pathlib.Path:
    project = tmp_path / f"{profile}-target"
    project.mkdir()
    init_git_repo(project)
    write_profile_shape(project, profile)
    # A conformant target carries the current review-guidelines section; tests that probe
    # its absence delete this file explicitly (see the missing-AGENTS.md gate tests).
    (project / "AGENTS.md").write_text(f"# {profile} target\n\nIntro.\n\n{load_canonical_review_guidelines()}\n", encoding="utf-8")
    (project / "justfile").write_text((ROOT / "scaffolds" / profile / "justfile").read_text())
    _write_trigger_workflows(project, profile)
    (project / ".ai-review-ci.toml").write_text(
        manifest_text(
            profile=profile,
            installed_ref="main",
            release_channel="main",
            workflow_template_version=1,
            local_delegation="global-justfile",
            default_branch="main",
        )
    )
    return project


def write_profile_shape(project: pathlib.Path, profile: str) -> None:
    if profile == "python":
        (project / "pyproject.toml").write_text('[project]\nname = "target"\nversion = "0.1.0"\n')
    elif profile == "bun":
        (project / "package.json").write_text(json.dumps({"scripts": {}}) + "\n")
        (project / "bun.lock").write_text("")
    elif profile == "bun-playwright":
        (project / "package.json").write_text(json.dumps({"scripts": {}}) + "\n")
        (project / "bun.lock").write_text("")
        (project / "playwright.config.ts").write_text("export default {};\n")
    elif profile == "rust":
        (project / "Cargo.toml").write_text('[package]\nname = "target"\nversion = "0.1.0"\nedition = "2024"\n')
    elif profile == "sage":
        (project / "example.sage").write_text("x = 1\n")
    else:
        raise AssertionError(f"unsupported test profile {profile}")


def status_for(project: pathlib.Path) -> tuple[str, dict[str, Any]]:
    report = doctor_report(project)
    payload = report.model_dump(mode="json")
    return str(payload["global_status"]), payload


@pytest.mark.parametrize("profile", ["python", "bun", "bun-playwright", "rust", "sage"])
def test_doctor_reports_current_for_installed_profile_targets(tmp_path: pathlib.Path, profile: str) -> None:
    project = create_target(tmp_path, profile)

    status, payload = status_for(project)

    assert status == "current"
    assert payload["installation_state"] == "compliant"
    assert payload["declared_profile"] == profile
    assert payload["effective_profile"] == profile
    assert payload["findings"] == []
    assert payload["branch_protection"]["observed_state"] == "not_applicable"
    assert "qc-doctor / qc-doctor" in payload["branch_protection"]["required_contexts"]
    assert payload["justfile_delegation"]["test"]["observed"]["caller_root_preserved"] is True
    assert payload["workflow_refs"]["review-pr.yml"]["observed_ref"] == "main"


def test_manifest_text_round_trips_through_toml_parser() -> None:
    text = manifest_text(
        profile="python",
        installed_ref="main",
        release_channel="main",
        workflow_template_version=1,
        local_delegation="global-justfile",
        default_branch="main",
    )

    parsed = tomllib.loads(text)

    assert parsed == {
        "schema_version": 1,
        "profile": "python",
        "installed_ref": "main",
        "release_channel": "main",
        "workflow_template_version": 1,
        "local_delegation": "global-justfile",
        "default_branch": "main",
    }


def test_doctor_cli_exits_zero_only_for_current_target(tmp_path: pathlib.Path) -> None:
    project = create_target(tmp_path, "python")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ai_review_ci.cli",
            "doctor",
            "--target",
            str(project),
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stdout + result.stderr
    assert payload["global_status"] == "current"


def test_doctor_flags_missing_agents_md_as_error(tmp_path: pathlib.Path) -> None:
    # A repo carrying no AGENTS.md carries zero review guidance for the reviewers that
    # read it — a false-green the always-on doctor must fail loud, not soften (#215).
    project = create_target(tmp_path, "python")
    (project / "AGENTS.md").unlink(missing_ok=True)

    status, payload = status_for(project)

    assert status == "misconfigured"
    review_findings = [f for f in payload["findings"] if f["surface"] == "review_guidelines"]
    assert len(review_findings) == 1, payload["findings"]
    assert "missing" in review_findings[0]["evidence"]


def test_doctor_cli_fails_the_gate_when_no_agents_md(tmp_path: pathlib.Path) -> None:
    # The gate boundary: `ai-review-ci doctor` must exit nonzero on a repo with no
    # AGENTS.md, so the qc-doctor check cannot pass a repo missing review guidance.
    project = create_target(tmp_path, "python")
    (project / "AGENTS.md").unlink(missing_ok=True)

    result = subprocess.run(
        [sys.executable, "-m", "ai_review_ci.cli", "doctor", "--target", str(project), "--json"],
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode != 0, result.stdout + result.stderr
    assert payload["global_status"] == "misconfigured"


def test_doctor_schema_cli_exports_producer_owned_contract() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "ai_review_ci.cli", "doctor-schema"],
        text=True,
        capture_output=True,
        check=False,
    )

    schema = json.loads(result.stdout)
    assert result.returncode == 0, result.stdout + result.stderr
    assert schema["title"] == "DoctorReport"
    assert schema["properties"]["global_status"]["enum"] == [
        "current",
        "stale",
        "misconfigured",
        "unverifiable",
    ]
    assert schema["additionalProperties"] is False


def test_doctor_schema_artifact_matches_exported_contract() -> None:
    schema = json.loads(DOCTOR_SCHEMA.read_text(encoding="utf-8"))

    assert schema == DoctorReport.model_json_schema()


def test_doctor_golden_example_validates_against_owned_model() -> None:
    report = DoctorReport.model_validate_json(DOCTOR_EXAMPLE.read_text(encoding="utf-8"))

    assert report.schema_version == 1
    assert report.global_status == "current"
    assert report.effective_profile == "python"


def test_doctor_classifies_outdated_workflow_refs_as_stale(tmp_path: pathlib.Path) -> None:
    project = create_target(tmp_path, "python")
    (project / ".ai-review-ci.toml").write_text(
        manifest_text(
            profile="python",
            installed_ref="release/v1",
            release_channel="stable",
            workflow_template_version=1,
            local_delegation="global-justfile",
            default_branch="main",
        )
    )

    status, payload = status_for(project)

    assert status == "stale"
    assert payload["installation_state"] == "outdated"
    assert payload["findings"][0]["surface"] == "workflow_ref"
    assert payload["workflow_refs"]["review-pr.yml"]["required_ref"] == "release/v1"
    assert payload["workflow_refs"]["review-pr.yml"]["observed_ref"] == "main"


def test_doctor_classifies_missing_manifest_as_misconfigured(tmp_path: pathlib.Path) -> None:
    project = create_target(tmp_path, "python")
    (project / ".ai-review-ci.toml").unlink()

    status, payload = status_for(project)

    assert status == "misconfigured"
    assert payload["installation_state"] == "uninstalled"
    assert payload["findings"][0]["surface"] == "manifest"


def test_doctor_classifies_wrong_profile_shape_as_misconfigured(tmp_path: pathlib.Path) -> None:
    project = create_target(tmp_path, "python")
    (project / ".ai-review-ci.toml").write_text(
        manifest_text(
            profile="rust",
            installed_ref="main",
            release_channel="main",
            workflow_template_version=1,
            local_delegation="global-justfile",
            default_branch="main",
        )
    )

    status, payload = status_for(project)

    assert status == "misconfigured"
    assert payload["installation_state"] == "noncompliant"
    assert payload["effective_profile"] == "python"
    assert payload["findings"][0]["surface"] == "profile"


def test_doctor_classifies_missing_workflow_as_misconfigured(tmp_path: pathlib.Path) -> None:
    project = create_target(tmp_path, "python")
    (project / ".github" / "workflows" / "review-pr.yml").unlink()

    status, payload = status_for(project)

    assert status == "misconfigured"
    assert payload["installation_state"] == "noncompliant"
    assert payload["findings"][0]["surface"] == "workflow"


def test_doctor_classifies_missing_bun_playwright_app_boot_as_misconfigured(tmp_path: pathlib.Path) -> None:
    project = create_target(tmp_path, "bun-playwright")
    (project / "justfile").write_text((ROOT / "scaffolds" / "bun" / "justfile").read_text())

    status, payload = status_for(project)

    assert status == "misconfigured"
    assert payload["installation_state"] == "noncompliant"
    assert payload["findings"][0]["surface"] == "justfile_delegation"
    assert payload["justfile_delegation"]["app-boot"]["observed"]["present"] is False


def test_doctor_classifies_wrong_caller_root_delegation_as_misconfigured(tmp_path: pathlib.Path) -> None:
    project = create_target(tmp_path, "python")
    (project / "justfile").write_text(
        "\n".join(
            [
                "test:",
                "    @just -f ~/ai-review-ci/justfiles/python.just test",
                "",
                "test-ci:",
                "    @just -f ~/ai-review-ci/justfiles/python.just test-ci",
                "",
            ]
        )
    )

    status, payload = status_for(project)

    assert status == "misconfigured"
    assert payload["installation_state"] == "noncompliant"
    assert payload["justfile_delegation"]["test"]["observed"]["caller_root_preserved"] is False
    assert payload["findings"][0]["remediation_commands"] == ["just install-qc-scaffold python <target-repo>"]


def test_doctor_reports_justfile_baseline_violations(tmp_path: pathlib.Path) -> None:
    project = create_target(tmp_path, "python")
    (project / "justfile").write_text(
        "\n".join(
            [
                "test:",
                "    @just -f ~/ai-review-ci/justfiles/python.just -d . test",
                "",
                "# Run push-tier Python QC through the central implementation.",
                "test-ci:",
                "    @just -f ~/ai-review-ci/justfiles/python.just -d . test-ci",
                "",
            ]
        )
    )

    status, payload = status_for(project)

    assert status == "misconfigured"
    justfile_findings = [finding for finding in payload["findings"] if finding["surface"] == "justfile_conformance"]
    assert [finding["evidence"].split(" ", 1)[1] for finding in justfile_findings] == [
        "header-comment: justfile must begin with a comment block",
        "default-recipe: no default recipe; bare just must list recipes",
        "public-recipe-doc: recipe `test` has no immediate # doc comment",
    ]


def test_check_justfile_cli_reports_baseline_violations(tmp_path: pathlib.Path) -> None:
    project = create_target(tmp_path, "python")
    (project / "justfile").write_text(
        "\n".join(
            [
                "# Delegates Python QC.",
                "",
                "# Run commit-tier Python QC through the central implementation.",
                "test:",
                "    @just -f ~/ai-review-ci/justfiles/python.just -d . test",
                "",
                "# Run push-tier Python QC through the central implementation.",
                "test-ci:",
                "    @just -f ~/ai-review-ci/justfiles/python.just -d . test-ci",
                "",
            ]
        )
    )

    result = subprocess.run(
        [sys.executable, "-m", "ai_review_ci.cli", "check-justfile", "--target", str(project)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "justfile_conformance" in result.stderr
    assert "default-recipe" in result.stderr


def test_doctor_justfile_parser_accepts_parameter_defaults_and_recipe_attributes(tmp_path: pathlib.Path) -> None:
    project = create_target(tmp_path, "python")
    (project / "justfile").write_text(
        "\n".join(
            [
                "# Delegates Python QC.",
                'api_url := "https://example.invalid:443"',
                "",
                "# List available recipes.",
                "[no-cd]",
                "default:",
                "    @just --list",
                "",
                "# Run commit-tier Python QC through the central implementation.",
                "[no-cd]",
                'test mode="fast":',
                "    @just -f ~/ai-review-ci/justfiles/python.just -d . test",
                "",
                "# Run push-tier Python QC through the central implementation.",
                "test-ci:",
                "    @just -f ~/ai-review-ci/justfiles/python.just -d . test-ci",
                "",
            ]
        )
    )

    status, payload = status_for(project)

    assert status == "current"
    assert payload["findings"] == []


def test_justfile_parser_accepts_trailing_dash_recipe_names_and_indented_private_attributes() -> None:
    lines = [
        "# Example justfile.",
        "test-recipe-:",
        "    @true",
        "",
        "  [private]",
        "helper:",
        "    @true",
    ]

    assert _justfile_recipes(lines)["test-recipe-"] == 2
    assert _has_private_attribute(lines, 6)


def test_doctor_classifies_non_github_remote_branch_protection_as_unverifiable(tmp_path: pathlib.Path) -> None:
    project = create_target(tmp_path, "python")
    assert run_git(project, "remote", "add", "origin", str(tmp_path / "not-github.git")).returncode == 0

    status, payload = status_for(project)

    assert status == "unverifiable"
    assert payload["installation_state"] == "unknown"
    assert payload["branch_protection"]["observed_state"] == "unverifiable"
    assert payload["findings"][0]["surface"] == "branch_protection"


def _compliant_manifest() -> QcManifest:
    return QcManifest.model_validate(
        {
            "schema_version": 1,
            "profile": "python",
            "installed_ref": "main",
            "release_channel": "main",
            "workflow_template_version": 1,
            "local_delegation": "global-justfile",
            "default_branch": "main",
        }
    )


def test_label_alignment_flags_missing_drifted_variant_and_ignores_extras() -> None:
    # #216: compare live labels against the canonical taxonomy on name + color +
    # description. Missing, drifted, and case/spelling variants are misalignments;
    # extra repo-specific labels are NOT flagged.
    canonical = load_taxonomy()
    by_name = {label.name: label for label in canonical}
    bug = by_name["bug"]
    enhancement = by_name["enhancement"]
    remote = {label.name: RemoteLabel(name=label.name, color=label.color, description=label.description) for label in canonical}
    # drift `enhancement`'s color; delete `bug`, re-add it only as a case variant `Bug`;
    # add an extra repo-specific label that must be ignored.
    remote["enhancement"] = RemoteLabel(name="enhancement", color="000000", description=enhancement.description)
    del remote["bug"]
    remote["Bug"] = RemoteLabel(name="Bug", color=bug.color, description=bug.description)
    remote["kilo-triaged"] = RemoteLabel(name="kilo-triaged", color="faf74f", description="repo-specific extra")

    observation = _evaluate_label_alignment(remote, canonical, evidence="test")

    assert observation.observed_state == "misaligned"
    assert observation.drifted == ("enhancement",)
    assert any(v.canonical == "bug" and "Bug" in v.remote_variants for v in observation.variants)
    assert "bug" not in observation.missing  # bug is a variant, not merely missing
    assert "kilo-triaged" not in observation.missing
    assert "kilo-triaged" not in observation.drifted


def test_label_alignment_compliant_when_repo_carries_canonical_set_exactly() -> None:
    canonical = load_taxonomy()
    remote = {label.name: RemoteLabel(name=label.name, color=label.color, description=label.description) for label in canonical}
    remote["kilo-triaged"] = RemoteLabel(name="kilo-triaged", color="faf74f", description="extra allowed")

    observation = _evaluate_label_alignment(remote, canonical, evidence="test")

    assert observation.observed_state == "compliant"
    assert observation.missing == ()
    assert observation.drifted == ()
    assert observation.variants == ()


def test_label_alignment_misalignment_is_a_required_error_feeding_global_status() -> None:
    # Mirror the qc-doctor contract: a real misalignment is a required (error) finding,
    # so it drives global_status to misconfigured (doctor exits nonzero / qc-doctor fails).
    canonical = load_taxonomy()
    by_name = {label.name: label for label in canonical}
    remote = {label.name: RemoteLabel(name=label.name, color=label.color, description=label.description) for label in canonical}
    # Exercise all three misalignment kinds so the finding message names each:
    # a case variant (bug -> Bug), a missing label (enhancement removed entirely),
    # and a drifted color (chore).
    del remote["bug"]
    remote["Bug"] = RemoteLabel(name="Bug", color=by_name["bug"].color, description=by_name["bug"].description)
    del remote["enhancement"]
    remote["chore"] = RemoteLabel(name="chore", color="000000", description=by_name["chore"].description)

    observation = _evaluate_label_alignment(remote, canonical, evidence="test")
    findings = _label_alignment_findings(observation)

    assert len(findings) == 1
    assert findings[0].surface == "label_alignment"
    assert findings[0].severity == "error"
    assert "missing" in findings[0].evidence
    assert "drifted" in findings[0].evidence
    assert "Bug" in findings[0].evidence
    _, global_status = _classify(_compliant_manifest(), findings)
    assert global_status == "misconfigured"


def test_manifest_declaring_exceptions_is_rejected_not_honored(tmp_path: pathlib.Path) -> None:
    """A manifest that declares an exception is invalid config; there is no suppression path."""
    project = create_target(tmp_path, "bun-playwright")
    (project / "justfile").write_text((ROOT / "scaffolds" / "bun" / "justfile").read_text())
    (project / ".ai-review-ci.toml").write_text(
        "\n".join(
            [
                "schema_version = 1",
                'profile = "bun-playwright"',
                'installed_ref = "main"',
                'release_channel = "main"',
                "workflow_template_version = 1",
                'local_delegation = "global-justfile"',
                'default_branch = "main"',
                "",
                "[[exceptions]]",
                'id = "app-boot-bootstrap"',
                'surface = "justfile_delegation"',
                'reason = "tracked downstream bootstrap exception"',
                "active = true",
                "",
            ]
        )
    )

    with pytest.raises(ValidationError):
        doctor_report(project)


def test_active_findings_are_noncompliant_with_no_exception_path(tmp_path: pathlib.Path) -> None:
    """A repo with active findings is noncompliant; nothing maps findings to a passing status."""
    project = create_target(tmp_path, "bun-playwright")
    (project / "justfile").write_text((ROOT / "scaffolds" / "bun" / "justfile").read_text())

    status, payload = status_for(project)

    assert status == "misconfigured"
    assert payload["installation_state"] == "noncompliant"
    assert payload["findings"]
    assert "exceptions" not in payload
