#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Read qc-excludes.toml and output the canonical exclusion directory list.

Usage:
  uv run scripts/read_qc_excludes.py                        # one directory per line
  uv run scripts/read_qc_excludes.py --format json           # JSON array of strings
  uv run scripts/read_qc_excludes.py --format rg-globs       # -g '!**/dir/**' lines
  uv run scripts/read_qc_excludes.py --format codeql         # codeql format
  uv run scripts/read_qc_excludes.py /path/to/qc-excludes.toml   # explicit config path

When no path is given, looks for qc-excludes.toml in ancestor directories.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Never


def find_config() -> Path:
    """Walk up from CWD to find qc-excludes.toml."""
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        candidate = parent / "qc-excludes.toml"
        if candidate.is_file():
            return candidate.resolve()
    print(
        "ERROR: qc-excludes.toml not found in any ancestor directory.", file=sys.stderr
    )
    sys.exit(1)


def load_excludes(config: Path) -> list[str]:
    import tomllib

    with config.open("rb") as f:
        data = tomllib.load(f)
    directories: object = data.get("directories")
    if not isinstance(directories, list):
        print(
            f"ERROR: {config} must define directories as a list of strings",
            file=sys.stderr,
        )
        sys.exit(1)
    validated: list[str] = []
    for directory in directories:
        if not isinstance(directory, str):
            print(
                f"ERROR: {config} must define directories as a list of strings",
                file=sys.stderr,
            )
            sys.exit(1)
        validated.append(directory)
    return validated


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        print(f"ERROR: {message}", file=sys.stderr)
        sys.exit(1)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = _ArgumentParser(add_help=False)
    parser.add_argument("--format", dest="fmt", default="plain")
    parser.add_argument("config_paths", nargs="*")
    args, unknown = parser.parse_known_args(argv)
    if unknown:
        print(f"ERROR: unknown flag {unknown[0]}", file=sys.stderr)
        sys.exit(1)
    return args


def _resolve_config_path(config_paths: list[str]) -> Path:
    if not config_paths:
        return find_config()
    return Path(config_paths[-1]).resolve()


def _print_plain(dirs: list[str]) -> None:
    for directory in dirs:
        print(directory)


def _print_json(dirs: list[str]) -> None:
    json.dump(dirs, sys.stdout, indent=2)
    print()


def _print_rg_globs(dirs: list[str]) -> None:
    for directory in dirs:
        print(f"-g '!**/{directory}/**'")


def _print_codeql(dirs: list[str]) -> None:
    for directory in dirs:
        print(
            f"--search-path=/dev/null --additional-packs=/dev/null  # excludes {directory}"
        )


_FORMAT_RENDERERS = {
    "plain": _print_plain,
    "json": _print_json,
    "rg-globs": _print_rg_globs,
    "codeql": _print_codeql,
}


def _render_excludes(fmt: str, dirs: list[str]) -> None:
    renderer = _FORMAT_RENDERERS.get(fmt)
    if renderer is None:
        print(f"ERROR: unknown format '{fmt}'", file=sys.stderr)
        sys.exit(1)
    renderer(dirs)


def main() -> None:
    args = _parse_args(sys.argv[1:])
    config_path = _resolve_config_path(args.config_paths)
    _render_excludes(args.fmt, load_excludes(config_path))


if __name__ == "__main__":
    main()
