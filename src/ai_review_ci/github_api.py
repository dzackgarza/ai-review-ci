"""Typed parsing for the GitHub API response shapes ai-review-ci reads.

Centralizes the code-scanning alert and review-thread shapes that ``context.py``
renders, replacing scattered key-by-key extraction (``_string`` / ``_integer`` /
``_mapping`` and the per-field ``_alert_*`` helpers) with one validated boundary.
``extra="ignore"`` lets GitHub return its many other fields without failing.

The constraints here mirror the previous hand-rolled validators exactly:
non-empty ``rule.id`` / ``location.path`` / ``html_url`` / comment ``body``,
strict integer ``start_line``, strict boolean ``isResolved``, and — for review
threads — a ``path`` that is required only once the thread actually has a
comment (an empty-comment thread is dropped before its path is read).

Scope note: only the fields the renderer consumes are modeled. The SARIF
carry-forward payload still forwards the *raw* alert dict verbatim
(``context._carry_forward_payload``), so no unmodeled field is dropped.
"""

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    model_validator,
)


class _ApiModel(BaseModel):
    # GitHub responses carry many fields the renderer never reads.
    model_config = ConfigDict(extra="ignore")


class AlertRule(_ApiModel):
    id: str = Field(min_length=1)
    name: str | None = None

    @property
    def label(self) -> str:
        return self.name if self.name else self.id


class AlertLocation(_ApiModel):
    path: str = Field(min_length=1)
    start_line: StrictInt


class AlertInstance(_ApiModel):
    location: AlertLocation


class CodeScanningAlert(_ApiModel):
    html_url: str = Field(min_length=1)
    rule: AlertRule
    most_recent_instance: AlertInstance
    dismissed_reason: str | None = None
    dismissed_comment: str | None = None

    @property
    def location(self) -> str:
        loc = self.most_recent_instance.location
        return f"{loc.path}:{loc.start_line}"


class _ReviewThreadComment(_ApiModel):
    body: str = Field(min_length=1)


class _ReviewThreadComments(_ApiModel):
    nodes: list[_ReviewThreadComment]


class ReviewThread(_ApiModel):
    # path is read only when the thread has a comment; an empty-comment thread
    # is dropped first, so path may be absent there (matches the old digest).
    path: str | None = None
    isResolved: StrictBool  # noqa: N815 — GraphQL field name, matched verbatim
    comments: _ReviewThreadComments

    @model_validator(mode="after")
    def _path_required_when_commented(self) -> Self:
        if self.comments.nodes and not self.path:
            raise ValueError("review thread with comments must have a non-empty path")
        return self

    def digest(self) -> dict[str, object] | None:
        """First-comment digest, or None when the thread has no comments.

        The headline is the first line of the first comment's body.
        """
        if not self.comments.nodes:
            return None
        return {
            "path": self.path,
            "headline": self.comments.nodes[0].body.splitlines()[0],
            "resolved": self.isResolved,
        }
