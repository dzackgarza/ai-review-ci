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


# Semgrep emits a result per scanned file for a rule it could not evaluate, carrying
# this text instead of a match. Rust is a Pro-engine language, so the shipped rs-* rules
# degrade this way whenever no SEMGREP_APP_TOKEN is present. The placeholder says
# nothing about the file it names, and with --scan-unknown-extensions it lands on every
# new .envrc/.service/.toml — which made any PR adding files fail the gate (#366).
UNEVALUATED_MARKER = "requires login"


def _is_unevaluated(result: dict[str, Any]) -> bool:
    extra = result.get("extra") if isinstance(result.get("extra"), dict) else {}
    message = str(extra.get("message", "")).strip()
    lines = str(extra.get("lines", "")).strip()
    return UNEVALUATED_MARKER in message or UNEVALUATED_MARKER in lines


def finding_signatures(path: Path) -> tuple[collections.Counter[str], set[str]]:
    """Return comparable finding signatures, plus the rules that could not be evaluated."""
    if not path.exists() or path.stat().st_size == 0:
        return collections.Counter(), set()
    payload = json.loads(path.read_text())
    results = payload.get("results", [])
    if not isinstance(results, list):
        return collections.Counter(), set()
    signatures: collections.Counter[str] = collections.Counter()
    unevaluated: set[str] = set()
    for result in results:
        if not isinstance(result, dict):
            continue
        if _is_unevaluated(result):
            unevaluated.add(str(result.get("check_id", "")))
            continue
        signatures[_result_signature(result)] += 1
    return signatures, unevaluated


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

    base, _ = finding_signatures(args.base_json)
    head, unevaluated = finding_signatures(args.head_json)

    # Surfaced rather than dropped: these rules did not run, so the scan is incomplete
    # for the languages they cover. That is real coverage debt, but it is not a finding
    # about the diff, so it reports without blocking.
    if unevaluated:
        print("semgrep: rules not evaluated in this run (no Pro engine available):")
        for check_id in sorted(unevaluated):
            print(f"  {check_id}")

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
