"""Slop torture fixtures for mock/proof-laundering policies."""

from typing import Protocol

# ruleid: py-no-mock-import
from unittest.mock import MagicMock

import pytest


class MonkeyPatchLike(Protocol):
    def setattr(self, target: str, value: object) -> None: ...


class RealClient(Protocol):
    def fetch(self) -> dict[str, str]: ...


def test_mocked_boundary() -> None:
    # ruleid: py-no-magicmock
    client = MagicMock()
    client.fetch.return_value = {"status": "ok"}
    assert client.fetch()["status"] == "ok"


def test_monkeypatch_boundary(monkeypatch: MonkeyPatchLike) -> None:
    # ruleid: py-no-monkeypatch
    monkeypatch.setattr("os.getcwd", lambda: "/fake")


# ruleid: py-no-skip-test
@pytest.mark.skip
def test_skipped_boundary() -> None:
    assert False


def test_real_boundary(real_client: RealClient) -> None:
    # ok: py-no-magicmock
    assert real_client.fetch()["status"] == "ok"
