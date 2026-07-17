import pathlib
import re
import subprocess

import pytest
from pydantic import ValidationError

from ai_review_ci import gates


@pytest.mark.parametrize("forbidden_field", ["remediation_code", "message"])
def test_diff_rule_rejects_authored_policy_route_prose(forbidden_field: str) -> None:
    raw: dict[str, object] = {
        "rule_id": "example-rule",
        "policy_code": "POLICY.NO_QC_SILENCING",
        "signal_keys": ("example-rule",),
        "pattern": re.compile("example"),
        "suffixes": (".py",),
        forbidden_field: "authored duplicate",
    }

    with pytest.raises(ValidationError, match=forbidden_field):
        gates.DiffRule.model_validate(raw)


def test_lexical_diff_gate_blocks_added_suppression_and_ignores_context() -> None:
    coverage_marker = "# pragma: no cov" + "er"
    diff = f"""diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -1,1 +1,3 @@
 pass  {coverage_marker}
+pass  {coverage_marker}
+value = config.get("model", "fallback")
"""

    assert gates.lexical_diff_findings(diff) == ["src/app.py:2: no-coverage-pragma: POLICY.NO_QC_SILENCING"]


def test_bypass_diff_rules_block_only_added_bypass_markers() -> None:
    coverage_marker = "# pragma: no cov" + "er"
    diff = f"""diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -1,1 +1,3 @@
 pass  {coverage_marker}
+pass  {coverage_marker}
+value = 1
"""

    assert gates.lexical_diff_findings(diff) == ["src/app.py:2: no-coverage-pragma: POLICY.NO_QC_SILENCING"]


def test_bypass_diff_rules_block_ts_expect_error_with_trailing_whitespace() -> None:
    marker = "@ts-expect-err" + "or"
    trailing_spaces = "   "
    diff = f"""diff --git a/src/app.ts b/src/app.ts
--- a/src/app.ts
+++ b/src/app.ts
@@ -0,0 +1,1 @@
+// {marker}{trailing_spaces}
"""

    assert gates.lexical_diff_findings(diff) == [
        "src/app.ts:1: no-unjustified-ts-expect-error: POLICY.NO_QC_SILENCING"
    ]


def test_delegation_accepts_canonical_scaffold(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "package.json").write_text('{"scripts": {}}\n')
    (project / "bun.lock").write_text("")
    justfile = project / "justfile"
    justfile.write_text((pathlib.Path(__file__).parents[1] / "scaffolds" / "bun" / "justfile").read_text())

    gates.check_delegation(project, "bun")


def test_delegation_accepts_central_bun_python_composite_profile(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text('[project]\nname = "project"\nversion = "0.1.0"\n')
    (project / "package.json").write_text('{"scripts": {}}\n')
    (project / "bun.lock").write_text("")
    (project / "justfile").write_text((pathlib.Path(__file__).parents[1] / "scaffolds" / "bun-python" / "justfile").read_text())

    gates.check_delegation(project, "bun-python")


def test_delegation_rejects_local_qc_override(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "justfile").write_text("test-commit:\n    @true\n\ntest-push:\n    @true\n\ntest-ci:\n    @true\n")
    (project / "package.json").write_text('{"scripts": {}}\n')
    (project / "bun.lock").write_text("")

    with pytest.raises(SystemExit):
        gates.check_delegation(project, "bun")


def test_delegation_rejects_profile_shape_mismatch(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "justfile").write_text((pathlib.Path(__file__).parents[1] / "scaffolds" / "bun" / "justfile").read_text())

    with pytest.raises(SystemExit):
        gates.check_delegation(project, "bun")


def test_app_boot_rejects_direct_local_playwright_before_execution(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "package.json").write_text('{"scripts": {}}\n')
    (project / "bun.lock").write_text("")
    (project / "playwright.config.ts").write_text("export default {};\n")
    marker = project / "local-command-ran"
    (project / "justfile").write_text(
        "\n".join(
            [
                "app-boot:",
                f"    @python3 -c 'from pathlib import Path; Path({str(marker)!r}).write_text(\"ran\")'",
                "    @bunx playwright test --config playwright.config.ts",
                "",
            ]
        )
    )

    with pytest.raises(SystemExit):
        gates.check_app_boot(project, "bun-playwright")
    assert not marker.exists()


def test_pr_description_checklist_detects_unchecked_variants() -> None:
    body = "\n".join(
        [
            "Ready:",
            "- [x] completed",
            "- [ ] incomplete",
            "* [  ] also incomplete",
            "+ [X] uppercase checked",
        ]
    )

    assert gates.unchecked_checklist_lines(body) == [3, 4]


def test_pr_description_checklist_accepts_checked_or_absent_items() -> None:
    body = "\n".join(
        [
            "No checklist here.",
            "- [x] checked lowercase",
            "- [X] checked uppercase",
        ]
    )

    assert gates.unchecked_checklist_lines(body) == []


def test_pr_description_gate_blocks_unchecked_items(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    monkeypatch.setattr(gates, "_gh_json", lambda args: {"body": "- [ ] finish this\n- [x] done\n"})

    with pytest.raises(SystemExit):
        gates.check_pr_description("owner/repo", 12, repo_root=tmp_path)


def test_pr_description_gate_passes_without_unchecked_items(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    monkeypatch.setattr(gates, "_gh_json", lambda args: {"body": "- [x] done\n"})

    gates.check_pr_description("owner/repo", 12, repo_root=tmp_path)


def _install_gate_template(repo_root: pathlib.Path, *, marker: bool = True) -> None:
    gh = repo_root / ".github"
    gh.mkdir(parents=True, exist_ok=True)
    body = "## Policy alignment gate\n"
    if marker:
        body += f"{gates.POLICY_GATE_MARKER}\n"
    (gh / "pull_request_template.md").write_text(body)


def test_gate_template_requires_marker_detects_installed_template(tmp_path: pathlib.Path) -> None:
    assert gates.gate_template_requires_marker(tmp_path) is False
    _install_gate_template(tmp_path, marker=False)
    assert gates.gate_template_requires_marker(tmp_path) is False
    _install_gate_template(tmp_path, marker=True)
    assert gates.gate_template_requires_marker(tmp_path) is True


def test_pr_description_blocks_missing_marker_when_template_installed(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    # Regression-lock for #154: a repo that installed the gate template cannot pass a
    # PR whose body omits the gate section, even when every checklist item is checked.
    _install_gate_template(tmp_path, marker=True)
    monkeypatch.setattr(gates, "_gh_json", lambda args: {"body": "## Summary\n\n- [x] done\n"})

    with pytest.raises(SystemExit):
        gates.check_pr_description("owner/repo", 12, repo_root=tmp_path)


def test_pr_description_passes_with_marker_and_checked_when_template_installed(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    _install_gate_template(tmp_path, marker=True)
    body = f"## Policy alignment gate\n{gates.POLICY_GATE_MARKER}\n\n- [x] affirmed\n"
    monkeypatch.setattr(gates, "_gh_json", lambda args: {"body": body})

    gates.check_pr_description("owner/repo", 12, repo_root=tmp_path)


def test_pr_description_lenient_when_no_template_installed(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    # Non-breaking: a repo that has NOT installed the gate template keeps the prior
    # lenient behavior, so distributing the gate does not fail unrelated repos' PRs.
    monkeypatch.setattr(gates, "_gh_json", lambda args: {"body": "## Summary\n\nno checklist, no marker\n"})

    gates.check_pr_description("owner/repo", 12, repo_root=tmp_path)


def test_branch_protection_payload_uses_profile_check_contexts() -> None:
    payload = gates.branch_protection_payload("bun")

    assert payload["required_status_checks"]["contexts"] == []
    assert payload["required_status_checks"]["checks"] == [
        {"context": "qc-ci / qc", "app_id": -1},
        {"context": "deterministic-diff / deterministic-diff", "app_id": -1},
        {"context": "delegation-conformance / delegation-conformance", "app_id": -1},
        {"context": "qc-doctor / qc-doctor", "app_id": -1},
        {"context": "pr-description-checklist / pr-description-checklist", "app_id": -1},
        {"context": "general / review", "app_id": -1},
        {"context": "slop / review", "app_id": -1},
        {"context": "thread-resolution / thread-resolution", "app_id": -1},
    ]


def test_branch_protection_payload_requires_app_boot_for_bun_playwright() -> None:
    checks = gates.branch_protection_payload("bun-playwright")["required_status_checks"]["checks"]

    assert {"context": "app-boot / app-boot", "app_id": -1} in checks


def test_thread_resolution_evidence_requires_a_thread_local_disposition() -> None:
    def node(reply: str) -> dict[str, object]:
        return {
            "comments": {
                "nodes": [
                    {"body": "<!-- ai-review-fingerprint: " + "a" * 64 + " -->"},
                    {"body": reply},
                ]
            }
        }

    accepted = """\
Disposition: Accepted as written
Policy basis: POLICY.NO_ERROR_DISCARD
Pre-filter: Gate 1 correctness defect -> current-PR remediation
Claim: Read failures are discarded as partial success.
Remediation: Propagate the failure with path context.
Code/action taken or explicit non-change: Propagate the read error with path context.
Proof: The boundary test proves a failed read cannot return partial success.
Commit: 123456789abc
Audit anchor: tests/test_reader.py::test_read_failure_is_visible
Deleted artifact: None
"""
    rejected = """\
Disposition: Rejected
Factual/contract basis: The requested fixture is present in the reviewed tree.
Pre-filter: Gate 1 factual premise false -> no change
Claim: The review says the fixture is absent.
Code/action taken or explicit non-change: No code change.
Audit anchor: tests/fixtures/extract_link.pdf
"""
    duplicate = """\
Disposition: Duplicate
Policy basis: POLICY.NO_MOCK_PROOF
Pre-filter: Same semantic finding -> inherit canonical disposition
Claim: This repeats the canonical proof concern.
Canonical thread: https://github.com/owner/repo/pull/7#discussion_r123
Code/action taken or explicit non-change: No additional code change.
Audit anchor: https://github.com/owner/repo/pull/7#discussion_r123
"""
    outdated = """\
Disposition: Outdated
Policy basis: POLICY.NO_ERROR_DISCARD
Pre-filter: Finding targets replaced code -> superseded
Claim: The former branch discarded read errors.
Superseding commit: abcdef123456
Code/action taken or explicit non-change: No additional code change.
Audit anchor: abcdef123456
"""

    assert gates._has_resolution_evidence(node(accepted))
    assert gates._has_resolution_evidence(node(rejected))
    assert gates._has_resolution_evidence(node(duplicate))
    assert gates._has_resolution_evidence(node(outdated))
    assert not gates._has_resolution_evidence(
        node(accepted.replace("Commit: 123456789abc", "Commit: 123456789abc trailing junk"))
    )
    assert not gates._has_resolution_evidence(
        node(accepted.replace("Pre-filter: Gate 1 correctness defect -> current-PR remediation", "Pre-filter: <gate>"))
    )
    assert not gates._has_resolution_evidence(
        node(accepted.replace("Deleted artifact: None\n", ""))
    )
    deleted = accepted.replace(
        "Deleted artifact: None",
        "Deleted artifact: tests/test_legacy.py\n"
        "Original burden: Prove read failures remain visible.\n"
        "Burden disposition: solved by tests/test_reader.py::test_read_failure_is_visible\n"
        "Verification: Focused boundary test passes.",
    )
    assert gates._has_resolution_evidence(node(deleted))
    assert not gates._has_resolution_evidence(node("Resolved by commit 123456789abc."))
    assert not gates._has_resolution_evidence(node("Disposition-ledger: accepted in PR body."))
    assert not gates._has_resolution_evidence(
        node(
            """\
Disposition: Accepted as written
Policy basis: POLICY.NO_ERROR_DISCARD
Pre-filter: Gate 1 correctness defect -> current-PR remediation
Claim: Read failures are discarded.
Remediation: Propagate the read error.
Code/action taken or explicit non-change: Propagate the read error.
Proof: Focused boundary test.
Audit anchor: tests/test_reader.py
"""
        )
    )
    assert not gates._has_resolution_evidence(
        {
            "comments": {
                "nodes": [
                    {
                        "body": accepted,
                    }
                ]
            }
        }
    )


def test_thread_resolution_gate_blocks_unresolved_non_ai_review_threads(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        gates,
        "_thread_nodes",
        lambda repo, pr_number: [
            {
                "path": "src/app.py",
                "isResolved": False,
                "comments": {"nodes": [{"body": "Human reviewer concern without ai-review fingerprint."}]},
            }
        ],
    )

    with pytest.raises(SystemExit):
        gates.check_review_threads("owner/repo", 7)

    assert "src/app.py: unresolved review thread" in capsys.readouterr().err


def test_thread_resolution_gate_requires_evidence_for_resolved_non_ai_review_threads(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        gates,
        "_thread_nodes",
        lambda repo, pr_number: [
            {
                "path": "src/app.py",
                "isResolved": True,
                "comments": {"nodes": [{"body": "Resolved in the UI without a thread-local disposition."}]},
            }
        ],
    )

    with pytest.raises(SystemExit):
        gates.check_review_threads("owner/repo", 7)

    assert "src/app.py: resolved review thread lacks a thread-local evidenced disposition" in capsys.readouterr().err


def test_thread_resolution_does_not_auto_resolve_stale_ai_review_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node = {
        "id": "THREAD_1",
        "path": "src/app.py",
        "isResolved": False,
        "comments": {
            "nodes": [
                {
                    "body": "\n".join(
                        [
                            "<!-- ai-review-fingerprint: " + "a" * 64 + " -->",
                            "**Proof:** `grep -n 'stderr.*pipe' src/pandoc-config.ts`",
                        ]
                    )
                }
            ]
        },
    }

    monkeypatch.setattr(gates, "_thread_nodes", lambda repo, pr_number: [node])
    monkeypatch.setattr(gates, "_pr_commit_shas", lambda repo, pr_number: set(), raising=False)

    def reject_mutation(*args: object, **kwargs: object) -> gates.JsonDict:
        raise AssertionError("an unresolved thread must never be auto-resolved")

    monkeypatch.setattr(gates, "_gh_json", reject_mutation)

    with pytest.raises(SystemExit):
        gates.check_review_threads("owner/repo", 7)



def test_thread_resolution_does_not_auto_resolve_reproducing_proof(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    node = {
        "id": "THREAD_1",
        "path": "src/app.py",
        "isResolved": False,
        "comments": {
            "nodes": [
                {
                    "body": "\n".join(
                        [
                            "<!-- ai-review-fingerprint: " + "a" * 64 + " -->",
                            "**Proof:** `rg 'still-present' src/app.ts`",
                        ]
                    )
                }
            ]
        },
    }

    monkeypatch.setattr(gates, "_thread_nodes", lambda repo, pr_number: [node])
    monkeypatch.setattr(
        gates.subprocess,
        "run",
        lambda args, **kwargs: subprocess.CompletedProcess(args, 0, "still-present", ""),
    )

    with pytest.raises(SystemExit):
        gates.check_review_threads("owner/repo", 7)

    assert "src/app.py: unresolved review thread" in capsys.readouterr().err


def test_thread_resolution_gate_rejects_legacy_root_only_evidence(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        gates,
        "_thread_nodes",
        lambda repo, pr_number: [
            {
                "path": "src/app.py",
                "isResolved": True,
                "comments": {"nodes": [{"body": "Resolved by commit 123456789abc."}]},
            }
        ],
    )
    monkeypatch.setattr(gates, "_pr_commit_shas", lambda repo, pr_number: set(), raising=False)

    with pytest.raises(SystemExit):
        gates.check_review_threads("owner/repo", 7)

    assert "resolved review thread lacks a thread-local evidenced disposition" in capsys.readouterr().err


def test_thread_resolution_gate_rejects_fabricated_commit_and_uncheckable_proof(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    accepted = """\
Disposition: Accepted as written
Policy basis: POLICY.NO_ADMIN_COMPLETION
Pre-filter: Gate 1 proof defect -> current-PR remediation
Claim: The resolution gate accepts syntax instead of evidence.
Remediation: Verify the commit and proof witness.
Code/action taken or explicit non-change: Added semantic evidence validation.
Proof: Focused gate test rejects fabricated evidence.
Commit: 123456789abc
Audit anchor: tests/test_missing.py::test_evidence
Deleted artifact: None
"""
    monkeypatch.setattr(
        gates,
        "_thread_nodes",
        lambda repo, pr_number: [
            {
                "path": "src/app.py",
                "isResolved": True,
                "comments": {"nodes": [{"body": "finding"}, {"body": accepted}]},
            }
        ],
    )
    monkeypatch.setattr(
        gates,
        "_pr_commit_shas",
        lambda repo, pr_number: {"f" * 40},
        raising=False,
    )

    with pytest.raises(SystemExit):
        gates.check_review_threads("owner/repo", 7, repo_root=tmp_path)

    error = capsys.readouterr().err
    assert "cited commit 123456789abc is not on this PR" in error
    assert "proof anchor tests/test_missing.py::test_evidence does not exist" in error



def test_delegation_accepts_docs_and_configs_profile(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "justfile").write_text(
        "\n".join(
            [
                "test-commit:",
                "    @just -f ~/ai-review-ci/justfiles/docs-and-configs.just -d . test-commit",
                "",
                "test-push:",
                "    @just -f ~/ai-review-ci/justfiles/docs-and-configs.just -d . test-push",
                "",
                "test-ci:",
                "    @just -f ~/ai-review-ci/justfiles/docs-and-configs.just -d . test-ci",
                "",
            ]
        )
    )

    gates.check_delegation(project, "docs-and-configs")
