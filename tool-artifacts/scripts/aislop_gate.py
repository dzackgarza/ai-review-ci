#!/usr/bin/env python3
"""Gate aislop diagnostics, optionally against a PR base revision."""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from typing import Any


def _relative_path(path_value: str, root: Path) -> str:
    path = Path(path_value)
    if not path.is_absolute():
        return path_value
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path_value


def _normalized_diagnostics(payload: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    diagnostics = payload.get("diagnostics", [])
    if not isinstance(diagnostics, list):
        return []
    normalized = []
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict):
            continue
        item = dict(diagnostic)
        path_value = item.get("filePath")
        if isinstance(path_value, str):
            item["filePath"] = _relative_path(path_value, root)
        normalized.append(item)
    return normalized


def _signature(diagnostic: dict[str, Any]) -> str:
    # Line numbers are intentionally excluded: inherited findings should not
    # become new PR failures merely because unrelated edits shifted a file.
    return "\0".join(
        [
            str(diagnostic.get("rule", "")),
            str(diagnostic.get("filePath", "")),
            str(diagnostic.get("message", "")).strip(),
        ]
    )


def _signatures(diagnostics: list[dict[str, Any]]) -> collections.Counter[str]:
    return collections.Counter(_signature(diagnostic) for diagnostic in diagnostics)


def _errors(diagnostics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [diagnostic for diagnostic in diagnostics if diagnostic.get("severity") == "error"]


def _warnings(diagnostics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [diagnostic for diagnostic in diagnostics if diagnostic.get("severity") == "warning"]


def _print_diagnostic(diagnostic: dict[str, Any]) -> None:
    print(
        "  {file}:{line} [{rule}] {message}".format(
            file=diagnostic.get("filePath", ""),
            line=diagnostic.get("line", ""),
            rule=diagnostic.get("rule", ""),
            message=diagnostic.get("message", ""),
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--head-json", type=Path, required=True)
    parser.add_argument("--head-root", type=Path, required=True)
    parser.add_argument("--base-json", type=Path)
    parser.add_argument("--base-root", type=Path)
    args = parser.parse_args()

    head_payload = json.loads(args.head_json.read_text())
    head_diagnostics = _normalized_diagnostics(head_payload, args.head_root)
    head_warnings = _warnings(head_diagnostics)
    if head_warnings:
        print(f"aislop: {len(head_warnings)} warning-tier finding(s) surfaced (advisory, not blocking):")
        for diagnostic in head_warnings:
            _print_diagnostic(diagnostic)

    if args.base_json is not None:
        if args.base_root is None:
            parser.error("--base-root is required with --base-json")
        base_payload = json.loads(args.base_json.read_text())
        base_diagnostics = _normalized_diagnostics(base_payload, args.base_root)
        new_signatures = _signatures(_errors(head_diagnostics)) - _signatures(_errors(base_diagnostics))
        new_errors = [
            diagnostic
            for diagnostic in _errors(head_diagnostics)
            if new_signatures[_signature(diagnostic)] > 0
        ]
        if not new_errors:
            print("aislop: error findings are unchanged relative to DIFF_COVER_BASE.")
            return 0
        for diagnostic in new_errors:
            _print_diagnostic(diagnostic)
        print("")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print(f"  ERROR: aislop found {len(new_errors)} new error-severity finding(s) relative to DIFF_COVER_BASE.")
        print("  Fix the project code.")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        return 1

    head_errors = _errors(head_diagnostics)
    if not head_errors:
        print("aislop: 0 error-severity findings — clean.")
        return 0
    for diagnostic in head_errors:
        _print_diagnostic(diagnostic)
    print("")
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print(f"  ERROR: aislop found {len(head_errors)} error-severity finding(s) in PROJECT CODE.")
    print("  Fix the project code.")
    print("")
    print("  PROBING GLOBAL QC IS REWARD-HACKING.")
    print("  Do NOT weaken the aislop config, add .aislopignore entries, or edit")
    print("  QC tooling in ~/ai-review-ci/ to suppress these findings.")
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
