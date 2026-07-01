#!/usr/bin/env python3
"""Publish this repo's owned enforcement skills into a target skills hub.

ai-review-ci owns its integration-time enforcement skills; their source of truth is the
repo-local ``skills/<name>`` directory. This installs each ``[owned.*]`` skill declared in
``reviews/vendor/MANIFEST.toml`` into ``<target>/opencode/skills/<name>`` (e.g. ``~/ai``),
which is a downstream install target, not a source. Only owned skills publish — consumed
docs (vendored from an external upstream) and repo-local skills not in the manifest do not.
Re-running is a no-op when the target already matches. See ai-review-ci#163.
"""

from __future__ import annotations

import argparse
import tomllib
from pathlib import Path

SKILLS_SUBPATH = "opencode/skills"


def owned_source_paths(vendor_root: Path) -> dict[str, str]:
    manifest_path = vendor_root / "MANIFEST.toml"
    if not manifest_path.is_file():
        raise SystemExit(f"missing vendor manifest: {manifest_path}")
    owned = tomllib.loads(manifest_path.read_text()).get("owned")
    if not owned:
        raise SystemExit(f"no [owned.*] skills declared in {manifest_path}")
    return {name: spec["source_path"] for name, spec in owned.items()}


def publish_skill(source: Path, target_skills: Path, name: str) -> list[str]:
    written: list[str] = []
    for source_file in sorted(source.rglob("*.md")):
        relative = source_file.relative_to(source)
        source_text = source_file.read_text()
        target_file = target_skills / name / relative
        if target_file.exists() and target_file.read_text() == source_text:
            continue
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(source_text)
        written.append(str(Path(name) / relative))
    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skills-root", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True, help="skills hub checkout root, e.g. ~/ai")
    parser.add_argument("--vendor-root", type=Path, default=Path("reviews/vendor"))
    args = parser.parse_args()

    if not args.target.is_dir():
        raise SystemExit(f"target skills hub does not exist: {args.target}")
    repo_root = args.skills_root.resolve().parent
    target_skills = args.target / SKILLS_SUBPATH

    for name, source_path in sorted(owned_source_paths(args.vendor_root).items()):
        source = repo_root / source_path
        if not source.is_dir():
            raise SystemExit(f"missing owned skill source directory: {source}")
        for relative in publish_skill(source, target_skills, name):
            print(f"published {relative}")


if __name__ == "__main__":
    main()
