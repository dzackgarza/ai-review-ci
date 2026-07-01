#!/usr/bin/env python3
"""Build vendored copies of owned enforcement skills from the local ``skills/`` source.

ai-review-ci owns its enforcement skills (QC applied at integration time). Their
source of truth is the repo-local ``skills/<name>`` directory; the copy under
``reviews/vendor/<name>`` is a build artifact the reviewer prompt and QC code read.
This replaces the old ``sync-policy-index`` step, which pulled the content the wrong
way (from ``dzackgarza/ai``). See ai-review-ci#163.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

OWNER_REPO = "dzackgarza/ai-review-ci"


def owned_skill_names(skills_root: Path) -> list[str]:
    """Owned skills are exactly the directories under ``skills/`` — no separate list."""
    names = sorted(path.name for path in skills_root.iterdir() if path.is_dir())
    if not names:
        raise SystemExit(f"no owned skills found under {skills_root}")
    return names


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def skill_markdown_files(skill_source: Path) -> list[Path]:
    files = sorted(path for path in skill_source.rglob("*.md"))
    if not files:
        raise SystemExit(f"owned skill source has no markdown files: {skill_source}")
    return files


def write_manifest(vendor_skill: Path, source_path: str, hashes: dict[str, str]) -> None:
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


def build_skill(skills_root: Path, vendor_root: Path, name: str) -> None:
    skill_source = skills_root / name
    if not skill_source.is_dir():
        raise SystemExit(f"missing owned skill source directory: {skill_source}")
    vendor_skill = vendor_root / name

    hashes: dict[str, str] = {}
    for source_file in skill_markdown_files(skill_source):
        relative = source_file.relative_to(skill_source)
        text = source_file.read_text()
        target = vendor_skill / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        hashes[str(relative)] = sha256_text(text)
    write_manifest(vendor_skill, f"{skills_root.name}/{name}", hashes)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skills-root", type=Path, required=True)
    parser.add_argument("--vendor-root", type=Path, required=True)
    args = parser.parse_args()

    for name in owned_skill_names(args.skills_root):
        build_skill(args.skills_root, args.vendor_root, name)


if __name__ == "__main__":
    main()
