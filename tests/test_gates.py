import pathlib

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


def test_delegation_rejects_local_qc_override(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "justfile").write_text("test:\n    @true\n\ntest-ci:\n    @true\n")
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


def test_branch_protection_payload_uses_profile_check_contexts() -> None:
    payload = gates.branch_protection_payload("bun")

    assert payload["required_status_checks"]["contexts"] == []
    assert payload["required_status_checks"]["checks"] == [
        {"context": "deterministic-diff / deterministic-diff", "app_id": -1},
        {"context": "delegation-conformance / delegation-conformance", "app_id": -1},
        {"context": "qc-doctor / qc-doctor", "app_id": -1},
        {"context": "general / review", "app_id": -1},
        {"context": "slop / review", "app_id": -1},
        {"context": "thread-resolution / thread-resolution", "app_id": -1},
    ]


def test_branch_protection_payload_requires_app_boot_for_bun_playwright() -> None:
    checks = gates.branch_protection_payload("bun-playwright")["required_status_checks"]["checks"]

    assert {"context": "app-boot / app-boot", "app_id": -1} in checks


def test_branch_protection_payload_enforces_conversation_resolution_for_every_profile() -> None:
    # Regression lock: the uniform contract must never silently stop blocking
    # merges with unresolved review threads, and must never become admin-bypassable.
    for profile in gates.SUPPORTED_PROFILES:
        payload = gates.branch_protection_payload(profile)
        assert payload["required_conversation_resolution"] is True, profile
        assert payload["enforce_admins"] is True, profile


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
