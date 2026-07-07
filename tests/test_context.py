"""Reviewer context rendering for captured GitHub alert shapes."""

import json
import os
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

from ai_review_ci.context import (
    _format_alert,
    _thread_digest,
    _validated_alert_page,
    fetch_context,
)


def _alert(number: int, state: str, label: str, path: str, line: int) -> dict[str, object]:
    return {
        "number": number,
        "state": state,
        "html_url": f"https://github.com/owner/repo/security/code-scanning/{number}",
        "rule": {"id": label.lower().replace(" ", "-"), "name": label},
        "most_recent_instance": {"location": {"path": path, "start_line": line}},
    }


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


@pytest.fixture
def gh_fixture(tmp_path: Path) -> Iterator[Path]:
    fixture_dir = tmp_path / "fixture"
    bin_dir = tmp_path / "bin"
    fixture_dir.mkdir()
    bin_dir.mkdir()
    gh_path = bin_dir / "gh"
    shutil.copyfile(Path(__file__).parent / "fixtures" / "gh_context_fixture.py", gh_path)
    gh_path.chmod(0o755)

    original_path = os.environ["PATH"]
    original_fixture_dir = os.environ.get("AI_REVIEW_CI_CONTEXT_FIXTURE_DIR")
    os.environ["PATH"] = f"{bin_dir}:{original_path}"
    os.environ["AI_REVIEW_CI_CONTEXT_FIXTURE_DIR"] = str(fixture_dir)
    yield fixture_dir
    os.environ["PATH"] = original_path
    if original_fixture_dir is None:
        os.environ.pop("AI_REVIEW_CI_CONTEXT_FIXTURE_DIR", None)
    else:
        os.environ["AI_REVIEW_CI_CONTEXT_FIXTURE_DIR"] = original_fixture_dir


def test_alert_format_uses_github_rule_name_without_location_properties() -> None:
    alert = {
        "html_url": "https://github.com/owner/repo/security/code-scanning/1",
        "rule": {"id": "bridge-burning", "name": "Bridge Burning"},
        "most_recent_instance": {"location": {"path": "src/app.py", "start_line": 7}},
    }

    assert _format_alert(alert) == "- **Bridge Burning** at `src/app.py:7`  \n  Alert: https://github.com/owner/repo/security/code-scanning/1"


def test_alert_format_uses_github_rule_id_when_name_is_absent() -> None:
    alert = {
        "html_url": "https://github.com/owner/repo/security/code-scanning/2",
        "rule": {"id": "bridge-burning"},
        "most_recent_instance": {"location": {"path": "src/app.py", "start_line": 8}},
    }

    assert _format_alert(alert) == "- **bridge-burning** at `src/app.py:8`  \n  Alert: https://github.com/owner/repo/security/code-scanning/2"


def test_alert_format_rejects_missing_rule_name_and_id() -> None:
    alert = {
        "html_url": "https://github.com/owner/repo/security/code-scanning/3",
        "rule": {},
        "most_recent_instance": {"location": {"path": "src/app.py", "start_line": 9}},
    }

    with pytest.raises(SystemExit):
        _format_alert(alert)


def test_alert_format_rejects_invalid_rule_and_location_shapes() -> None:
    empty_rule_id = {
        "html_url": "https://github.com/owner/repo/security/code-scanning/4",
        "rule": {"id": ""},
        "most_recent_instance": {"location": {"path": "src/app.py", "start_line": 10}},
    }
    string_line = {
        "html_url": "https://github.com/owner/repo/security/code-scanning/5",
        "rule": {"id": "bridge-burning"},
        "most_recent_instance": {"location": {"path": "src/app.py", "start_line": "10"}},
    }

    with pytest.raises(SystemExit):
        _format_alert(empty_rule_id)
    with pytest.raises(SystemExit):
        _format_alert(string_line)


def test_alert_page_validation_rejects_invalid_payload_shapes() -> None:
    with pytest.raises(SystemExit):
        _validated_alert_page("{}", "repos/owner/repo/code-scanning/alerts")
    with pytest.raises(SystemExit):
        _validated_alert_page('["not an alert object"]', "repos/owner/repo/code-scanning/alerts")


def test_fetch_context_renders_alert_states_threads_and_carry_forward(tmp_path: Path, gh_fixture: Path) -> None:
    open_alert = _alert(10, "open", "Open Finding", "src/app.py", 12)
    dismissed_alert = _alert(11, "dismissed", "Rejected Finding", "src/rejected.py", 4)
    dismissed_alert["dismissed_reason"] = "false positive"
    dismissed_alert["dismissed_comment"] = "accepted by maintainer"
    fixed_alert = _alert(12, "fixed", "Fixed Finding", "src/fixed.py", 9)
    _write_json(
        gh_fixture / "alerts.json",
        [
            {"tool_name": "ai-review/slop", "state": "open", "alert": open_alert},
            {
                "tool_name": "ai-review/slop",
                "state": "dismissed",
                "alert": dismissed_alert,
            },
            {"tool_name": "ai-review/slop", "state": "fixed", "alert": fixed_alert},
        ],
    )
    _write_json(
        gh_fixture / "threads.json",
        {
            "nodes": [
                {
                    "path": "justfiles/python.just",
                    "isResolved": False,
                    "comments": {
                        "nodes": [
                            {
                                "body": "Keep vulture status nonzero\nfull comment body",
                            }
                        ]
                    },
                }
            ],
            "pageInfo": {"hasNextPage": False, "endCursor": None},
        },
    )
    output = tmp_path / "context.md"
    carry_forward = tmp_path / "alerts.json"

    fetch_context(
        "owner/repo",
        tool_names="ai-review/slop",
        output=output,
        alerts_output=carry_forward,
        pr_number=3,
    )

    assert output.read_text(encoding="utf-8") == (
        "## Existing repo-wide review findings\n"
        "\n"
        "Open alerts are carried forward into the next SARIF upload by automation. "
        "Do not duplicate them in your report unless you have new evidence, the problem "
        "reappears in a materially different form, or the previous resolution is directly "
        "contradicted by the current code.\n"
        "\n"
        "### ai-review/slop\n"
        "\n"
        "**Open / accepted findings:**\n"
        "- **Open Finding** at `src/app.py:12`  \n"
        "  Alert: https://github.com/owner/repo/security/code-scanning/10\n"
        "\n"
        "**Dismissed / rejected findings:**\n"
        "- **Rejected Finding** at `src/rejected.py:4`  \n"
        "  Alert: https://github.com/owner/repo/security/code-scanning/11 (false positive: accepted by maintainer)\n"
        "\n"
        "**Fixed findings:**\n"
        "- **Fixed Finding** at `src/fixed.py:9`  \n"
        "  Alert: https://github.com/owner/repo/security/code-scanning/12\n"
        "\n"
        "## Review items already surfaced on this PR\n"
        "\n"
        "These findings already have review threads on this pull request. Do not re-raise them; a resolved thread is a disposition.\n"
        "\n"
        "- [open] `justfiles/python.just` — Keep vulture status nonzero\n"
    )
    assert json.loads(carry_forward.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "alerts": [{"tool_name": "ai-review/slop", "alert": open_alert}],
    }


def test_fetch_context_renders_resolved_paginated_threads_and_empty_open_group(tmp_path: Path, gh_fixture: Path) -> None:
    dismissed_alert = _alert(31, "dismissed", "Rejected Finding", "src/rejected.py", 4)
    dismissed_alert["dismissed_reason"] = "false positive"
    dismissed_alert["dismissed_comment"] = None
    _write_json(
        gh_fixture / "alerts.json",
        [
            {
                "tool_name": "ai-review/slop",
                "state": "dismissed",
                "alert": dismissed_alert,
            }
        ],
    )
    _write_json(
        gh_fixture / "threads.json",
        [
            {
                "nodes": [{"isResolved": False, "comments": {"nodes": []}}],
                "pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"},
            },
            {
                "nodes": [
                    {
                        "path": "src/context.py",
                        "isResolved": True,
                        "comments": {
                            "nodes": [
                                {
                                    "body": "Resolved finding\nfull comment body",
                                }
                            ]
                        },
                    }
                ],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            },
        ],
    )
    output = tmp_path / "context.md"

    fetch_context("owner/repo", tool_names="ai-review/slop", output=output, pr_number=4)

    assert output.read_text(encoding="utf-8") == (
        "## Existing repo-wide review findings\n"
        "\n"
        "Open alerts are carried forward into the next SARIF upload by automation. "
        "Do not duplicate them in your report unless you have new evidence, the problem "
        "reappears in a materially different form, or the previous resolution is directly "
        "contradicted by the current code.\n"
        "\n"
        "### ai-review/slop\n"
        "\n"
        "**Dismissed / rejected findings:**\n"
        "- **Rejected Finding** at `src/rejected.py:4`  \n"
        "  Alert: https://github.com/owner/repo/security/code-scanning/31 (false positive)\n"
        "\n"
        "## Review items already surfaced on this PR\n"
        "\n"
        "These findings already have review threads on this pull request. Do not re-raise them; a resolved thread is a disposition.\n"
        "\n"
        "- [resolved] `src/context.py` — Resolved finding\n"
    )


def test_fetch_context_rejects_invalid_dismissal_comment(gh_fixture: Path) -> None:
    dismissed_alert = _alert(32, "dismissed", "Rejected Finding", "src/rejected.py", 4)
    dismissed_alert["dismissed_reason"] = "false positive"
    dismissed_alert["dismissed_comment"] = {"not": "a string"}
    _write_json(
        gh_fixture / "alerts.json",
        [
            {
                "tool_name": "ai-review/slop",
                "state": "dismissed",
                "alert": dismissed_alert,
            }
        ],
    )

    with pytest.raises(SystemExit):
        fetch_context("owner/repo", tool_names="ai-review/slop")


def test_fetch_context_fails_loudly_on_gh_rest_and_graphql_errors(
    gh_fixture: Path,
) -> None:
    _write_json(
        gh_fixture / "failures.json",
        [{"tool_name": "ai-review/general", "state": "open"}],
    )
    with pytest.raises(SystemExit):
        fetch_context("owner/repo", tool_names="ai-review/general")

    (gh_fixture / "failures.json").unlink()
    (gh_fixture / "graphql_failure").write_text("1\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        fetch_context("owner/repo", tool_names="ai-review/general", pr_number=9)


def test_fetch_context_carries_repo_and_pr_alerts_without_duplicate_numbers(tmp_path: Path, gh_fixture: Path) -> None:
    repo_alert = _alert(21, "open", "Repo Finding", "src/repo.py", 2)
    duplicate_pr_alert = _alert(21, "open", "Duplicate PR Finding", "src/pr.py", 3)
    pr_alert = _alert(22, "open", "PR Finding", "src/pr.py", 5)
    _write_json(
        gh_fixture / "alerts.json",
        [
            {"tool_name": "ai-review/general", "state": "open", "alert": repo_alert},
            {
                "tool_name": "ai-review/general",
                "state": "open",
                "ref": "refs/pull/8/merge",
                "alert": duplicate_pr_alert,
            },
            {
                "tool_name": "ai-review/general",
                "state": "open",
                "ref": "refs/pull/8/merge",
                "alert": pr_alert,
            },
        ],
    )
    carry_forward = tmp_path / "carry-forward.json"

    fetch_context(
        "owner/repo",
        tool_names="ai-review/general",
        alerts_output=carry_forward,
        pr_number=8,
    )

    payload = json.loads(carry_forward.read_text(encoding="utf-8"))
    assert payload == {
        "schema_version": 1,
        "alerts": [
            {"tool_name": "ai-review/general", "alert": repo_alert},
            {"tool_name": "ai-review/general", "alert": pr_alert},
        ],
    }


def test_fetch_context_treats_no_analysis_as_empty_context(tmp_path: Path, gh_fixture: Path) -> None:
    _write_json(
        gh_fixture / "no_analysis.json",
        [
            {"tool_name": "ai-review/general", "state": "open"},
            {"tool_name": "ai-review/general", "state": "dismissed"},
            {"tool_name": "ai-review/general", "state": "fixed"},
        ],
    )
    output = tmp_path / "context.md"
    carry_forward = tmp_path / "carry-forward.json"

    fetch_context(
        "owner/repo",
        tool_names="ai-review/general",
        output=output,
        alerts_output=carry_forward,
    )

    assert output.read_text(encoding="utf-8") == (
        "## Existing repo-wide review findings\n"
        "\n"
        "Open alerts are carried forward into the next SARIF upload by automation. "
        "Do not duplicate them in your report unless you have new evidence, the problem "
        "reappears in a materially different form, or the previous resolution is directly "
        "contradicted by the current code.\n"
        "\n"
        "### ai-review/general\n"
        "\n"
        "_No existing findings._\n"
    )
    assert json.loads(carry_forward.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "alerts": [],
    }


def test_fetch_context_treats_code_scanning_disabled_as_empty_context(
    tmp_path: Path,
    gh_fixture: Path,
) -> None:
    _write_json(
        gh_fixture / "code_scanning_disabled.json",
        [
            {"tool_name": "ai-review/general", "state": "open"},
            {"tool_name": "ai-review/general", "state": "dismissed"},
            {"tool_name": "ai-review/general", "state": "fixed"},
        ],
    )
    output = tmp_path / "context.md"
    carry_forward = tmp_path / "carry-forward.json"

    fetch_context(
        "owner/repo",
        tool_names="ai-review/general",
        output=output,
        alerts_output=carry_forward,
    )

    assert output.read_text(encoding="utf-8") == (
        "## Existing repo-wide review findings\n"
        "\n"
        "Open alerts are carried forward into the next SARIF upload by automation. "
        "Do not duplicate them in your report unless you have new evidence, the problem "
        "reappears in a materially different form, or the previous resolution is directly "
        "contradicted by the current code.\n"
        "\n"
        "### ai-review/general\n"
        "\n"
        "_No existing findings._\n"
    )
    assert json.loads(carry_forward.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "alerts": [],
    }


def test_fetch_context_reads_alert_pages_until_short_page(tmp_path: Path, gh_fixture: Path) -> None:
    alerts = [_alert(number, "open", f"Finding {number}", f"src/file_{number}.py", number) for number in range(1, 102)]
    _write_json(
        gh_fixture / "alerts.json",
        [{"tool_name": "ai-review/general", "state": "open", "alert": alert} for alert in alerts],
    )
    carry_forward = tmp_path / "carry-forward.json"

    fetch_context("owner/repo", tool_names="ai-review/general", alerts_output=carry_forward)

    payload = json.loads(carry_forward.read_text(encoding="utf-8"))
    assert payload == {
        "schema_version": 1,
        "alerts": [{"tool_name": "ai-review/general", "alert": alert} for alert in alerts],
    }


def test_thread_digest_uses_review_thread_path() -> None:
    node = {
        "path": "src/ai_review_ci/context.py",
        "isResolved": False,
        "comments": {
            "nodes": [
                {
                    "body": "### Finding headline\n\nFinding body.",
                }
            ]
        },
    }

    assert _thread_digest(node) == {
        "path": "src/ai_review_ci/context.py",
        "headline": "### Finding headline",
        "resolved": False,
    }


def test_thread_digest_skips_threads_without_comments() -> None:
    node = {
        "path": "src/ai_review_ci/context.py",
        "isResolved": True,
        "comments": {"nodes": []},
    }

    assert _thread_digest(node) is None


# --- #185: proof-laundering / fake-boundary reviewer context ----------------
#
# Regression fixture modeled on the #110 / #177 failure class: a PR body claims
# a real downstream boundary (Bun Playwright app boot) is satisfied, but the
# cited evidence is developer-controlled (fake bunx shell script recording argv,
# empty Playwright configs). The LLM reviewer cannot detect this claim-vs-evidence
# mismatch unless fetch_context injects the PR body's claim map into the reviewer
# prompt. On main, fetch_context never fetches the PR body, so this test is RED.


_PR_110_BODY = """<!-- policy-alignment-gate -->

## Intended result

Bun Playwright downstream repos exercise actual app boot behavior through ai-review-ci's central QC path.

## GitHub tracking

- Target issue set / subtree: #177
- Closes on merge:
  - Closes #177

## Claim map

- [x] **#177 - actual app boot configs run through global QC**
  - Central Bun `app-boot` runs the primary `playwright.config.ts`.
  - A repo-owned downstream fixture carries a real `package.json`, Bun lockfile, Playwright configs, app source, and browser tests.
  - The fixed branch's test suite proves the actual app boots through real Playwright/browser/app sentinel behavior.

## Evidence

- Commit: `55edef6487a300610b6ca5c55bc84d05b4f21aa0`.
- Focused test: `tests/test_justfiles.py::test_bun_push_gate_runs_actual_app_boot_when_config_exists`
  - writes empty `playwright.config.ts` / `playwright.actual.config.ts` files;
  - writes a fake `bunx` executable that only records argv;
  - asserts recorded command-line arguments.
"""


def test_fetch_context_injects_pr_claim_map_for_proof_laundering_detection(tmp_path: Path, gh_fixture: Path) -> None:
    """The reviewer must see the PR body's claim map to detect fake-boundary evidence.

    Models the #110 failure: the PR claims #177 (real app boot) satisfied, but the
    evidence path is a fake bunx + argv recorder. Without the PR body in the reviewer
    context, the LLM cannot compare the *claimed boundary* against the *evidence shape*.
    """
    _write_json(gh_fixture / "alerts.json", [])
    _write_json(
        gh_fixture / "threads.json",
        {"nodes": [], "pageInfo": {"hasNextPage": False, "endCursor": None}},
    )
    _write_json(
        gh_fixture / "rest_repos_owner_repo_pulls_110.json",
        {
            "number": 110,
            "title": "Bun Playwright app boot through global QC",
            "body": _PR_110_BODY,
        },
    )
    output = tmp_path / "context.md"

    fetch_context("owner/repo", tool_names="ai-review/slop", output=output, pr_number=110)

    text = output.read_text(encoding="utf-8")
    # The reviewer context must carry a dedicated claim-map section so the LLM can
    # cross-reference the PR's claimed boundary obligation against the diff evidence.
    assert "## PR claim map" in text
    # The claim map content must be present: the claimed boundary and the linked issue.
    assert "#177" in text
    assert "actual app boot" in text
    # The evidence section — which names the fake-bunx/argv-recorder proof — must be
    # visible so the reviewer can judge whether the evidence crosses the claimed boundary.
    assert "fake `bunx`" in text
    assert "records argv" in text


def test_fetch_context_omits_pr_claim_map_when_not_a_pr_run(tmp_path: Path, gh_fixture: Path) -> None:
    """Repo-sweep runs (pr_number=0) have no PR body; the claim-map section is omitted."""
    _write_json(gh_fixture / "alerts.json", [])
    output = tmp_path / "context.md"

    fetch_context("owner/repo", tool_names="ai-review/slop", output=output, pr_number=0)

    text = output.read_text(encoding="utf-8")
    assert "## PR claim map" not in text
