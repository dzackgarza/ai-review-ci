"""Shared reviewer identity metadata for PR threads and SARIF results."""

import os
from collections.abc import Mapping

JsonDict = dict[str, str]

DEFAULT_REVIEW_AGENT = "opencode-ai"
REVIEW_AGENT_ENV = "AI_REVIEW_AGENT"
REVIEW_PROMPT_VERSION = "1.0.0"


def review_agent(environ: Mapping[str, str] | None = None) -> str:
    """Return the active reviewer agent name, defaulting to the shipped opencode harness."""
    source = os.environ if environ is None else environ
    configured = source.get(REVIEW_AGENT_ENV, "").strip()
    return configured or DEFAULT_REVIEW_AGENT


def reviewer_identity(report_type: str, environ: Mapping[str, str] | None = None) -> JsonDict:
    """Structured reviewer identity used by every review publication surface."""
    return {
        "type": report_type,
        "agent": review_agent(environ),
        "prompt_id": f"reviews/{report_type}",
        "prompt_version": REVIEW_PROMPT_VERSION,
    }
