"""Reviewer-signal eval metrics (#41, was #28).

Scores a candidate reviewer-prompt structure against the disposition-stamped
ground truth extracted from a real PR review loop (see
tool-artifacts/scripts/extract_reviewer_eval.py). The dataset labels every
review thread with the owner's disposition:

- ``accepted``: a real finding the reviewer should emit;
- ``rejected``: off-target or policy-misaligned churn the reviewer should
  never have emitted;
- ``outdated`` / ``duplicate`` / ``unstamped``: not scoreable — superseded by
  code motion, folded into a canonical thread, or resolved without a verdict.

A candidate is evaluated by the set of ground-truth findings it re-emits:
precision over the scoreable threads it touched (how much of its output is
real rather than churn) and recall of the accepted findings (how much real
signal it keeps). The #41 target is a prompt that raises precision without
dropping recall.
"""

import json
from dataclasses import dataclass
from pathlib import Path

DISPOSITIONS = ("accepted", "rejected", "outdated", "duplicate", "unstamped")
SCOREABLE = ("accepted", "rejected")


@dataclass(frozen=True)
class EvalThread:
    finding_id: int
    url: str
    path: str
    disposition: str
    finding_body: str


@dataclass(frozen=True)
class EvalMetrics:
    true_positives: int
    false_positives: int
    false_negatives: int

    @property
    def precision(self) -> float:
        emitted = self.true_positives + self.false_positives
        assert emitted > 0, "no scoreable findings emitted; nothing to measure"
        return self.true_positives / emitted

    @property
    def recall(self) -> float:
        real = self.true_positives + self.false_negatives
        assert real > 0, "dataset has no accepted findings; nothing to measure"
        return self.true_positives / real


def load_eval_dataset(path: Path) -> tuple[EvalThread, ...]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    threads = raw["threads"]
    assert threads, f"eval dataset {path} contains no threads"
    loaded = []
    for row in threads:
        thread = EvalThread(
            finding_id=row["finding_id"],
            url=row["url"],
            path=row["path"],
            disposition=row["disposition"],
            finding_body=row["finding_body"],
        )
        assert thread.disposition in DISPOSITIONS, (thread.finding_id, thread.disposition)
        assert thread.finding_body, f"thread {thread.finding_id} has an empty finding body"
        loaded.append(thread)
    assert len({t.finding_id for t in loaded}) == len(loaded), "duplicate finding ids in dataset"
    return tuple(loaded)


def score_emitted_findings(dataset: tuple[EvalThread, ...], emitted_ids: set[int]) -> EvalMetrics:
    """Score a candidate by the ground-truth finding ids it re-emitted.

    Only ``accepted``/``rejected`` threads carry a verdict; emitted ids
    matching non-scoreable threads are ignored, but unknown ids are an error
    — the candidate must be matched to dataset threads before scoring.
    """
    known = {thread.finding_id for thread in dataset}
    unknown = emitted_ids - known
    assert not unknown, f"emitted ids not present in the dataset: {sorted(unknown)}"

    accepted = {t.finding_id for t in dataset if t.disposition == "accepted"}
    rejected = {t.finding_id for t in dataset if t.disposition == "rejected"}
    return EvalMetrics(
        true_positives=len(emitted_ids & accepted),
        false_positives=len(emitted_ids & rejected),
        false_negatives=len(accepted - emitted_ids),
    )
