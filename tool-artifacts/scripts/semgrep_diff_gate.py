#!/usr/bin/env python3
"""Compare Semgrep JSON output and fail only on new ERROR finding signatures."""

from __future__ import annotations

import argparse
import collections
from collections.abc import Mapping
from pathlib import Path


from semgrep_report import load_report


def _string(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Semgrep signature fields must be strings")
    return value


def _result_signature(result: Mapping[str, object]) -> str:
    extra = result["extra"]
    if not isinstance(extra, dict):
        raise ValueError("Semgrep finding metadata must be an object")
    lines = _string(extra["lines"]).strip()
    message = _string(extra["message"]).strip()
    return "\0".join(
        [
            _string(result["check_id"]),
            _string(result["path"]),
            message,
            lines,
        ]
    )


def finding_signatures(path: Path) -> collections.Counter[str]:
    """Return comparable finding signatures from Semgrep JSON output."""
    payload = load_report(path)
    results = payload["results"]
    if not isinstance(results, list):
        raise ValueError("Semgrep results must be a list")
    signatures: collections.Counter[str] = collections.Counter()
    for result in results:
        if not isinstance(result, dict):
            raise ValueError("Semgrep finding must be an object")
        severity = result["extra"]["severity"]
        if severity not in ("ERROR", "WARNING", "INFO"):
            raise ValueError(f"unknown Semgrep finding severity: {severity}")
        if severity == "ERROR":
            signatures[_result_signature(result)] += 1
        else:
            print(f"semgrep review tripwire ({severity}): {_display_signature(_result_signature(result))}")
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
