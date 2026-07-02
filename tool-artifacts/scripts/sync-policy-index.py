#!/usr/bin/env python3
"""Sync the vendored policy index from this repo's canonical skills/policy-index."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path

SOURCE_FILES = (
    "skills/policy-index/SKILL.md",
    "skills/policy-index/references/policies.md",
    "skills/policy-index/references/remediations.md",
    "skills/policy-index/references/red-flags.md",
    "skills/policy-index/references/runtime-control-flow.md",
    "skills/policy-index/references/test-proof-rules.md",
)


def git_text(source_root: Path, ref: str, source_path: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(source_root), "show", f"{ref}:{source_path}"],
        text=True,
    )


def git_output(source_root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(source_root), *args], text=True).strip()


def destination_path(vendor_root: Path, source_path: str) -> Path:
    relative = source_path.removeprefix("skills/policy-index/")
    return vendor_root / relative


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def write_manifest(vendor_root: Path, source_root: Path, ref: str, hashes: dict[str, str]) -> None:
    status = git_output(source_root, "status", "--porcelain")
    lines = [
        "[source]",
        'repo = "dzackgarza/ai-review-ci"',
        f'ref = "{ref}"',
        'source_path = "skills/policy-index"',
        f"source_worktree_dirty = {str(bool(status)).lower()}",
        "",
        "[sync]",
        'command = "just sync-policy-index"',
        'mode = "git show <ref>:<source_path>, never dirty worktree copy"',
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
    (vendor_root / "VENDOR.toml").write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--vendor-root", type=Path, required=True)
    parser.add_argument("--ref", required=True)
    args = parser.parse_args()

    args.vendor_root.mkdir(parents=True, exist_ok=True)
    (args.vendor_root / "references").mkdir(exist_ok=True)

    hashes: dict[str, str] = {}
    for source_path in SOURCE_FILES:
        text = git_text(args.source_root, args.ref, source_path)
        target = destination_path(args.vendor_root, source_path)
        target.write_text(text)
        hashes[str(target.relative_to(args.vendor_root))] = sha256_text(text)
    write_manifest(args.vendor_root, args.source_root, args.ref, hashes)


if __name__ == "__main__":
    main()
