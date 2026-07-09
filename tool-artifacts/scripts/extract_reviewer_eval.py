# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Extract the reviewer-signal eval set from a disposition-stamped PR (#41, was #28).

zotero-gui PR #7 carries an owner disposition on every review thread, making
it a labeled ground-truth set for measuring reviewer-prompt candidates:
slop-precision (does the reviewer flag actual slop?) and real-correctness
recall (does it keep real findings?).

Pages all review threads through `gh api graphql` and writes the raw thread
data (finding + reply bodies). Extraction is purely mechanical; it imposes no
format on the dispositions. The verdict labels are added afterwards by
label_reviewer_eval.py, which has the CI model *read* each thread's replies —
dispositions are intelligent free text, not a template to regex:

    uv run tool-artifacts/scripts/extract_reviewer_eval.py \
        dzackgarza/zotero-gui 7 <raw.json>
    uv run tool-artifacts/scripts/label_reviewer_eval.py \
        <raw.json> tests/fixtures/reviewer-eval/zotero_gui_pr7.json

The committed labeled JSON is the reviewable artifact of record.
"""

import json
import subprocess
import sys
from pathlib import Path

QUERY = """
query($owner: String!, $name: String!, $number: Int!, $endCursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 50, after: $endCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          isResolved
          isOutdated
          path
          line
          comments(first: 100) {
            totalCount
            nodes { databaseId url author { login } body }
          }
        }
      }
    }
  }
}
"""


def fetch_threads(owner: str, name: str, number: int) -> list[dict[str, object]]:
    proc = subprocess.run(
        [
            "gh",
            "api",
            "graphql",
            "--paginate",
            "-f",
            f"query={QUERY}",
            "-F",
            f"owner={owner}",
            "-F",
            f"name={name}",
            "-F",
            f"number={number}",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    threads: list[dict[str, object]] = []
    # --paginate emits one JSON document per page, concatenated.
    for document in _iter_documents(proc.stdout):
        nodes = _dig(document, "data", "repository", "pullRequest", "reviewThreads", "nodes")
        assert isinstance(nodes, list), nodes
        for node in nodes:
            assert isinstance(node, dict), node
            threads.append(node)
    return threads


def _dig(value: object, *keys: str) -> object:
    """Assert-narrowed nested access into decoded GraphQL JSON (boundary parse)."""
    for key in keys:
        assert isinstance(value, dict), (key, type(value), value)
        value = value[key]
    return value


def _iter_documents(stream: str) -> list[object]:
    decoder = json.JSONDecoder()
    documents: list[object] = []
    index = 0
    while index < len(stream):
        if stream[index].isspace():
            index += 1
            continue
        document, end = decoder.raw_decode(stream, index)
        documents.append(document)
        index = end
    return documents


def build_dataset(owner: str, name: str, number: int) -> dict[str, object]:
    rows = []
    for thread in fetch_threads(owner, name, number):
        comments = _dig(thread, "comments", "nodes")
        assert isinstance(comments, list) and comments, f"review thread with no comments: {thread}"
        total_count = _dig(thread, "comments", "totalCount")
        assert len(comments) == total_count, f"thread comments truncated ({len(comments)} of {total_count}); raise the fetch bound"
        finding, replies = comments[0], comments[1:]
        assert isinstance(finding, dict), finding
        rows.append(
            {
                "finding_id": finding["databaseId"],
                "url": finding["url"],
                "path": thread["path"],
                "line": thread["line"],
                "is_resolved": thread["isResolved"],
                "finding_author": (finding["author"] or {}).get("login"),
                "finding_body": finding["body"],
                "replies": [{"id": r["databaseId"], "author": (r["author"] or {}).get("login"), "body": r["body"]} for r in replies],
            }
        )
    rows.sort(key=lambda row: row["finding_id"])
    return {
        "source": f"{owner}/{name}#{number}",
        "thread_count": len(rows),
        "threads": rows,
    }


def main() -> None:
    assert len(sys.argv) == 4, f"usage: {sys.argv[0]} OWNER/REPO PR_NUMBER OUTPUT_JSON"
    owner, name = sys.argv[1].split("/")
    dataset = build_dataset(owner, name, int(sys.argv[2]))
    output = Path(sys.argv[3])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dataset, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{dataset['thread_count']} threads -> {output}")
    print("next: label dispositions with tool-artifacts/scripts/label_reviewer_eval.py")


if __name__ == "__main__":
    main()
