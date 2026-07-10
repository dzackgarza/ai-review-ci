"""Proof for the Review Guidelines distribution gate (#215).

The canonical `# Review Guidelines` section is a pinned, packaged data artifact
(``data/review-guidelines.md``) — the same idiom as the label taxonomy
(``data/labels.json``): a version-controlled, reviewable canonical loaded via
``importlib.resources``, so the gate is deterministic offline with no live wiki
fetch and therefore no network boundary to mock (POLICY.NO_MOCK_PROOF).

Semantic behavior is proven in pure functions against the real packaged canonical
and real Markdown documents: presence, currency (normalized match), and uniqueness
(no duplicate sections). The ``check_review_guidelines`` command is proven end to end
against real on-disk checkouts. No mocks, no monkeypatch.
"""

from pathlib import Path

import pytest

from ai_review_ci.review_guidelines import (
    ReviewGuidelinesStatus,
    check_review_guidelines,
    classify_review_guidelines,
    extract_review_guidelines_sections,
    load_canonical_review_guidelines,
    normalize,
)

ROOT = Path(__file__).resolve().parents[1]

OTHER_SECTIONS = "# Something Else\n\nUnrelated top-level content.\n\n## A subsection\n\nMore.\n"


def _agents_md_with(section: str) -> str:
    """A realistic AGENTS.md: an unrelated section, then the given section."""
    return f"# Project\n\nIntro paragraph.\n\n{OTHER_SECTIONS}\n{section}\n"


# --- canonical artifact ---


def test_packaged_canonical_loads_nonempty_with_header() -> None:
    canonical = load_canonical_review_guidelines()
    assert canonical.strip(), "packaged canonical must be non-empty"
    assert canonical.lstrip().startswith("# Review Guidelines"), "canonical must be the section including its level-1 header"


# --- extraction: presence + uniqueness ---


def test_extract_returns_the_single_present_section() -> None:
    canonical = load_canonical_review_guidelines()
    sections = extract_review_guidelines_sections(_agents_md_with(canonical))
    assert len(sections) == 1
    assert normalize(sections[0]) == normalize(canonical)


def test_extract_returns_empty_when_absent() -> None:
    assert extract_review_guidelines_sections(_agents_md_with("")) == []


def test_extract_counts_duplicates() -> None:
    canonical = load_canonical_review_guidelines()
    doc = _agents_md_with(canonical) + "\n" + canonical + "\n"
    assert len(extract_review_guidelines_sections(doc)) == 2


def test_extract_ignores_inline_code_mention() -> None:
    # A prose mention like: See `# Review Guidelines` -> Evidence ... is NOT a section.
    doc = "# Doc\n\nSee `# Review Guidelines` for the reviewer-side counterpart.\n"
    assert extract_review_guidelines_sections(doc) == []


def test_extract_ignores_fenced_code_block() -> None:
    # A fenced code block whose content starts with `# Review Guidelines` at column 0
    # is example text, not a real section — it must not create a false (duplicate) hit.
    doc = "# Doc\n\n```\n# Review Guidelines\nnot the real thing\n```\n"
    assert extract_review_guidelines_sections(doc) == []


def test_extract_stops_at_next_level1_header() -> None:
    canonical = load_canonical_review_guidelines()
    doc = _agents_md_with(canonical)
    (section,) = extract_review_guidelines_sections(doc)
    # The trailing unrelated content after the section must not be swallowed.
    assert "Unrelated top-level content" not in section


# --- normalization: robust but non-laundering ---


def test_normalize_ignores_trailing_whitespace_and_blank_line_runs() -> None:
    canonical = load_canonical_review_guidelines()
    # Layout-only drift: widen each existing blank gap to a run and add trailing spaces
    # and a trailing newline run. Paragraph structure is preserved (no blanks inserted
    # between adjacent prose lines), so this normalizes equal.
    noisy = canonical.replace("\n\n", "\n\n\n")
    noisy = "".join(line.rstrip() + "   \n" for line in noisy.split("\n")) + "\n\n"
    assert normalize(noisy) == normalize(canonical)


def test_normalize_does_not_launder_genuine_staleness() -> None:
    canonical = load_canonical_review_guidelines()
    stale = canonical.replace("completion", "compleeetion", 1)
    assert stale != canonical
    assert normalize(stale) != normalize(canonical)


# --- classification: the gate result ---


def test_current_unique_section_passes() -> None:
    canonical = load_canonical_review_guidelines()
    status = classify_review_guidelines(_agents_md_with(canonical), canonical)
    assert isinstance(status, ReviewGuidelinesStatus)
    assert status.state == "current"


def test_missing_section_fails() -> None:
    canonical = load_canonical_review_guidelines()
    status = classify_review_guidelines(_agents_md_with(""), canonical)
    assert status.state == "missing"
    assert status.remediation, "a failing status must name the remediation"


def test_absent_agents_md_is_missing() -> None:
    canonical = load_canonical_review_guidelines()
    status = classify_review_guidelines(None, canonical)
    assert status.state == "missing"


def test_duplicated_section_fails() -> None:
    canonical = load_canonical_review_guidelines()
    doc = _agents_md_with(canonical) + "\n" + canonical + "\n"
    status = classify_review_guidelines(doc, canonical)
    assert status.state == "duplicated"


def test_stale_section_fails() -> None:
    canonical = load_canonical_review_guidelines()
    stale = canonical.replace("completion", "partial-ish thing", 1)
    status = classify_review_guidelines(_agents_md_with(stale), canonical)
    assert status.state == "stale"


def test_whitespace_only_drift_still_passes() -> None:
    canonical = load_canonical_review_guidelines()
    noisy_section = "\n".join(line + "  " for line in canonical.splitlines()) + "\n\n"
    status = classify_review_guidelines(_agents_md_with(noisy_section), canonical)
    assert status.state == "current"


def test_failing_status_points_at_git_guidelines_step() -> None:
    canonical = load_canonical_review_guidelines()
    status = classify_review_guidelines(_agents_md_with(""), canonical)
    assert "Publish review guidance before submission" in status.remediation


# --- dogfood: this repo must satisfy its own gate ---


def test_this_repo_agents_md_is_current() -> None:
    canonical = load_canonical_review_guidelines()
    agents_md = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    status = classify_review_guidelines(agents_md, canonical)
    assert status.state == "current", status.detail


# --- command: usable as a local hook / CI check ---


def test_check_command_passes_on_current_repo(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    canonical = load_canonical_review_guidelines()
    (tmp_path / "AGENTS.md").write_text(_agents_md_with(canonical), encoding="utf-8")
    check_review_guidelines(tmp_path)  # must not raise / exit
    assert "review guidance" in capsys.readouterr().out.lower()


def test_check_command_exits_nonzero_on_missing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "AGENTS.md").write_text(_agents_md_with(""), encoding="utf-8")
    with pytest.raises(SystemExit) as excinfo:
        check_review_guidelines(tmp_path)
    assert excinfo.value.code == 1
    assert "Publish review guidance before submission" in capsys.readouterr().err


def test_check_command_exits_nonzero_when_no_agents_md(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as excinfo:
        check_review_guidelines(tmp_path)
    assert excinfo.value.code == 1
