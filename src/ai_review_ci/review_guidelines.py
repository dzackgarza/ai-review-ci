"""Deterministic gate: the head repo's local ``AGENTS.md`` must carry the current
canonical ``# Review Guidelines`` section before a PR goes out for review (#215).

Review agents (codex, gemini, kilo, cubic, …) read the *target repo's local*
``AGENTS.md`` for the guidance that defines what they enforce. A PR opened / marked
ready / tagged for review while that distribution copy is missing, stale, or
duplicated is a false-green: the review runs, but against absent or wrong guidance.

Design mirrors the label-taxonomy gate (``labels.py``):

- The canonical is a pinned, version-controlled, reviewable data artifact
  (``data/review-guidelines.md``) loaded via ``importlib.resources`` — *not* a live
  wiki fetch. This makes the gate deterministic offline, so there is no network
  boundary to mock (POLICY.NO_MOCK_PROOF). The wiki page remains the human source of
  truth; distributing an update means committing it here, exactly as label changes
  commit ``labels.json``.
- The classification logic is a pure function over Markdown text (presence, currency,
  uniqueness), provable against real documents with no I/O.
- A missing/corrupt canonical fails loud (never a silent pass): "cannot verify the
  canonical" is not "current".
"""

import re
import sys
from importlib.resources import files
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

SECTION_TITLE = "Review Guidelines"
_SECTION_HEADER = f"# {SECTION_TITLE}"

# The exact git-guidelines step a failing repo must run to remediate. Named in every
# failure so the operator gets the fix, not a bare "check failed".
REMEDIATION = (
    "Publish review guidance before submission: create/replace/append the canonical "
    f"`{_SECTION_HEADER}` section in the head repo's local AGENTS.md from the "
    "Review-Guidelines wiki page (dzackgarza/ai), per the git-guidelines "
    "'Publish review guidance before submission' step, then request review. "
    "Exactly one such section must be present and match the canonical."
)

_HTML_COMMENT_LINE = re.compile(r"\s*<!--.*-->\s*$")


def _fence_marker(line: str) -> tuple[str, int, bool] | None:
    """Classify a line as a CommonMark fenced-code-block marker, else ``None``.

    Returns ``(fence_char, run_length, is_bare)`` where ``fence_char`` is ``` ``` ``` or
    ``~``, ``run_length`` is the count of fence characters, and ``is_bare`` is true when the
    run is followed only by whitespace (a valid *closing* fence). Per CommonMark: up to three
    leading spaces of indentation, then a run of at least three of the same fence character.
    """
    stripped = line.lstrip(" ")
    if len(line) - len(stripped) > 3:  # 4+ leading spaces is indented code, not a fence
        return None
    for ch in ("`", "~"):
        if stripped.startswith(ch * 3):
            run = len(stripped) - len(stripped.lstrip(ch))
            # ponytail: a backtick opening fence may not carry backticks in its info
            # string; treating such a line as a fence errs on the safe (skip) side.
            return ch, run, stripped[run:].strip() == ""
    return None


ReviewGuidelinesState = Literal["current", "missing", "stale", "duplicated"]


class ReviewGuidelinesStatus(BaseModel):
    """Classification of a repo's ``# Review Guidelines`` distribution copy."""

    model_config = ConfigDict(frozen=True)

    state: ReviewGuidelinesState
    detail: str
    # Empty only for the passing (``current``) state; every failing state names the fix.
    remediation: str = ""


def load_canonical_review_guidelines() -> str:
    """Load the pinned canonical ``# Review Guidelines`` section shipped with the package.

    Fails loud if the packaged artifact is missing or empty: a gate that cannot read its
    own canonical must not silently pass work as current.
    """
    text = (files("ai_review_ci") / "data" / "review-guidelines.md").read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("packaged canonical review-guidelines.md is empty; cannot verify currency")
    if not text.lstrip().startswith(_SECTION_HEADER):
        raise ValueError(f"packaged canonical must begin with '{_SECTION_HEADER}'")
    return text


def normalize(text: str) -> str:
    """Whitespace-robust normalization that does not launder genuine staleness.

    Normalizes line endings, strips trailing whitespace per line, collapses runs of
    blank lines, and trims leading/trailing blank lines. It deliberately preserves all
    words, punctuation, and heading text and does not touch intra-line spacing, so a
    copy that differs in actual content (not just layout) still mismatches.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    for raw in lines:
        line = raw.rstrip()
        if line == "" and (not out or out[-1] == ""):
            continue
        out.append(line)
    while out and out[-1] == "":
        out.pop()
    while out and out[0] == "":
        out.pop(0)
    return "\n".join(out)


def extract_review_guidelines_sections(doc: str) -> list[str]:
    """Return every top-level ``# Review Guidelines`` section body (header included).

    A section starts at a line that is exactly the level-1 header ``# Review Guidelines``
    (at column 0, not an inline code mention like ``See `# Review Guidelines` ``) and runs
    until the next level-1 ``# `` header or end of document. Content inside fenced code
    blocks — backtick (```` ``` ````) *and* tilde (``~~~``) fences, per CommonMark — is
    skipped so an example listing cannot forge a section; a fence closes only on a bare run
    of its own fence character at least as long as the opener. Trailing blank and standalone
    HTML-comment lines (e.g. a following managed block's ``<!-- ... -->`` delimiter) are
    markup, not review prose, and are dropped from the captured section.
    """
    lines = doc.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    sections: list[str] = []
    current: list[str] | None = None
    fence_char: str | None = None  # the open fence's character, or None when outside a fence
    fence_len = 0

    def close(section: list[str]) -> None:
        while section and (section[-1].strip() == "" or _HTML_COMMENT_LINE.match(section[-1])):
            section.pop()
        sections.append("\n".join(section))

    for line in lines:
        marker = _fence_marker(line)
        if marker is not None:
            ch, run, is_bare = marker
            if fence_char is None:
                fence_char, fence_len = ch, run
            elif ch == fence_char and is_bare and run >= fence_len:
                fence_char, fence_len = None, 0
            # A non-matching or info-string fence line inside an open fence is content.
            if current is not None:
                current.append(line)
            continue
        is_level1 = fence_char is None and line.startswith("# ") and not line.startswith("##")
        if is_level1 and line.rstrip() == _SECTION_HEADER:
            if current is not None:
                close(current)
            current = [line]
            continue
        if is_level1 and current is not None:
            # A different level-1 header closes the open section.
            close(current)
            current = None
            continue
        if current is not None:
            current.append(line)
    if current is not None:
        close(current)
    return sections


def classify_review_guidelines(agents_md: str | None, canonical: str) -> ReviewGuidelinesStatus:
    """Classify a repo's ``AGENTS.md`` against the canonical section.

    ``agents_md`` is the local distribution copy, or ``None`` when the repo has no
    ``AGENTS.md`` at all (the section is then trivially missing).
    """
    if agents_md is None:
        return ReviewGuidelinesStatus(state="missing", detail="repo has no local AGENTS.md", remediation=REMEDIATION)
    sections = extract_review_guidelines_sections(agents_md)
    if len(sections) == 0:
        return ReviewGuidelinesStatus(
            state="missing",
            detail=f"AGENTS.md has no top-level '{_SECTION_HEADER}' section",
            remediation=REMEDIATION,
        )
    if len(sections) > 1:
        return ReviewGuidelinesStatus(
            state="duplicated",
            detail=f"AGENTS.md has {len(sections)} top-level '{_SECTION_HEADER}' sections; exactly one is required",
            remediation=REMEDIATION,
        )
    if normalize(sections[0]) != normalize(canonical):
        return ReviewGuidelinesStatus(
            state="stale",
            detail=f"the '{_SECTION_HEADER}' section does not match the canonical source",
            remediation=REMEDIATION,
        )
    return ReviewGuidelinesStatus(state="current", detail=f"'{_SECTION_HEADER}' section is present, unique, and current")


def _review_guidelines_section_ranges(doc: str) -> list[tuple[int, int]]:
    """Line-index ``[start, end)`` ranges of each top-level ``# Review Guidelines`` section.

    Mirrors ``extract_review_guidelines_sections``' fence-aware, level-1-header boundary
    logic so the writer removes exactly what the gate would count as a section (and never a
    fenced-code mention).
    """
    lines = doc.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ranges: list[tuple[int, int]] = []
    start: int | None = None
    fence_char: str | None = None
    fence_len = 0
    for i, line in enumerate(lines):
        marker = _fence_marker(line)
        if marker is not None:
            ch, run, is_bare = marker
            if fence_char is None:
                fence_char, fence_len = ch, run
            elif ch == fence_char and is_bare and run >= fence_len:
                fence_char, fence_len = None, 0
            continue
        is_level1 = fence_char is None and line.startswith("# ") and not line.startswith("##")
        if is_level1 and line.rstrip() == _SECTION_HEADER:
            if start is not None:
                ranges.append((start, i))
            start = i
            continue
        if is_level1 and start is not None:
            ranges.append((start, i))
            start = None
    if start is not None:
        ranges.append((start, len(lines)))
    return ranges


def upsert_review_guidelines_section(agents_md: str | None, canonical: str) -> str:
    """Return AGENTS.md content carrying exactly one current canonical section.

    Removes any pre-existing ``# Review Guidelines`` section(s) — stale or duplicated — and
    appends the canonical once at the end, preserving all other content. Idempotent:
    re-running on already-current content yields the same single current section. This is the
    writer half of the gate ``classify_review_guidelines`` enforces; both live here so the
    contract has one source of truth.
    """
    canonical_block = canonical.strip()
    if agents_md is None or agents_md.strip() == "":
        return canonical_block + "\n"
    lines = agents_md.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    drop: set[int] = set()
    for s, e in _review_guidelines_section_ranges(agents_md):
        drop.update(range(s, e))
    kept = [line for idx, line in enumerate(lines) if idx not in drop]
    while kept and kept[-1].strip() == "":
        kept.pop()
    if not kept:
        return canonical_block + "\n"
    return "\n".join(kept) + "\n\n" + canonical_block + "\n"


def check_review_guidelines(target: Path) -> None:
    """Fail unless the target repo's AGENTS.md carries the current canonical section.

    Usable both as a local pre-push/pre-PR hook (``ai-review-ci check-review-guidelines
    --target .``) and as a CI check, so a missing/stale/duplicated distribution copy
    surfaces before reviewers are tagged rather than after.
    """
    target = target.resolve()
    agents_path = target / "AGENTS.md"
    agents_md = agents_path.read_text(encoding="utf-8") if agents_path.is_file() else None
    status = classify_review_guidelines(agents_md, load_canonical_review_guidelines())
    if status.state != "current":
        print(f"Review Guidelines gate failed for {target}: {status.state}: {status.detail}", file=sys.stderr)
        print(status.remediation, file=sys.stderr)
        sys.exit(1)
    print(f"Review guidance gate passed for {target}: {status.detail}.")
