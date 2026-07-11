"""Tests for the issues-ledger delivery path (publish-issues + context)."""

import json
from pathlib import Path
from typing import Any

import yaml

from ai_review_ci import issues
from ai_review_ci.context import _issue_ledger_lines
from ai_review_ci.issues import (
    FINGERPRINT_MARKER,
    _issue_body,
    _marked_fingerprint,
    issue_fingerprint,
    publish_issues,
)

ROOT = Path(__file__).parent.parent

JsonDict = dict[str, Any]


def _finding(label: str = "WRONG_DUAL", path: str = "src/lattice.py") -> JsonDict:
    return {
        "label": label,
        "tier": "tier1",
        "category": "semantic-regression",
        "location": {"path": path, "start_line": 10, "end_line": 12},
        "violated_invariant": "dual() must rescale the form",
        "proof_command": "grep -n 'def dual' src/lattice.py",
    }


def _artifact(tmp_path: Path, findings: list[JsonDict]) -> Path:
    artifact = tmp_path / ".review-report-artifact.json"
    artifact.write_text(json.dumps({"report_type": "general", "findings": findings}))
    return artifact


def test_issue_fingerprint_is_finer_than_coarse_fingerprint() -> None:
    # Two distinct invariants in the same file and category must be two
    # tracked issues, not one.
    a = issue_fingerprint("semantic-regression", "src/lattice.py", "WRONG_DUAL")
    b = issue_fingerprint("semantic-regression", "src/lattice.py", "WRONG_SATURATION")
    assert a != b
    assert a == issue_fingerprint("semantic-regression", "src/lattice.py", "WRONG_DUAL")


def test_issue_body_carries_marker_narrative_and_parent() -> None:
    body = _issue_body(_finding(), "general", parent_issue=46)
    fp = issue_fingerprint("semantic-regression", "src/lattice.py", "WRONG_DUAL")
    assert _marked_fingerprint(body) == fp
    assert "src/lattice.py:10-12" in body
    assert "dual() must rescale the form" in body
    assert "grep -n 'def dual' src/lattice.py" in body
    assert "Tracked under #46." in body
    assert "do-not-re-raise" in body


def test_marked_fingerprint_ignores_unmarked_bodies() -> None:
    assert _marked_fingerprint("just prose, no marker") is None
    assert _marked_fingerprint(f"<!-- {FINGERPRINT_MARKER} abc123 -->\nrest") == "abc123"


def test_publish_creates_updates_and_respects_dispositions(
    tmp_path: Path, monkeypatch: Any, capsys: Any
) -> None:
    tracked_fp = issue_fingerprint("semantic-regression", "src/lattice.py", "WRONG_DUAL")
    closed_fp = issue_fingerprint("semantic-regression", "src/other.py", "OLD_FINDING")
    ledger = [
        {
            "number": 7,
            "state": "open",
            "body": f"<!-- {FINGERPRINT_MARKER} {tracked_fp} -->",
        },
        {
            "number": 3,
            "state": "closed",
            "body": f"<!-- {FINGERPRINT_MARKER} {closed_fp} -->",
        },
    ]
    calls: list[tuple[str, Any]] = []

    monkeypatch.setattr(issues, "_ensure_labels", lambda repo, labels: calls.append(("labels", labels)))
    monkeypatch.setattr(issues, "_ledger_issues", lambda repo: ledger)
    monkeypatch.setattr(issues, "_attach_to_parent", lambda repo, parent, child: calls.append(("attach", (parent, child))))

    def fake_gh_api(args: list[str], *, input_body: JsonDict | None = None) -> JsonDict:
        calls.append(("api", (args[:2], input_body)))
        if args and args[0].endswith("/issues") and input_body and "title" in input_body and "-X" not in args:
            return {"number": 99, "id": 12345}
        return {}

    monkeypatch.setattr(issues, "_gh_api", fake_gh_api)

    findings = [
        _finding(),  # open issue #7 -> update
        _finding(label="NEW_FINDING", path="src/new.py"),  # -> create + attach
        _finding(label="OLD_FINDING", path="src/other.py"),  # closed #3 -> suppressed
    ]
    publish_issues(_artifact(tmp_path, findings), "owner/repo", parent_issue=46)

    out = capsys.readouterr().out
    assert "1 created, 1 updated, 1 suppressed by disposition (3 findings)" in out
    assert ("attach", (46, 99)) in calls
    patch_calls = [c for c in calls if c[0] == "api" and "-X" in c[1][0]]
    assert len(patch_calls) == 1  # exactly the update of #7; closed #3 untouched


def test_context_issue_ledger_lines_render_states() -> None:
    lines = _issue_ledger_lines(
        "ai-review/general",
        [
            {"number": 7, "state": "open", "title": "open finding"},
            {"number": 3, "state": "closed", "state_reason": "not_planned", "title": "rejected finding"},
        ],
    )
    text = "\n".join(lines)
    assert "do not re-report" in text
    assert "open finding (#7)" in text
    assert "rejected finding (#3, not_planned)" in text
    assert "do not re-raise" in text
    assert _issue_ledger_lines("ai-review/general", []) == []


def test_review_workflow_gates_delivery_paths() -> None:
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "_review.yml").read_text())
    inputs = workflow[True]["workflow_call"]["inputs"]
    assert inputs["delivery"]["default"] == "sarif"
    assert inputs["parent_issue"]["type"] == "number"

    steps = workflow["jobs"]["review"]["steps"]
    by_name = {step.get("name"): step for step in steps}
    assert by_name["Convert report to SARIF"]["if"] == "inputs.delivery == 'sarif'"
    assert by_name["Upload review findings"]["if"] == "inputs.delivery == 'sarif'"
    publish = by_name["Publish findings to the issues ledger"]
    assert publish["if"] == "inputs.delivery == 'issues'"
    assert "publish-issues" in publish["run"]
    assert workflow["jobs"]["review"]["permissions"]["issues"] == "write"
