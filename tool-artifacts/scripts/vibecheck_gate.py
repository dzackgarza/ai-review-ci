#!/usr/bin/env python3
"""Gate vibecheck JSON findings, optionally against a PR base revision."""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from typing import Any


def _relative_path(path_value: str, root: Path) -> str:
    path = Path(path_value)
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path_value


def _is_comment_line(content: str | None) -> bool:
    trimmed = (content or "").strip()
    return trimmed.startswith(("//", "#", "/*", "*", "<!--"))


def _has_non_empty_except_handler(finding: dict[str, Any]) -> bool:
    if finding.get("rule_id") != "G22":
        return False
    path_value = finding.get("file")
    line_value = finding.get("line")
    if not path_value or not isinstance(line_value, int):
        return False
    path = Path(path_value)
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return False
    if line_value < 1 or line_value > len(lines):
        return False
    except_line = lines[line_value - 1]
    except_indent = len(except_line) - len(except_line.lstrip())
    for candidate in lines[line_value:]:
        stripped = candidate.strip()
        if not stripped:
            continue
        indent = len(candidate) - len(candidate.lstrip())
        if indent <= except_indent:
            return False
        if stripped.startswith("#"):
            continue
        return stripped not in {"pass", "..."}
    return False


def _is_python_prose_arrow(finding: dict[str, Any]) -> bool:
    # G118 flags Unicode arrows as pseudocode operators. In a .py file that the
    # syntax tier already requires to compile, an arrow used as an operator is a
    # SyntaxError, so any G118 hit in compiled Python is notation in a string,
    # comment, or docstring, not executable pseudocode.
    if finding.get("rule_id") != "G118":
        return False
    path_value = finding.get("file") or ""
    return path_value.endswith(".py")


def _filter_payload(payload: dict[str, Any], root: Path) -> tuple[dict[str, Any], dict[str, int]]:
    filtered = []
    ignored = {"G141": 0, "G22": 0, "G118": 0, "G20": 0}
    findings = payload.get("findings", [])
    if not isinstance(findings, list):
        findings = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        if finding.get("rule_id") == "G20":
            ignored["G20"] += 1
            continue
        if finding.get("rule_id") == "G141" and not _is_comment_line(finding.get("content")):
            ignored["G141"] += 1
            continue
        if _has_non_empty_except_handler(finding):
            ignored["G22"] += 1
            continue
        if _is_python_prose_arrow(finding):
            ignored["G118"] += 1
            continue
        normalized = dict(finding)
        file_value = normalized.get("file")
        if isinstance(file_value, str):
            normalized["file"] = _relative_path(file_value, root)
        filtered.append(normalized)

    filtered_payload = dict(payload)
    filtered_payload["findings"] = filtered
    summary = dict(filtered_payload.get("summary") or {})
    for severity in ("critical", "high", "medium", "low"):
        summary[severity] = sum(1 for finding in filtered if finding.get("severity") == severity)
    filtered_payload["summary"] = summary
    filtered_payload["passed"] = summary.get("critical", 0) + summary.get("high", 0) == 0
    return filtered_payload, ignored


def _signature(finding: dict[str, Any]) -> str:
    return "\0".join(
        [
            str(finding.get("rule_id", "")),
            str(finding.get("file", "")),
            str(finding.get("content", "")).strip(),
        ]
    )


def _signatures(payload: dict[str, Any]) -> collections.Counter[str]:
    return collections.Counter(_signature(finding) for finding in payload.get("findings", []))


def _high_or_critical(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        finding
        for finding in payload.get("findings", [])
        if finding.get("severity") in {"critical", "high"}
    ]


def _print_ignored(ignored: dict[str, int]) -> None:
    messages = {
        "G141": "G141 non-comment false-positive finding(s)",
        "G22": "G22 non-empty except-handler false-positive finding(s)",
        "G118": "G118 prose-arrow finding(s) in compiled Python (notation, not pseudocode)",
        "G20": "G20 prompt-context false-positive finding(s)",
    }
    for rule_id, message in messages.items():
        count = ignored.get(rule_id, 0)
        if count > 0:
            print(f"vibecheck: ignored {count} {message}.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--head-json", type=Path, required=True)
    parser.add_argument("--head-root", type=Path, required=True)
    parser.add_argument("--base-json", type=Path)
    parser.add_argument("--base-root", type=Path)
    args = parser.parse_args()

    head_payload = json.loads(args.head_json.read_text())
    head_filtered, head_ignored = _filter_payload(head_payload, args.head_root)
    _print_ignored(head_ignored)

    if args.base_json is not None:
        if args.base_root is None:
            parser.error("--base-root is required with --base-json")
        base_payload = json.loads(args.base_json.read_text())
        base_filtered, _base_ignored = _filter_payload(base_payload, args.base_root)
        new_signatures = _signatures(head_filtered) - _signatures(base_filtered)
        new_findings = [
            finding
            for finding in _high_or_critical(head_filtered)
            if new_signatures[_signature(finding)] > 0
        ]
        if not new_findings:
            print("vibecheck: findings are unchanged relative to DIFF_COVER_BASE.")
            return 0
        print(json.dumps({"findings": new_findings, "errors": []}, indent=2))
        print("")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("  ERROR: vibecheck found new anti-slop findings relative to DIFF_COVER_BASE.")
        print("  Findings are in PROJECT CODE — fix the project code.")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        return 1

    remaining = _high_or_critical(head_filtered)
    if not remaining:
        print("vibecheck: 0 findings — clean.")
        return 0
    print(json.dumps(head_filtered, indent=2))
    print("")
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print("  ERROR: vibecheck found anti-slop pattern violations.")
    print("  Findings are in PROJECT CODE — fix the project code.")
    print("")
    print("  PROBING GLOBAL QC IS REWARD-HACKING.")
    print("  Do NOT modify QC configs or tooling in ~/ai-review-ci/")
    print("  to suppress these findings.")
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
