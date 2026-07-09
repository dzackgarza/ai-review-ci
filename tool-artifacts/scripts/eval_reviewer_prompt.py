# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Measure a candidate reviewer prompt against the labeled eval set (#41).

For every scoreable thread (owner-dispositioned accepted or rejected), the CI
model is shown the candidate reviewer framing plus the original finding body
and asked whether a reviewer operating under that framing would emit the
finding. The emitted set is scored with ai_review_ci.reviewer_eval:
precision (emitted findings that were real, not dispositioned rejects) and
recall (real findings kept).

    uv run tool-artifacts/scripts/eval_reviewer_prompt.py \
        tests/fixtures/reviewer-eval/zotero_gui_pr7.json candidate.md

Compare candidates by running once per framing file; the #41 target is a
framing that raises precision without dropping recall.
"""

import json
import subprocess
import sys
from pathlib import Path

# Repo-local script: the owned metrics implementation lives in src/.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from ai_review_ci.reviewer_eval import load_eval_dataset, score_emitted_findings  # noqa: E402

MODEL = "opencode/deepseek-v4-flash-free"
BATCH_SIZE = 5
FINDING_CHAR_LIMIT = 1500
TIMEOUT_RETRIES = 2

PROMPT_TEMPLATE = """You are a code reviewer operating under the following review framing:

<review-framing>
{framing}
</review-framing>

Below are findings that reviewers previously raised on a pull request. For each finding, \
decide whether a reviewer operating strictly under the framing above would emit it. \
Judge the finding as written — do not assume access to the code.

Respond with ONLY a JSON object mapping each finding id (as a string) to "emit" or \
"drop", no other text. Example: {{"123": "emit", "456": "drop"}}

{findings}"""


def _model_judge(framing: str, threads: list[dict[str, object]]) -> dict[str, str]:
    sections = [f"### Finding id {t['finding_id']}\n{str(t['finding_body'])[:FINDING_CHAR_LIMIT]}" for t in threads]
    prompt = PROMPT_TEMPLATE.format(framing=framing, findings="\n\n".join(sections))
    for attempt in range(1, TIMEOUT_RETRIES + 2):
        try:
            proc = subprocess.run(
                ["opencode", "run", "-m", MODEL, prompt],
                capture_output=True,
                text=True,
                check=True,
                timeout=600,
            )
            break
        except subprocess.TimeoutExpired as error:
            print(f"--- opencode timed out (attempt {attempt}): {error.cmd[:4]} ---", file=sys.stderr)
            assert attempt <= TIMEOUT_RETRIES, f"model call timed out {attempt} times; aborting"
    text = proc.stdout
    start, end = text.find("{"), text.rfind("}")
    assert start != -1 and end > start, f"no JSON object in model output:\n{text}"
    decisions = json.loads(text[start : end + 1])
    assert isinstance(decisions, dict), decisions
    return {str(key): str(value).strip().lower() for key, value in decisions.items()}


def _validated(threads: list[dict[str, object]], decisions: dict[str, str]) -> dict[str, str] | None:
    expected_ids = {str(t["finding_id"]) for t in threads}
    if set(decisions) != expected_ids or not all(choice in ("emit", "drop") for choice in decisions.values()):
        return None
    return decisions


def main() -> None:
    assert len(sys.argv) == 3, f"usage: {sys.argv[0]} LABELED_DATASET_JSON FRAMING_MD"
    dataset_path, framing_path = Path(sys.argv[1]), Path(sys.argv[2])
    framing = framing_path.read_text(encoding="utf-8")
    dataset = load_eval_dataset(dataset_path)
    scoreable = [{"finding_id": t.finding_id, "finding_body": t.finding_body, "disposition": t.disposition} for t in dataset if t.disposition in ("accepted", "rejected")]
    assert scoreable, "dataset has no scoreable (accepted/rejected) threads"

    emitted: set[int] = set()
    for offset in range(0, len(scoreable), BATCH_SIZE):
        batch = scoreable[offset : offset + BATCH_SIZE]
        decisions = _validated(batch, _model_judge(framing, batch))
        if decisions is None:
            decisions = {}
            for thread in batch:
                single = _validated([thread], _model_judge(framing, [thread]))
                assert single is not None, f"model could not judge finding {thread['finding_id']}"
                decisions.update(single)
        emitted.update(int(fid) for fid, choice in decisions.items() if choice == "emit")
        print(f"judged {min(offset + BATCH_SIZE, len(scoreable))}/{len(scoreable)}", file=sys.stderr)

    metrics = score_emitted_findings(dataset, emitted)
    result = {
        "framing": str(framing_path),
        "scoreable": len(scoreable),
        "emitted": len(emitted),
        "true_positives": metrics.true_positives,
        "false_positives": metrics.false_positives,
        "false_negatives": metrics.false_negatives,
        "precision": round(metrics.precision, 3),
        "recall": round(metrics.recall, 3),
    }
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
