import json
import pathlib
import subprocess
import sys
import tomllib
from typing import Any

import pytest

from ai_review_ci.doctor import DoctorReport, doctor_report, manifest_text
from ai_review_ci.install import _write_trigger_workflows

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
            exceptions=(),
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
        exceptions=(),
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
        "exceptions": [],
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
        "intentional_exception",
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
            exceptions=(),
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
            exceptions=(),
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
    justfile_findings = [
        finding
        for finding in payload["findings"]
        if finding["surface"] == "justfile_conformance"
    ]
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


def test_doctor_classifies_non_github_remote_branch_protection_as_unverifiable(tmp_path: pathlib.Path) -> None:
    project = create_target(tmp_path, "python")
    assert run_git(project, "remote", "add", "origin", str(tmp_path / "not-github.git")).returncode == 0

    status, payload = status_for(project)

    assert status == "unverifiable"
    assert payload["installation_state"] == "unknown"
    assert payload["branch_protection"]["observed_state"] == "unverifiable"
    assert payload["findings"][0]["surface"] == "branch_protection"


def test_active_manifest_exception_maps_matching_findings_to_intentional_exception(tmp_path: pathlib.Path) -> None:
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

    status, payload = status_for(project)

    assert status == "intentional_exception"
    assert payload["installation_state"] == "noncompliant"
    assert payload["exceptions"][0]["id"] == "app-boot-bootstrap"
