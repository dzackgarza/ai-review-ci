#!/usr/bin/env python3
"""Compare Semgrep JSON output and fail only on new finding signatures."""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from typing import Any


def _result_signature(result: dict[str, Any]) -> str:
    extra = result.get("extra") if isinstance(result.get("extra"), dict) else {}
    lines = str(extra.get("lines", "")).strip()
    message = str(extra.get("message", "")).strip()
    return "\0".join(
        [
            str(result.get("check_id", "")),
            str(result.get("path", "")),
            message,
            lines,
        ]
    )


def finding_signatures(path: Path) -> collections.Counter[str]:
    """Return comparable finding signatures from Semgrep JSON output."""
    if not path.exists() or path.stat().st_size == 0:
        return collections.Counter()
    payload = json.loads(path.read_text())
    results = payload.get("results", [])
    if not isinstance(results, list):
        return collections.Counter()
    signatures: collections.Counter[str] = collections.Counter()
    for result in results:
        if isinstance(result, dict):
            signatures[_result_signature(result)] += 1
    return signatures


def _display_signature(signature: str) -> str:
    check_id, path, message, lines = signature.split("\0", 3)
    detail = lines if lines else message
    if detail:
        return f"{path}: {check_id}: {detail}"
    return f"{path}: {check_id}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-json", type=Path, required=True)
    parser.add_argument("--head-json", type=Path, required=True)
    args = parser.parse_args()

    base = finding_signatures(args.base_json)
    head = finding_signatures(args.head_json)
    new_findings = head - base
    if not new_findings:
        print("semgrep: findings are unchanged relative to DIFF_COVER_BASE.")
        return 0

    print("ERROR: semgrep found new findings relative to DIFF_COVER_BASE:")
    for signature, count in sorted(new_findings.items()):
        suffix = f" x{count}" if count > 1 else ""
        print(f"  {_display_signature(signature)}{suffix}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
