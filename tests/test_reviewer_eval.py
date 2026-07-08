"""Reviewer-signal eval set and metrics harness (#41, was #28)."""

import json
import pathlib

import pytest

from ai_review_ci.reviewer_eval import (
    DISPOSITIONS,
    EvalThread,
    load_eval_dataset,
    score_emitted_findings,
)

DATASET = pathlib.Path(__file__).resolve().parent / "fixtures" / "reviewer-eval" / "zotero_gui_pr7.json"


def _thread(finding_id: int, disposition: str) -> EvalThread:
    return EvalThread(
        finding_id=finding_id,
        url=f"https://example.invalid/r{finding_id}",
        path="src/app.ts",
        disposition=disposition,
        finding_body=f"finding {finding_id}",
    )


def test_committed_pr7_dataset_is_loadable_ground_truth() -> None:
    """The tracked eval artifact carries the labeled PR #7 review loop."""
    dataset = load_eval_dataset(DATASET)

    assert len(dataset) == 242
    counts = {disposition: 0 for disposition in DISPOSITIONS}
    for thread in dataset:
        counts[thread.disposition] += 1
    # The scoreable core of the ground truth: real findings the reviewer
    # should emit, and dispositioned rejects it should never have emitted.
    assert counts["accepted"] == 57
    assert counts["rejected"] == 64


def test_metrics_computed_from_dispositions() -> None:
    dataset = (
        _thread(1, "accepted"),
        _thread(2, "accepted"),
        _thread(3, "rejected"),
        _thread(4, "rejected"),
        _thread(5, "duplicate"),
        _thread(6, "unstamped"),
    )
    # Candidate re-emits one real finding, one reject, and one duplicate
    # (ignored as non-scoreable); misses one real finding.
    metrics = score_emitted_findings(dataset, {1, 3, 5})

    assert metrics.true_positives == 1
    assert metrics.false_positives == 1
    assert metrics.false_negatives == 1
    assert metrics.precision == 0.5
    assert metrics.recall == 0.5


def test_unknown_emitted_ids_fail_loudly() -> None:
    dataset = (_thread(1, "accepted"),)
    with pytest.raises(AssertionError, match=r"\[99\]"):
        score_emitted_findings(dataset, {99})


def test_loader_rejects_unknown_disposition(tmp_path: pathlib.Path) -> None:
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text(
        json.dumps(
            {
                "source": "x/y#1",
                "thread_count": 1,
                "threads": [
                    {
                        "finding_id": 1,
                        "url": "https://example.invalid/r1",
                        "path": "a.py",
                        "disposition": "maybe",
                        "finding_body": "text",
                    }
                ],
            }
        )
    )
    with pytest.raises(AssertionError, match="maybe"):
        load_eval_dataset(corrupt)
