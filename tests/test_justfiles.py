import json
import os
import pathlib
import shutil
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_python_syntax_recipe_is_isolated_from_sage_state(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "python-project"
    source_dir = project / "src"
    source_dir.mkdir(parents=True)
    (source_dir / "app.py").write_text("VALUE: int = 41 + 1\n")

    result = subprocess.run(
        [
            "just",
            "--justfile",
            str(ROOT / "justfiles" / "python.just"),
            "-d",
            str(project),
            "_python-syntax",
        ],
        cwd=project,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_common_normalization_formats_structured_text(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    markdown = project / "README.md"
    json_file = project / "config.json"

    markdown.write_text("# Title\n\n-   item\n")
    json_file.write_text('{"b":2,"a":1}\n')

    result = subprocess.run(
        [
            "just",
            "--justfile",
            str(ROOT / "justfiles" / "shared.just"),
            "-d",
            str(project),
            "_format-structured-text",
        ],
        cwd=project,
        text=True,
        capture_output=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert markdown.read_text() == "# Title\n\n- item\n"
    assert json_file.read_text() == '{ "b": 2, "a": 1 }\n'


def test_envrc_check_accepts_root_envrc_and_rejects_dotenv_files(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".envrc").write_text("source_up\n")
    env = os.environ | {"DIRENV_CONFIGURED_CORRECTLY": "1"}

    accepted = subprocess.run(
        [
            "just",
            "--justfile",
            str(ROOT / "justfiles" / "shared.just"),
            "-d",
            str(project),
            "_check-envrc",
        ],
        cwd=project,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert accepted.returncode == 0, accepted.stdout + accepted.stderr

    (project / ".env").write_text("EXAMPLE=value\n")
    rejected = subprocess.run(
        [
            "just",
            "--justfile",
            str(ROOT / "justfiles" / "shared.just"),
            "-d",
            str(project),
            "_check-envrc",
        ],
        cwd=project,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert rejected.returncode != 0, rejected.stdout + rejected.stderr


def test_eslint_flat_config_imports_with_declared_tool_config_deps(
    tmp_path: pathlib.Path,
) -> None:
    tool_config = tmp_path / "tool-configs"
    tool_config.mkdir()
    for file_name in ("package.json", "bun.lock", "eslint.config.js"):
        shutil.copy(ROOT / "tool-configs" / file_name, tool_config / file_name)

    install = subprocess.run(
        ["bun", "install", "--frozen-lockfile"],
        cwd=tool_config,
        text=True,
        capture_output=True,
        check=False,
    )
    assert install.returncode == 0, install.stdout + install.stderr

    config_import = subprocess.run(
        ["node", "-e", 'import("./eslint.config.js")'],
        cwd=tool_config,
        text=True,
        capture_output=True,
        check=False,
    )
    assert config_import.returncode == 0, config_import.stdout + config_import.stderr


def test_bun_scaffold_delegates_qc_in_project_directory(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "bun-project"
    project.mkdir()
    (project / "package.json").write_text(json.dumps({"scripts": {}}) + "\n")
    (project / "bun.lock").write_text("")

    result = subprocess.run(
        [
            "just",
            "--justfile",
            str(ROOT / "scaffolds" / "bun" / "justfile"),
            "-d",
            str(project),
            "test",
        ],
        cwd=project,
        text=True,
        capture_output=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "TypeScript project must have a package.json file" not in output
    assert "TypeScript project must use Bun" not in output
    assert "TypeScript project must have tests" in output


def test_tsc_removes_temp_output_on_success(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "bun-project"
    project.mkdir()
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    (project / "package.json").write_text(json.dumps({"scripts": {"typecheck": "printf typecheck-ok"}}) + "\n")

    result = subprocess.run(
        [
            "just",
            "--justfile",
            str(ROOT / "justfiles" / "bun.just"),
            "-d",
            str(project),
            "_tsc",
        ],
        cwd=project,
        env=os.environ | {"TMPDIR": str(tmpdir)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert sorted(tmpdir.iterdir()) == []


def test_pytest_with_coverage_fails_when_threshold_fails(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "python-project"
    package_dir = project / "src" / "coverage_failure_project"
    tests_dir = project / "tests"
    package_dir.mkdir(parents=True)
    tests_dir.mkdir()
    (project / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "coverage-failure-project"',
                'version = "0.1.0"',
                'requires-python = ">=3.14"',
                "",
                "[build-system]",
                'requires = ["setuptools"]',
                'build-backend = "setuptools.build_meta"',
                "",
                "[tool.setuptools.packages.find]",
                'where = ["src"]',
                "",
            ]
        )
    )
    (package_dir / "__init__.py").write_text(
        "\n".join(
            [
                "def covered() -> int:",
                "    return 1",
                "",
                "",
                "def uncovered() -> int:",
                "    return 2",
                "",
            ]
        )
    )
    (tests_dir / "test_package.py").write_text(
        "\n".join(
            [
                "from coverage_failure_project import covered",
                "",
                "",
                "def test_covered() -> None:",
                "    assert covered() == 1",
                "",
            ]
        )
    )

    result = subprocess.run(
        [
            "just",
            "--justfile",
            str(ROOT / "justfiles" / "python.just"),
            "-d",
            str(project),
            "_pytest_with_coverage",
        ],
        cwd=project,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0, result.stdout + result.stderr


def test_deptry_accepts_declared_distributions_with_different_import_names(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "mapped-dependency-project"
    package_dir = project / "src" / "mapped_dependency_project"
    package_dir.mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "mapped-dependency-project"',
                'version = "0.1.0"',
                'requires-python = ">=3.14"',
                "dependencies = [",
                '    "python-slugify>=8",',
                '    "PyYAML>=6",',
                '    "types-PyYAML>=6",',
                "]",
                "",
            ]
        )
    )
    (package_dir / "__init__.py").write_text(
        "\n".join(
            [
                "import yaml",
                "from slugify import slugify",
                "",
                'VALUE = yaml.safe_dump({"slug": slugify("A B")})',
                "",
            ]
        )
    )

    result = subprocess.run(
        [
            "just",
            "--justfile",
            str(ROOT / "justfiles" / "python.just"),
            "-d",
            str(project),
            "_deptry",
        ],
        cwd=project,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_rust_preflight_accepts_nested_cargo_manifest_and_routes_missing_tests(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "tauri-project"
    source_dir = project / "src-tauri" / "src"
    source_dir.mkdir(parents=True)
    (project / "src-tauri" / "Cargo.toml").write_text(
        "\n".join(
            [
                "[package]",
                'name = "tauri-project"',
                'version = "0.1.0"',
                'edition = "2021"',
                "",
            ]
        )
    )
    (source_dir / "lib.rs").write_text("pub fn value() -> u8 { 42 }\n")

    result = subprocess.run(
        [
            "just",
            "--justfile",
            str(ROOT / "justfiles" / "rust.just"),
            "-d",
            str(project),
            "_check-rust-project",
        ],
        cwd=project,
        text=True,
        capture_output=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert "Rust project must have a Cargo.toml file" not in output
    assert "TEST-WRITING TRIAGE REQUIRED" in output
    assert "test-writing" in output


def test_rust_normalization_formats_nested_manifest_project(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "rust-project"
    source_dir = project / "src-tauri" / "src"
    source_dir.mkdir(parents=True)
    (project / "src-tauri" / "Cargo.toml").write_text(
        "\n".join(
            [
                "[package]",
                'name = "rust-project"',
                'version = "0.1.0"',
                'edition = "2021"',
                "",
            ]
        )
    )
    (source_dir / "lib.rs").write_text("pub fn value()->u8{42}\n")

    result = subprocess.run(
        [
            "just",
            "--justfile",
            str(ROOT / "justfiles" / "rust.just"),
            "-d",
            str(project),
            "_normalize",
            "_rustfmt",
        ],
        cwd=project,
        text=True,
        capture_output=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert (source_dir / "lib.rs").read_text() == "pub fn value() -> u8 {\n    42\n}\n"
