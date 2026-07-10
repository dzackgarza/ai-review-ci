"""Proof for the canonical label taxonomy and its idempotent planner.

The taxonomy is loaded from the real packaged artifact (no fixture copy) and the
planner is exercised with real inputs. There is no gh mock: the network boundary
carries no proof burden — the idempotence logic lives entirely in
``compute_label_actions``, which is pure.
"""

import pytest
from pydantic import ValidationError

from ai_review_ci.labels import (
    Label,
    RemoteLabel,
    Taxonomy,
    compute_label_actions,
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
