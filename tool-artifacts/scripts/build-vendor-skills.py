#!/usr/bin/env python3
"""Build vendored copies of this repo's owned enforcement skills.

ai-review-ci owns its enforcement skills (QC applied at integration time). Their source
of truth is the repo-local ``skills/<name>`` directory; the copy under ``reviews/vendor``
is a build artifact the reviewer prompt and QC code read. ``reviews/vendor/MANIFEST.toml``
classifies every vendored entry: this script rebuilds the ``[owned.*]`` ones from their
``skills/`` source and never touches ``[consumed.*]`` ones (those are vendored from an
external upstream, not authored here). See ai-review-ci#163.

Each owned skill declares a ``vendor_layout``:
  nested — reviews/vendor/<name>/{SKILL.md,references/...} + a VENDOR.toml sha256 manifest
           (read at runtime by src/ai_review_ci/policy_index.py).
  flat   — reviews/vendor/<name>.md (from SKILL.md) plus, if the skill ships references,
           reviews/vendor/<name>-references/ (from references/).
The layout mirrors how each skill was already vendored so the reviewer bundle
(reviews/*/manifest.txt) and doc links stay stable.
"""

from __future__ import annotations

import argparse
import hashlib
import tomllib
from pathlib import Path
from typing import cast

OWNER_REPO = "dzackgarza/ai-review-ci"


def load_owned(vendor_root: Path) -> dict[str, dict[str, str]]:
    manifest_path = vendor_root / "MANIFEST.toml"
    if not manifest_path.is_file():
        raise SystemExit(f"missing vendor manifest: {manifest_path}")
    manifest = tomllib.loads(manifest_path.read_text())
    owned = manifest.get("owned")
    if not owned:
        raise SystemExit(f"no [owned.*] skills declared in {manifest_path}")
    return cast(dict[str, dict[str, str]], owned)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def skill_markdown_files(skill_source: Path) -> list[Path]:
    files = sorted(path for path in skill_source.rglob("*.md"))
    if not files:
        raise SystemExit(f"owned skill source has no markdown files: {skill_source}")
    return files


def write_nested_manifest(vendor_skill: Path, source_path: str, hashes: dict[str, str]) -> None:
    lines = [
        "[source]",
        f'repo = "{OWNER_REPO}"',
        f'source_path = "{source_path}"',
        'ownership = "owned"',
        "",
        "[build]",
        'command = "just vendor-owned-skills"',
        'mode = "copy from local skills/ source, sha256-pinned"',
        "",
        "[copied_files]",
    ]
    for relative_path, digest in sorted(hashes.items()):
        lines.extend(
            [
                f'  [copied_files."{relative_path}"]',
                f'  sha256 = "{digest}"',
            ]
        )
    (vendor_skill / "VENDOR.toml").write_text("\n".join(lines) + "\n")


def build_nested(skill_source: Path, vendor_root: Path, name: str, source_path: str) -> None:
    vendor_skill = vendor_root / name
    hashes: dict[str, str] = {}
    for source_file in skill_markdown_files(skill_source):
        relative = source_file.relative_to(skill_source)
        text = source_file.read_text()
        target = vendor_skill / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        hashes[str(relative)] = sha256_text(text)
    write_nested_manifest(vendor_skill, source_path, hashes)


def build_flat(skill_source: Path, vendor_root: Path, name: str) -> None:
    skill_file = skill_source / "SKILL.md"
    if not skill_file.is_file():
        raise SystemExit(f"flat owned skill missing SKILL.md: {skill_file}")
    (vendor_root / f"{name}.md").write_text(skill_file.read_text())

    references = skill_source / "references"
    if references.is_dir():
        for source_file in sorted(references.rglob("*.md")):
            relative = source_file.relative_to(references)
            target = vendor_root / f"{name}-references" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source_file.read_text())


def build_skill(repo_root: Path, vendor_root: Path, name: str, spec: dict[str, str]) -> None:
    source_path = spec["source_path"]
    layout = spec["vendor_layout"]
    skill_source = repo_root / source_path
    if not skill_source.is_dir():
        raise SystemExit(f"missing owned skill source directory: {skill_source}")
    if layout == "nested":
        build_nested(skill_source, vendor_root, name, source_path)
    elif layout == "flat":
        build_flat(skill_source, vendor_root, name)
    else:
        raise SystemExit(f"unknown vendor_layout {layout!r} for owned skill {name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skills-root", type=Path, required=True)
    parser.add_argument("--vendor-root", type=Path, required=True)
    args = parser.parse_args()

    repo_root = args.skills_root.resolve().parent
    for name, spec in sorted(load_owned(args.vendor_root).items()):
        build_skill(repo_root, args.vendor_root, name, spec)


if __name__ == "__main__":
    main()
