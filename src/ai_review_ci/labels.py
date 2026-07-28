"""Canonical cross-repo GitHub label taxonomy and its installer.

The taxonomy is a tracked data artifact (``data/labels.json``), not a dict emitted
from code, so it is reviewable in isolation. Every downstream repo should carry this
label set for consistent cross-repo triage and routing; ``install_labels`` propagates
it via ``gh``.

Structure mirrors the rest of this package: a typed boundary (the pydantic models and
``load_taxonomy``), a pure planning function (``compute_label_actions`` — the proof
surface, exercised against the real artifact with no mocks), and a thin fail-loud
``gh`` I/O layer (``install_labels``). The planning logic never touches the network, so
the ``gh`` boundary carries no proof burden that a mock could fake.
"""

import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from importlib.resources import files
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

LabelCategory = Literal["type", "scope", "status", "area", "complexity"]
_HEX_COLOR = r"^[0-9a-fA-F]{6}$"


class Label(BaseModel):
    """One canonical taxonomy entry."""

    name: str = Field(min_length=1)
    color: str = Field(pattern=_HEX_COLOR)
    description: str = Field(min_length=1)
    category: LabelCategory


class Taxonomy(BaseModel):
    labels: tuple[Label, ...] = Field(min_length=1)

    def model_post_init(self, _context: object) -> None:
        names = [label.name for label in self.labels]
        assert len(names) == len(set(names)), f"duplicate label names in taxonomy: {sorted({n for n in names if names.count(n) > 1})}"


class RemoteLabel(BaseModel):
    """A label as ``gh label list`` reports it.

    GitHub returns ``"description": null`` for a label with no description (common on
    real repos), so null is coerced to the empty string rather than rejected.
    """

    name: str = Field(min_length=1)
    color: str = Field(pattern=_HEX_COLOR)
    description: str = ""

    @field_validator("description", mode="before")
    @classmethod
    def _null_description_is_empty(cls, value: object) -> object:
        return "" if value is None else value


class LabelMisalignment(BaseModel):
    """A canonical label present on the remote only as a case/spelling variant.

    ``remote_variants`` names the repo's actual label(s) that collide with the
    canonical name case-insensitively (e.g. remote ``Bug`` vs canonical ``bug``).
    This is a misalignment, never a match: exact-name matching is preserved, so the
    variant is surfaced for the maintainer to rename rather than laundered into a match
    or auto-renamed.
    """

    model_config = ConfigDict(frozen=True)

    canonical: Label
    remote_variants: tuple[str, ...] = Field(min_length=1)


class LabelPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    create: tuple[Label, ...]
    update: tuple[Label, ...]
    unchanged: tuple[Label, ...]
    misaligned: tuple[LabelMisalignment, ...] = ()


def load_taxonomy(path: Path | None = None) -> tuple[Label, ...]:
    """Load and validate the canonical taxonomy.

    Reads the packaged ``data/labels.json`` by default, or a caller-supplied override.
    Malformed data fails loudly at the pydantic boundary.
    """
    text = path.read_text(encoding="utf-8") if path is not None else (files("ai_review_ci") / "data" / "labels.json").read_text(encoding="utf-8")
    return Taxonomy.model_validate_json(text).labels


def compute_label_actions(remote: Mapping[str, RemoteLabel], taxonomy: Sequence[Label]) -> LabelPlan:
    """Pure plan reconciling the mandatory canonical set against a repo's labels.

    Every canonical (taxonomy) label is required to exist *exactly*: it is *created*
    when its name is absent, *updated* when its color (compared case-insensitively —
    hex casing is not semantic) or description drifts, and *unchanged* on an exact
    match. Non-canonical labels the repo also carries are left untouched — extra labels
    are allowed since we cannot predict every repo's needs. But the canonical set is not
    optional and is matched by *exact* name: a close-but-unequal variant (e.g. a
    different name casing) is a misalignment, not a match, so that a canonical name like
    ``bug`` means the same label in every repo and aggregates cleanly across them.
    """
    create: list[Label] = []
    update: list[Label] = []
    unchanged: list[Label] = []
    misaligned: list[LabelMisalignment] = []
    for label in taxonomy:
        existing = remote.get(label.name)
        if existing is None:
            variants = _case_variants(label.name, remote)
            if variants:
                # A canonical label absent by exact name but present as a case variant
                # would produce a create that gh rejects (labels collide
                # case-insensitively). Surface it as a misalignment instead of a doomed
                # create — exact matching stays; the maintainer renames to align.
                misaligned.append(LabelMisalignment(canonical=label, remote_variants=variants))
            else:
                create.append(label)
        elif existing.color.lower() != label.color.lower() or existing.description != label.description:
            update.append(label)
        else:
            unchanged.append(label)
    return LabelPlan(create=tuple(create), update=tuple(update), unchanged=tuple(unchanged), misaligned=tuple(misaligned))


def _case_variants(canonical_name: str, remote: Mapping[str, RemoteLabel]) -> tuple[str, ...]:
    """Remote label names that collide with ``canonical_name`` case-insensitively.

    An exact-name match is excluded (that is a match, handled by the caller). The
    collision set is exactly what ``gh label create`` rejects for a canonical name whose
    only near-equal is a case/spelling variant, so detecting it here replaces gh's
    cryptic "label already exists" with an explicit misalignment.
    """
    folded = canonical_name.casefold()
    return tuple(sorted(name for name in remote if name != canonical_name and name.casefold() == folded))


def label_misalignment_messages(plan: LabelPlan) -> tuple[str, ...]:
    """Explicit, maintainer-facing messages for each case/spelling misalignment.

    Each message names the repo's actual label(s) and the required canonical name so the
    maintainer can rename to align. Exact matching is preserved — the variant is never
    accepted or auto-renamed.
    """
    return tuple(
        f"label misalignment: repo has {', '.join(repr(variant) for variant in item.remote_variants)} "
        f"where the canonical taxonomy requires the exact name {item.canonical.name!r}; "
        f"rename it to align (a case/spelling variant is a misalignment, not a match)"
        for item in plan.misaligned
    )


def label_commands(plan: LabelPlan, repo: str) -> tuple[tuple[str, ...], ...]:
    """Pure: translate a plan into the exact ``gh`` argv lists to run, in order.

    Creates precede updates; ``unchanged`` labels emit no command. This is the owned
    mapping from a reconciliation plan to CLI invocations — provable with real data
    without touching the network.
    """
    commands: list[tuple[str, ...]] = []
    for label in plan.create:
        commands.append(("label", "create", label.name, "--repo", repo, "--color", label.color, "--description", label.description))
    for label in plan.update:
        commands.append(("label", "edit", label.name, "--repo", repo, "--color", label.color, "--description", label.description))
    return tuple(commands)


def _gh(args: Sequence[str]) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FATAL: gh {' '.join(args[:2])} failed: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def _fetch_remote_labels(repo: str) -> dict[str, RemoteLabel]:
    # High limit so the existing-label read is never truncated: a partial read would
    # plan a spurious create for a canonical label already present past the cutoff.
    # gh paginates internally up to --limit; no real repo approaches this many labels.
    raw = json.loads(_gh(["label", "list", "--repo", repo, "--limit", "5000", "--json", "name,color,description"]))
    assert isinstance(raw, list), "gh label list must return a JSON array"
    labels = [RemoteLabel.model_validate(entry) for entry in raw]
    return {label.name: label for label in labels}


def install_labels(repo: str, *, taxonomy: Path | None = None) -> None:
    """Create or update the canonical label taxonomy on a target repo.

    Idempotent: existing labels that already match are left alone; drifted labels are
    updated to match the taxonomy; missing labels are created. Any ``gh`` failure is
    fatal — a partial label set is not reported as success.

    Args:
        repo: GitHub repository in owner/name form.
        taxonomy: Optional path to a custom taxonomy JSON (defaults to the packaged set).
    """
    labels = load_taxonomy(taxonomy)
    plan = compute_label_actions(_fetch_remote_labels(repo), labels)
    if plan.misaligned:
        # A canonical label present only as a case/spelling variant cannot be created
        # (gh collides case-insensitively) and must not be silently accepted. Fail loud
        # with an explicit message rather than partially applying a doomed plan.
        for message in label_misalignment_messages(plan):
            print(f"FATAL: {message}", file=sys.stderr)
        sys.exit(1)
    for command in label_commands(plan, repo):
        _gh(command)
    print(f"{len(plan.create)} created, {len(plan.update)} updated, {len(plan.unchanged)} already current ({len(labels)} canonical labels).")
