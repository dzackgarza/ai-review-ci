"""Proof for the canonical label taxonomy, its planner, and its gh installer.

Semantic behavior is proven in pure functions against the real packaged artifact and
real gh-shaped data (``compute_label_actions``, ``label_commands``, ``RemoteLabel``
parsing). The gh boundary is proven against real ``gh`` invocations — offline
``--version`` success and a real nonzero-exit failure — with no mocks, per
POLICY.NO_MOCK_PROOF. ``install_labels`` is proven end-to-end against real repositories:
a read-only no-op against this repo, and a real failing create against a public repo the
CI token cannot write.
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_review_ci.labels import (
    Label,
    LabelPlan,
    RemoteLabel,
    Taxonomy,
    _gh,
    compute_label_actions,
    install_labels,
    label_commands,
    load_taxonomy,
)

REQUIRED_CATEGORIES = {"type", "scope", "status", "area"}


# --- pure: taxonomy + planner + command mapping (real artifact, real data) ---


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
    same = {"bug": RemoteLabel(name="bug", color="d73a4a", description="Something isn't working")}
    assert compute_label_actions(same, [label]).unchanged == (label,)
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
    assert plan.unchanged == (label,)
    assert plan.create == ()
    assert plan.update == ()


def test_label_commands_maps_plan_to_gh_argv_in_order() -> None:
    create = Label(name="new", color="aaaaaa", description="fresh", category="type")
    update = Label(name="old", color="bbbbbb", description="drifted", category="scope")
    plan = LabelPlan(create=(create,), update=(update,), unchanged=())
    assert label_commands(plan, "owner/repo") == (
        ("label", "create", "new", "--repo", "owner/repo", "--color", "aaaaaa", "--description", "fresh"),
        ("label", "edit", "old", "--repo", "owner/repo", "--color", "bbbbbb", "--description", "drifted"),
    )


def test_remote_label_parses_real_gh_list_shape() -> None:
    # The exact JSON shape `gh label list --json name,color,description` returns.
    raw = json.loads('[{"name":"bug","color":"d73a4a","description":"Something isn\'t working"}]')
    parsed = [RemoteLabel.model_validate(entry) for entry in raw]
    assert parsed == [RemoteLabel(name="bug", color="d73a4a", description="Something isn't working")]


def test_duplicate_taxonomy_names_are_rejected() -> None:
    dup = Label(name="bug", color="d73a4a", description="dup", category="type")
    with pytest.raises((ValidationError, AssertionError)):
        Taxonomy(labels=(dup, dup))


def test_invalid_color_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Label(name="bug", color="not-hex", description="x", category="type")


# --- real gh boundary: fail-loud wrapper, exercised against real gh (no mock) ---


def test_gh_returns_output_on_real_success() -> None:
    # `gh --version` is offline and always exits 0.
    assert "gh version" in _gh(["--version"])


def test_gh_is_fatal_on_real_nonzero_exit(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        _gh(["not-a-real-gh-subcommand-xyzzy"])
    assert excinfo.value.code == 1
    assert "FATAL: gh not-a-real-gh-subcommand-xyzzy failed" in capsys.readouterr().err


# --- real gh boundary: install_labels end-to-end against real repositories ---


def test_install_labels_is_a_noop_when_all_labels_already_present(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Read-only real gh: a custom taxonomy whose sole label already exists unchanged on
    # this repo (a GitHub default) yields an empty plan, so nothing is mutated while the
    # real fetch/compute/summary path executes.
    taxonomy = tmp_path / "labels.json"
    taxonomy.write_text(json.dumps({"labels": [{"name": "bug", "color": "d73a4a", "description": "Something isn't working", "category": "type"}]}))
    install_labels("dzackgarza/ai-review-ci", taxonomy=taxonomy)
    assert "0 created, 0 updated, 1 already current" in capsys.readouterr().out


def test_install_labels_fails_loud_when_a_create_is_rejected(tmp_path: Path) -> None:
    # Real boundary: octocat/Hello-World is public (readable) but not writable by the CI
    # token, so a label absent there is planned for creation, the create is attempted for
    # real, gh exits nonzero, and install_labels fails loud (POLICY.FAIL_OPEN). No mock.
    taxonomy = tmp_path / "labels.json"
    taxonomy.write_text(json.dumps({"labels": [{"name": "zz-ai-review-ci-probe", "color": "ededed", "description": "probe", "category": "type"}]}))
    with pytest.raises(SystemExit):
        install_labels("octocat/Hello-World", taxonomy=taxonomy)
