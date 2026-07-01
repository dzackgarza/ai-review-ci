#!/usr/bin/env python3
"""Publish ai-review-ci's owned enforcement skills into a target skills hub.

ai-review-ci owns its integration-time enforcement skills; their source of truth is the
repo-local ``skills/<name>`` directory. This installs each owned skill into
``<target>/opencode/skills/<name>`` (e.g. ``~/ai``), which is a downstream install target,
not a source. Re-running is a no-op when the target already matches. See ai-review-ci#163.
"""

from __future__ import annotations

import argparse
from pathlib import Path

SKILLS_SUBPATH = "opencode/skills"


def owned_skill_names(skills_root: Path) -> list[str]:
    """Owned skills are exactly the directories under ``skills/`` — no separate list."""
    names = sorted(path.name for path in skills_root.iterdir() if path.is_dir())
    if not names:
        raise SystemExit(f"no owned skills found under {skills_root}")
    return names


def publish_skill(skills_root: Path, target_skills: Path, name: str) -> list[str]:
    source = skills_root / name
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
    args = parser.parse_args()

    if not args.target.is_dir():
        raise SystemExit(f"target skills hub does not exist: {args.target}")
    target_skills = args.target / SKILLS_SUBPATH

    for name in owned_skill_names(args.skills_root):
        written = publish_skill(args.skills_root, target_skills, name)
        for relative in written:
            print(f"published {relative}")


if __name__ == "__main__":
    main()
