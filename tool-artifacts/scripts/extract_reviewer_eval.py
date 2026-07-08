# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Extract the reviewer-signal eval set from a disposition-stamped PR (#41, was #28).

zotero-gui PR #7 carries an owner disposition on every review thread, making
it a labeled ground-truth set for measuring reviewer-prompt candidates:
slop-precision (does the reviewer flag actual slop?) and real-correctness
recall (does it keep real findings?).

Pages all review threads through `gh api graphql`, mechanically parses each
thread's disposition from its reply comments, and writes the tracked dataset
consumed by ai_review_ci.reviewer_eval:

    uv run tool-artifacts/scripts/extract_reviewer_eval.py \
        dzackgarza/zotero-gui 7 tests/fixtures/reviewer-eval/zotero_gui_pr7.json

Re-running regenerates the dataset deterministically from the live PR; the
committed JSON is the reviewable artifact of record.
"""

import json
import re
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
          comments(first: 50) {
            nodes { databaseId url author { login } body }
          }
        }
      }
    }
  }
}
"""

# A disposition stamp is a reply that names its verdict. Scanned in reverse
# reply order so the final stamp wins over earlier triage chatter.
_DISPOSITION_VERDICTS = (
    ("outdated", re.compile(r"\b[Oo]utdated\b|\bsuperseded\b")),
    ("duplicate", re.compile(r"\bduplicate\b")),
    ("accepted", re.compile(r"\bAccepted\b")),
    ("rejected", re.compile(r"\bRejected\b")),
)
_STAMP_MARKER = re.compile(r"^Disposition\b", re.MULTILINE)


def parse_disposition(replies: list[dict[str, object]]) -> tuple[str, int | None]:
    """(verdict, stamping comment databaseId) for a thread's reply comments.

    Explicit "Disposition ..." stamps win over terse verdict-only replies;
    within each tier the latest reply wins.
    """
    for require_marker in (True, False):
        for reply in reversed(replies):
            body = str(reply["body"])
            if require_marker and not _STAMP_MARKER.search(body):
                continue
            for verdict, pattern in _DISPOSITION_VERDICTS:
                if pattern.search(body):
                    database_id = reply["databaseId"]
                    assert database_id is None or isinstance(database_id, int), reply
                    return verdict, database_id
    return "unstamped", None


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
        finding, replies = comments[0], comments[1:]
        assert isinstance(finding, dict), finding
        verdict, stamp_id = parse_disposition(replies)
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
                "disposition": verdict,
                "disposition_comment_id": stamp_id,
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
    rows = dataset["threads"]
    assert isinstance(rows, list), rows
    counts: dict[str, int] = {}
    for row in rows:
        verdict = row["disposition"]
        assert isinstance(verdict, str), row
        if verdict not in counts:
            counts[verdict] = 0
        counts[verdict] += 1
    print(f"{dataset['thread_count']} threads -> {output}")
    print(json.dumps(counts, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
