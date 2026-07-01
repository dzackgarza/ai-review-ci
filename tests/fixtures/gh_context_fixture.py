#!/usr/bin/env python3
"""Executable gh fixture for context-fetching tests."""

import json
import os
import sys
from pathlib import Path


def _field_values(argv: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for index, token in enumerate(argv):
        if token in {"--field", "-F"}:
            key, value = argv[index + 1].split("=", 1)
            fields[key] = value
    return fields


def _read_json(path: Path) -> object:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    return value


def _json_object(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def _json_object_list(path: Path) -> list[dict[str, object]]:
    value = _read_json(path)
    assert isinstance(value, list)
    return [_json_object(item) for item in value]


def _append_call(fixture_dir: Path, payload: dict[str, object]) -> None:
    calls_path = fixture_dir / "calls.jsonl"
    with calls_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _matches_no_analysis(entry: dict[str, object], fields: dict[str, str]) -> bool:
    return entry["tool_name"] == fields["tool_name"] and entry.get("state") == fields.get("state") and entry.get("ref", "") == fields.get("ref", "")


def _request_matches(path: Path, fields: dict[str, str]) -> bool:
    return path.exists() and any(_matches_no_analysis(entry, fields) for entry in _json_object_list(path))


def _matching_alerts(entries: list[dict[str, object]], fields: dict[str, str]) -> list[dict[str, object]]:
    alerts: list[dict[str, object]] = []
    for entry in entries:
        if entry["tool_name"] == fields["tool_name"] and entry["state"] == fields["state"] and entry.get("ref", "") == fields.get("ref", ""):
            alerts.append(_json_object(entry["alert"]))
    return alerts


def _alert_entries(fixture_dir: Path) -> list[dict[str, object]]:
    alerts_path = fixture_dir / "alerts.json"
    return _json_object_list(alerts_path) if alerts_path.exists() else []


def _emit_rest_page(argv: list[str], fixture_dir: Path) -> None:
    path = argv[argv.index("GET") + 1]
    fields = _field_values(argv)
    _append_call(fixture_dir, {"kind": "rest", "path": path, "fields": fields})

    if _request_matches(fixture_dir / "failures.json", fields):
        print("code scanning request failed", file=sys.stderr)
        raise SystemExit(2)
    if _request_matches(fixture_dir / "code_scanning_disabled.json", fields):
        print(
            "gh: Code scanning is not enabled for this repository. "
            "Please enable code scanning in the repository settings. (HTTP 403)",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if _request_matches(fixture_dir / "no_analysis.json", fields):
        print("no analysis found for requested ref", file=sys.stderr)
        raise SystemExit(1)

    entries = _alert_entries(fixture_dir)
    alerts = _matching_alerts(entries, fields)
    per_page = int(fields["per_page"])
    page = int(fields["page"])
    start = (page - 1) * per_page
    print(json.dumps(alerts[start : start + per_page]))


def _emit_graphql_page(argv: list[str], fixture_dir: Path) -> None:
    fields = _field_values(argv)
    _append_call(fixture_dir, {"kind": "graphql", "fields": fields})
    if (fixture_dir / "graphql_failure").exists():
        print("review threads request failed", file=sys.stderr)
        raise SystemExit(2)
    threads_path = fixture_dir / "threads.json"
    if not threads_path.exists():
        page: object = {"nodes": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}
    else:
        data = _read_json(threads_path)
        if isinstance(data, list):
            pages = [_json_object(item) for item in data]
            page = pages[0] if "cursor" not in fields else pages[1]
        else:
            page = _json_object(data)
    print(json.dumps({"data": {"repository": {"pullRequest": {"reviewThreads": page}}}}))


def main() -> None:
    fixture_dir = Path(os.environ["AI_REVIEW_CI_CONTEXT_FIXTURE_DIR"])
    argv = sys.argv[1:]
    if argv[:2] == ["api", "graphql"]:
        _emit_graphql_page(argv, fixture_dir)
    elif argv[:3] == ["api", "--method", "GET"]:
        _emit_rest_page(argv, fixture_dir)
    else:
        raise AssertionError(f"unsupported gh fixture invocation: {argv}")


if __name__ == "__main__":
    main()
