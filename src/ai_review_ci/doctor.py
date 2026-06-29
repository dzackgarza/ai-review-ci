"""QC doctor manifest parsing and target repository observations."""

import hashlib
import json as jsonlib
import re
import subprocess
import sys
import tomllib
from collections.abc import Mapping
from importlib.metadata import version
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from cyclopts import Parameter
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from ai_review_ci.gates import PROJECT_PROFILES, SUPPORTED_PROFILES, ProjectProfile, required_check_contexts
from ai_review_ci.install import TEMPLATES

MANIFEST_NAME = ".ai-review-ci.toml"
SCHEMA_VERSION: Literal[1] = 1
WORKFLOW_TEMPLATE_VERSION: Literal[1] = 1
LOCAL_DELEGATION_MODE = "global-justfile"
DOCTOR_CHECK_CONTEXT = "qc-doctor / qc-doctor"
MISSING_JUSTFILE_NAME = ".ai-review-ci-missing-justfile"

ProfileName = Literal["python", "bun", "bun-playwright", "rust", "sage"]
ObservedProfile = Literal["python", "bun", "bun-playwright", "rust", "sage", "unknown"]
InstallationState = Literal["compliant", "outdated", "noncompliant", "uninstalled", "unknown"]
GlobalStatus = Literal["current", "stale", "misconfigured", "unverifiable", "intentional_exception"]
FindingSeverity = Literal["error", "warning"]
FindingSurface = Literal[
    "manifest",
    "profile",
    "workflow",
    "workflow_ref",
    "justfile_delegation",
    "justfile_conformance",
    "branch_protection",
]
BranchProtectionState = Literal["not_applicable", "compliant", "missing", "missing_contexts", "unverifiable"]

JsonDict = dict[str, Any]
ProfileAdapter: TypeAdapter[ProfileName] = TypeAdapter(ProfileName)
UNKNOWN_PROFILE: ObservedProfile = "unknown"


class ManifestException(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    surface: FindingSurface
    reason: str
    active: bool


class QcManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    profile: ProfileName
    installed_ref: str = Field(min_length=1)
    release_channel: str = Field(min_length=1)
    workflow_template_version: Literal[1]
    local_delegation: Literal["global-justfile"]
    default_branch: str = Field(min_length=1)
    exceptions: tuple[ManifestException, ...] = ()


class MissingManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    present: Literal[False]
    reason: str


ManifestDeclaration = QcManifest | MissingManifest


class TargetObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root: str
    remote: str
    head: str


class DeclarationObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str
    manifest: ManifestDeclaration


class ProfileProofObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: ProfileName
    required_paths: tuple[str, ...]
    missing_paths: tuple[str, ...]


class WorkflowRefObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    required_ref: str
    observed_ref: str
    required_gates: tuple[str, ...]
    observed_gates: tuple[str, ...]


class DelegationCommandObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    present: bool
    command: str
    delegates_to_global_qc: bool
    caller_root_preserved: bool


class DelegationObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_justfile: str
    observed: DelegationCommandObservation


class BranchProtectionObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_contexts: tuple[str, ...]
    observed_contexts: tuple[str, ...]
    observed_state: BranchProtectionState
    evidence: str


class DoctorFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: FindingSeverity
    surface: FindingSurface
    evidence: str
    remediation_commands: tuple[str, ...]


class DoctorReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    tool_version: str
    target: TargetObservation
    declaration: DeclarationObservation
    declaration_hash: str
    declared_profile: ObservedProfile
    effective_profile: ObservedProfile
    workflow_refs: dict[str, WorkflowRefObservation]
    justfile_delegation: dict[str, DelegationObservation]
    branch_protection: BranchProtectionObservation
    profile_proof_requirements: dict[str, ProfileProofObservation]
    findings: tuple[DoctorFinding, ...]
    invalidation_inputs: tuple[str, ...]
    installation_state: InstallationState
    global_status: GlobalStatus
    exceptions: tuple[ManifestException, ...]


def manifest_text(
    *,
    profile: str,
    installed_ref: str,
    release_channel: str,
    workflow_template_version: int,
    local_delegation: str,
    default_branch: str,
    exceptions: tuple[ManifestException, ...],
) -> str:
    """Render the repo-owned QC manifest deterministically."""
    ProfileAdapter.validate_python(profile)
    lines = [
        "schema_version = 1",
        f'profile = "{profile}"',
        f'installed_ref = "{installed_ref}"',
        f'release_channel = "{release_channel}"',
        f"workflow_template_version = {workflow_template_version}",
        f'local_delegation = "{local_delegation}"',
        f'default_branch = "{default_branch}"',
    ]
    if not exceptions:
        lines.append("exceptions = []")
        return "\n".join(lines) + "\n"
    for exception in exceptions:
        lines.extend(
            [
                "",
                "[[exceptions]]",
                f'id = "{exception.id}"',
                f'surface = "{exception.surface}"',
                f'reason = "{exception.reason}"',
                f"active = {jsonlib.dumps(exception.active)}",
            ]
        )
    return "\n".join(lines) + "\n"


def doctor(target: Path, *, json: Annotated[int, Parameter(name="--json", count=True)] = 0) -> None:
    """Evaluate the target repository's declared ai-review-ci contract."""
    report = doctor_report(target)
    if json > 0:
        print(report.model_dump_json(indent=2))
    else:
        print(f"{report.global_status}: {target.resolve()}")
        for finding in report.findings:
            print(f"- {finding.surface}: {finding.evidence}")
    if report.global_status not in ("current", "intentional_exception"):
        sys.exit(1)


def check_justfile(target: Path) -> None:
    """Fail if the target justfile violates the baseline public justfile contract."""
    report = doctor_report(target)
    findings = [
        finding
        for finding in report.findings
        if finding.surface in ("justfile_conformance", "justfile_delegation")
    ]
    if findings:
        for finding in findings:
            print(f"{finding.surface}: {finding.evidence}", file=sys.stderr)
        sys.exit(1)
    print(f"Justfile conformance passed for {Path(target).resolve()}.")


def doctor_schema() -> None:
    """Print the JSON Schema for the machine-readable doctor payload."""
    print(jsonlib.dumps(DoctorReport.model_json_schema(), indent=2))


def version_command() -> None:
    """Print the installed ai-review-ci package version."""
    print(version("ai-review-ci"))


def doctor_report(target: Path) -> DoctorReport:
    """Build a machine-readable doctor report for a target repository."""
    target_root = _target_root(target)
    manifest_path = target_root / MANIFEST_NAME
    manifest = _load_manifest(manifest_path) if manifest_path.is_file() else MissingManifest(present=False, reason="manifest file is missing")
    declared_profile: ObservedProfile = manifest.profile if isinstance(manifest, QcManifest) else UNKNOWN_PROFILE
    effective_profile = _effective_profile(target_root, declared_profile)
    report_profile = _report_profile(manifest, effective_profile)
    profile_proof = _profile_proofs(target_root)
    workflow_refs = _workflow_refs(target_root, manifest, report_profile)
    justfile_delegation = _justfile_delegation(target_root, report_profile)
    branch_protection = _branch_protection(target_root, manifest, report_profile)
    findings = _findings(
        target_root=target_root,
        manifest=manifest,
        report_profile=report_profile,
        declared_profile=declared_profile,
        effective_profile=effective_profile,
        workflow_refs=workflow_refs,
        justfile_delegation=justfile_delegation,
        branch_protection=branch_protection,
        profile_proof=profile_proof,
    )
    installation_state, global_status = _classify(manifest, findings)
    declaration_hash = _sha256(manifest_path) if manifest_path.is_file() else ""
    return DoctorReport(
        schema_version=SCHEMA_VERSION,
        tool_version=version("ai-review-ci"),
        target=TargetObservation(
            root=str(target_root),
            remote=_remote(target_root),
            head=_head(target_root),
        ),
        declaration=DeclarationObservation(path=str(manifest_path), sha256=declaration_hash, manifest=manifest),
        declaration_hash=declaration_hash,
        declared_profile=declared_profile,
        effective_profile=effective_profile,
        workflow_refs=workflow_refs,
        justfile_delegation=justfile_delegation,
        branch_protection=branch_protection,
        profile_proof_requirements=profile_proof,
        findings=tuple(findings),
        invalidation_inputs=_invalidation_inputs(target_root, declaration_hash),
        installation_state=installation_state,
        global_status=global_status,
        exceptions=manifest.exceptions if isinstance(manifest, QcManifest) else (),
    )


def _target_root(target: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(target), "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
    )
    if result.returncode == 0:
        return Path(result.stdout.strip()).resolve()
    return target.resolve()


def _load_manifest(path: Path) -> QcManifest:
    data = tomllib.loads(path.read_text())
    return QcManifest.model_validate(data)


def _effective_profile(target: Path, declared_profile: ObservedProfile) -> ObservedProfile:
    matches = [profile for profile in SUPPORTED_PROFILES if not _profile_missing_paths(target, PROJECT_PROFILES[profile])]
    if declared_profile in matches:
        return ProfileAdapter.validate_python(declared_profile)
    if len(matches) == 1:
        return ProfileAdapter.validate_python(matches[0])
    return UNKNOWN_PROFILE


def _report_profile(manifest: ManifestDeclaration, effective_profile: ObservedProfile) -> ProfileName:
    if isinstance(manifest, QcManifest):
        return manifest.profile
    if effective_profile != UNKNOWN_PROFILE:
        return ProfileAdapter.validate_python(effective_profile)
    return "python"


def _profile_missing_paths(target: Path, project_profile: ProjectProfile) -> tuple[str, ...]:
    missing = [path for path in project_profile.required_paths if not (target / path).exists()]
    if project_profile.requires_bun_lock and not ((target / "bun.lock").exists() or (target / "bun.lockb").exists()):
        missing.append("bun.lock or bun.lockb")
    if project_profile.requires_sage_file and not any(path.suffix == ".sage" and ".git" not in path.parts for path in target.rglob("*.sage")):
        missing.append("at least one .sage file")
    return tuple(missing)


def _profile_proofs(target: Path) -> dict[str, ProfileProofObservation]:
    return {
        profile: ProfileProofObservation(
            profile=ProfileAdapter.validate_python(profile),
            required_paths=PROJECT_PROFILES[profile].required_paths,
            missing_paths=_profile_missing_paths(target, PROJECT_PROFILES[profile]),
        )
        for profile in SUPPORTED_PROFILES
    }


def _workflow_refs(target: Path, manifest: ManifestDeclaration, profile: ProfileName) -> dict[str, WorkflowRefObservation]:
    workflows: dict[str, WorkflowRefObservation] = {}
    required_ref = manifest.installed_ref if isinstance(manifest, QcManifest) else ""
    for name in TEMPLATES:
        path = target / ".github" / "workflows" / name
        refs: set[str] = set()
        gates: set[str] = set()
        if path.is_file():
            data = _yaml_mapping(path)
            jobs = TypeAdapter(dict[str, dict[str, Any]]).validate_python(data["jobs"] if "jobs" in data else {})
            for job in jobs.values():
                uses = str(job["uses"]) if "uses" in job else ""
                if "dzackgarza/ai-review-ci/.github/workflows/" in uses and "@" in uses:
                    refs.add(uses.rsplit("@", 1)[1])
                if "dzackgarza/ai-review-ci/.github/workflows/_gates.yml" in uses:
                    with_block = TypeAdapter(dict[str, Any]).validate_python(job["with"]) if "with" in job else {}
                    gate = with_block["gate"] if "gate" in with_block else ""
                    if isinstance(gate, str):
                        gates.add(gate)
        workflows[name] = WorkflowRefObservation(
            path=str(path),
            required_ref=required_ref,
            observed_ref=next(iter(refs)) if len(refs) == 1 else "",
            required_gates=_required_workflow_gates(name, profile),
            observed_gates=tuple(sorted(gates)),
        )
    return workflows


def _yaml_mapping(path: Path) -> Mapping[object, object]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, Mapping):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def _required_workflow_gates(name: str, profile: ProfileName) -> tuple[str, ...]:
    if name != "review-pr.yml":
        return ()
    gates = ("deterministic-diff", "delegation-conformance", "qc-doctor", "thread-resolution")
    if PROJECT_PROFILES[profile].requires_app_boot:
        return gates[:3] + ("app-boot",) + gates[3:]
    return gates


def _justfile_delegation(target: Path, profile: ProfileName) -> dict[str, DelegationObservation]:
    project_profile = PROJECT_PROFILES[profile]
    recipes = ["test", "test-ci"]
    if project_profile.requires_app_boot:
        recipes.append("app-boot")
    justfile = _justfile_path(target)
    return {recipe: _recipe_delegation(target, justfile, project_profile, recipe) for recipe in recipes}


def _justfile_path(target: Path) -> Path:
    candidates = [target / "justfile", target / "Justfile"]
    existing = [candidate for candidate in candidates if candidate.exists()]
    if len(existing) == 1:
        return existing[0]
    return target / MISSING_JUSTFILE_NAME


def _recipe_delegation(target: Path, justfile: Path, project_profile: ProjectProfile, recipe: str) -> DelegationObservation:
    if not justfile.is_file():
        return DelegationObservation(
            required_justfile=project_profile.justfile_name,
            observed=DelegationCommandObservation(
                present=False,
                command="",
                delegates_to_global_qc=False,
                caller_root_preserved=False,
            ),
        )
    result = subprocess.run(
        ["just", "--dry-run", "--justfile", str(justfile), "-d", str(target), recipe],
        text=True,
        capture_output=True,
    )
    command = result.stdout + result.stderr
    return DelegationObservation(
        required_justfile=project_profile.justfile_name,
        observed=DelegationCommandObservation(
            present=result.returncode == 0,
            command=command,
            delegates_to_global_qc=f"ai-review-ci/justfiles/{project_profile.justfile_name}" in command,
            caller_root_preserved=" -d . " in f" {command} ",
        ),
    )


def _branch_protection(target: Path, manifest: ManifestDeclaration, profile: ProfileName) -> BranchProtectionObservation:
    required = required_check_contexts(profile)
    remote = _remote(target)
    if remote == "":
        return BranchProtectionObservation(
            required_contexts=required,
            observed_contexts=(),
            observed_state="not_applicable",
            evidence="target repository has no origin remote",
        )
    repo = _github_repo(remote)
    if repo == "":
        return BranchProtectionObservation(
            required_contexts=required,
            observed_contexts=(),
            observed_state="unverifiable",
            evidence=f"origin remote is not a GitHub repository: {remote}",
        )
    branch = manifest.default_branch if isinstance(manifest, QcManifest) else "main"
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/branches/{branch}/protection"],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        state: BranchProtectionState = "missing" if "Branch not protected" in result.stderr else "unverifiable"
        return BranchProtectionObservation(
            required_contexts=required,
            observed_contexts=(),
            observed_state=state,
            evidence=result.stderr.strip(),
        )
    data: JsonDict = jsonlib.loads(result.stdout)
    observed = tuple(_observed_contexts(data))
    missing = tuple(context for context in required if context not in observed)
    if missing:
        return BranchProtectionObservation(
            required_contexts=required,
            observed_contexts=observed,
            observed_state="missing_contexts",
            evidence=f"missing required contexts: {', '.join(missing)}",
        )
    return BranchProtectionObservation(
        required_contexts=required,
        observed_contexts=observed,
        observed_state="compliant",
        evidence=f"GitHub branch protection for {repo}@{branch} contains required contexts",
    )


def _observed_contexts(data: JsonDict) -> list[str]:
    status_checks = TypeAdapter(dict[str, Any]).validate_python(data["required_status_checks"])
    contexts = [str(context) for context in TypeAdapter(list[Any]).validate_python(status_checks["contexts"])]
    checks = [str(check["context"]) for check in TypeAdapter(list[dict[str, Any]]).validate_python(status_checks["checks"])]
    return contexts + checks


def _github_repo(remote: str) -> str:
    ssh_match = re.fullmatch(r"git@github\.com:([^/]+/[^/]+)(?:\.git)?", remote)
    if ssh_match is not None:
        return ssh_match.group(1).removesuffix(".git")
    https_match = re.fullmatch(r"https://github\.com/([^/]+/[^/]+)(?:\.git)?", remote)
    if https_match is not None:
        return https_match.group(1).removesuffix(".git")
    return ""


def _findings(
    *,
    target_root: Path,
    manifest: ManifestDeclaration,
    report_profile: ProfileName,
    declared_profile: ObservedProfile,
    effective_profile: ObservedProfile,
    workflow_refs: dict[str, WorkflowRefObservation],
    justfile_delegation: dict[str, DelegationObservation],
    branch_protection: BranchProtectionObservation,
    profile_proof: dict[str, ProfileProofObservation],
) -> list[DoctorFinding]:
    findings: list[DoctorFinding] = []
    if not isinstance(manifest, QcManifest):
        findings.append(
            DoctorFinding(
                severity="error",
                surface="manifest",
                evidence=f"{target_root / MANIFEST_NAME} is missing",
                remediation_commands=(
                    "uvx --from git+https://github.com/dzackgarza/ai-review-ci ai-review-ci install --target <target-repo> --repo owner/repo --branch main --profile <profile>",
                ),
            )
        )
        findings.extend(_justfile_conformance_findings(target_root, report_profile))
        return findings
    declared = manifest.profile
    if effective_profile != declared:
        findings.append(
            DoctorFinding(
                severity="error",
                surface="profile",
                evidence=(
                    f"declared profile {declared} does not match observed target shape {effective_profile}; "
                    f"missing for declared profile: {', '.join(profile_proof[declared].missing_paths)}"
                ),
                remediation_commands=(f"just install-qc-scaffold {declared} <target-repo>",),
            )
        )
    for workflow in workflow_refs.values():
        if not Path(workflow.path).is_file():
            findings.append(
                DoctorFinding(
                    severity="error",
                    surface="workflow",
                    evidence=f"{workflow.path} is missing",
                    remediation_commands=("ai-review-ci install --target <target-repo> --repo owner/repo --branch main --profile <profile>",),
                )
            )
            continue
        missing_gates = tuple(gate for gate in workflow.required_gates if gate not in workflow.observed_gates)
        if missing_gates:
            findings.append(
                DoctorFinding(
                    severity="error",
                    surface="workflow",
                    evidence=f"{workflow.path} missing gate(s): {', '.join(missing_gates)}",
                    remediation_commands=("ai-review-ci install --target <target-repo> --repo owner/repo --branch main --profile <profile>",),
                )
            )
        if workflow.required_ref != "" and workflow.observed_ref != workflow.required_ref:
            findings.append(
                DoctorFinding(
                    severity="warning",
                    surface="workflow_ref",
                    evidence=f"{workflow.path} uses {workflow.observed_ref}; manifest requires {workflow.required_ref}",
                    remediation_commands=(f"edit {workflow.path} to use dzackgarza/ai-review-ci reusable workflows at @{workflow.required_ref}",),
                )
            )
    for recipe, observation in justfile_delegation.items():
        observed = observation.observed
        if not observed.present or not observed.delegates_to_global_qc or not observed.caller_root_preserved:
            findings.append(
                DoctorFinding(
                    severity="error",
                    surface="justfile_delegation",
                    evidence=f"{recipe} must delegate through ~/ai-review-ci/justfiles/{observation.required_justfile} with -d .",
                    remediation_commands=(f"just install-qc-scaffold {declared} <target-repo>",),
                )
            )
    findings.extend(_justfile_conformance_findings(target_root, declared))
    if branch_protection.observed_state in ("missing", "missing_contexts"):
        findings.append(
            DoctorFinding(
                severity="error",
                surface="branch_protection",
                evidence=branch_protection.evidence,
                remediation_commands=(f"ai-review-ci protect-branch --repo owner/repo --branch {manifest.default_branch} --profile {manifest.profile}",),
            )
        )
    if branch_protection.observed_state == "unverifiable":
        findings.append(
            DoctorFinding(
                severity="warning",
                surface="branch_protection",
                evidence=branch_protection.evidence,
                remediation_commands=("run doctor with GitHub branch protection API access",),
            )
        )
    return findings


def _justfile_conformance_findings(target: Path, profile: ProfileName) -> list[DoctorFinding]:
    justfile = _justfile_path(target)
    if not justfile.is_file():
        return [
            DoctorFinding(
                severity="error",
                surface="justfile_conformance",
                evidence=f"{target} must contain exactly one justfile or Justfile",
                remediation_commands=(f"just install-qc-scaffold {profile} <target-repo>",),
            )
        ]
    lines = justfile.read_text(encoding="utf-8").splitlines()
    findings: list[DoctorFinding] = []
    if not lines or not lines[0].startswith("#"):
        findings.append(
            DoctorFinding(
                severity="error",
                surface="justfile_conformance",
                evidence=f"{justfile}:1 header-comment: justfile must begin with a comment block",
                remediation_commands=(f"just install-qc-scaffold {profile} <target-repo>",),
            )
        )
    recipes = _justfile_recipes(lines)
    default = recipes.get("default")
    if default is None:
        findings.append(
            DoctorFinding(
                severity="error",
                surface="justfile_conformance",
                evidence=f"{justfile} default-recipe: no default recipe; bare just must list recipes",
                remediation_commands=(f"just install-qc-scaffold {profile} <target-repo>",),
            )
        )
    elif "just --list" not in _recipe_delegation(target, justfile, PROJECT_PROFILES[profile], "default").observed.command:
        findings.append(
            DoctorFinding(
                severity="error",
                surface="justfile_conformance",
                evidence=f"{justfile}:{default} default-recipe: default must resolve to just --list",
                remediation_commands=(f"just install-qc-scaffold {profile} <target-repo>",),
            )
        )
    for recipe, line_no in recipes.items():
        if not _has_private_attribute(lines, line_no) and not _has_immediate_doc_comment(lines, line_no):
            findings.append(
                DoctorFinding(
                    severity="error",
                    surface="justfile_conformance",
                    evidence=f"{justfile}:{line_no} public-recipe-doc: recipe `{recipe}` has no immediate # doc comment",
                    remediation_commands=(f"just install-qc-scaffold {profile} <target-repo>",),
                )
            )
    return findings


def _justfile_recipes(lines: list[str]) -> dict[str, int]:
    recipes: dict[str, int] = {}
    for index, line in enumerate(lines, start=1):
        if line.startswith((" ", "\t", "#", "[")) or ":=" in line or "=" in line:
            continue
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\b.*:", line)
        if match is not None:
            recipes[match.group(1)] = index
    return recipes


def _has_immediate_doc_comment(lines: list[str], line_no: int) -> bool:
    return line_no > 1 and lines[line_no - 2].startswith("#")


def _has_private_attribute(lines: list[str], line_no: int) -> bool:
    index = line_no - 2
    while index >= 0 and lines[index].startswith("["):
        if lines[index].strip() == "[private]":
            return True
        index -= 1
    return False


def _classify(manifest: ManifestDeclaration, findings: list[DoctorFinding]) -> tuple[InstallationState, GlobalStatus]:
    if not isinstance(manifest, QcManifest):
        return "uninstalled", "misconfigured"
    exception_surfaces = {exception.surface for exception in manifest.exceptions if exception.active}
    if findings and all(finding.surface in exception_surfaces for finding in findings):
        state: InstallationState = "outdated" if any(finding.surface == "workflow_ref" for finding in findings) else "noncompliant"
        return state, "intentional_exception"
    if not findings:
        return "compliant", "current"
    if any(finding.surface == "branch_protection" and finding.severity == "warning" for finding in findings):
        return "unknown", "unverifiable"
    if any(finding.surface == "workflow_ref" for finding in findings):
        return "outdated", "stale"
    return "noncompliant", "misconfigured"


def _remote(target: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(target), "remote", "get-url", "origin"],
        text=True,
        capture_output=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return ""


def _head(target: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(target), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return ""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _invalidation_inputs(target: Path, declaration_hash: str) -> tuple[str, ...]:
    inputs = [f"target_head:{_head(target)}", f"manifest_sha256:{declaration_hash}"]
    for path in [
        target / "justfile",
        target / "Justfile",
        *(target / ".github" / "workflows" / name for name in TEMPLATES),
    ]:
        if path.is_file():
            inputs.append(f"{path.relative_to(target)}:{_sha256(path)}")
    return tuple(inputs)
