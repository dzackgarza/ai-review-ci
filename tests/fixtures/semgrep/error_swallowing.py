"""Slop torture fixtures for POLICY.NO_ERROR_DISCARD."""

import contextlib
from collections.abc import Callable
from typing import Protocol


class ReleasableContext(Protocol):
    def __enter__(self) -> object: ...

    def __exit__(self, exc_type: object, exc: object, tb: object) -> object: ...

    def release(self) -> None: ...


def swallowed_bare_except(work: Callable[[], object]) -> None:
    # ruleid: py-no-bare-except
    try:
        work()
    except:  # noqa: E722 - intentional torture fixture
        pass


def swallowed_with_suppress(work: Callable[[], object]) -> None:
    # ruleid: py-no-suppress
    with contextlib.suppress(Exception):
        work()


def fail_loud_specific_exception(work: Callable[[], object]) -> None:
    try:
        work()
    except ValueError as exc:
        raise RuntimeError("invalid observed value") from exc


def explicit_cleanup_guard(lock: ReleasableContext) -> None:
    # ok: py-no-suppress
    with lock:
        lock.release()
