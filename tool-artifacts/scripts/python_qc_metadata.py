from __future__ import annotations

import json
import sys
import tomllib
from collections.abc import Iterable
from pathlib import Path
from typing import cast


def _load_pyproject(project_root: Path) -> dict[str, object]:
    pyproject_path = project_root / "pyproject.toml"
    if not pyproject_path.is_file():
        raise SystemExit(
            f"ERROR: no pyproject.toml at {pyproject_path.resolve()} — QC installs the project\n"
            "       editable and reads dependency groups from it. Create a minimal one:\n"
            "         [project]\n"
            '         name = "<project-name>"\n'
            '         version = "0.0.1"\n'
            '         requires-python = ">=3.14"\n'
        )
    raw_config = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    return cast("dict[str, object]", raw_config)


def _optional_table(
    parent: dict[str, object],
    key: str,
    qualified_name: str,
) -> dict[str, object]:
    value = parent.get(key)
    if value is None:
        return {}
    assert isinstance(value, dict), f"{qualified_name} must be a TOML table"
    return cast("dict[str, object]", value)


def _required_list(
    parent: dict[str, object],
    key: str,
    qualified_name: str,
) -> list[object]:
    value = parent[key]
    assert isinstance(value, list), f"{qualified_name} must be a TOML array"
    return value


def _string_list(value: object, qualified_name: str) -> list[str]:
    assert isinstance(value, list), f"{qualified_name} must be a TOML array"
    strings: list[str] = []
    for index, item in enumerate(value):
        assert isinstance(item, str) and item, f"{qualified_name}[{index}] must be a non-empty string"
        strings.append(item)
    return strings


def _source_modules(source_root: Path) -> list[str]:
    if not source_root.exists():
        return []

    modules: list[str] = []
    for child in sorted(source_root.iterdir()):
        if child.name.startswith("."):
            continue
        if child.is_dir() and any(child.rglob("*.py")):
            modules.append(child.name)
        elif child.is_file() and child.suffix == ".py" and child.stem != "__init__":
            modules.append(child.stem)
    return modules


def _hatch_wheel_packages(pyproject: dict[str, object]) -> list[str]:
    tool = _optional_table(pyproject, "tool", "tool")
    hatch = _optional_table(tool, "hatch", "tool.hatch")
    build = _optional_table(hatch, "build", "tool.hatch.build")
    targets = _optional_table(build, "targets", "tool.hatch.build.targets")
    wheel = _optional_table(targets, "wheel", "tool.hatch.build.targets.wheel")
    packages = wheel.get("packages")
    if packages is None:
        return []

    package_paths = _string_list(packages, "tool.hatch.build.targets.wheel.packages")
    return [Path(package_path).name for package_path in package_paths]


def _setuptools_explicit_packages(pyproject: dict[str, object]) -> list[str]:
    # setuptools accepts packages as an explicit list of dotted package names
    # (the alternative to the {find = {where = [...]}} table). The top-level
    # segment of each name is the first-party module; sub-packages collapse
    # into their root.
    tool = _optional_table(pyproject, "tool", "tool")
    setuptools = _optional_table(tool, "setuptools", "tool.setuptools")
    packages = setuptools.get("packages")
    if not isinstance(packages, list):
        return []
    names = _string_list(packages, "tool.setuptools.packages")
    return [name.split(".")[0] for name in names]


def _setuptools_package_roots(project_root: Path, pyproject: dict[str, object]) -> list[Path]:
    tool = _optional_table(pyproject, "tool", "tool")
    setuptools = _optional_table(tool, "setuptools", "tool.setuptools")
    # The explicit-list form declares package names, not source roots.
    if isinstance(setuptools.get("packages"), list):
        return []
    packages = _optional_table(setuptools, "packages", "tool.setuptools.packages")
    find = _optional_table(packages, "find", "tool.setuptools.packages.find")
    where = find.get("where")
    if where is None:
        return []

    return [project_root / path for path in _string_list(where, "tool.setuptools.packages.find.where")]


def _setuptools_py_modules(pyproject: dict[str, object]) -> list[str]:
    tool = _optional_table(pyproject, "tool", "tool")
    setuptools = _optional_table(tool, "setuptools", "tool.setuptools")
    py_modules = setuptools.get("py-modules")
    if py_modules is None:
        return []
    return _string_list(py_modules, "tool.setuptools.py-modules")


def first_party_modules(project_root: Path) -> list[str]:
    pyproject = _load_pyproject(project_root)
    modules: list[str] = []
    modules.extend(_source_modules(project_root / "src"))
    for package_root in _setuptools_package_roots(project_root, pyproject):
        modules.extend(_source_modules(package_root))
    modules.extend(_setuptools_explicit_packages(pyproject))
    modules.extend(_hatch_wheel_packages(pyproject))
    modules.extend(_setuptools_py_modules(pyproject))
    return list(dict.fromkeys(modules))


def import_linter_config(project_root: Path) -> str:
    modules = first_party_modules(project_root)
    assert modules, "import-linter: no first-party modules discovered"

    lines = [
        "[tool.importlinter]",
        f"root_packages = {json.dumps(modules)}",
        "",
    ]
    if len(modules) > 1:
        lines.extend(
            [
                "[[tool.importlinter.contracts]]",
                'name = "First-party packages are independent"',
                'type = "independence"',
                f"modules = {json.dumps(modules)}",
                "",
            ]
        )
    return "\n".join(lines)


def dependency_group_requirements(project_root: Path) -> list[str]:
    pyproject = _load_pyproject(project_root)
    groups = pyproject.get("dependency-groups")
    if groups is None:
        return []
    assert isinstance(groups, dict), "dependency-groups must be a TOML table"
    dependency_groups = cast("dict[str, object]", groups)

    def collect(group_name: str, stack: tuple[str, ...]) -> list[str]:
        assert group_name not in stack, f"dependency-groups contains an include cycle at {group_name}"
        group = _required_list(
            dependency_groups,
            group_name,
            f"dependency-groups.{group_name}",
        )
        requirements: list[str] = []
        for index, item in enumerate(group):
            if isinstance(item, str):
                assert item, f"dependency-groups.{group_name}[{index}] must be non-empty"
                requirements.append(item)
            elif isinstance(item, dict):
                include = cast("dict[str, object]", item)
                assert set(include) == {"include-group"}, f"dependency-groups.{group_name}[{index}] must be an include-group table"
                include_group = include["include-group"]
                assert isinstance(include_group, str) and include_group, f"dependency-groups.{group_name}[{index}].include-group must be a non-empty string"
                requirements.extend(collect(include_group, (*stack, group_name)))
            else:
                raise AssertionError(f"dependency-groups.{group_name}[{index}] must be a requirement string or include-group table")
        return requirements

    requirements: list[str] = []
    for group_name in sorted(dependency_groups):
        requirements.extend(collect(group_name, ()))
    return list(dict.fromkeys(requirements))


def _has_pep723_script_metadata(path: Path) -> bool:
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line.strip() != "# /// script":
            continue
        for metadata_line in lines[index + 1 :]:
            if metadata_line.strip() == "# ///":
                return True
        raise AssertionError(f"{path} has an unterminated PEP 723 script metadata block")
    return False


def _pep723_metadata(path: Path) -> dict[str, object] | None:
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line.strip() != "# /// script":
            continue
        block: list[str] = []
        for metadata_line in lines[index + 1 :]:
            if metadata_line.strip() == "# ///":
                raw = "\n".join(block)
                return cast("dict[str, object]", tomllib.loads(raw)) if raw else {}
            if not metadata_line.startswith("#"):
                raise AssertionError(f"{path} has a malformed PEP 723 script metadata line")
            block.append(metadata_line[1:].removeprefix(" "))
        raise AssertionError(f"{path} has an unterminated PEP 723 script metadata block")
    return None


def pep723_scripts(paths: list[str]) -> list[str]:
    return [path for path in paths if _has_pep723_script_metadata(Path(path))]


def pep723_requirements(paths: list[str]) -> list[str]:
    requirements: list[str] = []
    for path in paths:
        metadata = _pep723_metadata(Path(path))
        if metadata is None:
            continue
        dependencies: object = []
        if "dependencies" in metadata:
            dependencies = metadata["dependencies"]
        requirements.extend(_string_list(dependencies, f"{path} dependencies"))
    return list(dict.fromkeys(requirements))


def _print_lines(values: Iterable[str]) -> None:
    for value in values:
        print(value)


def main() -> None:
    assert len(sys.argv) >= 3
    command = sys.argv[1]
    if command == "first-party-modules":
        assert len(sys.argv) == 3
        _print_lines(first_party_modules(Path(sys.argv[2])))
    elif command == "import-linter-config":
        assert len(sys.argv) == 3
        print(import_linter_config(Path(sys.argv[2])), end="")
    elif command == "dependency-group-requirements":
        assert len(sys.argv) == 3
        _print_lines(dependency_group_requirements(Path(sys.argv[2])))
    elif command == "pep723-scripts":
        _print_lines(pep723_scripts(sys.argv[2:]))
    elif command == "pep723-requirements":
        _print_lines(pep723_requirements(sys.argv[2:]))
    else:
        raise AssertionError(f"unknown command: {command}")


if __name__ == "__main__":
    main()
