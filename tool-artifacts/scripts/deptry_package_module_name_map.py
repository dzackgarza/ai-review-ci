from __future__ import annotations

import sys
import tomllib
from pathlib import Path


def _module_names(value: object) -> str:
    if isinstance(value, str):
        assert value
        return value

    assert isinstance(value, list) and value
    modules: list[str] = []
    for module in value:
        assert isinstance(module, str) and module
        modules.append(module)
    return "|".join(modules)


def deptry_package_module_name_map(config_path: Path) -> str:
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    tool_config = config["tool"]
    assert isinstance(tool_config, dict)
    deptry_config = tool_config["deptry"]
    assert isinstance(deptry_config, dict)
    mapping = deptry_config["package_module_name_map"]
    assert isinstance(mapping, dict) and mapping

    entries: list[str] = []
    for package, module_names in mapping.items():
        assert isinstance(package, str) and package
        entries.append(f"{package}={_module_names(module_names)}")
    return ",".join(entries)


def main() -> None:
    assert len(sys.argv) == 2
    print(deptry_package_module_name_map(Path(sys.argv[1])))


if __name__ == "__main__":
    main()
