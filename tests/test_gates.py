import pathlib
import subprocess

import pytest

from ai_review_ci import gates


def test_diff_gate_blocks_added_mock_and_ignores_context_backlog() -> None:
    diff = """diff --git a/src/App.test.tsx b/src/App.test.tsx
--- a/src/App.test.tsx
+++ b/src/App.test.tsx
@@ -1,3 +1,4 @@
 const OLD_API_URL = "https://example.test";
 const existing = value ?? fallback;
+const fetchMock = vi.stubGlobal("fetch", vi.fn());
 context();
"""

    assert gates.diff_findings(diff) == ["src/App.test.tsx:3: ts-no-vitest-mock-boundary: Vitest mock helpers replace real proof boundaries."]


def test_diff_gate_blocks_uppercase_literals_but_not_local_const_calls() -> None:
    diff = """diff --git a/src/settings.ts b/src/settings.ts
--- a/src/settings.ts
+++ b/src/settings.ts
@@ -1,1 +1,3 @@
+const API_URL = "https://example.test";
+const localValue = buildValue();
 export const existing = buildValue();
"""

    assert gates.diff_findings(diff) == ["src/settings.ts:1: no-const-assignment: Hardcoded config-shaped constants belong in required config."]


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


def test_thread_resolution_evidence_accepts_commit_or_ledger() -> None:
    commit_node = {
        "comments": {
            "nodes": [
                {"body": "<!-- ai-review-fingerprint: " + "a" * 64 + " -->"},
                {"body": "Resolved by commit 123456789abc."},
            ]
        }
    }
    ledger_node = {
        "comments": {
            "nodes": [
                {"body": "<!-- ai-review-fingerprint: " + "b" * 64 + " -->"},
                {"body": "Disposition-ledger: accepted in PR body."},
            ]
        }
    }
    empty_node = {"comments": {"nodes": [{"body": "<!-- ai-review-fingerprint: " + "c" * 64 + " -->"}]}}

    assert gates._has_resolution_evidence(commit_node)
    assert gates._has_resolution_evidence(ledger_node)
    assert not gates._has_resolution_evidence(empty_node)


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
                "comments": {"nodes": [{"body": "Resolved in the UI without a commit or ledger citation."}]},
            }
        ],
    )

    with pytest.raises(SystemExit):
        gates.check_review_threads("owner/repo", 7)

    assert "src/app.py: resolved review thread lacks commit or disposition-ledger evidence" in capsys.readouterr().err


def test_thread_resolution_auto_resolves_stale_ai_review_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolved: list[str] = []
    ran: list[list[str]] = []
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

    def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        ran.append(args)
        return subprocess.CompletedProcess(args, 1, "", "")

    def fake_gh(args: list[str], body: gates.JsonDict | None = None) -> gates.JsonDict:
        assert "resolveReviewThread" in args[3]
        resolved.append(args[-1])
        return {"data": {"resolveReviewThread": {"thread": {"id": "THREAD_1", "isResolved": True}}}}

    monkeypatch.setattr(gates.subprocess, "run", fake_run)
    monkeypatch.setattr(gates, "_gh_json", fake_gh)

    gates.check_review_threads("owner/repo", 7)

    assert ran == [["grep", "-n", "stderr.*pipe", "src/pandoc-config.ts"]]
    assert resolved == ["threadId=THREAD_1"]


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


def test_thread_resolution_rejects_shell_proof_for_auto_resolution() -> None:
    assert gates._safe_proof_args("grep stale src/app.ts && rm -rf /") is None


def test_thread_resolution_gate_accepts_resolved_non_ai_review_threads_with_evidence(
    monkeypatch: pytest.MonkeyPatch,
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

    gates.check_review_threads("owner/repo", 7)


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
