"""Deterministic gates that do not depend on reviewer judgment."""

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

from unidiff import PatchSet

from ai_review_ci.threads import FINGERPRINT_MARKER

JsonDict = dict[str, Any]

_TS_JS_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
_PY_SUFFIXES = (".py",)
_RUST_SUFFIXES = (".rs",)
_SHELL_SUFFIXES = (".sh",)
_JUST_SUFFIXES = (".just",)


@dataclass(frozen=True)
class DiffRule:
    rule_id: str
    pattern: re.Pattern[str]
    suffixes: tuple[str, ...]
    message: str


@dataclass(frozen=True)
class ProjectProfile:
    name: str
    justfile_name: str
    required_paths: tuple[str, ...]
    requires_bun_lock: bool = False
    requires_sage_file: bool = False
    requires_app_boot: bool = False


PROJECT_PROFILES = {
    "python": ProjectProfile("python", "python.just", ("pyproject.toml",)),
    "bun": ProjectProfile("bun", "bun.just", ("package.json",), requires_bun_lock=True),
    "bun-playwright": ProjectProfile(
        "bun-playwright",
        "bun.just",
        ("package.json", "playwright.config.ts"),
        requires_bun_lock=True,
        requires_app_boot=True,
    ),
    "rust": ProjectProfile("rust", "rust.just", ("Cargo.toml",)),
    "sage": ProjectProfile("sage", "sage.just", (), requires_sage_file=True),
}

BASE_REQUIRED_CHECK_CONTEXTS = (
    "deterministic-diff / deterministic-diff",
    "delegation-conformance / delegation-conformance",
    "general / review",
    "slop / review",
    "thread-resolution / thread-resolution",
)

APP_BOOT_CHECK_CONTEXT = "app-boot / app-boot"

SUPPORTED_PROFILES = tuple(PROJECT_PROFILES)

REQUIRED_CHECK_CONTEXTS = BASE_REQUIRED_CHECK_CONTEXTS


DIFF_RULES = (
    DiffRule(
        "no-nullish-coalescing",
        re.compile(r"\?\?"),
        _TS_JS_SUFFIXES,
        "Nullish coalescing introduces a runtime fallback.",
    ),
    DiffRule(
        "ts-no-or-default",
        re.compile(r"\|\|"),
        _TS_JS_SUFFIXES + _SHELL_SUFFIXES + _JUST_SUFFIXES,
        "Logical OR introduces a fallback/default path.",
    ),
    DiffRule(
        "no-double-cast",
        re.compile(r"\bas\s+(?:unknown|any|never)\s+as\b"),
        _TS_JS_SUFFIXES,
        "Double-casting bypasses TypeScript's type system.",
    ),
    DiffRule(
        "ts-no-any-cast",
        re.compile(r"\bas\s+any\b"),
        _TS_JS_SUFFIXES,
        "as any disables TypeScript evidence at the boundary.",
    ),
    DiffRule(
        "ts-no-vitest-mock-boundary",
        re.compile(r"\bvi\.(?:mock|stubGlobal|fn|spyOn|stubEnv)\s*\("),
        _TS_JS_SUFFIXES,
        "Vitest mock helpers replace real proof boundaries.",
    ),
    DiffRule(
        "ts-no-jest-mock-boundary",
        re.compile(r"\bjest\.(?:mock|fn|spyOn)\s*\("),
        _TS_JS_SUFFIXES,
        "Jest mock helpers replace real proof boundaries.",
    ),
    DiffRule(
        "no-const-assignment",
        re.compile(r"^\s*(?:export\s+)?const\s+[A-Z][A-Z0-9_]*\s*=\s*(?:[\"'`][^\"'`]*[\"'`]|[0-9]+(?:\.[0-9]+)?|\[[^\n]*\]|\{[^\n]*\})"),
        _TS_JS_SUFFIXES,
        "Hardcoded uppercase literal constants belong in required config.",
    ),
    DiffRule(
        "py-no-getenv-default",
        re.compile(r"\bos\.getenv\s*\([^,\n]+,"),
        _PY_SUFFIXES,
        "os.getenv with a default creates a runtime fallback.",
    ),
    DiffRule(
        "py-no-dict-get-default",
        re.compile(r"\.get\s*\([^,\n]+,"),
        _PY_SUFFIXES,
        "dict.get with a default hides missing required data.",
    ),
    DiffRule(
        "rs-no-unwrap-or",
        re.compile(r"\.unwrap_or(?:_default)?\s*\("),
        _RUST_SUFFIXES,
        "unwrap_or fallback paths hide failed Rust results.",
    ),
)

_THREADS_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          path
          isResolved
          comments(first: 50) {
            nodes {
              body
              url
            }
          }
        }
      }
    }
  }
}
"""

_COMMIT_EVIDENCE = re.compile(r"(?:commit|commits/|[/-])\s*[0-9a-f]{7,40}\b|\b[0-9a-f]{12,40}\b", re.IGNORECASE)
_LEDGER_EVIDENCE = re.compile(r"disposition[- ]ledger|resolution[- ]ledger", re.IGNORECASE)
_DIRECT_PLAYWRIGHT = re.compile(r"\b(?:bunx|npx|npm|pnpm|yarn)\s+(?:exec\s+)?playwright\b|\bplaywright\s+test\b")


def _fail(message: str) -> NoReturn:
    print(f"FATAL: {message}", file=sys.stderr)
    sys.exit(1)


def _profile(profile: str) -> ProjectProfile:
    try:
        return PROJECT_PROFILES[profile]
    except KeyError:
        _fail(
            f"unsupported project profile {profile!r}; "
            f"expected one of: {', '.join(SUPPORTED_PROFILES)}"
        )


def _has_sage_file(target: Path) -> bool:
    return any(path.suffix == ".sage" and ".git" not in path.parts for path in target.rglob("*.sage"))


def check_profile(target: Path, profile: str) -> None:
    """Fail if the target repository does not match its curated project profile."""
    target = target.resolve()
    project_profile = _profile(profile)
    missing = [path for path in project_profile.required_paths if not (target / path).exists()]
    if project_profile.requires_bun_lock and not (
        (target / "bun.lock").exists() or (target / "bun.lockb").exists()
    ):
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
    if rule.rule_id == "no-const-assignment" and _is_config_path(path):
        return False
    return Path(path).name == "justfile" or path.endswith(rule.suffixes)


def diff_findings(diff_text: str) -> list[str]:
    """Return deterministic findings introduced by added lines in a unified diff."""
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
                for rule in DIFF_RULES:
                    if _rule_applies(file_path, rule) and rule.pattern.search(text):
                        findings.append(f"{file_path}:{line.target_line_no}: {rule.rule_id}: {rule.message}")
    return findings


def check_diff(diff: Path) -> None:
    """Fail if the PR unified diff introduces deterministic QC violations."""
    findings = diff_findings(diff.read_text())
    if findings:
        print("Deterministic diff gate found introduced violations:", file=sys.stderr)
        for finding in findings:
            print(f"- {finding}", file=sys.stderr)
        sys.exit(1)
    print("Deterministic diff gate found no introduced violations.")


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


def _delegates_to_global_qc(output: str, project_profile: ProjectProfile) -> bool:
    return f"ai-review-ci/justfiles/{project_profile.justfile_name}" in output and " -d . " in f" {output} "


def check_delegation(target: Path, profile: str) -> None:
    """Fail if target test/test-ci recipes do not delegate to global QC."""
    target = target.resolve()
    project_profile = _profile(profile)
    check_profile(target, profile)
    justfile = _justfile_for(target)
    failed: list[str] = []
    for recipe in ("test", "test-ci"):
        output = _dry_run_recipe(target, justfile, recipe)
        if not _delegates_to_global_qc(output, project_profile):
            failed.append(recipe)
    if failed:
        _fail(
            f"{target} does not delegate {profile} recipe(s) through "
            f"~/ai-review-ci/justfiles/{project_profile.justfile_name} "
            f"with -d .: {', '.join(failed)}"
        )
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
    if not _delegates_to_global_qc(output, project_profile):
        _fail(
            f"{target} app-boot must delegate through "
            f"~/ai-review-ci/justfiles/{project_profile.justfile_name} with -d ."
        )
    if _DIRECT_PLAYWRIGHT.search(output):
        _fail(
            f"{target} app-boot must not invoke Playwright directly; "
            "delegate to ~/ai-review-ci/justfiles/bun.just"
        )
    result = subprocess.run(["just", "--justfile", str(justfile), "-d", str(target), "app-boot"])
    if result.returncode != 0:
        _fail(f"app-boot gate failed for {target}")
    print(f"App boot gate passed for {target}.")


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


def _thread_nodes(repo: str, pr_number: int) -> list[JsonDict]:
    owner, name = repo.split("/")
    nodes: list[JsonDict] = []
    cursor: str | None = None
    while True:
        args = [
            "api",
            "graphql",
            "-f",
            f"query={_THREADS_QUERY}",
            "-F",
            f"owner={owner}",
            "-F",
            f"name={name}",
            "-F",
            f"number={pr_number}",
        ]
        if cursor:
            args.extend(["-F", f"cursor={cursor}"])
        page = _gh_json(args)["data"]["repository"]["pullRequest"]["reviewThreads"]
        nodes.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            return nodes
        cursor = page["pageInfo"]["endCursor"]


def _comments(node: JsonDict) -> list[JsonDict]:
    comments = node["comments"]["nodes"]
    if not isinstance(comments, list):
        _fail("review thread comments were not an array")
    return comments


def _is_ai_review_thread(node: JsonDict) -> bool:
    return any(FINGERPRINT_MARKER in str(comment["body"]) for comment in _comments(node))


def _has_resolution_evidence(node: JsonDict) -> bool:
    for comment in _comments(node):
        body = str(comment["body"])
        if _COMMIT_EVIDENCE.search(body) or _LEDGER_EVIDENCE.search(body):
            return True
    return False


def check_review_threads(repo: str, pr_number: int) -> None:
    """Fail unless all ai-review PR threads are resolved with visible evidence."""
    failures: list[str] = []
    for node in _thread_nodes(repo, pr_number):
        if not _is_ai_review_thread(node):
            continue
        path = str(node["path"])
        if not node["isResolved"]:
            failures.append(f"{path}: unresolved ai-review thread")
        elif not _has_resolution_evidence(node):
            failures.append(f"{path}: resolved ai-review thread lacks commit or disposition-ledger evidence")
    if failures:
        print("Review thread gate found unresolved or unevidenced threads:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        sys.exit(1)
    print(f"Review thread gate passed for {repo} PR #{pr_number}.")


def required_check_contexts(profile: str) -> tuple[str, ...]:
    """Required branch-protection check contexts for a curated project profile."""
    project_profile = _profile(profile)
    if project_profile.requires_app_boot:
        return BASE_REQUIRED_CHECK_CONTEXTS[:2] + (APP_BOOT_CHECK_CONTEXT,) + BASE_REQUIRED_CHECK_CONTEXTS[2:]
    return BASE_REQUIRED_CHECK_CONTEXTS


def branch_protection_payload(profile: str) -> JsonDict:
    """GitHub branch protection payload for the required global QC checks."""
    contexts = required_check_contexts(profile)
    return {
        "required_status_checks": {
            "strict": True,
            "contexts": [],
            "checks": [{"context": context, "app_id": -1} for context in contexts],
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
