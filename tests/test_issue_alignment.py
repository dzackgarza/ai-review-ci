"""Contract tests for the advisory issue-alignment verdict.

The verdict is the only thing this check can say, so what the model refuses to represent
is the substance: a graded approval it could be cited as, and a finding it cannot ground
in the issue text it was given.
"""

import pathlib

import pytest
import yaml
from pydantic import ValidationError

from ai_review_ci.issue_alignment import (
    RULING_LABEL,
    VERDICT_MARKER,
    AlignmentVerdict,
    build_prompt,
    render_comment,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
TASK = ROOT / "reviews" / "issue-alignment" / "task.md"
MANIFEST = ROOT / "reviews" / "issue-alignment" / "manifest.txt"

ISSUE_BODY = "The rule needs a way to admit declared protocol invariants without a suppression comment."


def _suspected(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "verdict": "suspected-inversion",
        "quote": "a way to admit declared protocol invariants",
        "who_can_make_it_stand_down": "declare an invariant at the site and the rule stops firing there",
        "rationale": "The declaration is authored in the consuming repository, so the repository decides where the rule applies.",
    }
    payload.update(overrides)
    return payload


def test_no_objection_cannot_carry_an_approval() -> None:
    """A clean verdict has no field a later reader could cite as clearance."""
    with pytest.raises(ValidationError) as exc:
        AlignmentVerdict.model_validate({"schema_version": 1, "verdict": "no-objection", "rationale": "reviewed and fine"})
    assert "must carry no finding fields" in str(exc.value)

    clean = AlignmentVerdict.model_validate({"schema_version": 1, "verdict": "no-objection"})
    assert clean.quote is None


def test_suspected_inversion_requires_the_evidence_fields() -> None:
    with pytest.raises(ValidationError) as exc:
        AlignmentVerdict.model_validate({"schema_version": 1, "verdict": "suspected-inversion"})
    message = str(exc.value)
    assert "quote" in message
    assert "who_can_make_it_stand_down" in message


def test_finding_must_quote_the_issue_verbatim() -> None:
    """A quote the checker reconstructed is not evidence, however plausible."""
    paraphrased = AlignmentVerdict.model_validate(_suspected(quote="a way to admit protocol invariants"))
    with pytest.raises(ValueError, match="does not appear in the issue body"):
        paraphrased.grounded_in(ISSUE_BODY)

    verbatim = AlignmentVerdict.model_validate(_suspected())
    assert verbatim.grounded_in(ISSUE_BODY).quote in ISSUE_BODY


def test_comment_states_that_it_decides_nothing() -> None:
    body = render_comment(AlignmentVerdict.model_validate(_suspected()))
    assert VERDICT_MARKER in body
    assert "not a decision" in body
    assert "clears nothing" in body


def test_prompt_carries_the_guides_the_issue_and_the_task() -> None:
    prompt = build_prompt(TASK, MANIFEST, "Rule flags a protocol invariant", ISSUE_BODY)
    # The authority test the verdict turns on reaches the model.
    assert "who can make the rule stand down" in prompt.lower()
    # POLICY.GLOBAL_QC_AUTHORITY is inlined, not merely cited by name.
    assert "Repos delegate; they do not reimplement or override" in prompt
    assert ISSUE_BODY in prompt
    assert "Rule flags a protocol invariant" in prompt


def test_workflow_runs_only_for_owner_authored_issues_and_never_closes() -> None:
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "issue-alignment.yml").read_text())
    job = workflow["jobs"]["alignment"]

    assert job["if"] == "github.event.issue.user.login == 'dzackgarza'"
    assert workflow[True]["issues"]["types"] == ["opened", "edited"]
    # Advisory: it may label and comment, and has no permission to do more.
    assert job["permissions"] == {"contents": "read", "issues": "write"}


def test_ruling_label_is_in_the_canonical_taxonomy() -> None:
    """The label the check applies must exist in every repo install-labels touches."""
    import json

    taxonomy = json.loads((ROOT / "src" / "ai_review_ci" / "data" / "labels.json").read_text())
    assert RULING_LABEL in {label["name"] for label in taxonomy["labels"]}
