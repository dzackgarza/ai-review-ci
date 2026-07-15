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
          comments(first: 100) {
            pageInfo { hasNextPage endCursor }
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

_THREAD_COMMENTS_QUERY = """
query($threadId: ID!, $cursor: String!) {
  node(id: $threadId) {
    ... on PullRequestReviewThread {
      comments(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes { body url }
      }
    }
  }
}
"""

_PR_COMMITS_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      commits(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes { commit { oid } }
      }
    }
  }
}
"""

_DISPOSITION_FIELD = re.compile(
    r"^\s*Disposition:\s*"
    r"(?P<disposition>Accepted as written|Accepted with modified remediation|Rejected|Duplicate|Outdated|"
    r"Backlogged as minor technical debt)\s*\.?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_POLICY_CODE = re.compile(r"\bPOLICY\.[A-Z][A-Z0-9_]*\b", re.IGNORECASE)
_COMMIT_FIELD = re.compile(
    r"^\s*Commit:\s*(?P<commit>[0-9a-f]{7,40})\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_SUPERSEDING_COMMIT_FIELD = re.compile(
    r"^\s*Superseding commit:\s*(?P<commit>[0-9a-f]{7,40})\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_CANONICAL_THREAD_FIELD = re.compile(
    r"^\s*Canonical thread:\s*(?:https?://\S+|[A-Za-z0-9_-]+)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_DEBT_ISSUE_FIELD = re.compile(
    r"^\s*Debt issue:\s*https://github\.com/\S+/issues/\d+\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_BURDEN_DISPOSITION = re.compile(
    r"^(?:solved by|invalidated by|transferred to|remains open in)\b",
    re.IGNORECASE,
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
        any(f"ai-review-ci/justfiles/{justfile_name}" in line and re.search(r"(?:-d|--working-directory)\s+\.", line) is not None for line in command_lines)
        for justfile_name in project_profile.justfile_names
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


def _graphql_object(value: object, context: str) -> JsonDict:
    if not isinstance(value, dict):
        _fail(f"GitHub returned invalid {context}: expected an object")
    return value


def _graphql_nodes(value: object, context: str) -> list[JsonDict]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        _fail(f"GitHub returned invalid {context}: expected an object array")
    return value


def _append_remaining_thread_comments(node: JsonDict) -> None:
    connection = _graphql_object(node.get("comments"), "review-thread comments connection")
    comments = _graphql_nodes(connection.get("nodes"), "review-thread comments")
    page_info = _graphql_object(connection.get("pageInfo"), "review-thread comment page info")
    cursor = page_info.get("endCursor")
    while page_info.get("hasNextPage"):
        if not isinstance(cursor, str) or not cursor:
            _fail("GitHub reported another review-thread comment page without an end cursor")
        payload = _gh_json(
            [
                "api",
                "graphql",
                "-f",
                f"query={_THREAD_COMMENTS_QUERY}",
                "-F",
                f"threadId={node['id']}",
                "-F",
                f"cursor={cursor}",
            ]
        )
        data = _graphql_object(payload.get("data"), "GraphQL data")
        thread = data.get("node")
        if thread is None:
            _fail(f"review thread {node['id']} not found or inaccessible")
        connection = _graphql_object(
            _graphql_object(thread, "review thread").get("comments"),
            "review-thread comments connection",
        )
        comments.extend(
            _graphql_nodes(connection.get("nodes"), "review-thread comments")
        )
        page_info = _graphql_object(
            connection.get("pageInfo"),
            "review-thread comment page info",
        )
        cursor = page_info.get("endCursor")
    _graphql_object(node.get("comments"), "review-thread comments connection")["nodes"] = comments


def _thread_nodes(repo: str, pr_number: int) -> list[JsonDict]:
    owner, name = repo.split("/", 1)
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
        payload = _gh_json(args)
        data = _graphql_object(payload.get("data"), "GraphQL data")
        repository = data.get("repository")
        if repository is None:
            _fail(f"repository {repo} not found or inaccessible")
        pull_request = _graphql_object(repository, "repository").get("pullRequest")
        if pull_request is None:
            _fail(f"pull request #{pr_number} not found in {repo}")
        page = _graphql_object(
            _graphql_object(pull_request, "pull request").get("reviewThreads"),
            "review-threads connection",
        )
        page_nodes = _graphql_nodes(page.get("nodes"), "review-thread nodes")
        for node in page_nodes:
            _append_remaining_thread_comments(node)
            nodes.append(node)
        page_info = _graphql_object(page.get("pageInfo"), "review-thread page info")
        if not page_info.get("hasNextPage"):
            return nodes
        cursor = page_info.get("endCursor")
        if not isinstance(cursor, str) or not cursor:
            _fail("GitHub reported another review-thread page without an end cursor")


def _comments(node: JsonDict) -> list[JsonDict]:
    connection = _graphql_object(node.get("comments"), "review-thread comments connection")
    return _graphql_nodes(connection.get("nodes"), "review-thread comments")


def _field_value(body: str, label: str) -> str | None:
    match = re.search(
        rf"^\s*{re.escape(label)}:\s*(?P<value>\S(?:.*\S)?)\s*$",
        body,
        re.IGNORECASE | re.MULTILINE,
    )
    if match is None:
        return None
    value = match.group("value").strip()
    if re.fullmatch(r"<[^>]+>", value):
        return None
    return value


def _basis_is_valid(body: str) -> bool:
    policy = _field_value(body, "Policy basis")
    if policy is not None and _POLICY_CODE.search(policy):
        return True
    return _field_value(body, "Factual/contract basis") is not None


def _deletion_fields_are_valid(body: str) -> bool:
    artifact = _field_value(body, "Deleted artifact")
    if artifact is None:
        return False
    if artifact.casefold() == "none":
        return True
    disposition = _field_value(body, "Burden disposition")
    return bool(
        _field_value(body, "Original burden")
        and disposition
        and _BURDEN_DISPOSITION.search(disposition)
        and _field_value(body, "Verification")
    )


def _reply_has_resolution_evidence(body: str) -> bool:
    disposition_match = _DISPOSITION_FIELD.search(body)
    if disposition_match is None or not _basis_is_valid(body):
        return False
    if not all(
        _field_value(body, label)
        for label in (
            "Pre-filter",
            "Claim",
            "Code/action taken or explicit non-change",
            "Audit anchor",
        )
    ):
        return False

    disposition = disposition_match.group("disposition").lower()
    if disposition.startswith("accepted"):
        return bool(
            _field_value(body, "Remediation")
            and _field_value(body, "Proof")
            and _COMMIT_FIELD.search(body)
            and _deletion_fields_are_valid(body)
        )
    if disposition == "duplicate":
        return bool(_CANONICAL_THREAD_FIELD.search(body))
    if disposition == "outdated":
        return bool(_SUPERSEDING_COMMIT_FIELD.search(body))
    if disposition == "backlogged as minor technical debt":
        return bool(_DEBT_ISSUE_FIELD.search(body))
    return disposition == "rejected"


def _resolution_reply(node: JsonDict) -> str | None:
    for comment in reversed(_comments(node)[1:]):
        body = str(comment.get("body", ""))
        if _reply_has_resolution_evidence(body):
            return body
    return None


def _has_resolution_evidence(node: JsonDict) -> bool:
    return _resolution_reply(node) is not None


def _pr_commit_shas(repo: str, pr_number: int) -> set[str]:
    owner, name = repo.split("/", 1)
    commits: set[str] = set()
    cursor: str | None = None
    while True:
        args = [
            "api",
            "graphql",
            "-f",
            f"query={_PR_COMMITS_QUERY}",
            "-F",
            f"owner={owner}",
            "-F",
            f"name={name}",
            "-F",
            f"number={pr_number}",
        ]
        if cursor:
            args.extend(["-F", f"cursor={cursor}"])
        payload = _gh_json(args)
        data = _graphql_object(payload.get("data"), "GraphQL data")
        repository = data.get("repository")
        if repository is None:
            _fail(f"repository {repo} not found or inaccessible")
        pull_request = _graphql_object(repository, "repository").get("pullRequest")
        if pull_request is None:
            _fail(f"pull request #{pr_number} not found in {repo}")
        connection = _graphql_object(
            _graphql_object(pull_request, "pull request").get("commits"),
            "pull-request commits connection",
        )
        for node in _graphql_nodes(connection.get("nodes"), "pull-request commit nodes"):
            commit = _graphql_object(node.get("commit"), "pull-request commit")
            oid = commit.get("oid")
            if not isinstance(oid, str) or not re.fullmatch(
                r"[0-9a-f]{40}", oid, re.IGNORECASE
            ):
                _fail("GitHub returned an invalid pull-request commit SHA")
            commits.add(oid.lower())
        page_info = _graphql_object(connection.get("pageInfo"), "commit page info")
        if not page_info.get("hasNextPage"):
            return commits
        cursor = page_info.get("endCursor")
        if not isinstance(cursor, str) or not cursor:
            _fail("GitHub reported another commit page without an end cursor")


def _commit_match_count(cited: str, commits: set[str]) -> int:
    return sum(sha.startswith(cited.lower()) for sha in commits)


def _audit_anchor_error(
    body: str,
    commits: set[str],
    repo_root: Path,
) -> str | None:
    anchor = _field_value(body, "Audit anchor")
    assert anchor is not None
    if re.fullmatch(r"https?://\S+", anchor):
        return None
    if re.fullmatch(r"[0-9a-f]{7,40}", anchor, re.IGNORECASE):
        if _commit_match_count(anchor, commits) == 1:
            return None
        return f"proof anchor {anchor} is not a unique commit on this PR"
    path_text = anchor.split("::", 1)[0]
    path_text = re.sub(r"#L\d+(?:-L\d+)?$", "", path_text)
    path_text = re.sub(r":\d+(?::\d+)?$", "", path_text)
    if path_text and (repo_root / path_text).is_file():
        return None
    return f"proof anchor {anchor} does not exist"


def _reply_semantic_errors(
    body: str,
    commits: set[str],
    repo_root: Path,
) -> list[str]:
    disposition_match = _DISPOSITION_FIELD.search(body)
    assert disposition_match is not None
    disposition = disposition_match.group("disposition").lower()
    errors: list[str] = []
    if disposition.startswith("accepted"):
        commit_match = _COMMIT_FIELD.search(body)
        assert commit_match is not None
        cited = commit_match.group("commit")
        if _commit_match_count(cited, commits) != 1:
            errors.append(f"cited commit {cited} is not on this PR")
        anchor_error = _audit_anchor_error(body, commits, repo_root)
        if anchor_error:
            errors.append(anchor_error)
    elif disposition == "outdated":
        commit_match = _SUPERSEDING_COMMIT_FIELD.search(body)
        assert commit_match is not None
        cited = commit_match.group("commit")
        if _commit_match_count(cited, commits) != 1:
            errors.append(f"superseding commit {cited} is not on this PR")
    return errors


def check_review_threads(
    repo: str,
    pr_number: int,
    repo_root: Path = Path("."),
) -> None:
    """Fail unless every PR review thread is resolved with visible evidence."""
    failures: list[str] = []
    commits: set[str] | None = None
    for node in _thread_nodes(repo, pr_number):
        path = str(node["path"])
        if not node["isResolved"]:
            failures.append(f"{path}: unresolved review thread")
            continue
        reply = _resolution_reply(node)
        if reply is None:
            failures.append(
                f"{path}: resolved review thread lacks a thread-local evidenced disposition"
            )
            continue
        disposition_match = _DISPOSITION_FIELD.search(reply)
        assert disposition_match is not None
        disposition = disposition_match.group("disposition").lower()
        if disposition.startswith("accepted") or disposition == "outdated":
            if commits is None:
                commits = _pr_commit_shas(repo, pr_number)
            for error in _reply_semantic_errors(reply, commits, repo_root):
                failures.append(f"{path}: {error}")
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
        insertion = BASE_REQUIRED_CHECK_CONTEXTS.index("pr-description-checklist / pr-description-checklist")
        return BASE_REQUIRED_CHECK_CONTEXTS[:insertion] + (APP_BOOT_CHECK_CONTEXT,) + BASE_REQUIRED_CHECK_CONTEXTS[insertion:]
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
