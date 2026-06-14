import json
import os
import pathlib
import shutil
import subprocess
import tomllib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
TRIAGE_MARKER = "QC FAILURE"


def run_just(
    justfile: pathlib.Path,
    workdir: pathlib.Path,
    recipe: str,
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "just",
            "--justfile",
            str(justfile),
            "-d",
            str(workdir),
            recipe,
        ],
        cwd=workdir,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def path_with_only(tmp_path: pathlib.Path, *commands: str) -> str:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for command in commands:
        target = shutil.which(command)
        assert target is not None, f"required command missing for test setup: {command}"
        (bin_dir / command).symlink_to(target)
    return str(bin_dir)


def project_with_sage_file(tmp_path: pathlib.Path) -> pathlib.Path:
    project = tmp_path / "sage-project"
    project.mkdir()
    (project / "example.sage").write_text("x = 1\n")
    return project


@pytest.mark.parametrize("recipe", ["_sage-syntax", "_vulture"])
@pytest.mark.parametrize("configured_path", ["missing", "not-executable"])
def test_sage_recipes_require_configured_executable_sage_path(
    tmp_path: pathlib.Path,
    recipe: str,
    configured_path: str,
) -> None:
    project = project_with_sage_file(tmp_path)
    env = os.environ.copy()
    env.pop("SAGE_BIN", None)
    if configured_path == "not-executable":
        sage_bin = tmp_path / "not-executable-sage"
        sage_bin.write_text("#!/usr/bin/env bash\nexit 0\n")
        env["SAGE_BIN"] = str(sage_bin)

    result = run_just(ROOT / "justfiles" / "sage.just", project, recipe, env=env)

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert TRIAGE_MARKER in output


def test_tsc_requires_ags_when_tsconfig_declares_ags(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "ags-project"
    project.mkdir()
    (project / "package.json").write_text(json.dumps({"scripts": {}}) + "\n")
    (project / "tsconfig.json").write_text(
        json.dumps({"compilerOptions": {"jsxImportSource": "ags/gtk4"}}) + "\n"
    )
    env = os.environ | {"PATH": path_with_only(tmp_path, "bash", "jq", "just")}

    result = run_just(ROOT / "justfiles" / "bun.just", project, "_tsc", env=env)

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert TRIAGE_MARKER in output


def test_install_global_hooks_requires_env_only_inside_recipe(tmp_path: pathlib.Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env = os.environ | {
        "HOME": str(home),
        "GIT_CONFIG_GLOBAL": str(home / ".gitconfig"),
    }
    env.pop("GIT_GLOBAL_HOOKS_DIR", None)

    recipe_list = subprocess.run(
        ["just", "--justfile", str(ROOT / "justfile"), "--list"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert recipe_list.returncode == 0, recipe_list.stdout + recipe_list.stderr

    install = run_just(ROOT / "justfile", tmp_path, "install-global-hooks", env=env)

    output = install.stdout + install.stderr
    assert install.returncode != 0, output
    assert "ERROR:" in output
    assert "GIT_GLOBAL_HOOKS_DIR" in output
    assert not (home / ".config" / "git" / "hooks").exists()


def test_sync_qc_excludes_preserves_non_owned_artifacts_and_updates_grain(
    tmp_path: pathlib.Path,
) -> None:
    repo = tmp_path / "repo"
    qc_root = repo / "tool-configs"
    justfiles = repo / "justfiles"
    qc_root.mkdir(parents=True)
    justfiles.mkdir()

    for file_name in (
        "biome.json",
        "knip.json",
        "jscpd.json",
        "slop-scan.config.json",
        "pyright-local.json",
        "grain.toml",
    ):
        shutil.copy(ROOT / "tool-configs" / file_name, qc_root / file_name)
    (qc_root / "qc-excludes.toml").write_text('directories = ["central-owned"]\n')
    eslint_config = qc_root / "eslint.config.js"
    rust_justfile = justfiles / "rust.just"
    eslint_config.write_text("export default [{ ignores: ['sentinel'] }];\n")
    rust_justfile.write_text("# rust sentinel\n")

    result = subprocess.run(
        [
            "uv",
            "run",
            str(ROOT / "tool-artifacts" / "scripts" / "sync_qc_excludes.py"),
            str(qc_root / "qc-excludes.toml"),
        ],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    grain = tomllib.loads((qc_root / "grain.toml").read_text())
    assert "fail_on" in grain["grain"]
    assert "central-owned/*" in grain["grain"]["exclude"]
    assert eslint_config.read_text() == "export default [{ ignores: ['sentinel'] }];\n"
    assert rust_justfile.read_text() == "# rust sentinel\n"


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


def test_deptry_accepts_first_party_imports_in_src_layout(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "first-party-project"
    package_dir = project / "src" / "first_party_project"
    package_dir.mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "first-party-project"',
                'version = "0.1.0"',
                'requires-python = ">=3.14"',
                "dependencies = []",
                "",
            ]
        )
    )
    (package_dir / "core.py").write_text("VALUE = 42\n")
    (package_dir / "__init__.py").write_text(
        "\n".join(
            [
                "from first_party_project.core import VALUE",
                "",
                "RESULT = VALUE",
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


def test_deptry_treats_pep723_script_dependencies_as_script_owned(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "pep723-script-project"
    package_dir = project / "src" / "pep723_script_project"
    script_dir = project / "tool-artifacts" / "scripts"
    package_dir.mkdir(parents=True)
    script_dir.mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "pep723-script-project"',
                'version = "0.1.0"',
                'requires-python = ">=3.14"',
                "dependencies = []",
                "",
            ]
        )
    )
    (package_dir / "__init__.py").write_text("VALUE = 42\n")
    (script_dir / "make_slug.py").write_text(
        "\n".join(
            [
                "# /// script",
                '# dependencies = ["python-slugify>=8"]',
                "# ///",
                "",
                "from slugify import slugify",
                "",
                'VALUE = slugify("A B")',
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


def test_mypy_recipe_fails_when_mypy_reports_type_errors(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "typed-failure-project"
    package_dir = project / "src" / "typed_failure_project"
    package_dir.mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "typed-failure-project"',
                'version = "0.1.0"',
                'requires-python = ">=3.14"',
                "dependencies = []",
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
    (package_dir / "__init__.py").write_text('VALUE: int = "not an int"\n')

    result = subprocess.run(
        [
            "just",
            "--justfile",
            str(ROOT / "justfiles" / "python.just"),
            "-d",
            str(project),
            "_mypy",
        ],
        cwd=project,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0, result.stdout + result.stderr


def test_mypy_uses_declared_dependency_group_type_stubs(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "stub-project"
    package_dir = project / "src" / "stub_project"
    package_dir.mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "stub-project"',
                'version = "0.1.0"',
                'requires-python = ">=3.14"',
                'dependencies = ["unidiff>=0.7.5"]',
                "",
                "[dependency-groups]",
                'dev = ["types-unidiff>=0.7.0.20260518"]',
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
                "from unidiff import PatchSet",
                "",
                "",
                "def parse_patch(text: str) -> int:",
                "    return len(PatchSet(text.splitlines(keepends=True)))",
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
            "_mypy",
        ],
        cwd=project,
        text=True,
        capture_output=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "Library stubs not installed" not in output


def test_mypy_uses_pep723_script_dependencies(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "script-typed-project"
    package_dir = project / "src" / "script_typed_project"
    script_dir = project / "tool-artifacts" / "scripts"
    package_dir.mkdir(parents=True)
    script_dir.mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "script-typed-project"',
                'version = "0.1.0"',
                'requires-python = ">=3.14"',
                "dependencies = []",
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
    (package_dir / "__init__.py").write_text("VALUE = 42\n")
    (script_dir / "fetch_status.py").write_text(
        "\n".join(
            [
                "# /// script",
                '# dependencies = ["requests>=2", "types-requests>=2"]',
                "# ///",
                "",
                "import requests",
                "",
                "",
                "def fetch_status(url: str) -> int:",
                "    response = requests.get(url, timeout=3)",
                "    return response.status_code",
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
            "_mypy",
        ],
        cwd=project,
        text=True,
        capture_output=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert 'Cannot find implementation or library stub for module named "requests"' not in output
    assert 'Library stubs not installed for "requests"' not in output


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
