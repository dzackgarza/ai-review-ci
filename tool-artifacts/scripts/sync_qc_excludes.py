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

import json
import sys
from pathlib import Path

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
    directories = cfg["directories"]
    assert isinstance(directories, list), "qc-excludes directories must be a list"
    result: list[str] = []
    for directory in directories:
        assert isinstance(directory, str), "qc-excludes directories must contain strings"
        result.append(directory)
    return result


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


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    config_path: Path | None = None
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    if args:
        config_path = Path(args[0])
    if config_path is None:
        config_path = find_config()
    else:
        config_path = config_path.resolve()

    qc_root = config_path.parent
    dirs = load_toml_dirs(config_path)

    print(f"QC root: {qc_root}")
    print(f"Canonical excludes ({len(dirs)}): {', '.join(dirs)}")

    if dry_run:
        print("\nDRY RUN — no files modified.\n")
        return

    print()
    for cfg in configs:
        fmt = cfg["format"]
        if fmt == "json":
            write_json_config(qc_root, cfg, dirs)
        elif fmt == "toml":
            write_toml_config(qc_root, cfg, dirs)

    print("\nDone.")


if __name__ == "__main__":
    main()
