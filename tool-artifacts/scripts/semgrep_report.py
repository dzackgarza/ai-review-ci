#!/usr/bin/env python3
"""Validate scanner evaluation before findings can determine publication status."""

import argparse
import json
from pathlib import Path


def load_report(path: Path) -> dict[str, object]:
    """Preserve scanner metadata, rejecting missing or failed evaluations."""
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError('Semgrep report must be an object')
    if not isinstance(payload['errors'], list):
        raise ValueError('Semgrep diagnostics must be a list')
    for diagnostic in payload['errors']:
        if not isinstance(diagnostic, dict) or diagnostic['level'] not in {'error', 'warn', 'info'}:
            raise ValueError('unknown Semgrep diagnostic severity')
        if not isinstance(diagnostic['message'], str):
            raise ValueError('Semgrep diagnostic message must be a string')
        if diagnostic['level'] == 'error':
            raise ValueError(f"Semgrep evaluation failed: {diagnostic['message']}")
        # Native warn/info diagnostics are nonfatal, but incomplete analysis is
        # review input with its complete locations and metadata, never empty success.
        print(f"semgrep: independent review required (scanner {diagnostic['level']}): "
              f"{json.dumps(diagnostic, sort_keys=True)}")
    if not isinstance(payload['results'], list):
        raise ValueError('Semgrep results must be a list')
    for result in payload['results']:
        if not isinstance(result, dict):
            raise ValueError('Semgrep finding must be an object')
        for field in ('check_id', 'path'):
            if not isinstance(result[field], str) or not result[field]:
                raise ValueError(f'Semgrep {field} must be a nonempty string')
        if not isinstance(result['start']['line'], int) or result['start']['line'] < 1:
            raise ValueError('Semgrep start line must be a positive integer')
        if not isinstance(result['extra'], dict):
            raise ValueError('Semgrep finding metadata must be an object')
        if result['extra']['severity'] not in {'ERROR', 'WARNING', 'INFO'}:
            raise ValueError('unknown Semgrep finding severity')
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--empty-output', type=Path, required=True)
    parser.add_argument('--base', required=True)
    args = parser.parse_args()
    args.empty_output.write_text(json.dumps({
        'results': [], 'errors': [],
        'ai_review_ci': {'evaluation': 'empty-domain', 'targets': [], 'base': args.base},
    }))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
