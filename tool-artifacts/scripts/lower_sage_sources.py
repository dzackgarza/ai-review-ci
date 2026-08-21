from __future__ import annotations

import sys
from pathlib import Path

from sageparse.build import lower_file


def lower_sources(snapshot_root: Path, relative_sources: list[str]) -> None:
    """Lower selected Sage sources inside one repository snapshot."""
    resolved_root = snapshot_root.resolve()
    for relative_source in relative_sources:
        relative = Path(relative_source)
        assert not relative.is_absolute(), f"Sage source must be relative: {relative}"
        source = (resolved_root / relative).resolve()
        assert source.is_relative_to(resolved_root), f"Sage source must remain inside the snapshot: {relative}"
        assert source.is_file(), f"Sage source does not exist: {source}"
        target = source.with_suffix(".py")
        assert not target.exists(), f"Sage source conflicts with an existing Python module: {target}"
        lower_file(source, target)


def main() -> None:
    if sys.argv[1:] == ["--check"]:
        return
    assert len(sys.argv) >= 3, "usage: lower_sage_sources.py SNAPSHOT_ROOT RELATIVE_SOURCE [RELATIVE_SOURCE ...]"
    lower_sources(Path(sys.argv[1]), sys.argv[2:])


if __name__ == "__main__":
    main()
