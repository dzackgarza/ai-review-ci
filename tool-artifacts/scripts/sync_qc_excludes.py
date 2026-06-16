#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "tomlkit>=0.13.2",
# ]
# ///
"""Sync qc-excludes.toml into structured tool config exclude arrays.

Each owned JSON/TOML exclude array gets the UNION of its own static entries
(preserved verbatim, first) and the canonical directory-exclusion list from
qc-excludes.toml (converted to the tool's glob format, appended).

Usage:
  uv run scripts/sync_qc_excludes.py
  uv run scripts/sync_qc_excludes.py /path/to/qc-excludes.toml
  uv run scripts/sync_qc_excludes.py --dry-run
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Never

import tomlkit

# ── Tool config descriptors ──────────────────────────────────────────────────
# Each entry describes how to update one config file.
#
#   path       : relative to QC root
#   format     : "json" or "toml"
#   key        : [key, ...] path to the exclude array (for json/toml)
#   is_dir_fn  : lambda(str) → glob pattern for a TOML directory entry
#   static     : list of entries preserved verbatim, emitted before TOML dirs
#
# The generated list is always: static + [is_dir_fn(d) for d in toml_dirs]

ToolConfig = dict

configs: list[ToolConfig] = [
    {
        "path": "biome.json",
        "format": "json",
        "key": ["files", "includes"],
        "is_dir_fn": lambda d: f"!**/{d}/**",
        "static": [
            "**",
            "!tsconfig.json",
            "!**/tsconfig.json",
        ],
    },
    {
        "path": "knip.json",
        "format": "json",
        "key": ["ignore"],
        "is_dir_fn": lambda d: f"**/{d}/**",
        "static": [
            "**/*.test.ts",
            "**/*.spec.ts",
            "**/__tests__/**",
            "**/env.d.ts",
            "**/*.tsx",
        ],
    },
    {
        "path": "jscpd.json",
        "format": "json",
        "key": ["ignore"],
        "is_dir_fn": lambda d: f"**/{d}/**",
        "static": [
            "**/*.test.ts",
            "**/*.spec.ts",
            "**/__tests__/**",
            "**/coverage.xml",
            "**/codeql-report.sarif",
        ],
    },
    {
        "path": "slop-scan.config.json",
        "format": "json",
        "key": ["ignores"],
        "is_dir_fn": lambda d: f"**/{d}/**",
        "static": [
            "**/*.generated.*",
            "**/*.min.*",
        ],
    },
    {
        "path": "pyright-local.json",
        "format": "json",
        "key": ["exclude"],
        "is_dir_fn": lambda d: f"**/{d}",
        "static": [],
    },
    {
        "path": "grain.toml",
        "format": "toml",
        "key": ["grain", "exclude"],
        "is_dir_fn": lambda d: f"{d}/*",
        "static": [
            "tests/*",
            "*_test.py",
            "test_*.py",
            "*.sage.py",
            "src/external/**",
            "src/backends/external/**",
            "theory/literature/**",
            "theory/references/literature/**",
        ],
    },
]


def find_config() -> Path:
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        candidate = parent / "qc-excludes.toml"
        if candidate.is_file():
            return candidate.resolve()
    print("ERROR: qc-excludes.toml not found in any ancestor directory.", file=sys.stderr)
    sys.exit(1)


def load_toml_dirs(config: Path) -> list[str]:
    import tomllib

    with config.open("rb") as data:
        cfg = tomllib.load(data)
    directories: object = cfg.get("directories")
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


def _build_entries(cfg: ToolConfig, dirs: list[str]) -> list[str]:
    """Build the full exclude list for one tool: static + TOML-derived."""
    result = list(cfg["static"])
    fn = cfg["is_dir_fn"]
    for d in dirs:
        result.append(fn(d))
    return result


def write_json_config(qc_root: Path, cfg: ToolConfig, dirs: list[str]) -> None:
    path = qc_root / cfg["path"]
    with path.open("rb") as f:
        data = json.load(f)

    entries = _build_entries(cfg, dirs)

    parent = data
    for k in cfg["key"][:-1]:
        parent = parent[k]
    last_key = cfg["key"][-1]

    if parent[last_key] == entries:
        print(f"  No change: {cfg['path']}")
        return

    parent[last_key] = entries
    with path.open("w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print(f"  Updated {cfg['path']} ({len(entries)} entries)")


def write_toml_config(qc_root: Path, cfg: ToolConfig, dirs: list[str]) -> None:
    path = qc_root / cfg["path"]
    entries = _build_entries(cfg, dirs)
    document = tomlkit.parse(path.read_text())

    parent = document
    for key in cfg["key"][:-1]:
        parent = parent[key]
    last_key = cfg["key"][-1]

    if list(parent[last_key]) == entries:
        print(f"  No change: {cfg['path']}")
        return

    exclude = tomlkit.array()
    exclude.multiline(True)
    for entry in entries:
        exclude.append(entry)
    parent[last_key] = exclude
    path.write_text(tomlkit.dumps(document))
    print(f"  Updated {cfg['path']} ({len(entries)} entries)")


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        print(f"ERROR: {message}", file=sys.stderr)
        sys.exit(1)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = _ArgumentParser(add_help=False)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("config_paths", nargs="*")
    args, unknown = parser.parse_known_args(argv)
    if unknown:
        print(f"ERROR: unknown flag {unknown[0]}", file=sys.stderr)
        sys.exit(1)
    return args


def _resolve_config_path(config_paths: list[str]) -> Path:
    if not config_paths:
        return find_config()
    return Path(config_paths[0]).resolve()


def _print_sync_status(qc_root: Path, dirs: list[str]) -> None:
    print(f"QC root: {qc_root}")
    print(f"Canonical excludes ({len(dirs)}): {', '.join(dirs)}")


def _print_dry_run_status() -> None:
    print("\nDRY RUN — no files modified.\n")


_CONFIG_WRITERS = {
    "json": write_json_config,
    "toml": write_toml_config,
}


def _write_tool_config(qc_root: Path, cfg: ToolConfig, dirs: list[str]) -> None:
    writer = _CONFIG_WRITERS.get(cfg["format"])
    if writer is None:
        print(f"ERROR: unknown config format {cfg['format']}", file=sys.stderr)
        sys.exit(1)
    writer(qc_root, cfg, dirs)


def _write_all_configs(qc_root: Path, dirs: list[str]) -> None:
    print()
    for cfg in configs:
        _write_tool_config(qc_root, cfg, dirs)
    print("\nDone.")


def main() -> None:
    args = _parse_args(sys.argv[1:])
    config_path = _resolve_config_path(args.config_paths)
    qc_root = config_path.parent
    dirs = load_toml_dirs(config_path)
    _print_sync_status(qc_root, dirs)
    if args.dry_run:
        _print_dry_run_status()
        return
    _write_all_configs(qc_root, dirs)


if __name__ == "__main__":
    main()
