"""Slop torture fixtures for runtime defaults and optional core state."""

import os


def runtime_defaults(config: dict[str, str], payload: object) -> tuple[str, str, object]:
    # ruleid: py-no-getenv-default
    endpoint = os.getenv("SERVICE_ENDPOINT", "https://example.invalid")
    # ruleid: py-no-dict-get-default
    token = config.get("token", "")
    # ruleid: py-no-getattr-default
    name = getattr(payload, "name", "anonymous")
    return endpoint, token, name


# ruleid: py-no-optional-type
MAYBE_USER: str | None
# ruleid: py-no-optional-type
MAYBE_COUNT: int | None


def fail_loud_config(config: dict[str, str]) -> str:
    # ok: py-no-dict-get-default
    token = config["token"]
    # ok: py-no-getenv-default
    endpoint = os.environ["SERVICE_ENDPOINT"]
    return f"{endpoint}:{token}"
