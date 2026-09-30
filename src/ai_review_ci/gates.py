"""Deterministic gates that do not depend on reviewer judgment."""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn

from pydantic import BaseModel, ConfigDict
from unidiff import PatchSet

JsonDict = dict[str, Any]

_TS_JS_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
_NON_CODE_SUFFIXES = (".md", ".markdown", ".mdx")
_DIFF_SECTION_START = re.compile(r"(?m)(?=^diff --git )")
_NON_TEXT_DIFF_CONTENT = re.compile(r"[\udc80-\udcff\x0b\x0c\x1c-\x1e\x85\u2028\u2029]|\r(?!\n)")


class DiffRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    rule_id: str
    policy_code: str
    signal_keys: tuple[str, ...]
    pattern: re.Pattern[str]
    suffixes: tuple[str, ...]
    excluded_suffixes: tuple[str, ...] = ()
    exclude_config_paths: bool = False


class ProjectProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    justfile_names: tuple[str, ...]
    required_paths: tuple[str, ...]
    requires_bun_lock: bool = False
    requires_cargo_manifest: bool = False
    requires_sage_file: bool = False
    requires_app_boot: bool = False


PROJECT_PROFILES = {
    "python": ProjectProfile(name="python", justfile_names=("python.just",), required_paths=("pyproject.toml",)),
    "bun": ProjectProfile(name="bun", justfile_names=("bun.just",), required_paths=("package.json",), requires_bun_lock=True),
    "bun-playwright": ProjectProfile(
        name="bun-playwright",
        justfile_names=("bun.just",),
        required_paths=("package.json", "playwright.config.ts"),
        requires_bun_lock=True,
        requires_app_boot=True,
    ),
    "bun-python": ProjectProfile(
        name="bun-python",
        justfile_names=("python.just", "bun.just"),
        required_paths=("pyproject.toml", "package.json"),
        requires_bun_lock=True,
    ),
    "docs-and-configs": ProjectProfile(name="docs-and-configs", justfile_names=("docs-and-configs.just",), required_paths=()),
    "rust": ProjectProfile(name="rust", justfile_names=("rust.just",), required_paths=(), requires_cargo_manifest=True),
    "sage": ProjectProfile(name="sage", justfile_names=("sage.just",), required_paths=("pyproject.toml",), requires_sage_file=True),
}

BASE_REQUIRED_CHECK_CONTEXTS = (
    "qc-ci / qc",
    "deterministic-diff / deterministic-diff",
    "delegation-conformance / delegation-conformance",
    "qc-doctor / qc-doctor",
    "pr-description-checklist / pr-description-checklist",
)

APP_BOOT_CHECK_CONTEXT = "app-boot / app-boot"

SUPPORTED_PROFILES = tuple(PROJECT_PROFILES)

REQUIRED_CHECK_CONTEXTS = BASE_REQUIRED_CHECK_CONTEXTS


# Added-line regex scanning is reserved for lexical suppression markers whose
# policy significance is carried by source text itself. Semantic code shapes
# belong to Semgrep or ast-grep, which parse the language syntax tree.


LEXICAL_DIFF_RULES = (
    DiffRule(
        rule_id="no-coverage-pragma",
        policy_code="POLICY.NO_QC_SILENCING",
        signal_keys=("no-coverage-pragma",),
        pattern=re.compile(r"# pragma: no cov" + "er"),
        suffixes=(),
        excluded_suffixes=_NON_CODE_SUFFIXES,
    ),
    DiffRule(
        rule_id="no-istanbul-ignore",
        policy_code="POLICY.NO_QC_SILENCING",
        signal_keys=("no-istanbul-ignore",),
        pattern=re.compile(r"// istanbul ign" + "ore"),
        suffixes=(),
        excluded_suffixes=_NON_CODE_SUFFIXES,
    ),
    DiffRule(
        rule_id="no-noqa",
        policy_code="POLICY.NO_QC_SILENCING",
        signal_keys=("no-noqa",),
        pattern=re.compile(r"# no" + "qa"),
        suffixes=(),
        excluded_suffixes=_NON_CODE_SUFFIXES,
    ),
    DiffRule(
        rule_id="no-type-ignore",
        policy_code="POLICY.NO_QC_SILENCING",
        signal_keys=("no-type-ignore",),
        pattern=re.compile(r"# type: ign" + "ore"),
        suffixes=(),
        excluded_suffixes=_NON_CODE_SUFFIXES,
    ),
    DiffRule(
        rule_id="no-double-cast",
        policy_code="POLICY.NO_TYPE_ESCAPE",
        signal_keys=("no-double-cast",),
        pattern=re.compile(r"\bas\s+(?:unknown|any|never)\s+as\s+"),
        suffixes=(),
        excluded_suffixes=_NON_CODE_SUFFIXES,
    ),
    DiffRule(
        rule_id="no-ts-ignore",
        policy_code="POLICY.NO_QC_SILENCING",
        signal_keys=("no-ts-ignore",),
        pattern=re.compile(r"@ts-ign" + "ore"),
        suffixes=(),
        excluded_suffixes=_NON_CODE_SUFFIXES,
    ),
    DiffRule(
        rule_id="no-unjustified-ts-expect-error",
        policy_code="POLICY.NO_QC_SILENCING",
        signal_keys=("no-unjustified-ts-expect-error",),
        pattern=re.compile(r"@ts-expect-err" + r"or[ \t]*$"),
        suffixes=(),
        excluded_suffixes=_NON_CODE_SUFFIXES,
    ),
    DiffRule(
        rule_id="no-eslint-disable",
        policy_code="POLICY.NO_QC_SILENCING",
        signal_keys=("no-eslint-disable",),
        pattern=re.compile(r"// eslint-dis" + "able"),
        suffixes=(),
        excluded_suffixes=_NON_CODE_SUFFIXES,
    ),
)

_DIRECT_PLAYWRIGHT = re.compile(r"\b(?:bunx|npx|npm|pnpm|yarn)\s+(?:exec\s+)?playwright\b|\bplaywright\s+test\b")


def _fail(message: str) -> NoReturn:
    print(f"FATAL: {message}", file=sys.stderr)
    sys.exit(1)


def _profile(profile: str) -> ProjectProfile:
    try:
        return PROJECT_PROFILES[profile]
    except KeyError:
        _fail(f"unsupported project profile {profile!r}; expected one of: {', '.join(SUPPORTED_PROFILES)}")


def _has_sage_file(target: Path) -> bool:
    return any(path.suffix == ".sage" and ".git" not in path.parts for path in target.rglob("*.sage"))


def check_profile(target: Path, profile: str) -> None:
    """Fail if the target repository does not match its curated project profile."""
    target = target.resolve()
    project_profile = _profile(profile)
    missing = [path for path in project_profile.required_paths if not (target / path).exists()]
    if project_profile.requires_bun_lock and not ((target / "bun.lock").exists() or (target / "bun.lockb").exists()):
        missing.append("bun.lock or bun.lockb")
    if project_profile.requires_sage_file and not _has_sage_file(target):
        missing.append("at least one .sage file")
    if missing:
        _fail(f"{target} does not satisfy {profile} profile; missing: {', '.join(missing)}")
    print(f"Project profile {profile} passed for {target}.")


def _is_config_path(path: str) -> bool:
    name = Path(path).name
    return "config" in path or name.endswith(".d.ts")


def _rule_applies(path: str, rule: DiffRule) -> bool:
    if rule.exclude_config_paths and _is_config_path(path):
        return False
    if path.lower().endswith(rule.excluded_suffixes):
        return False
    if not rule.suffixes:
        return True
    return Path(path).name.lower() == "justfile" or path.endswith(rule.suffixes)


def lexical_diff_findings(diff_text: str) -> list[str]:
    """Return added-line findings for lexical suppression markers.

    Regex is intentionally limited to source-text markers that syntax-tree tools
    discard. Semantic code shapes are owned by Semgrep or ast-grep.
    """
    findings: list[str] = []
    for patched_file in PatchSet(diff_text.splitlines(keepends=True)):
        if patched_file.is_removed_file:
            continue
        file_path = str(patched_file.path)
        for hunk in patched_file:
            for line in hunk:
                if not line.is_added:
                    continue
                if line.target_line_no is None:
                    _fail(f"missing target line number in diff for {file_path}")
                text = line.value.rstrip("\n")
                for rule in LEXICAL_DIFF_RULES:
                    if _rule_applies(file_path, rule) and rule.pattern.search(text):
                        findings.append(f"{file_path}:{line.target_line_no}: {rule.rule_id}: {rule.policy_code}")
    return findings


def _text_diff_sections(diff_text: str) -> str:
    """Keep file sections whose content is safe for unified-text parsing."""
    sections = _DIFF_SECTION_START.split(diff_text)
    return "".join(section for section in sections if _NON_TEXT_DIFF_CONTENT.search(section) is None)


def check_staged_bypass() -> None:
    """Fail if staged added lines introduce validator or type-system bypasses."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--unified=0", "--diff-filter=ACM"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="surrogateescape",
    )
    if result.returncode != 0:
        _fail(f"git diff --cached failed: {result.stderr.strip()}")
    findings = lexical_diff_findings(_text_diff_sections(result.stdout))
    if findings:
        print("Staged bypass gate found introduced violations:", file=sys.stderr)
        for finding in findings:
            print(f"- {finding}", file=sys.stderr)
        sys.exit(1)
    print("No bypass comments detected in staged files.")


def _justfile_for(target: Path) -> Path:
    candidates = (target / "justfile", target / "Justfile")
    existing = [candidate for candidate in candidates if candidate.exists()]
    if len(existing) != 1:
        _fail(f"expected exactly one justfile or Justfile in {target}, found {len(existing)}")
    return existing[0]


def _dry_run_recipe(target: Path, justfile: Path, recipe: str) -> str:
    result = subprocess.run(
        ["just", "--dry-run", "--justfile", str(justfile), "-d", str(target), recipe],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        _fail(f"just dry-run for recipe {recipe} failed: {result.stderr.strip()}")
    return result.stdout + result.stderr


def delegates_to_global_qc(output: str, project_profile: ProjectProfile, recipe: str) -> bool:
    """Require the declared profile delegation, plus Lean scans at push/CI tiers and Lean
    compilation (a build, or the axiom audit of a built environment) at the CI tier only."""
    observed = set(re.findall(r"ai-review-ci/justfiles/([a-z-]+\.just)", output))
    expected = set(project_profile.justfile_names)
    allowed = expected | ({"lean.just"} if recipe in {"test-push", "test-ci"} else set())
    if recipe != "test-ci" and re.search(r"\blake\s+(?:build|exe)\b|\blean-axiom-audit\b|\blean\.just\b.*\btest-ci\b", output):
        return False
    command_lines = output.splitlines()
    return expected <= observed <= allowed and all(
        any(f"ai-review-ci/justfiles/{justfile_name}" in line and re.search(r"(?:-d|--working-directory)\s+\.", line) is not None for line in command_lines)
        for justfile_name in observed
    )


def check_delegation(target: Path, profile: str) -> None:
    """Fail unless every public QC tier delegates to global QC."""
    target = target.resolve()
    project_profile = _profile(profile)
    check_profile(target, profile)
    justfile = _justfile_for(target)
    failed: list[str] = []
    for recipe in ("test-commit", "test-push", "test-ci"):
        output = _dry_run_recipe(target, justfile, recipe)
        if not delegates_to_global_qc(output, project_profile, recipe):
            failed.append(recipe)
    if failed:
        required = ", ".join(f"~/ai-review-ci/justfiles/{name}" for name in project_profile.justfile_names)
        _fail(f"{target} does not delegate {profile} recipe(s) through {required} with -d .: {', '.join(failed)}")
    print(f"Delegation conformance passed for {target} profile {profile}.")


def check_app_boot(target: Path, profile: str) -> None:
    """Run the target repo's centrally delegated bun-playwright app-boot gate."""
    target = target.resolve()
    project_profile = _profile(profile)
    if not project_profile.requires_app_boot:
        _fail(f"profile {profile} does not define an app-boot gate")
    check_profile(target, profile)
    justfile = _justfile_for(target)
    output = _dry_run_recipe(target, justfile, "app-boot")
    if not delegates_to_global_qc(output, project_profile, "app-boot"):
        _fail(f"{target} app-boot must delegate through ~/ai-review-ci/justfiles/{project_profile.justfile_names[0]} with -d .")
    if _DIRECT_PLAYWRIGHT.search(output):
        _fail(f"{target} app-boot must not invoke Playwright directly; delegate to ~/ai-review-ci/justfiles/bun.just")
    result = subprocess.run(["just", "--justfile", str(justfile), "-d", str(target), "app-boot"])
    if result.returncode != 0:
        _fail(f"app-boot gate failed for {target}")
    print(f"App boot gate passed for {target}.")


_UNCHECKED_CHECKLIST_ITEM = re.compile(r"^\s*[-*+]\s*\[\s*\]\s+\S", re.MULTILINE)


def unchecked_checklist_lines(body: str) -> list[int]:
    """Return 1-indexed PR body lines containing unchecked markdown checklist items."""
    return [line_no for line_no, line in enumerate(body.splitlines(), start=1) if _UNCHECKED_CHECKLIST_ITEM.search(line)]


# Machine marker embedded in the distributed PR template's Policy Alignment Gate
# section. A repo "opts in" to gate enforcement by installing that template; the
# gate then requires the marker in every PR body so the section cannot be deleted
# to bypass the affirmation. See AGENTS.md -> Policy Alignment Gate and #154.
POLICY_GATE_MARKER = "<!-- policy-alignment-gate -->"


def gate_template_requires_marker(repo_root: Path) -> bool:
    """True when the repo has installed the policy-alignment PR template.

    Enforcement is opt-in by installation: only when the repo's own PR template
    carries the marker do we require PR bodies to carry it too. Repos without the
    template keep the lenient unchecked-items-only behavior, so distributing the
    gate does not break repos that have not installed the template.
    """
    template = repo_root / ".github" / "pull_request_template.md"
    # The template carries non-ASCII glyphs; the gate runs in CI where the locale
    # is not guaranteed UTF-8, so read_text() without an explicit encoding could
    # raise. Pin UTF-8 (the template's actual encoding).
    return template.is_file() and POLICY_GATE_MARKER in template.read_text(encoding="utf-8")


def _gh_json(args: list[str], body: JsonDict | None = None) -> JsonDict:
    result = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        input=json.dumps(body) if body is not None else None,
    )
    if result.returncode != 0:
        _fail(f"gh {' '.join(args[:3])} failed: {result.stderr.strip()}")
    data: JsonDict = json.loads(result.stdout)
    return data


def check_pr_description(repo: str, pr_number: int, repo_root: Path = Path(".")) -> None:
    """Fail if the PR description omits the policy-alignment gate or has unchecked items.

    When the repo has installed the policy-alignment PR template (opt-in), the PR body
    must carry the gate marker: the affirmation section cannot be deleted to bypass the
    gate. The unchecked-checklist-item check always applies.
    """
    pr = _gh_json(["api", f"repos/{repo}/pulls/{pr_number}"])
    body = pr.get("body")
    if body is None:
        body = ""
    if not isinstance(body, str):
        _fail("pull request body was not a string")
    if gate_template_requires_marker(repo_root) and POLICY_GATE_MARKER not in body:
        print(
            "PR description is missing the required policy-alignment gate section "
            f"(marker {POLICY_GATE_MARKER!r}). This repo installs the gate template; "
            "restore the section from .github/pull_request_template.md and affirm it.",
            file=sys.stderr,
        )
        sys.exit(1)
    unchecked = unchecked_checklist_lines(body)
    if unchecked:
        print("PR description contains unchecked markdown checklist items:", file=sys.stderr)
        for line_no in unchecked:
            print(f"- PR body line {line_no}: unchecked checklist item", file=sys.stderr)
        sys.exit(1)
    print("PR description checklist gate found no unchecked items.")


def required_check_contexts(profile: str) -> tuple[str, ...]:
    """Required branch-protection check contexts for a curated project profile."""
    project_profile = _profile(profile)
    if project_profile.requires_app_boot:
        insertion = BASE_REQUIRED_CHECK_CONTEXTS.index("pr-description-checklist / pr-description-checklist")
        return BASE_REQUIRED_CHECK_CONTEXTS[:insertion] + (APP_BOOT_CHECK_CONTEXT,) + BASE_REQUIRED_CHECK_CONTEXTS[insertion:]
    return BASE_REQUIRED_CHECK_CONTEXTS


def branch_protection_payload(profile: str) -> JsonDict:
    """GitHub branch protection payload for the required global QC checks."""
    contexts = required_check_contexts(profile)
    return {
        "required_status_checks": {
            "strict": True,
            "checks": [{"context": context} for context in contexts],
        },
        "enforce_admins": True,
        "required_pull_request_reviews": None,
        "restrictions": None,
        "required_conversation_resolution": True,
    }


def protect_branch(repo: str, branch: str, profile: str) -> None:
    """Apply required global-QC branch protection checks to a GitHub branch."""
    _gh_json(
        [
            "api",
            "--method",
            "PUT",
            f"repos/{repo}/branches/{branch}/protection",
            "--input",
            "-",
        ],
        body=branch_protection_payload(profile),
    )
    print(f"Applied branch protection for {repo}@{branch}: {', '.join(required_check_contexts(profile))}")
