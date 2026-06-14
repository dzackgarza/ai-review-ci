from ai_review_ci.context import _thread_digest


def test_thread_digest_uses_review_thread_path() -> None:
    node = {
        "path": "src/ai_review_ci/context.py",
        "isResolved": False,
        "comments": {
            "nodes": [
                {
                    "body": "### Finding headline\n\nFinding body.",
                }
            ]
        },
    }

    assert _thread_digest(node) == {
        "path": "src/ai_review_ci/context.py",
        "headline": "### Finding headline",
        "resolved": False,
    }


def test_thread_digest_skips_threads_without_comments() -> None:
    node = {
        "path": "src/ai_review_ci/context.py",
        "isResolved": True,
        "comments": {"nodes": []},
    }

    assert _thread_digest(node) is None
