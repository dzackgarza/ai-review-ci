"""Proof for the canonical label taxonomy and its idempotent planner.

The taxonomy is loaded from the real packaged artifact (no fixture copy) and the
planner is exercised with real inputs. There is no gh mock: the network boundary
carries no proof burden — the idempotence logic lives entirely in
``compute_label_actions``, which is pure.
"""

import subprocess

import pytest
from pydantic import ValidationError

from ai_review_ci import labels as labels_module
from ai_review_ci.labels import (
    Label,
    RemoteLabel,
    Taxonomy,
    _fetch_remote_labels,
    _gh,
    compute_label_actions,
    install_labels,
    load_taxonomy,
)

REQUIRED_CATEGORIES = {"type", "scope", "status", "area"}


def test_shipped_taxonomy_loads_and_is_well_formed() -> None:
    taxonomy = load_taxonomy()
    assert taxonomy, "packaged taxonomy must be non-empty"
    names = [label.name for label in taxonomy]
    assert len(names) == len(set(names)), "packaged taxonomy has duplicate names"
    assert {label.category for label in taxonomy} == REQUIRED_CATEGORIES


def test_missing_labels_are_created() -> None:
    taxonomy = load_taxonomy()
    plan = compute_label_actions({}, taxonomy)
    assert plan.create == taxonomy
    assert plan.update == ()
    assert plan.unchanged == ()


def test_exact_match_is_unchanged() -> None:
    taxonomy = load_taxonomy()
    remote = {label.name: RemoteLabel(name=label.name, color=label.color, description=label.description) for label in taxonomy}
    plan = compute_label_actions(remote, taxonomy)
    assert plan.unchanged == taxonomy
    assert plan.create == ()
    assert plan.update == ()


def test_color_drift_is_an_update_case_insensitively() -> None:
    label = Label(name="bug", color="D73A4A", description="Something isn't working", category="type")
    # Same color, different case -> unchanged.
    same = {"bug": RemoteLabel(name="bug", color="d73a4a", description="Something isn't working")}
    assert compute_label_actions(same, [label]).unchanged == (label,)
    # Genuinely different color -> update.
    drifted = {"bug": RemoteLabel(name="bug", color="000000", description="Something isn't working")}
    assert compute_label_actions(drifted, [label]).update == (label,)


def test_description_drift_is_an_update() -> None:
    label = Label(name="epic", color="5319e7", description="Canonical description", category="scope")
    remote = {"epic": RemoteLabel(name="epic", color="5319e7", description="stale description")}
    assert compute_label_actions(remote, [label]).update == (label,)


def test_remote_labels_outside_taxonomy_are_left_untouched() -> None:
    label = Label(name="bug", color="d73a4a", description="Something isn't working", category="type")
    remote = {
        "bug": RemoteLabel(name="bug", color="d73a4a", description="Something isn't working"),
        "kilo-triaged": RemoteLabel(name="kilo-triaged", color="faf74f", description="Auto-generated"),
    }
    plan = compute_label_actions(remote, [label])
    # kilo-triaged appears in no bucket: the taxonomy is additive, not a destructive sync.
    assert plan.unchanged == (label,)
    assert plan.create == ()
    assert plan.update == ()


def test_duplicate_taxonomy_names_are_rejected() -> None:
    dup = Label(name="bug", color="d73a4a", description="dup", category="type")
    with pytest.raises((ValidationError, AssertionError)):
        Taxonomy(labels=(dup, dup))


def test_invalid_color_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Label(name="bug", color="not-hex", description="x", category="type")


# --- I/O seam coverage: the gh boundary is a thin fail-loud wrapper; the semantic
# proof lives in compute_label_actions above. These cover control flow, not a mocked
# claim of owned behavior. ---


def test_gh_returns_stdout_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ai_review_ci.labels.subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="out", stderr=""),
    )
    assert _gh(["label", "list"]) == "out"


def test_gh_is_fatal_on_nonzero_returncode(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(
        "ai_review_ci.labels.subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess(a, 1, stdout="", stderr="boom"),
    )
    with pytest.raises(SystemExit) as excinfo:
        _gh(["label", "create", "x"])
    assert excinfo.value.code == 1
    assert "gh label create failed: boom" in capsys.readouterr().err


def test_fetch_remote_labels_parses_gh_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        labels_module,
        "_gh",
        lambda args: '[{"name":"bug","color":"d73a4a","description":"Something isn\'t working"}]',
    )
    remote = _fetch_remote_labels("owner/repo")
    assert remote["bug"] == RemoteLabel(name="bug", color="d73a4a", description="Something isn't working")


def test_install_labels_creates_missing_and_updates_drifted(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    taxonomy = load_taxonomy()
    # bug present but drifted (update); everything else absent (create).
    remote = {"bug": RemoteLabel(name="bug", color="000000", description="stale")}
    monkeypatch.setattr(labels_module, "_fetch_remote_labels", lambda repo: remote)
    calls: list[list[str]] = []

    def record_gh(args: list[str]) -> str:
        calls.append(args)
        return ""

    monkeypatch.setattr(labels_module, "_gh", record_gh)

    install_labels("owner/repo")

    verbs = {args[1] for args in calls}
    assert verbs == {"create", "edit"}
    edited = [args[2] for args in calls if args[1] == "edit"]
    assert edited == ["bug"]
    created = [args[2] for args in calls if args[1] == "create"]
    assert len(created) == len(taxonomy) - 1
    out = capsys.readouterr().out
    assert f"{len(taxonomy) - 1} created, 1 updated, 0 already current" in out
