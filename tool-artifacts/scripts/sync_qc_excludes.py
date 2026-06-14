#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Sync qc-excludes.toml into each tool config file.

Each tool config gets the UNION of its own static entries (preserved
verbatim, first) and the canonical directory-exclusion list from
qc-excludes.toml (converted to the tool's glob format, appended).

Usage:
  uv run scripts/sync_qc_excludes.py
  uv run scripts/sync_qc_excludes.py /path/to/qc-excludes.toml
  uv run scripts/sync_qc_excludes.py --dry-run
"""

import json
import sys
from pathlib import Path

# ── Tool config descriptors ──────────────────────────────────────────────────
# Each entry describes how to update one config file.
#
#   path       : relative to QC root
#   format     : "json", "toml", or "eslint"
#   key        : [key, ...] path to the exclude array (for json/toml)
#   is_dir_fn  : lambda(str) → glob pattern for a TOML directory entry
#   static     : list of entries preserved verbatim, emitted before TOML dirs
#
# The generated list is always: static + [is_dir_fn(d) for d in toml_dirs]

ToolConfig = dict

configs: list[ToolConfig] = [
    {
        "path": "eslint.config.js",
        "format": "eslint",
        "is_dir_fn": lambda d: f"**/{d}/**",
        "static": [
            "**/env.d.ts",
        ],
    },
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


def write_eslint_config(qc_root: Path, cfg: ToolConfig, dirs: list[str]) -> None:
    path = qc_root / cfg["path"]
    entries = _build_entries(cfg, dirs)
    ignore_lines = "\n".join(f'      "{entry}",' for entry in entries)
    new_text = f"/** @type {{import('eslint').Linter.FlatConfig[]}} */\nexport default [\n  {{\n    ignores: [\n{ignore_lines}\n    ],\n  }},\n];\n"
    if new_text == path.read_text():
        print(f"  No change: {cfg['path']}")
        return
    path.write_text(new_text)
    print(f"  Updated {cfg['path']} ({len(entries)} entries)")


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
    entry_lines = "\n".join(f'  "{entry}",' for entry in entries)
    new_text = f'[grain]\nfail-under = 0.0\nmin-tokens = 50\nsimilarity = 0.8\nlanguages = ["python"]\nexclude = [\n{entry_lines}\n]\n'
    if new_text == path.read_text():
        print(f"  No change: {cfg['path']}")
        return
    path.write_text(new_text)
    print(f"  Updated {cfg['path']} ({len(entries)} entries)")


def write_rust_qc_files(repo_root: Path, dirs: list[str]) -> None:
    path = repo_root / "justfiles" / "rust.just"
    not_paths = " ".join(f"-not -path '*/{d}/*'" for d in dirs)
    new_text = (
        "# justfile-rust — Rust-specific quality control\n"
        "\n"
        'infra := justfile_directory() / ".."\n'
        'configs := infra / "tool-configs"\n'
        'artifacts := infra / "tool-artifacts"\n'
        "\n"
        "_rust-qc-files:\n"
        "\t#!/usr/bin/env bash\n"
        "\tset -euo pipefail\n"
        f"\tfind . -name '*.rs' {not_paths}\n"
        "\n"
        "test: _rust-qc-files\n"
        "\t#!/usr/bin/env bash\n"
        "\tset -euo pipefail\n"
        "\tmapfile -t rust_files < <(just --justfile {{justfile()}} -d . _rust-qc-files)\n"
        '\tif [ "${#rust_files[@]}" -eq 0 ]; then\n'
        '\t\techo "ERROR: Rust QC: no Rust files found."\n'
        "\t\texit 1\n"
        "\tfi\n"
        "\tcargo fmt --check\n"
        "\tcargo clippy --all-targets --all-features -- -D warnings\n"
        "\tcargo test --all-targets --all-features\n"
    )
    if new_text == path.read_text():
        print("  No change: justfiles/rust.just")
        return
    path.write_text(new_text)
    print(f"  Updated _rust-qc-files in justfiles/rust.just ({len(dirs)} entries)")


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
    repo_root = qc_root.parent
    dirs = load_toml_dirs(config_path)

    print(f"QC root: {qc_root}")
    print(f"Canonical excludes ({len(dirs)}): {', '.join(dirs)}")

    if dry_run:
        print("\nDRY RUN — no files modified.\n")
        return

    print()
    for cfg in configs:
        fmt = cfg["format"]
        if fmt == "eslint":
            write_eslint_config(qc_root, cfg, dirs)
        elif fmt == "json":
            write_json_config(qc_root, cfg, dirs)
        elif fmt == "toml":
            write_toml_config(qc_root, cfg, dirs)

    write_rust_qc_files(repo_root, dirs)
    print("\nDone.")


if __name__ == "__main__":
    main()
