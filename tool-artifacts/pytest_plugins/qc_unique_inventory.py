"""Traverse native directories once for the full gate's unique file inventory.

Pytest rescans a file's parent for every explicit file argument. Reusing native
child nodes avoids that repeated work without changing arguments or discovery.
This plugin is not loaded for focus runs, which may request duplicate files.
The extension point is pytest's documented ``pytest_collect_directory`` hook.
"""

from collections.abc import Iterator
from functools import cached_property
from pathlib import Path

import pytest


class InventoryDirectory(pytest.Dir):
    @cached_property
    def _children(self) -> tuple[pytest.Collector | pytest.Item, ...]:
        return tuple(super().collect())

    def collect(self) -> Iterator[pytest.Collector | pytest.Item]:
        return iter(self._children)


class InventoryPackage(pytest.Package):
    @cached_property
    def _children(self) -> tuple[pytest.Collector | pytest.Item, ...]:
        return tuple(super().collect())

    def collect(self) -> Iterator[pytest.Collector | pytest.Item]:
        return iter(self._children)


def pytest_collect_directory(path: Path, parent: pytest.Collector) -> pytest.Collector:
    if (path / "__init__.py").is_file():
        return InventoryPackage.from_parent(parent, path=path)
    return InventoryDirectory.from_parent(parent, path=path)
