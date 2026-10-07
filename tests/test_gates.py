import pathlib
import re

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

    assert gates.lexical_diff_findings(diff) == ["src/app.ts:1: no-unjustified-ts-expect-error: POLICY.NO_QC_SILENCING"]


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


def test_delegation_accepts_lean_scans_at_push_and_lean_audit_at_ci(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "package.json").write_text('{"scripts": {}}\n')
    (project / "bun.lock").write_text("")
    (project / "justfile").write_text(
        "test-commit:\n"
        "    @just -f ~/ai-review-ci/justfiles/bun.just -d . test-commit\n\n"
        "test-push:\n"
        "    @just -f ~/ai-review-ci/justfiles/bun.just -d . test-push\n"
        "    @just -f ~/ai-review-ci/justfiles/lean.just -d . test-push\n\n"
        "test-ci:\n"
        "    @just -f ~/ai-review-ci/justfiles/bun.just -d . test-ci\n"
        "    @just -f ~/ai-review-ci/justfiles/lean.just -d . lean-axiom-audit\n"
    )

    gates.check_delegation(project, "bun")


@pytest.mark.parametrize(
    "push_line",
    [
        "    @just -f ~/ai-review-ci/justfiles/lean.just -d . lean-axiom-audit\n",
        "    @just -f ~/ai-review-ci/justfiles/lean.just -d . test-ci\n",
        "    lake build\n",
    ],
)
def test_delegation_rejects_lean_compilation_at_push_tier(tmp_path: pathlib.Path, push_line: str) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "package.json").write_text('{"scripts": {}}\n')
    (project / "bun.lock").write_text("")
    (project / "justfile").write_text(
        "test-commit:\n"
        "    @just -f ~/ai-review-ci/justfiles/bun.just -d . test-commit\n\n"
        "test-push:\n"
        "    @just -f ~/ai-review-ci/justfiles/bun.just -d . test-push\n"
        f"{push_line}\n"
        "test-ci:\n"
        "    @just -f ~/ai-review-ci/justfiles/bun.just -d . test-ci\n"
    )

    with pytest.raises(SystemExit):
        gates.check_delegation(project, "bun")


def test_delegation_rejects_shared_lean_audit_at_commit_tier(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "package.json").write_text('{"scripts": {}}\n')
    (project / "bun.lock").write_text("")
    (project / "justfile").write_text(
        "test-commit:\n"
        "    @just -f ~/ai-review-ci/justfiles/bun.just -d . test-commit\n"
        "    @just -f ~/ai-review-ci/justfiles/lean.just -d . lean-axiom-audit\n\n"
        "test-push:\n"
        "    @just -f ~/ai-review-ci/justfiles/bun.just -d . test-push\n\n"
        "test-ci:\n"
        "    @just -f ~/ai-review-ci/justfiles/bun.just -d . test-ci\n"
    )

    with pytest.raises(SystemExit):
        gates.check_delegation(project, "bun")


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

    assert "contexts" not in payload["required_status_checks"]
    assert payload["required_status_checks"]["checks"] == [
        {"context": "qc-ci / qc"},
        {"context": "deterministic-diff / deterministic-diff"},
        {"context": "delegation-conformance / delegation-conformance"},
        {"context": "qc-doctor / qc-doctor"},
        {"context": "pr-description-checklist / pr-description-checklist"},
    ]


def test_branch_protection_payload_requires_app_boot_for_bun_playwright() -> None:
    checks = gates.branch_protection_payload("bun-playwright")["required_status_checks"]["checks"]

    assert {"context": "app-boot / app-boot"} in checks


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
