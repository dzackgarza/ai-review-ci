from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "pr-feedback-triage" / "scripts" / "triage_state.py"


def load_triage_state() -> ModuleType:
    spec = importlib.util.spec_from_file_location("triage_state", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_graphql_queries_have_balanced_selection_braces() -> None:
    triage = load_triage_state()

    assert triage.THREADS_QUERY.count("{") == triage.THREADS_QUERY.count("}")
    assert triage.COMMENTS_QUERY.count("{") == triage.COMMENTS_QUERY.count("}")
    assert triage.PR_COMMITS_QUERY.count("{") == triage.PR_COMMITS_QUERY.count("}")


def thread(
    finding: str,
    *replies: str,
    resolved: bool = False,
    path: str = "src/reader.py",
) -> dict[str, object]:
    comments = [
        {
            "id": f"comment-{index}",
            "databaseId": index,
            "url": f"https://github.com/owner/repo/pull/7#discussion_r{index}",
            "author": {"login": "reviewer" if index == 0 else "worker"},
            "body": body,
            "createdAt": "2026-07-15T00:00:00Z",
        }
        for index, body in enumerate((finding, *replies))
    ]
    return {
        "id": "PRRT_thread",
        "isResolved": resolved,
        "isOutdated": False,
        "path": path,
        "line": 12,
        "comments": {"nodes": comments},
    }


def test_stable_key_prefers_fingerprint_and_ignores_line_shifts() -> None:
    triage = load_triage_state()
    finding = "<!-- ai-review-fingerprint: " + "a" * 64 + " -->\n## Read failure"
    first = thread(finding)
    shifted = thread(finding)
    shifted["line"] = 900

    assert triage.stable_key(first) == "fp:" + "a" * 64
    assert triage.stable_key(shifted) == triage.stable_key(first)


def test_normalized_title_ignores_multiline_html_comment() -> None:
    triage = load_triage_state()
    body = """\
<!--
generated review metadata that is not visible
-->
## Reject unsafe fallback
"""

    assert triage.normalized_title(body) == "reject unsafe fallback"


def test_disposition_parser_requires_complete_thread_reply_not_root_text() -> None:
    triage = load_triage_state()
    accepted = """\
Disposition: Accepted as written
Policy basis: POLICY.NO_ERROR_DISCARD
Pre-filter: Gate 1 correctness defect -> current-PR remediation
Claim: Read failures are discarded.
Remediation: Propagate the read error.
Code/action taken or explicit non-change: Propagate the read error.
Proof: Boundary test rejects partial success.
Commit: 123456789abc
Audit anchor: tests/test_reader.py::test_failure
Deleted artifact: None
"""
    root_only = thread(accepted, resolved=True)
    incomplete_reply = thread(
        "Read failures are discarded.",
        """\
Disposition: Accepted as written
Policy basis: POLICY.NO_ERROR_DISCARD
Pre-filter: Gate 1 correctness defect -> current-PR remediation
Claim: Read failures are discarded.
Remediation: Propagate the read error.
Code/action taken or explicit non-change: Propagate the read error.
Proof: Boundary test rejects partial success.
Audit anchor: tests/test_reader.py::test_failure
""",
        resolved=True,
    )
    complete_reply = thread("Read failures are discarded.", accepted, resolved=True)

    assert triage.disposition_of(root_only) is None
    assert triage.disposition_of(incomplete_reply)["complete"] is False
    assert triage.classify(incomplete_reply, triage.disposition_of(incomplete_reply), None) == "OPEN-PENDING"
    assert triage.disposition_of(complete_reply)["complete"] is True
    assert triage.classify(complete_reply, triage.disposition_of(complete_reply), None) == "CLOSED"


def test_re_emitted_finding_uses_prior_complete_disposition_as_resume_state() -> None:
    triage = load_triage_state()
    finding = "<!-- ai-review-fingerprint: " + "b" * 64 + " -->\n## Missing proof"
    current = thread(finding)
    key = triage.stable_key(current)
    previous = {
        key: {
            "verdict": "rejected",
            "complete": True,
            "commit": None,
            "by": "worker",
            "url": "https://github.com/owner/repo/pull/7#discussion_r4",
        }
    }

    records = triage.build_records([current], previous, "f" * 40)

    assert records[0]["state"] == "RE-RAISED"
    assert records[0]["key"] == key


def test_stable_key_uses_the_complete_visible_finding_not_only_its_title() -> None:
    triage = load_triage_state()
    first = thread("## Shared title\nThe parser discards the first failure.")
    second = thread("## Shared title\nThe parser fabricates a fallback value.")

    assert triage.stable_key(first) != triage.stable_key(second)


def test_disposition_parser_selects_the_latest_complete_reply() -> None:
    triage = load_triage_state()
    incomplete = """\
Disposition: Accepted as written
Policy basis: POLICY.NO_ERROR_DISCARD
Pre-filter: <gate>
Claim: Read failures are discarded.
Remediation: Propagate the read error.
Code/action taken or explicit non-change: Propagate the read error.
Proof: Boundary test rejects partial success.
Commit: 123456789abc
Audit anchor: <anchor>
Deleted artifact: None
"""
    corrected = """\
Disposition: Accepted as written.
Policy basis: POLICY.NO_ERROR_DISCARD
Pre-filter: Gate 1 correctness defect -> current-PR remediation
Claim: Read failures are discarded.
Remediation: Propagate the read error.
Code/action taken or explicit non-change: Propagate the read error.
Proof: Boundary test rejects partial success.
Commit: abcdef123456
Audit anchor: tests/test_reader.py::test_failure
Deleted artifact: None
"""
    item = thread("Read failures are discarded.", incomplete, corrected, resolved=True)

    disposition = triage.disposition_of(item)

    assert disposition["complete"] is True
    assert disposition["commit"] == "abcdef123456"
    assert disposition["body"] == corrected


def test_deletion_disposition_requires_burden_fields() -> None:
    triage = load_triage_state()
    missing_burden = """\
Disposition: Accepted with modified remediation
Policy basis: POLICY.NO_DELETION_LAUNDERING
Pre-filter: Gate 2 deletion -> burden disposition required
Claim: A tracked proof artifact is deleted.
Remediation: Transfer its proof burden to the owned boundary test.
Code/action taken or explicit non-change: Deleted tests/test_legacy.py.
Proof: The replacement boundary test fails on the former broken behavior.
Commit: abcdef123456
Audit anchor: tests/test_boundary.py::test_failure
Deleted artifact: tests/test_legacy.py
"""
    complete = (
        missing_burden
        + """\
Original burden: Prove read failures remain visible.
Burden disposition: solved by tests/test_boundary.py::test_failure
Verification: Focused boundary test passes.
"""
    )

    assert triage.disposition_of(thread("Finding", missing_burden))["complete"] is False
    assert triage.disposition_of(thread("Finding", complete))["complete"] is True


def test_build_records_preserves_raw_finding_and_current_head() -> None:
    triage = load_triage_state()
    current = thread("Exact reviewer text.")

    record = triage.build_records([current], {}, "a" * 40)[0]

    assert record["head_sha"] == "a" * 40
    assert record["author"] == "reviewer"
    assert record["finding"]["body"] == "Exact reviewer text."
    assert record["comments"][0]["body"] == "Exact reviewer text."


def test_build_records_rejects_fabricated_pr_evidence(tmp_path: Path) -> None:
    triage = load_triage_state()
    accepted = """\
Disposition: Accepted as written
Policy basis: POLICY.NO_ADMIN_COMPLETION
Pre-filter: Gate 1 proof defect -> current-PR remediation
Claim: The collector trusts evidence-shaped text.
Remediation: Validate the cited commit and audit anchor.
Code/action taken or explicit non-change: Added semantic evidence validation.
Proof: The collector leaves fabricated evidence pending.
Commit: 123456789abc
Audit anchor: tests/test_missing.py::test_evidence
Deleted artifact: None
"""
    current = thread("Fabricated evidence.", accepted, resolved=True)

    record = triage.build_records(
        [current],
        {},
        "a" * 40,
        pr_commits={"f" * 40},
        repo_root=tmp_path,
    )[0]

    assert record["state"] == "OPEN-PENDING"
    assert record["disp"]["complete"] is False
    assert "cited commit 123456789abc is not on this PR" in record["disp"]["validation_errors"]
    assert "proof anchor tests/test_missing.py::test_evidence does not exist" in record["disp"]["validation_errors"]


def test_state_path_is_namespaced_by_repository(tmp_path: Path) -> None:
    triage = load_triage_state()
    checkout = git_checkout(tmp_path / "checkout", FIRST_REPO)

    first = triage.state_path("owner/first", 7, checkout)
    second = triage.state_path("owner/second", 7, checkout)
    another_pr = triage.state_path("owner/first", 8, checkout)

    assert len({first, second, another_pr}) == 3
    assert all(path.is_relative_to(checkout / ".git") for path in (first, second, another_pr))


def test_load_previous_rejects_non_object_state(tmp_path: Path) -> None:
    triage = load_triage_state()
    path = tmp_path / "state.json"
    path.write_text(json.dumps([]), encoding="utf-8")

    with pytest.raises(SystemExit, match="expected a JSON object"):
        triage.load_previous(path, "owner/repo", 7)


def test_load_previous_resumes_only_complete_dispositions_for_matching_identity(tmp_path: Path) -> None:
    triage = load_triage_state()
    path = tmp_path / "state.json"
    complete = {"verdict": "rejected", "complete": True}
    path.write_text(json.dumps({
        "repo": "owner/repo", "pr": 7,
        "records": [
            {"key": "completed", "disp": complete},
            {"key": "pending", "disp": {"verdict": "rejected", "complete": False}},
            {"key": "new", "disp": None},
        ],
    }))

    assert triage.load_previous(path, "OWNER/Repo", 7) == {"completed": complete}


def test_fetch_threads_fails_loudly_for_missing_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    triage = load_triage_state()
    monkeypatch.setattr(
        triage,
        "gh_graphql",
        lambda query, **variables: {"data": {"repository": None}},
    )

    with pytest.raises(SystemExit, match="not found or inaccessible"):
        triage.fetch_threads("owner/missing", 7)


def test_fetch_threads_paginates_comments_and_returns_head_sha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    triage = load_triage_state()
    first_comments = [
        {
            "id": f"comment-{index}",
            "databaseId": index,
            "url": f"https://example.test/{index}",
            "author": {"login": "reviewer"},
            "body": f"body {index}",
            "createdAt": "2026-07-15T00:00:00Z",
        }
        for index in range(100)
    ]
    calls = iter(
        [
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "headRefOid": "a" * 40,
                            "reviewThreads": {
                                "nodes": [
                                    {
                                        "id": "thread-1",
                                        "isResolved": False,
                                        "isOutdated": False,
                                        "path": "src/app.py",
                                        "line": 10,
                                        "comments": {
                                            "nodes": first_comments,
                                            "pageInfo": {
                                                "hasNextPage": True,
                                                "endCursor": "comments-100",
                                            },
                                        },
                                    }
                                ],
                                "pageInfo": {
                                    "hasNextPage": False,
                                    "endCursor": None,
                                },
                            },
                        }
                    }
                }
            },
            {
                "data": {
                    "node": {
                        "comments": {
                            "nodes": [
                                {
                                    "id": "comment-100",
                                    "databaseId": 100,
                                    "url": "https://example.test/100",
                                    "author": {"login": "worker"},
                                    "body": "canonical disposition",
                                    "createdAt": "2026-07-15T00:01:00Z",
                                }
                            ],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    }
                }
            },
        ]
    )
    monkeypatch.setattr(triage, "gh_graphql", lambda query, **variables: next(calls))

    head_sha, threads = triage.fetch_threads("owner/repo", 7)

    assert head_sha == "a" * 40
    assert len(threads[0]["comments"]["nodes"]) == 101


FIRST_REPO = "dzackgarza/ai-review-ci"
FIRST_PR = 529
SECOND_REPO = "dzackgarza/sage-lsp-server"
SECOND_PR = 5


def git_checkout(path: Path, repo: str) -> Path:
    subprocess.run(["git", "init", "--quiet", str(path)], check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", f"https://github.com/{repo}.git"],
        cwd=path, check=True,
    )
    subprocess.run(
        ["git", "-c", "user.name=Triage fixture", "-c", "user.email=fixture@example.test",
         "-c", "core.hooksPath=/dev/null", "commit", "--quiet", "--allow-empty", "-m", "fixture"],
        cwd=path, check=True,
    )
    return path


def run_collector(
    checkout: Path, repo: str | None, pr: int, *options: str,
    gh_repo: str | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items() if key != "GH_REPO"}
    if gh_repo is not None:
        env["GH_REPO"] = gh_repo
    command = [sys.executable, str(SCRIPT), "--pr", str(pr), "--json", *options]
    if repo is not None:
        command.extend(["--repo", repo])
    return subprocess.run(
        command, cwd=checkout, env=env, capture_output=True, text=True, check=False,
    )


def metadata_path(checkout: Path, repo: str, pr: int) -> Path:
    slug = repo.replace("/", "-")
    return Path(subprocess.check_output(
        ["git", "rev-parse", "--path-format=absolute", "--git-path",
         f"ai-review-ci/{slug}/pr-feedback-triage-{pr}.json"],
        cwd=checkout, text=True,
    ).strip())


@pytest.mark.gh_boundary
@pytest.mark.parametrize("requested_repo", [SECOND_REPO, None])
def test_collector_rejects_mismatched_checkout(
    tmp_path: Path, requested_repo: str | None,
) -> None:
    checkout = git_checkout(tmp_path / "first", FIRST_REPO)
    result = run_collector(checkout, requested_repo, SECOND_PR, gh_repo=SECOND_REPO)

    assert result.returncode != 0, result.stdout
    assert FIRST_REPO in result.stderr
    assert SECOND_REPO in result.stderr
    assert not metadata_path(checkout, SECOND_REPO, SECOND_PR).exists()


@pytest.mark.gh_boundary
@pytest.mark.parametrize("foreign_identity", [
    {"repo": SECOND_REPO, "pr": FIRST_PR},
    {"repo": FIRST_REPO, "pr": FIRST_PR + 1},
    {"repo": FIRST_REPO},
    {"pr": FIRST_PR},
])
def test_collector_rejects_foreign_resume_state(
    tmp_path: Path, foreign_identity: dict[str, str | int],
) -> None:
    checkout = git_checkout(tmp_path / "first", FIRST_REPO)
    path = metadata_path(checkout, FIRST_REPO, FIRST_PR)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({**foreign_identity, "records": []}))
    before = path.read_bytes()

    result = run_collector(checkout, FIRST_REPO, FIRST_PR, "--no-write")

    assert result.returncode != 0, result.stdout
    assert "triage state" in result.stderr
    assert "identity" in result.stderr
    assert path.read_bytes() == before


@pytest.mark.gh_boundary
def test_collector_keeps_repositories_and_worktrees_isolated(tmp_path: Path) -> None:
    first = git_checkout(tmp_path / "first", FIRST_REPO)
    second = git_checkout(tmp_path / "second", SECOND_REPO)
    linked = tmp_path / "linked"
    subprocess.run(["git", "worktree", "add", "--quiet", "--detach", str(linked)],
                   cwd=first, check=True)
    nested = linked / "nested"
    nested.mkdir()

    def collect(checkout: Path, repo: str, pr: int) -> Path:
        result = run_collector(checkout, repo, pr)
        assert result.returncode == 0, result.stderr
        path = metadata_path(checkout, repo, pr)
        emitted = Path(json.loads(result.stdout)["state_path"])
        assert emitted.is_absolute()
        assert emitted == path
        state = json.loads(path.read_text())
        assert (state["repo"], state["pr"]) == (repo, pr)
        head = subprocess.check_output(
            ["gh", "pr", "view", str(pr), "--repo", repo, "--json", "headRefOid", "-q", ".headRefOid"],
            text=True,
        ).strip()
        assert state["head_sha"] == head
        return path

    first_path = collect(first, FIRST_REPO, FIRST_PR)
    first_bytes = first_path.read_bytes()
    second_path = collect(second, SECOND_REPO, SECOND_PR)
    second_bytes = second_path.read_bytes()
    linked_path = collect(nested, FIRST_REPO, FIRST_PR)
    assert len({first_path, second_path, linked_path}) == 3
    assert first_path.read_bytes() == first_bytes
    assert second_path.read_bytes() == second_bytes
    result = run_collector(first, None, FIRST_PR, "--no-write", gh_repo=FIRST_REPO)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["state_path"] is None
    assert first_path.read_bytes() == first_bytes
    assert not any((checkout / ".pr").exists() for checkout in (first, second, linked))
