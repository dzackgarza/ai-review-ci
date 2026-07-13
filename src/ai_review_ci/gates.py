"""Deterministic gates that do not depend on reviewer judgment."""

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn

from pydantic import BaseModel, ConfigDict
from unidiff import PatchSet

from ai_review_ci.threads import FINGERPRINT_MARKER

JsonDict = dict[str, Any]

_TS_JS_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
_PY_SUFFIXES = (".py",)
_RUST_SUFFIXES = (".rs",)
_SHELL_SUFFIXES = (".sh",)
_JUST_SUFFIXES = (".just",)


class DiffRule(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    rule_id: str
    pattern: re.Pattern[str]
    suffixes: tuple[str, ...]
    message: str


class ProjectProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    justfile_names: tuple[str, ...]
    required_paths: tuple[str, ...]
    requires_bun_lock: bool = False
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
    "rust": ProjectProfile(name="rust", justfile_names=("rust.just",), required_paths=("Cargo.toml",)),
    "sage": ProjectProfile(name="sage", justfile_names=("sage.just",), required_paths=("pyproject.toml",), requires_sage_file=True),
}

BASE_REQUIRED_CHECK_CONTEXTS = (
    "deterministic-diff / deterministic-diff",
    "delegation-conformance / delegation-conformance",
    "qc-doctor / qc-doctor",
    "pr-description-checklist / pr-description-checklist",
    "general / review",
    "slop / review",
    "thread-resolution / thread-resolution",
)

APP_BOOT_CHECK_CONTEXT = "app-boot / app-boot"

SUPPORTED_PROFILES = tuple(PROJECT_PROFILES)

REQUIRED_CHECK_CONTEXTS = BASE_REQUIRED_CHECK_CONTEXTS


DIFF_RULES = (
    DiffRule(
        rule_id="no-nullish-coalescing",
        pattern=re.compile(r"\?\?"),
        suffixes=_TS_JS_SUFFIXES,
        message="Nullish coalescing introduces a runtime fallback.",
    ),
    DiffRule(
        rule_id="ts-no-or-default",
        pattern=re.compile(r"\|\|"),
        suffixes=_TS_JS_SUFFIXES + _SHELL_SUFFIXES + _JUST_SUFFIXES,
        message="Logical OR introduces a fallback/default path.",
    ),
    DiffRule(
        rule_id="no-double-cast",
        pattern=re.compile(r"\bas\s+(?:unknown|any|never)\s+as\b"),
        suffixes=_TS_JS_SUFFIXES,
        message="Double-casting bypasses TypeScript's type system.",
    ),
    DiffRule(
        rule_id="ts-no-any-cast",
        pattern=re.compile(r"\bas\s+any\b"),
        suffixes=_TS_JS_SUFFIXES,
        message="as any disables TypeScript evidence at the boundary.",
    ),
    DiffRule(
        rule_id="ts-no-vitest-mock-boundary",
        pattern=re.compile(r"\bvi\.(?:mock|stubGlobal|fn|spyOn|stubEnv)\s*\("),
        suffixes=_TS_JS_SUFFIXES,
        message="Vitest mock helpers replace real proof boundaries.",
    ),
    DiffRule(
        rule_id="ts-no-jest-mock-boundary",
        pattern=re.compile(r"\bjest\.(?:mock|fn|spyOn)\s*\("),
        suffixes=_TS_JS_SUFFIXES,
        message="Jest mock helpers replace real proof boundaries.",
    ),
    DiffRule(
        rule_id="no-const-assignment",
        pattern=re.compile(
            r"^\s*(?:export\s+)?const\s+(?:"
            r"[A-Z][A-Z0-9_]*(?:URL|URI|ENDPOINT|HOST|PORT|SERVER|DATABASE|COMMAND|CWD|PATH|DIR|DIRECTORY|TIMEOUT|RETRY|THRESHOLD|SECRET|TOKEN)[A-Z0-9_]*"
            r"\s*=\s*(?:[\"'`][^\"'`]*[\"'`]|[0-9]+(?:\.[0-9]+)?|\[[^\n]*\]|\{[^\n]*\})"
            r"|[A-Z][A-Z0-9_]*\s*=\s*[\"'`](?:https?://|file://)[^\"'`]*[\"'`]"
            r")",
        ),
        suffixes=_TS_JS_SUFFIXES,
        message="Hardcoded config-shaped constants belong in required config.",
    ),
    DiffRule(
        rule_id="py-no-getenv-default",
        pattern=re.compile(r"\bos\.getenv\s*\([^,\n]+,"),
        suffixes=_PY_SUFFIXES,
        message="os.getenv with a default creates a runtime fallback.",
    ),
    DiffRule(
        rule_id="py-no-dict-get-default",
        pattern=re.compile(r"\.get\s*\([^,\n]+,"),
        suffixes=_PY_SUFFIXES,
        message="dict.get with a default hides missing required data.",
    ),
    DiffRule(
        rule_id="rs-no-unwrap-or",
        pattern=re.compile(r"\.unwrap_or(?:_default)?\s*\("),
        suffixes=_RUST_SUFFIXES,
        message="unwrap_or fallback paths hide failed Rust results.",
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
_PROOF_COMMAND = re.compile(r"\*\*Proof:\*\*\s*`([^`]+)`")
_RESOLVE_THREAD_MUTATION = """
mutation($threadId: ID!) {
  resolveReviewThread(input: {threadId: $threadId}) {
    thread { id isResolved }
  }
}
"""


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


def delegates_to_global_qc(output: str, project_profile: ProjectProfile) -> bool:
    """Require exactly the centrally declared delegation set for a profile."""
    observed = set(re.findall(r"ai-review-ci/justfiles/([a-z-]+\.just)", output))
    expected = set(project_profile.justfile_names)
    command_lines = output.splitlines()
    return observed == expected and all(
        any(
            f"ai-review-ci/justfiles/{justfile_name}" in line
            and re.search(r"(?:-d|--working-directory)\s+\.", line) is not None
            for line in command_lines
        )
        for justfile_name in project_profile.justfile_names
    )


def check_delegation(target: Path, profile: str) -> None:
    """Fail if target test/test-ci recipes do not delegate to global QC."""
    target = target.resolve()
    project_profile = _profile(profile)
    check_profile(target, profile)
    justfile = _justfile_for(target)
    failed: list[str] = []
    for recipe in ("test", "test-ci"):
        output = _dry_run_recipe(target, justfile, recipe)
        if not delegates_to_global_qc(output, project_profile):
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
    if not delegates_to_global_qc(output, project_profile):
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


def _first_ai_review_proof(node: JsonDict) -> str | None:
    """Proof command from an ai-review thread body, if the body uses our marker."""
    for comment in _comments(node):
        body = str(comment["body"])
        if FINGERPRINT_MARKER not in body:
            continue
        match = _PROOF_COMMAND.search(body)
        if match is not None:
            return match.group(1)
    return None


def _safe_proof_args(proof_command: str) -> list[str] | None:
    """Return argv for safe grep/rg proof commands; reject shell features."""
    try:
        args = shlex.split(proof_command)
    except ValueError:
        return None
    if not args or args[0] not in {"grep", "rg"}:
        return None
    if any(token in {";", "&&", "||", "|", ">", "<"} for token in args):
        return None
    if args[0] == "grep":
        # grep proofs must name at least a pattern and a target path. Recursive
        # project scans are too broad to auto-resolve safely.
        operands = [arg for arg in args[1:] if not arg.startswith("-")]
        if len(operands) < 2:
            return None
    return args


def _proof_is_stale(proof_command: str) -> bool:
    args = _safe_proof_args(proof_command)
    if args is None:
        return False
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    # grep/rg exit 1 means no matches. Any other non-zero status is an
    # execution error and must not auto-resolve the thread.
    return result.returncode == 1


def _resolve_review_thread(thread_id: str) -> None:
    _gh_json(
        [
            "api",
            "graphql",
            "-f",
            f"query={_RESOLVE_THREAD_MUTATION}",
            "-F",
            f"threadId={thread_id}",
        ]
    )


def _auto_resolve_stale_thread(node: JsonDict) -> bool:
    proof = _first_ai_review_proof(node)
    if proof is None or not _proof_is_stale(proof):
        return False
    thread_id = str(node.get("id", ""))
    if not thread_id:
        _fail("cannot auto-resolve stale proof thread without a thread id")
    _resolve_review_thread(thread_id)
    return True


def _has_resolution_evidence(node: JsonDict) -> bool:
    for comment in _comments(node):
        body = str(comment["body"])
        if _COMMIT_EVIDENCE.search(body) or _LEDGER_EVIDENCE.search(body):
            return True
    return False


def check_review_threads(repo: str, pr_number: int) -> None:
    """Fail unless every PR review thread is resolved with visible evidence."""
    failures: list[str] = []
    for node in _thread_nodes(repo, pr_number):
        path = str(node["path"])
        if not node["isResolved"]:
            if _auto_resolve_stale_thread(node):
                continue
            failures.append(f"{path}: unresolved review thread")
        elif not _has_resolution_evidence(node):
            failures.append(f"{path}: resolved review thread lacks commit or disposition-ledger evidence")
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
