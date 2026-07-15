from __future__ import annotations

import importlib.util
import json
import subprocess
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


def test_state_path_is_namespaced_by_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    triage = load_triage_state()
    calls: list[list[str]] = []

    def fake_run(args: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, ".git/ai-review-ci/state.json\n", "")

    monkeypatch.setattr(triage, "run", fake_run)

    triage.state_path("owner/first", 7)
    first = calls[-1][-1]
    triage.state_path("owner/second", 7)
    second = calls[-1][-1]

    assert first != second
    assert "owner-first" in first
    assert "owner-second" in second


def test_load_previous_rejects_non_object_state(tmp_path: Path) -> None:
    triage = load_triage_state()
    path = tmp_path / "state.json"
    path.write_text(json.dumps([]), encoding="utf-8")

    with pytest.raises(SystemExit, match="expected a JSON object"):
        triage.load_previous(path)


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
