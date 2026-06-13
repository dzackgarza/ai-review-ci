from ai_review_ci import context


def _alert() -> context.JsonDict:
    return {
        "number": 42,
        "state": "dismissed",
        "dismissed_reason": "false positive",
        "dismissed_comment": "README documentation accuracy clean_diff placeholder",
        "html_url": "https://github.com/example/repo/security/code-scanning/42",
        "rule": {
            "id": "DOC_CONSISTENCY",
            "name": "DOC_CONSISTENCY",
            "description": "README documentation accuracy finding",
        },
        "most_recent_instance": {
            "location": {
                "path": "README.md",
                "start_line": 606,
                "properties": {"label": "DOC_CONSISTENCY"},
            },
            "message": {"text": "README documentation accuracy clean_diff placeholder"},
        },
    }


def test_alert_context_is_guardrail_not_prior_finding_prose() -> None:
    text = "\n".join(context._alert_section("ai-review/general", [_alert()]))

    assert "alert #42" in text
    assert "README.md:606" in text
    assert "https://github.com/example/repo/security/code-scanning/42" in text
    assert "DOC_CONSISTENCY" not in text
    assert "clean_diff" not in text
    assert "README documentation accuracy" not in text


def test_pr_thread_context_omits_review_headlines(
    monkeypatch,
) -> None:
    def fetch_threads(repo: str, pr_number: int) -> list[context.JsonDict]:
        return [
            {
                "path": "AGENTS.md",
                "headline": "Slop Review clean_diff placeholder",
                "resolved": False,
            }
        ]

    monkeypatch.setattr(context, "_fetch_pr_threads", fetch_threads)

    text = "\n".join(context._pr_thread_lines("example/repo", 13))

    assert "AGENTS.md" in text
    assert "open" in text
    assert "clean_diff" not in text
    assert "Slop Review" not in text
