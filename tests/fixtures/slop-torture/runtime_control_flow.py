"""Slop-torture fixtures: runtime control flow and defensiveness (#41, was #62).

Deliberately noncompliant code exercising the shipped semgrep rules for
runtime defaults, optional state, swallowed errors, and optional critical
dependencies, mixed with compliant counterparts.

Annotation convention (semgrep's own): ``# ruleid: <id>`` marks the line
below as an expected match; ``# ok: <id>`` marks it as an expected
non-match. Run by tests/test_slop_torture.py against the real rules parsed
out of tool-configs/semgrep.yml.

This directory is excluded from the repo's own QC surface via
tool-configs/qc-excludes.toml: the fixtures are adversarial *data* for the
detector tests, not owned product code.
"""

import contextlib
import os
from collections import defaultdict
from typing import Optional

# ok: py-no-try-import
import json

# ruleid: py-no-try-import
try:
    import lizard
except ImportError:
    lizard = None


def env_with_default() -> str:
    # ruleid: py-no-getenv-default
    return os.getenv("REVIEWER_HOME", "/tmp/reviewer")


def env_required() -> str:
    # ok: py-no-getenv-default
    return os.environ["REVIEWER_HOME"]


def config_with_default(config: dict[str, str]) -> str:
    # ruleid: py-no-dict-get-default
    return config.get("model", "claude-fable-5")


def config_required(config: dict[str, str]) -> str:
    # ok: py-no-dict-get-default
    return config["model"]


def attr_with_default(finding: object) -> str:
    # ruleid: py-no-getattr-default
    return getattr(finding, "policy_code", "POLICY.UNKNOWN")


def counts_by_policy() -> dict[str, int]:
    # ruleid: py-no-defaultdict
    return defaultdict(int)


def counts_explicit(codes: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for code in codes:
        if code not in counts:
            # ok: py-no-defaultdict
            counts[code] = 0
        # ok: py-no-dict-get-default
        counts[code] += 1
    return counts


def optional_icon() -> None:
    # ruleid: py-no-optional-type
    icon: Optional[str]
    # ruleid: py-no-optional-type
    label: str | None
    icon = None
    label = None
    del icon, label


def required_label() -> None:
    # ok: py-no-optional-type
    label: str = "reviewer"
    del label


def swallow_everything(path: str) -> str:
    # ruleid: py-no-bare-except
    try:
        return open(path).read()
    except:
        pass
    return ""


def swallow_typed(path: str) -> str:
    # ruleid: py-no-bare-except
    try:
        return open(path).read()
    except OSError:
        pass
    return ""


def handle_domain_error(path: str) -> str:
    # ok: py-no-bare-except
    try:
        return open(path).read()
    except FileNotFoundError as error:
        raise RuntimeError(f"required review artifact missing: {path}") from error


def fail_loudly(path: str) -> str:
    # ok: py-no-bare-except
    return open(path).read()


def suppress_cleanup(path: str) -> None:
    # ruleid: py-no-suppress
    with contextlib.suppress(OSError):
        os.unlink(path)


def cleanup_loudly(path: str) -> None:
    # ok: py-no-suppress
    os.unlink(path)
