#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Print the aislop score gate (ci.failBelow) declared by a scanned project.

Usage:
  read_aislop_failbelow.py [DIR]   # DIR defaults to CWD

Looks for DIR/.aislop/config.yml (then .yaml). Prints the integer ci.failBelow
when the project has opted into the score tier; prints nothing (exit 0) when
there is no config or no failBelow key, so the shared _aislop gate stays
error-only for repos that have not opted in. A malformed config or a
non-integer failBelow is a QC-tooling failure and exits non-zero.
"""

import sys
from pathlib import Path

import yaml


def read_failbelow(project_dir: Path) -> int | None:
    config_path = next(
        (p for name in ("config.yml", "config.yaml") if (p := project_dir / ".aislop" / name).is_file()),
        None,
    )
    if config_path is None:
        return None
    data = yaml.safe_load(config_path.read_text())
    if data is None:
        return None
    if not isinstance(data, dict):
        print(f"ERROR: {config_path} must be a YAML mapping", file=sys.stderr)
        sys.exit(1)
    ci = data.get("ci")
    if ci is None:
        return None
    if not isinstance(ci, dict):
        print(f"ERROR: {config_path} 'ci' must be a mapping", file=sys.stderr)
        sys.exit(1)
    fail_below: object = ci.get("failBelow")
    if fail_below is None:
        return None
    if isinstance(fail_below, bool) or not isinstance(fail_below, int):
        print(f"ERROR: {config_path} ci.failBelow must be an integer", file=sys.stderr)
        sys.exit(1)
    return fail_below


def main() -> None:
    if len(sys.argv) > 2:
        print("ERROR: expected at most one directory argument", file=sys.stderr)
        sys.exit(1)
    project_dir = Path(sys.argv[1] if len(sys.argv) == 2 else ".")
    fail_below = read_failbelow(project_dir)
    if fail_below is not None:
        print(fail_below)


if __name__ == "__main__":
    main()
