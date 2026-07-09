# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Label reviewer-eval threads by having the CI model read the dispositions (#41).

Disposition stamps are intelligent free text written by reviewers and triage
agents — not automated-check output. Parsing them with keyword regexes both
mislabels threads (negations, casing, embedded quotes) and pressures authors
toward box-checking templates. This script instead sends each thread's reply
comments to the same model the review CI runs (ci/reviewer_home config) and
asks it to judge what the owner ultimately decided.

    uv run tool-artifacts/scripts/label_reviewer_eval.py raw.json labeled.json

Threads with no replies are labeled ``unstamped`` directly — there is nothing
to read. Every model answer is validated against the id set and label enum;
a batch that fails validation is retried thread-by-thread, and any thread
that still fails aborts the run loudly.
"""

import json
import subprocess
import sys
from pathlib import Path

MODEL = "opencode/deepseek-v4-flash-free"
LABELS = ("accepted", "rejected", "outdated", "duplicate", "needs-investigation", "unstamped")
BATCH_SIZE = 10
REPLY_CHAR_LIMIT = 2000

PROMPT_HEADER = """You are reading code-review threads. Each thread below shows the REPLY \
comments that followed a review finding (the finding itself is omitted). The repository \
owner (or their triage agent) expressed a decision about the finding somewhere in these \
replies, in ordinary prose — there is no required format.

For each thread, judge what the owner ULTIMATELY decided:
- accepted: the finding was acknowledged as real/actionable (even if remediation was deferred)
- rejected: the finding was turned down as wrong, out of scope, or policy-misaligned
- outdated: the finding no longer applied because the code had moved on / was superseded
- duplicate: the thread was closed as a duplicate of a canonical thread
- needs-investigation: the owner explicitly deferred judgment pending investigation
- unstamped: no decision is expressed in the replies

Read the prose for its meaning; negations like "why NOT accepted" are not acceptances. \
The latest decision wins if earlier replies disagree.

Respond with ONLY a JSON object mapping each thread id (as a string) to one label, \
no other text. Example: {"123": "rejected", "456": "duplicate"}

"""


def _model_judge(threads: list[dict[str, object]]) -> dict[str, str]:
    sections = []
    for thread in threads:
        replies = thread["replies"]
        assert isinstance(replies, list)
        bodies = "\n---\n".join(str(r["body"])[:REPLY_CHAR_LIMIT] for r in replies)
        sections.append(f"### Thread id {thread['finding_id']}\n{bodies}")
    prompt = PROMPT_HEADER + "\n\n".join(sections)
    proc = subprocess.run(
        ["opencode", "run", "-m", MODEL, prompt],
        capture_output=True,
        text=True,
        check=True,
        timeout=600,
    )
    # opencode prints a session banner line before the answer; the answer is
    # the JSON object, which may be wrapped in a code fence.
    text = proc.stdout
    start, end = text.find("{"), text.rfind("}")
    assert start != -1 and end > start, f"no JSON object in model output:\n{text}"
    verdicts = json.loads(text[start : end + 1])
    assert isinstance(verdicts, dict), verdicts
    return {str(key): str(value).strip().lower() for key, value in verdicts.items()}


def _validated(threads: list[dict[str, object]], verdicts: dict[str, str]) -> dict[str, str] | None:
    expected_ids = {str(t["finding_id"]) for t in threads}
    if set(verdicts) != expected_ids or not all(label in LABELS for label in verdicts.values()):
        return None
    return verdicts


def label_threads(threads: list[dict[str, object]]) -> dict[str, str]:
    with_replies = [t for t in threads if t["replies"]]
    labels = {str(t["finding_id"]): "unstamped" for t in threads if not t["replies"]}

    for offset in range(0, len(with_replies), BATCH_SIZE):
        batch = with_replies[offset : offset + BATCH_SIZE]
        verdicts = _validated(batch, _model_judge(batch))
        if verdicts is None:
            # Retry thread-by-thread so one malformed answer doesn't take
            # down the batch; individual failure is terminal.
            verdicts = {}
            for thread in batch:
                single = _validated([thread], _model_judge([thread]))
                assert single is not None, f"model could not label thread {thread['finding_id']}"
                verdicts.update(single)
        labels.update(verdicts)
        done = len(labels)
        print(f"labeled {done}/{len(threads)}", file=sys.stderr)
    return labels


def main() -> None:
    assert len(sys.argv) == 3, f"usage: {sys.argv[0]} RAW_JSON LABELED_JSON"
    raw_path, labeled_path = Path(sys.argv[1]), Path(sys.argv[2])
    dataset = json.loads(raw_path.read_text(encoding="utf-8"))
    threads = dataset["threads"]
    assert threads, f"no threads in {raw_path}"

    labels = label_threads(threads)
    for thread in threads:
        thread["disposition"] = labels[str(thread["finding_id"])]
    dataset["labeled_by"] = MODEL

    labeled_path.parent.mkdir(parents=True, exist_ok=True)
    labeled_path.write_text(json.dumps(dataset, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    counts: dict[str, int] = {}
    for thread in threads:
        verdict = thread["disposition"]
        if verdict not in counts:
            counts[verdict] = 0
        counts[verdict] += 1
    print(f"{len(threads)} threads -> {labeled_path}")
    print(json.dumps(counts, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
