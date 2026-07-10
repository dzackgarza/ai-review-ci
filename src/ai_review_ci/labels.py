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
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

LabelCategory = Literal["type", "scope", "status", "area"]
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
    """A label as ``gh label list`` reports it. Descriptions may be empty remotely."""

    name: str = Field(min_length=1)
    color: str = Field(pattern=_HEX_COLOR)
    description: str = ""


@dataclass(frozen=True)
class LabelPlan:
    create: tuple[Label, ...]
    update: tuple[Label, ...]
    unchanged: tuple[Label, ...]


def load_taxonomy(path: Path | None = None) -> tuple[Label, ...]:
    """Load and validate the canonical taxonomy.

    Reads the packaged ``data/labels.json`` by default, or a caller-supplied override.
    Malformed data fails loudly at the pydantic boundary.
    """
    text = path.read_text(encoding="utf-8") if path is not None else (files("ai_review_ci") / "data" / "labels.json").read_text(encoding="utf-8")
    return Taxonomy.model_validate_json(text).labels


def compute_label_actions(remote: Mapping[str, RemoteLabel], taxonomy: Sequence[Label]) -> LabelPlan:
    """Pure idempotent plan: which taxonomy labels to create, update, or leave.

    A label is *created* when absent remotely, *updated* when its color (compared
    case-insensitively) or description drifts from the taxonomy, and *unchanged*
    otherwise. Remote labels outside the taxonomy are left untouched — the taxonomy is
    additive, not a destructive sync.
    """
    create: list[Label] = []
    update: list[Label] = []
    unchanged: list[Label] = []
    for label in taxonomy:
        existing = remote.get(label.name)
        if existing is None:
            create.append(label)
        elif existing.color.lower() != label.color.lower() or existing.description != label.description:
            update.append(label)
        else:
            unchanged.append(label)
    return LabelPlan(create=tuple(create), update=tuple(update), unchanged=tuple(unchanged))


def _gh(args: list[str]) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FATAL: gh {' '.join(args[:2])} failed: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def _fetch_remote_labels(repo: str) -> dict[str, RemoteLabel]:
    raw = json.loads(_gh(["label", "list", "--repo", repo, "--limit", "200", "--json", "name,color,description"]))
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

    for label in plan.create:
        _gh(["label", "create", label.name, "--repo", repo, "--color", label.color, "--description", label.description])
        print(f"created  {label.name}")
    for label in plan.update:
        _gh(["label", "edit", label.name, "--repo", repo, "--color", label.color, "--description", label.description])
        print(f"updated  {label.name}")
    print(f"\n{len(plan.create)} created, {len(plan.update)} updated, {len(plan.unchanged)} already current ({len(labels)} canonical labels).")
