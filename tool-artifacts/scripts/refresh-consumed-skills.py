#!/usr/bin/env python3
"""Refresh vendored copies of consumed advisory skills from their upstream checkout.

Consumed docs (see reviews/vendor/MANIFEST.toml [consumed.*]) are pre-/during-writing
advisory guidance that ~/ai owns; this repo only vendors them so the reviewer prompt can
inline them. This pulls each one from a local checkout of its upstream at a chosen ref
(`git show <ref>:<upstream_path>`), so the refresh is reproducible and pinned rather than a
hand-copy. It never touches [owned.*] skills (those are authored here). See ai-review-ci#163.

All [consumed.*] entries must share one upstream_repo per run; pass that repo's checkout as
--source and run once per upstream if they ever differ.
"""

from __future__ import annotations

import argparse
import subprocess
import tomllib
from pathlib import Path


def load_consumed(vendor_root: Path) -> dict[str, dict[str, str]]:
    manifest_path = vendor_root / "MANIFEST.toml"
    if not manifest_path.is_file():
        raise SystemExit(f"missing vendor manifest: {manifest_path}")
    consumed = tomllib.loads(manifest_path.read_text()).get("consumed")
    if not consumed:
        raise SystemExit(f"no [consumed.*] docs declared in {manifest_path}")
    return {name: dict(spec) for name, spec in consumed.items()}


def git_output(source: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(source), *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} in {source} failed: {result.stderr.strip()}")
    return result.stdout


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True, help="checkout of the upstream repo, e.g. ~/ai")
    parser.add_argument("--ref", default="HEAD", help="upstream ref to pin the refresh to (default HEAD)")
    parser.add_argument("--vendor-root", type=Path, default=Path("reviews/vendor"))
    args = parser.parse_args()

    if not (args.source / ".git").exists():
        raise SystemExit(f"--source is not a git checkout: {args.source}")

    resolved = git_output(args.source, "rev-parse", args.ref).strip()
    changed: list[str] = []
    for name, spec in sorted(load_consumed(args.vendor_root).items()):
        upstream_text = git_output(args.source, "show", f"{args.ref}:{spec['upstream_path']}")
        target = args.vendor_root / spec["vendor_path"]
        if target.exists() and target.read_text() == upstream_text:
            continue
        target.write_text(upstream_text)
        changed.append(f"{name} <- {spec['upstream_repo']} {resolved[:12]}:{spec['upstream_path']}")

    if not changed:
        print(f"consumed docs already current with {args.source} @ {resolved[:12]}")
        return
    for line in changed:
        print(f"refreshed {line}")


if __name__ == "__main__":
    main()
