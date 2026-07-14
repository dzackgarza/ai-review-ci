import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import tomllib
from typing import Any

import pytest
import yaml
from pydantic import TypeAdapter

ROOT = pathlib.Path(__file__).resolve().parents[1]
TRIAGE_MARKER = "QC FAILURE"
LINT_STAGED_CONFIG = TypeAdapter(dict[str, list[str]])


@pytest.fixture(autouse=True)
def private_recipe_failure_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Private-recipe tests exercise CI-style directives unless overridden."""
    monkeypatch.setenv("AI_REVIEW_CI_FAILURE_MODE", "triage")


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


def run_git(workdir: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key in (
        "GIT_DIR",
        "GIT_INDEX_FILE",
        "GIT_WORK_TREE",
        "GIT_PREFIX",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_COMMON_DIR",
    ):
        env.pop(key, None)
    return subprocess.run(
        ["git", "-C", str(workdir), *args],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def init_git_repo(project: pathlib.Path) -> None:
    assert run_git(project, "init").returncode == 0
    assert run_git(project, "config", "user.email", "test@example.invalid").returncode == 0
    assert run_git(project, "config", "user.name", "Test User").returncode == 0


def commit_without_hooks(project: pathlib.Path, message: str) -> None:
    result = run_git(project, "-c", "core.hooksPath=/dev/null", "commit", "-m", message)
    assert result.returncode == 0, result.stdout + result.stderr


def top_level_skill_dirs() -> list[pathlib.Path]:
    return sorted(path for path in (ROOT / "skills").iterdir() if path.is_dir() and (path / "SKILL.md").is_file())


def test_install_skills_symlinks_every_top_level_skill(tmp_path: pathlib.Path) -> None:
    skills_dir = tmp_path / "skills-hub"
    env = os.environ.copy()
    env["AI_SKILLS_DIR"] = str(skills_dir)

    result = run_just(ROOT / "justfile", ROOT, "install-skills", env=env)

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    expected_skills = top_level_skill_dirs()
    assert expected_skills
    assert sorted(path.name for path in skills_dir.iterdir()) == [path.name for path in expected_skills]
    for source in expected_skills:
        target = skills_dir / source.name
        assert target.is_symlink(), f"{target} should be a symlink"
        assert target.resolve() == source.resolve()


def test_install_skills_requires_ai_skills_dir(tmp_path: pathlib.Path) -> None:
    env = os.environ.copy()
    env.pop("AI_SKILLS_DIR", None)

    result = run_just(ROOT / "justfile", tmp_path, "install-skills", env=env)

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "AI_SKILLS_DIR must be set" in output


def test_install_skills_refuses_to_replace_non_symlink(tmp_path: pathlib.Path) -> None:
    skills_dir = tmp_path / "skills-hub"
    blocking_skill = top_level_skill_dirs()[0]
    blocking_target = skills_dir / blocking_skill.name
    blocking_target.mkdir(parents=True)
    env = os.environ.copy()
    env["AI_SKILLS_DIR"] = str(skills_dir)

    result = run_just(ROOT / "justfile", ROOT, "install-skills", env=env)

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "refusing to replace non-symlink skill" in output
    assert blocking_target.is_dir()
    assert not blocking_target.is_symlink()


def project_with_sage_file(tmp_path: pathlib.Path) -> pathlib.Path:
    project = tmp_path / "sage-project"
    project.mkdir()
    (project / "example.sage").write_text("x = 1\n")
    return project


def test_no_bypass_ignores_preexisting_markers_when_staging_other_changes(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "git-project"
    project.mkdir()
    source = project / "app.py"
    coverage_marker = "# pragma: no cov" + "er"
    source.write_text(f"def legacy() -> None:\n    pass  {coverage_marker}\n")
    init_git_repo(project)
    assert run_git(project, "add", "app.py").returncode == 0
    commit_without_hooks(project, "baseline")
    source.write_text(f"def legacy() -> None:\n    pass  {coverage_marker}\n\nVALUE = 1\n")
    assert run_git(project, "add", "app.py").returncode == 0

    result = run_just(ROOT / "justfiles" / "shared.just", project, "_no-bypass")

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "No bypass comments detected" in output


def test_no_bypass_blocks_newly_staged_markers(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "git-project"
    project.mkdir()
    source = project / "app.py"
    coverage_marker = "# pragma: no cov" + "er"
    source.write_text("def clean() -> None:\n    pass\n")
    init_git_repo(project)
    assert run_git(project, "add", "app.py").returncode == 0
    commit_without_hooks(project, "baseline")
    source.write_text(f"def clean() -> None:\n    pass  {coverage_marker}\n")
    assert run_git(project, "add", "app.py").returncode == 0

    result = run_just(ROOT / "justfiles" / "shared.just", project, "_no-bypass")

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "coverage bypass marker" in output
    assert TRIAGE_MARKER in output


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


def test_qc_excludes_notebooks_as_user_work() -> None:
    data = tomllib.loads((ROOT / "tool-configs" / "qc-excludes.toml").read_text())

    assert "notebooks" in data["directories"]


def test_python_vulture_files_ignore_scripts_and_global_notebooks_directories(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    for relative in (
        "src/app.py",
        "scripts/tool.py",
        "pkg/scripts/nested_tool.py",
        "notebooks/analysis.py",
        "pkg/notebooks/nested_analysis.py",
    ):
        path = project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("def target() -> None:\n    pass\n")

    result = run_just(ROOT / "justfiles" / "python.just", project, "_python-vulture-files")

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert result.stdout.splitlines() == ["src/app.py"]


def test_sage_vulture_files_ignore_scripts_and_global_notebooks_directories(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    for relative in (
        "src/app.sage",
        "scripts/tool.sage",
        "pkg/scripts/nested_tool.sage",
        "notebooks/analysis.sage",
        "pkg/notebooks/nested_analysis.sage",
    ):
        path = project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("def target():\n    pass\n")

    result = run_just(ROOT / "justfiles" / "sage.just", project, "_sage-vulture-files")

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert result.stdout.splitlines() == ["src/app.sage"]


@pytest.mark.parametrize(
    ("justfile_name", "recipe", "suffix", "expected_active"),
    [
        ("python.just", "_python-qc-files", ".py", "src/active.py"),
        ("sage.just", "_sage-qc-files", ".sage", "src/active.sage"),
        ("bun.just", "_js-qc-files", ".ts", "src/active.ts"),
        ("rust.just", "_rust-qc-files", ".rs", "./src/active.rs"),
    ],
)
def test_qc_file_selection_excludes_user_authored_scripts_and_notebooks(
    tmp_path: pathlib.Path,
    justfile_name: str,
    recipe: str,
    suffix: str,
    expected_active: str,
) -> None:
    project = tmp_path / "project"
    for relative in (
        f"src/active{suffix}",
        f"scripts/derivation{suffix}",
        f"research/scripts/nested_derivation{suffix}",
        f"notebooks/exploration{suffix}",
        f"research/notebooks/nested_exploration{suffix}",
    ):
        path = project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("source\n")

    result = run_just(ROOT / "justfiles" / justfile_name, project, recipe)

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert result.stdout.splitlines() == [expected_active]


@pytest.mark.parametrize(
    ("justfile_name", "recipe"),
    [
        ("python.just", "_python-qc-files"),
        ("sage.just", "_sage-qc-files"),
        ("bun.just", "_js-qc-files"),
        ("rust.just", "_rust-qc-files"),
    ],
)
def test_qc_file_selection_fails_loudly_when_exclusion_lookup_fails(
    tmp_path: pathlib.Path,
    justfile_name: str,
    recipe: str,
) -> None:
    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)
    (project / "src" / "active.py").write_text("source\n")
    shim_dir = tmp_path / "shim"
    shim_dir.mkdir()
    uv_shim = shim_dir / "uv"
    uv_shim.write_text("#!/usr/bin/env bash\necho forced exclusion lookup failure >&2\nexit 86\n")
    uv_shim.chmod(0o755)
    env = os.environ | {"PATH": f"{shim_dir}:{os.environ['PATH']}"}

    result = run_just(ROOT / "justfiles" / justfile_name, project, recipe, env=env)

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "forced exclusion lookup failure" in output


def test_tsc_requires_ags_when_tsconfig_declares_ags(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "ags-project"
    project.mkdir()
    (project / "package.json").write_text(json.dumps({"scripts": {}}) + "\n")
    (project / "tsconfig.json").write_text(json.dumps({"compilerOptions": {"jsxImportSource": "ags/gtk4"}}) + "\n")
    env = os.environ | {"PATH": path_with_only(tmp_path, "bash", "cat", "jq", "just")}

    result = run_just(ROOT / "justfiles" / "bun.just", project, "_tsc", env=env)

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert TRIAGE_MARKER in output


def test_install_global_hooks_requires_env_only_inside_recipe(
    tmp_path: pathlib.Path,
) -> None:
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
        "slopconfig.yaml",
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
    slopconfig_text = (qc_root / "slopconfig.yaml").read_text()
    assert slopconfig_text.startswith("# Maximally strict production config for ai-slop-detector\n")
    slopconfig = yaml.safe_load(slopconfig_text)
    assert slopconfig["ignore"] == ["central-owned/**", "**/central-owned/**"]
    assert eslint_config.read_text() == "export default [{ ignores: ['sentinel'] }];\n"
    assert rust_justfile.read_text() == "# rust sentinel\n"


def test_knip_config_does_not_blanket_ignore_owned_typescript(tmp_path: pathlib.Path) -> None:
    """#225 Defect 4: knip applies its `ignore` list over its own entry/project
    tsx globs, so a blanket `**/*.tsx` silently disables dead-code detection for
    every .tsx file. Test files are owned code too: they must be entrypoints so
    test-only dependency use remains visible. The regenerated config must not
    carry either blanket exclusion."""
    shipped = json.loads((ROOT / "tool-configs" / "knip.json").read_text())
    assert "**/*.tsx" not in shipped["ignore"], shipped["ignore"]
    assert "**/*.test.ts" not in shipped["ignore"]
    assert "**/*.spec.ts" not in shipped["ignore"]
    assert "**/__tests__/**" not in shipped["ignore"]

    # The shipped config must be the deterministic output of the sync script
    # (no hand edits): regenerating in place yields no change.
    repo = tmp_path / "repo"
    qc_root = repo / "tool-configs"
    qc_root.mkdir(parents=True)
    shutil.copytree(ROOT / "tool-configs", qc_root, dirs_exist_ok=True)
    result = subprocess.run(
        ["uv", "run", str(ROOT / "tool-artifacts" / "scripts" / "sync_qc_excludes.py"), str(qc_root / "qc-excludes.toml")],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads((qc_root / "knip.json").read_text())["ignore"] == shipped["ignore"]
    assert "**/*.tsx" not in json.loads((qc_root / "knip.json").read_text())["ignore"]


def test_knip_follows_dependency_imported_through_test_helper(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "bun-project"
    tests_dir = project / "tests"
    node_modules = project / "node_modules"
    tests_dir.mkdir(parents=True)
    for dependency in ("browser-boundary", "unused-boundary"):
        package_dir = node_modules / dependency
        package_dir.mkdir(parents=True)
        (package_dir / "package.json").write_text(json.dumps({"name": dependency, "version": "1.0.0", "type": "module"}) + "\n")
        (package_dir / "index.js").write_text("export const boundary = true;\n")
    (project / "package.json").write_text(
        json.dumps(
            {
                "name": "knip-test-graph-fixture",
                "version": "1.0.0",
                "devDependencies": {
                    "browser-boundary": "1.0.0",
                    "unused-boundary": "1.0.0",
                },
            }
        )
        + "\n"
    )
    (tests_dir / "shared-browser-boundary.ts").write_text('import { boundary } from "browser-boundary";\nexport const observed = boundary;\n')
    (tests_dir / "reader.test.ts").write_text('import { observed } from "./shared-browser-boundary";\nvoid observed;\n')

    result = run_just(ROOT / "justfiles" / "bun.just", project, "_knip")

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "unused-boundary" in output
    assert "browser-boundary" not in output


def test_knip_ignores_exact_assembled_pdfjs_module_only(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "bun-project"
    reader_dir = project / "extension" / "reader"
    reader_dir.mkdir(parents=True)
    (project / "package.json").write_text(json.dumps({"name": "knip-generated-module-fixture", "version": "1.0.0"}) + "\n")
    (reader_dir / "reader.js").write_text(
        "\n".join(
            [
                'import "./vendor/pdfjs/pdf_viewer.mjs";',
                'import "./vendor/pdfjs/not-assembled.mjs";',
                "",
            ]
        )
    )

    result = run_just(ROOT / "justfiles" / "bun.just", project, "_knip")

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "./vendor/pdfjs/not-assembled.mjs" in output
    assert "./vendor/pdfjs/pdf_viewer.mjs" not in output


def test_grain_config_preserves_lexicon_sage_verifier_exemption(
    tmp_path: pathlib.Path,
) -> None:
    """#225 Defect 5: Sage stub verifiers under lexicon/ accumulate import
    failures into a hard-failing problems list grain misreads as NAKED_EXCEPT.
    Both glob depths (grain fnmatches relative paths) must survive regeneration,
    and the shipped config must equal the sync script's deterministic output."""
    shipped = tomllib.loads((ROOT / "tool-configs" / "grain.toml").read_text())
    for pattern in ("**/lexicon/**", "lexicon/**"):
        assert pattern in shipped["grain"]["exclude"], shipped["grain"]["exclude"]

    repo = tmp_path / "repo"
    qc_root = repo / "tool-configs"
    qc_root.mkdir(parents=True)
    shutil.copytree(ROOT / "tool-configs", qc_root, dirs_exist_ok=True)
    result = subprocess.run(
        ["uv", "run", str(ROOT / "tool-artifacts" / "scripts" / "sync_qc_excludes.py"), str(qc_root / "qc-excludes.toml")],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    regenerated = tomllib.loads((qc_root / "grain.toml").read_text())["grain"]["exclude"]
    for pattern in ("**/lexicon/**", "lexicon/**"):
        assert pattern in regenerated, regenerated


def test_grain_config_excludes_nested_directory_occurrences(
    tmp_path: pathlib.Path,
) -> None:
    """#225 Defect 6: grain matches excludes with fnmatch (grain/runner.py),
    where a root-anchored `node_modules/*` misses a nested
    `pkg/sub/node_modules/x.py` — unlike the JSON tools' `**/{d}/**`. Vendored
    and generated trees deep in the layout must stay out of grain's scan, so
    every TOML-derived directory must be excluded at both depths."""
    import fnmatch

    nested = "packages/app/node_modules/vendored/mod.py"
    shipped = tomllib.loads((ROOT / "tool-configs" / "grain.toml").read_text())["grain"]["exclude"]
    assert any(fnmatch.fnmatch(nested, pat) for pat in shipped), f"nested vendored path not excluded by grain's fnmatch patterns:\n{shipped}"

    # Deterministic SSOT output: regenerating in a temp copy holds the property.
    repo = tmp_path / "repo"
    qc_root = repo / "tool-configs"
    qc_root.mkdir(parents=True)
    shutil.copytree(ROOT / "tool-configs", qc_root, dirs_exist_ok=True)
    result = subprocess.run(
        ["uv", "run", str(ROOT / "tool-artifacts" / "scripts" / "sync_qc_excludes.py"), str(qc_root / "qc-excludes.toml")],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    regenerated = tomllib.loads((qc_root / "grain.toml").read_text())["grain"]["exclude"]
    assert any(fnmatch.fnmatch(nested, pat) for pat in regenerated), regenerated


def test_rust_qc_files_consume_central_excludes(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "rust-project"
    source_dir = project / "src"
    excluded_source_dir = project / "vendor"
    source_dir.mkdir(parents=True)
    excluded_source_dir.mkdir()
    (source_dir / "lib.rs").write_text("pub fn kept() -> u8 { 1 }\n")
    (excluded_source_dir / "ignored.rs").write_text("pub fn ignored() -> u8 { 2 }\n")

    result = run_just(ROOT / "justfiles" / "rust.just", project, "_rust-qc-files")

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "src/lib.rs" in result.stdout
    assert "vendor/ignored.rs" not in result.stdout


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


def load_lint_staged_config() -> dict[str, list[str]]:
    result = subprocess.run(
        [
            "node",
            "--input-type=module",
            "-e",
            "import config from './tool-configs/lintstagedrc.mjs'; console.log(JSON.stringify(config));",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return LINT_STAGED_CONFIG.validate_json(result.stdout)


def test_shared_ast_grep_uses_official_cli_and_central_rules_without_parsing_markdown(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "AESTHETIC-GUIDELINES.md").write_text(
        "\n".join(
            [
                "> From: https://chatgpt.com/c/example",
                "",
                "# transcript",
                "",
                "This prose file is project documentation, not TypeScript.",
                "",
            ]
        )
    )
    source_dir = project / "src"
    source_dir.mkdir()
    (source_dir / "app.ts").write_text(
        "\n".join(
            [
                "export async function loadPlugin() {",
                '  const plugin = await import("./plugin");',
                "  return plugin;",
                "}",
                "",
            ]
        )
    )

    result = run_just(ROOT / "justfiles" / "shared.just", project, "_ast-grep")

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "no-dynamic-import" in output
    assert "SyntaxError" not in output


def test_shared_ast_grep_excludes_user_authored_scripts_and_notebooks(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "project"
    source_dir = project / "src"
    script_dir = project / "research" / "scripts"
    notebook_dir = project / "notebooks"
    source_dir.mkdir(parents=True)
    script_dir.mkdir(parents=True)
    notebook_dir.mkdir(parents=True)
    (source_dir / "app.py").write_text("VALUE = 1\n")
    # The rule is intentionally real and blocking. A generic AST scan must
    # not turn an exploratory research artifact into a defect in that artifact.
    (script_dir / "derivation.py").write_text("CONFIG_VALUE = Field(default=1)\n")
    (notebook_dir / "exploration.py").write_text("CONFIG_VALUE = Field(default=1)\n")

    result = run_just(ROOT / "justfiles" / "shared.just", project, "_ast-grep")

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "no-field-default" not in output


def test_python_ast_grep_uses_official_cli_and_central_rules(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "python-project"
    project.mkdir()
    (project / "app.py").write_text("CONFIG_VALUE = Field(default=1)\n")

    result = run_just(ROOT / "justfiles" / "python.just", project, "_ast-grep")

    # no-field-default carries POLICY.RUNTIME_DEFAULT, a hard bridge-burning
    # policy. A policy-bearing rule must BAN the pattern (block the gate), not
    # emit an ignorable warning. The gate blocks on error[ findings, so the rule
    # must be error-tier and the scan must exit nonzero.
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "no-field-default" in output


def test_python_ast_grep_blocks_dynamic_import(
    tmp_path: pathlib.Path,
) -> None:
    # POLICY.CRITICAL_DEPENDENCY is enforced for TypeScript (await import(...))
    # via no-dynamic-import. Python's equivalent dynamic-import forms —
    # importlib.import_module(...) and __import__(...) — are the same policy
    # violation and must block the Python gate equivalently, not go unaudited.
    project = tmp_path / "python-dynamic-import-project"
    project.mkdir()
    (project / "app.py").write_text(
        "\n".join(
            [
                "import importlib",
                "from importlib import import_module",
                'attr = importlib.import_module("attr_form")',
                'direct = import_module("direct_form")',
                'dunder = __import__("dunder_form")',
                "",
            ]
        )
    )

    result = run_just(ROOT / "justfiles" / "python.just", project, "_ast-grep")

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    # Assert the Python rule id specifically, not a loose prefix that the
    # TypeScript no-dynamic-import rule would also satisfy.
    assert "no-dynamic-import-python" in output


def test_bun_ast_grep_uses_official_cli_and_central_rules_without_parsing_markdown(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "bun-project"
    project.mkdir()
    (project / "AESTHETIC-GUIDELINES.md").write_text(
        "\n".join(
            [
                "> From: https://chatgpt.com/c/example",
                "",
                "# transcript",
                "",
                "This prose file is project documentation, not TypeScript.",
                "",
            ]
        )
    )
    source_dir = project / "src"
    source_dir.mkdir()
    (source_dir / "app.ts").write_text(
        "\n".join(
            [
                "export async function loadPlugin() {",
                '  const plugin = await import("./plugin");',
                "  return plugin;",
                "}",
                "",
            ]
        )
    )

    result = run_just(ROOT / "justfiles" / "bun.just", project, "_ast-grep")

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "no-dynamic-import" in output
    assert "SyntaxError" not in output


def test_lint_staged_ast_grep_uses_official_cli_with_central_config(
    tmp_path: pathlib.Path,
) -> None:
    commands = load_lint_staged_config()
    staged_commands = commands["*.{ts,tsx,js,jsx,mjs,cjs,json,jsonc}"]
    ast_grep_command = staged_commands[1]

    assert staged_commands[0] == "biome check --write --no-errors-on-unmatched"
    assert shlex.split(ast_grep_command) == [
        "npx",
        "-y",
        "--package",
        "@ast-grep/cli",
        "ast-grep",
        "scan",
        "--config",
        str(ROOT / "tool-configs" / "sgconfig.yml"),
    ]

    project = tmp_path / "lint-staged-project"
    project.mkdir()
    source_dir = project / "src"
    source_dir.mkdir()
    (source_dir / "app.ts").write_text(
        "\n".join(
            [
                "export async function loadPlugin() {",
                '  const plugin = await import("./plugin");',
                "  return plugin;",
                "}",
                "",
            ]
        )
    )

    result = subprocess.run(
        [*shlex.split(ast_grep_command), "."],
        cwd=project,
        text=True,
        capture_output=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "no-dynamic-import" in output


def test_lint_staged_runs_biome_before_ast_grep() -> None:
    commands = load_lint_staged_config()

    assert commands["*.{ts,tsx,js,jsx,mjs,cjs,json,jsonc}"][:2] == [
        "biome check --write --no-errors-on-unmatched",
        f"npx -y --package @ast-grep/cli ast-grep scan --config {ROOT / 'tool-configs' / 'sgconfig.yml'}",
    ]


def test_semgrep_autofix_defers_unfixed_findings_to_push_tier(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "semgrep-project"
    project.mkdir()
    source = project / "app.ts"
    source.write_text('const API_URL = "https://example.test";\nconsole.log(API_URL);\n')

    commit_tier = run_just(ROOT / "justfiles" / "shared.just", project, "_semgrep-autofix")
    push_tier = run_just(ROOT / "justfiles" / "shared.just", project, "_semgrep")

    assert commit_tier.returncode == 0, commit_tier.stdout + commit_tier.stderr
    assert source.read_text() == 'const API_URL = "https://example.test";\nconsole.log(API_URL);\n'
    assert push_tier.returncode != 0, push_tier.stdout + push_tier.stderr


def test_semgrep_blocks_typescript_value_defaults(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "semgrep-value-default-project"
    project.mkdir()
    (project / "app.ts").write_text(
        "\n".join(
            [
                "export function pickLabel(maybeLabel: string | null): string {",
                "  return maybeLabel || 'fallback';",
                "}",
                "",
            ]
        )
    )

    result = run_just(ROOT / "justfiles" / "shared.just", project, "_semgrep")

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "ts-no-or-default" in output
    assert "maybeLabel || 'fallback'" in output
    assert "Review the Semgrep finding snippets above" in output
    assert "Route POLICY.RUNTIME_DEFAULT and other POLICY.* findings" in output


def test_semgrep_allows_fail_loud_typescript_guards(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "semgrep-guard-project"
    project.mkdir()
    (project / "guards.ts").write_text(
        "\n".join(
            [
                "export function requireString(value: string | null): string {",
                '  if (!value || value.trim() === "") {',
                '    throw new Error("missing value");',
                "  }",
                "  return value;",
                "}",
                "",
                "export function keepNonEmpty(values: Array<string | null>): string[] {",
                "  let result: string[] = [];",
                "  for (let i = 0; i < values.length; i += 1) {",
                "    let cleaned = values[i]?.trim();",
                '    if (!cleaned || cleaned === "") {',
                "      continue;",
                "    }",
                "    result.push(cleaned);",
                "  }",
                "  return result;",
                "}",
                "",
            ]
        )
    )

    result = run_just(ROOT / "justfiles" / "shared.just", project, "_semgrep")

    output = result.stdout + result.stderr
    assert result.returncode == 0, output


def test_semgrep_scans_tests_tree_for_banned_test_patterns(tmp_path: pathlib.Path) -> None:
    """#214: semgrep's bundled default .semgrepignore excludes tests/, silently
    killing the test-antipattern rules (py-no-monkeypatch and siblings) that are
    designed to fire *in* test files. The gate must scan the tests/ tree, so a
    repo committing those banned patterns goes red."""
    project = tmp_path / "semgrep-tests-scope-project"
    (project / "tests").mkdir(parents=True)
    (project / "tests" / "test_thing.py").write_text(
        "\n".join(
            [
                "import unittest.mock",
                "from unittest.mock import patch",
                "",
                "def test_x(monkeypatch):",
                "    monkeypatch.setattr(x, 'y', z)",
                "    m = MagicMock()",
                "",
                "@pytest.mark.skip",
                "def test_y():",
                "    pass",
                "",
            ]
        )
    )

    result = run_just(ROOT / "justfiles" / "shared.just", project, "_semgrep")

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    for rule in ("py-no-monkeypatch", "py-no-mock-import", "py-no-magicmock", "py-no-skip-test"):
        assert rule in output, f"{rule} did not fire on test-file code:\n{output}"


def test_semgrep_ignores_exported_html_under_notebooks(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "semgrep-notebook-html-project"
    notebook_export = project / "computations" / "notebooks" / "periods" / "fermat-periods-nbviewer.html"
    notebook_export.parent.mkdir(parents=True)
    notebook_export.write_text('<a href="http://example.com">nbviewer export</a>\n')

    result = run_just(ROOT / "justfiles" / "shared.just", project, "_semgrep")

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "fermat-periods-nbviewer.html" not in output


def test_semgrep_preserves_tracked_ignore_and_fails_loud_on_backup_failure(
    tmp_path: pathlib.Path,
) -> None:
    """#225 Defect 1: the _semgrep gate overwrites .semgrepignore to force the
    QC exclude set, backing up any pre-existing file for restore-on-exit. A
    tracked .semgrepignore the recipe did NOT create must survive even when the
    backup step fails, and the gate must fail loud (QC triage) instead of dying
    silently or letting the restore trap rm a file it never created."""
    project = tmp_path / "semgrep-backup-failure-project"
    project.mkdir()
    tracked_ignore = project / ".semgrepignore"
    sentinel = "tests/fixtures/user-owned-exclusion/**\n"
    tracked_ignore.write_text(sentinel)

    # Force the backup step to fail with a real on-PATH mktemp shim — no mock of
    # the recipe itself. The recipe must detect the failure before overwriting.
    shim_dir = tmp_path / "shim"
    shim_dir.mkdir()
    mktemp_shim = shim_dir / "mktemp"
    mktemp_shim.write_text("#!/usr/bin/env bash\nexit 1\n")
    mktemp_shim.chmod(0o755)
    env = os.environ | {"PATH": f"{shim_dir}:{os.environ['PATH']}"}

    result = run_just(ROOT / "justfiles" / "shared.just", project, "_semgrep", env=env)

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert tracked_ignore.read_text() == sentinel, f"tracked .semgrepignore was clobbered:\n{output}"
    assert TRIAGE_MARKER in output, output


def write_fake_npx_slop_scan(tmp_path: pathlib.Path, payload: dict[str, Any]) -> pathlib.Path:
    bin_dir = tmp_path / "fake-bin"
    bin_dir.mkdir()
    npx = bin_dir / "npx"
    npx.write_text(
        f"#!/usr/bin/env bash\ncat <<'JSON'\n{json.dumps(payload)}\nJSON\n",
    )
    npx.chmod(0o755)
    return bin_dir


def write_fake_uvx_vibecheck(
    tmp_path: pathlib.Path,
    payload: dict[str, Any],
    *,
    exit_code: int,
) -> pathlib.Path:
    bin_dir = tmp_path / "fake-bin"
    bin_dir.mkdir()
    uvx = bin_dir / "uvx"
    uvx.write_text(
        f"#!/usr/bin/env bash\ncat <<'JSON'\n{json.dumps(payload)}\nJSON\nexit {exit_code}\n",
    )
    uvx.chmod(0o755)
    return bin_dir


def vibecheck_payload(*findings: dict[str, Any]) -> dict[str, Any]:
    severity_counts = {severity: sum(1 for finding in findings if finding["severity"] == severity) for severity in ("critical", "high", "medium", "low")}
    return {
        "version": "0.1.0",
        "passed": severity_counts["critical"] + severity_counts["high"] == 0,
        "summary": {"rules_run": 49, **severity_counts},
        "findings": list(findings),
        "errors": [],
    }


def test_vibecheck_installs_central_exclusions_without_persisting_them(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "vibe-project"
    project.mkdir()
    ignore_file = project / ".ignore"
    sentinel = "user-owned-pattern"
    ignore_file.write_text(sentinel)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    uvx = fake_bin / "uvx"
    uvx.write_text(
        "#!/usr/bin/env bash\n"
        "for expected in scripts notebooks; do\n"
        "  if ! grep -Fxq \"$expected\" .ignore; then\n"
        "    echo \"missing temporary exclusion: $expected\" >&2\n"
        "    exit 86\n"
        "  fi\n"
        "done\n"
        f"cat <<'JSON'\n{json.dumps(vibecheck_payload())}\nJSON\n",
    )
    uvx.chmod(0o755)
    env = os.environ | {"PATH": f"{fake_bin}:{os.environ['PATH']}"}

    result = run_just(ROOT / "justfiles" / "shared.just", project, "_vibecheck", env=env)

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert ignore_file.read_text() == sentinel


def test_vibecheck_ignores_g141_non_comment_matches(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "vibe-project"
    project.mkdir()
    payload = vibecheck_payload(
        {
            "rule_id": "G141",
            "name": "Research citations in code comments",
            "severity": "high",
            "category": "ai-slop",
            "file": str(project / "src" / "utils" / "doi.ts"),
            "line": 1,
            "content": "export function doiUrl(doi: string): string {",
            "notes": "(Source: ...) or (PMC12345) in code comments = hallucinated authority",
            "two_pass": False,
            "co_occurrence": False,
        },
    )
    env = os.environ | {"PATH": f"{write_fake_uvx_vibecheck(tmp_path, payload, exit_code=1)}:{os.environ['PATH']}"}

    result = run_just(ROOT / "justfiles" / "shared.just", project, "_vibecheck", env=env)

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "ignored 1 G141 non-comment false-positive finding(s)" in output
    assert "vibecheck: 0 findings" in output


def test_vibecheck_ignores_g22_non_empty_except_handlers(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "vibe-project"
    project.mkdir()
    source = project / "app.py"
    source.write_text("try:\n    raise KeyError\nexcept KeyError:\n    raise ValueError('handled')\n")
    payload = vibecheck_payload(
        {
            "rule_id": "G22",
            "name": "Empty except block",
            "severity": "high",
            "category": "ai-slop",
            "file": str(source),
            "line": 3,
            "content": "except KeyError:",
            "notes": "Empty except blocks hide failures",
            "two_pass": False,
            "co_occurrence": False,
        },
    )
    env = os.environ | {"PATH": f"{write_fake_uvx_vibecheck(tmp_path, payload, exit_code=1)}:{os.environ['PATH']}"}

    result = run_just(ROOT / "justfiles" / "shared.just", project, "_vibecheck", env=env)

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "ignored 1 G22 non-empty except-handler false-positive finding(s)" in output
    assert "vibecheck: 0 findings" in output


def test_vibecheck_still_blocks_g141_comment_matches(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "vibe-project"
    project.mkdir()
    payload = vibecheck_payload(
        {
            "rule_id": "G141",
            "name": "Research citations in code comments",
            "severity": "high",
            "category": "ai-slop",
            "file": str(project / "src" / "app.ts"),
            "line": 10,
            "content": "// (Source: imagined paper)",
            "notes": "(Source: ...) or (PMC12345) in code comments = hallucinated authority",
            "two_pass": False,
            "co_occurrence": False,
        },
    )
    env = os.environ | {"PATH": f"{write_fake_uvx_vibecheck(tmp_path, payload, exit_code=1)}:{os.environ['PATH']}"}

    result = run_just(ROOT / "justfiles" / "shared.just", project, "_vibecheck", env=env)

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "Research citations in code comments" in output
    assert TRIAGE_MARKER in output


def aislop_payload(*diagnostics: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "1",
        "score": max(0, 100 - 20 * len(diagnostics)),
        "summary": {
            "errors": sum(1 for d in diagnostics if d["severity"] == "error"),
            "warnings": sum(1 for d in diagnostics if d["severity"] == "warning"),
            "fixable": 0,
            "files": 1,
        },
        "diagnostics": list(diagnostics),
    }


def test_aislop_receives_central_script_and_notebook_exclusions(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "aislop-project"
    project.mkdir()
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    npx = fake_bin / "npx"
    npx.write_text(
        "#!/usr/bin/env bash\n"
        "for expected in '**/scripts/**' '**/notebooks/**'; do\n"
        "  case \"$*\" in\n"
        "    *\"$expected\"*) ;;\n"
        "    *) echo \"missing aislop exclusion: $expected\" >&2; exit 86 ;;\n"
        "  esac\n"
        "done\n"
        f"cat <<'JSON'\n{json.dumps(aislop_payload())}\nJSON\n",
    )
    npx.chmod(0o755)
    env = os.environ | {"PATH": f"{fake_bin}:{os.environ['PATH']}"}

    result = run_just(ROOT / "justfiles" / "shared.just", project, "_aislop", env=env)

    output = result.stdout + result.stderr
    assert result.returncode == 0, output


def test_aislop_blocks_on_error_severity_findings(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "aislop-project"
    project.mkdir()
    payload = aislop_payload(
        {
            "filePath": "app.py",
            "line": 3,
            "rule": "ai-slop/swallowed-exception",
            "severity": "error",
            "message": "Catch block only prints error without proper handling",
        },
    )
    env = os.environ | {"PATH": f"{write_fake_npx_slop_scan(tmp_path, payload)}:{os.environ['PATH']}"}

    result = run_just(ROOT / "justfiles" / "shared.just", project, "_aislop", env=env)

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "ai-slop/swallowed-exception" in output


def test_aislop_surfaces_warnings_without_blocking(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "aislop-project"
    project.mkdir()
    payload = aislop_payload(
        {
            "filePath": "app.py",
            "line": 1,
            "rule": "ai-slop/python-print-debug",
            "severity": "warning",
            "message": "print() left in code",
        },
    )
    env = os.environ | {"PATH": f"{write_fake_npx_slop_scan(tmp_path, payload)}:{os.environ['PATH']}"}

    result = run_just(ROOT / "justfiles" / "shared.just", project, "_aislop", env=env)

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "python-print-debug" in output


def test_aislop_fails_closed_on_unexpected_schema(tmp_path: pathlib.Path) -> None:
    # A parseable-but-unexpected aislop response (no numeric summary counts,
    # no diagnostics array) must NOT be treated as clean: the numeric guards
    # would otherwise fall through and pass the gate. The recipe must fail
    # closed on scanner schema/tooling drift.
    project = tmp_path / "aislop-project"
    project.mkdir()
    payload = {"schemaVersion": "1", "score": 100, "note": "no summary or diagnostics"}
    env = os.environ | {"PATH": f"{write_fake_npx_slop_scan(tmp_path, payload)}:{os.environ['PATH']}"}

    result = run_just(ROOT / "justfiles" / "shared.just", project, "_aislop", env=env)

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "expected schema" in output


def test_repo_aislop_config_disables_print_debug_rule() -> None:
    # The repo's own .aislop/config.yml must parse and keep python-print-debug
    # off (owner policy: prints are signal here, not slop). This is the whole
    # payload of the aislop-signal cleanup — guard it against silent breakage.
    config = yaml.safe_load((ROOT / ".aislop" / "config.yml").read_text())
    assert config["rules"]["ai-slop/python-print-debug"] == "off"
    # No score gate: scores are golfable, so nothing gates on them.
    assert "failBelow" not in (config.get("ci") or {})


def test_slop_scan_ignores_non_gating_structural_heuristics(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "slop-project"
    project.mkdir()
    (project / "app.ts").write_text("export const value = 1;\n")
    shutil.copy(
        ROOT / "tool-configs" / "slop-scan.config.json",
        project / "slop-scan.config.json",
    )
    payload = {
        "summary": {"findingCount": 2},
        "findings": [
            {
                "ruleId": "structure.pass-through-wrappers",
                "severity": "strong",
                "path": "app.ts",
                "location": {"line": 1},
            },
            {
                "ruleId": "structure.directory-fanout-hotspot",
                "severity": "medium",
                "path": "src",
                "location": {"line": 1},
            },
        ],
    }
    env = os.environ | {"PATH": f"{write_fake_npx_slop_scan(tmp_path, payload)}:{os.environ['PATH']}"}

    result = run_just(ROOT / "justfiles" / "bun.just", project, "_slop-scan", env=env)

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "ignored 2 non-gating structural heuristic finding(s)" in output


def test_slop_scan_still_blocks_concrete_slop_findings(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "slop-project"
    project.mkdir()
    (project / "app.ts").write_text("export const value = 1;\n")
    shutil.copy(
        ROOT / "tool-configs" / "slop-scan.config.json",
        project / "slop-scan.config.json",
    )
    payload = {
        "summary": {"findingCount": 2},
        "findings": [
            {
                "ruleId": "structure.pass-through-wrappers",
                "severity": "strong",
                "path": "app.ts",
                "location": {"line": 1},
            },
            {
                "ruleId": "errors.swallowed",
                "severity": "strong",
                "path": "app.ts",
                "location": {"line": 2},
            },
        ],
    }
    env = os.environ | {"PATH": f"{write_fake_npx_slop_scan(tmp_path, payload)}:{os.environ['PATH']}"}

    result = run_just(ROOT / "justfiles" / "bun.just", project, "_slop-scan", env=env)

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "ignored 1 non-gating structural heuristic finding(s)" in output
    assert "errors.swallowed" in output
    assert "structure.pass-through-wrappers" not in output


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


def test_python_scaffold_bare_push_gate_reaches_downstream_preflight_without_working_directory_env(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "python-scaffold-project"
    project.mkdir()
    shutil.copy(ROOT / "scaffolds" / "python" / "justfile", project / "justfile")
    (project / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "scaffold-python-target"',
                'version = "0.1.0"',
                'requires-python = ">=3.14"',
                "",
            ]
        )
    )
    (project / ".envrc").write_text("source_up\n")
    env = os.environ | {"DIRENV_CONFIGURED_CORRECTLY": "1"}

    result = subprocess.run(
        ["just", "test-push"],
        cwd=project,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "Python project must have tests" in output
    assert "the following required arguments were not provided" not in output


def test_python_scaffold_bare_push_gate_breaks_when_just_working_directory_is_exported(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "python-scaffold-project"
    project.mkdir()
    shutil.copy(ROOT / "scaffolds" / "python" / "justfile", project / "justfile")
    (project / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "scaffold-python-target"',
                'version = "0.1.0"',
                'requires-python = ">=3.14"',
                "",
            ]
        )
    )
    (project / ".envrc").write_text('source_up\nexport JUST_WORKING_DIRECTORY="$(pwd -P)"\n')
    env = os.environ | {
        "DIRENV_CONFIGURED_CORRECTLY": "1",
        "JUST_WORKING_DIRECTORY": str(project),
    }

    result = subprocess.run(
        ["just", "test-push"],
        cwd=project,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "the following required arguments were not provided" in output
    assert "--justfile <JUSTFILE>" in output


def test_eslint_flat_config_imports_with_declared_tool_config_deps(
    tmp_path: pathlib.Path,
) -> None:
    tool_config = tmp_path / "tool-configs"
    tool_config.mkdir()
    for file_name in ("package.json", "bun.lock", "eslint.config.js"):
        shutil.copy(ROOT / "tool-configs" / file_name, tool_config / file_name)
    (tool_config / "qc-excludes.toml").write_text('directories = ["central-owned"]\n')

    install = subprocess.run(
        ["bun", "install", "--frozen-lockfile"],
        cwd=tool_config,
        text=True,
        capture_output=True,
        check=False,
    )
    assert install.returncode == 0, install.stdout + install.stderr

    config_import = subprocess.run(
        [
            "node",
            "-e",
            'import("./eslint.config.js").then((config) => console.log(JSON.stringify(config.default[0].ignores)))',
        ],
        cwd=tool_config,
        text=True,
        capture_output=True,
        check=False,
    )
    assert config_import.returncode == 0, config_import.stdout + config_import.stderr
    ignores = json.loads(config_import.stdout)
    assert "**/env.d.ts" in ignores
    assert "**/central-owned/**" in ignores


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
            "test-push",
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


@pytest.mark.parametrize(
    ("language", "project_files", "expected_error", "wrong_root_errors"),
    [
        (
            "bun",
            {
                "package.json": json.dumps({"scripts": {}}) + "\n",
                "bun.lock": "",
            },
            "TypeScript project must have tests",
            (
                "TypeScript project must have a package.json file",
                "TypeScript project must use Bun",
            ),
        ),
        (
            "bun-playwright",
            {
                "package.json": json.dumps({"scripts": {}}) + "\n",
                "bun.lock": "",
            },
            "TypeScript project must have tests",
            (
                "TypeScript project must have a package.json file",
                "TypeScript project must use Bun",
            ),
        ),
        (
            "python",
            {
                "pyproject.toml": "\n".join(
                    [
                        "[project]",
                        'name = "scaffold-python-target"',
                        'version = "0.1.0"',
                        'requires-python = ">=3.14"',
                        "",
                    ]
                ),
            },
            "Python project must have tests",
            ("Python project must have a pyproject.toml file",),
        ),
        (
            "rust",
            {
                "Cargo.toml": "\n".join(
                    [
                        "[package]",
                        'name = "scaffold-rust-target"',
                        'version = "0.1.0"',
                        'edition = "2021"',
                        "",
                    ]
                ),
            },
            "Rust project must have tests",
            ("Rust project must contain at least one Cargo.toml",),
        ),
        (
            "sage",
            {"example.sage": "x = 1\n"},
            # Semantic key, not the copied diagnostic sentence
            # (POLICY.NO_EXACT_STRING_PROOF): the preflight must fail *about*
            # SAGE_BIN, whatever its wording.
            "SAGE_BIN",
            ("no .sage files found",),
        ),
    ],
)
def test_scaffolds_delegate_qc_in_project_directory(
    tmp_path: pathlib.Path,
    language: str,
    project_files: dict[str, str],
    expected_error: str,
    wrong_root_errors: tuple[str, ...],
) -> None:
    project = tmp_path / f"{language}-project"
    project.mkdir()
    for relative_path, contents in project_files.items():
        target = project / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents)

    env = os.environ.copy()
    if language == "sage":
        env.pop("SAGE_BIN", None)

    result = subprocess.run(
        [
            "just",
            "--justfile",
            str(ROOT / "scaffolds" / language / "justfile"),
            "-d",
            str(project),
            "test-commit",
        ],
        cwd=project,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert expected_error in output
    for wrong_root_error in wrong_root_errors:
        assert wrong_root_error not in output


def test_bun_playwright_scaffold_delegates_app_boot_to_global_qc(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "bun-playwright-project"
    project.mkdir()

    result = subprocess.run(
        [
            "just",
            "--dry-run",
            "--justfile",
            str(ROOT / "scaffolds" / "bun-playwright" / "justfile"),
            "-d",
            str(project),
            "app-boot",
        ],
        cwd=project,
        text=True,
        capture_output=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "just -f ~/ai-review-ci/justfiles/bun.just -d . app-boot" in output
    assert "bunx playwright" not in output


def test_bun_playwright_gate_requires_standard_config(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "bun-playwright-project"
    project.mkdir()

    result = subprocess.run(
        [
            "just",
            "--justfile",
            str(ROOT / "justfiles" / "bun.just"),
            "-d",
            str(project),
            "app-boot",
        ],
        cwd=project,
        text=True,
        capture_output=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "playwright.config.ts" in output


@pytest.mark.parametrize(
    ("justfile_name", "recipes"),
    [
        ("bun.just", ("test-commit", "test-push", "test-ci")),
        ("python.just", ("test-commit", "test-push", "test-ci")),
        ("rust.just", ("test-commit", "test-push", "test-ci")),
        ("sage.just", ("test-commit", "test-push", "test-ci")),
    ],
)
def test_language_qc_delegates_nested_global_recipes_in_project_directory(
    tmp_path: pathlib.Path,
    justfile_name: str,
    recipes: tuple[str, ...],
) -> None:
    project = tmp_path / "project"
    project.mkdir()

    for recipe in recipes:
        result = subprocess.run(
            [
                "just",
                "--dry-run",
                "--justfile",
                str(ROOT / "justfiles" / justfile_name),
                "-d",
                str(project),
                recipe,
            ],
            cwd=project,
            text=True,
            capture_output=True,
            check=False,
        )

        output = result.stdout + result.stderr
        assert result.returncode == 0, output
        delegated_lines = [line.strip() for line in output.splitlines() if "just -f " in line]
        assert delegated_lines, output
        for line in delegated_lines:
            assert " -d . " in f" {line} ", line


@pytest.mark.parametrize(
    ("justfile_name", "full_suite_recipe"),
    [
        ("python.just", "_pytest"),
        ("bun.just", "_bun-test"),
        ("rust.just", "_cargo-test"),
        ("sage.just", "_sage-pytest"),
    ],
)
def test_public_gate_composition_separates_immediate_checks_from_full_suite(
    justfile_name: str,
    full_suite_recipe: str,
) -> None:
    text = (ROOT / "justfiles" / justfile_name).read_text()

    commit = re.search(r"(?ms)^test-commit:\n(?P<body>.*?)(?=^# public:)", text)
    push = re.search(r"(?ms)^test-push:\n(?P<body>.*?)(?=^# public:|\Z)", text)
    ci = re.search(r"(?ms)^test-ci:\n(?P<body>.*)\Z", text)

    assert commit is not None
    assert push is not None
    assert ci is not None
    assert full_suite_recipe not in commit.group("body")
    assert full_suite_recipe in push.group("body")
    assert "test-push" in ci.group("body")


@pytest.mark.parametrize(
    "path",
    [
        ROOT / "justfile",
        ROOT / "justfiles" / "python.just",
        ROOT / "justfiles" / "bun.just",
        ROOT / "justfiles" / "rust.just",
        ROOT / "justfiles" / "sage.just",
        ROOT / "justfiles" / "qc-tooling.just",
    ],
)
def test_old_test_gate_alias_is_removed(path: pathlib.Path) -> None:
    assert re.search(r"(?m)^test:", path.read_text()) is None


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
    assert sorted(ROOT.glob(".tsc-output.*")) == []


def test_pytest_installs_dependency_group_requirements(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "python-project"
    package_dir = project / "src" / "dependency_group_project"
    tests_dir = project / "tests"
    package_dir.mkdir(parents=True)
    tests_dir.mkdir()
    (project / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "dependency-group-project"',
                'version = "0.1.0"',
                'requires-python = ">=3.14"',
                "",
                "[dependency-groups]",
                'dev = ["PyYAML"]',
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
    (package_dir / "__init__.py").write_text("VALUE = 1\n")
    (tests_dir / "test_dependency_group.py").write_text(
        "\n".join(
            [
                "import yaml",
                "",
                "",
                "def test_dependency_group_requirement_is_available() -> None:",
                '    assert yaml.safe_load("value: 1") == {"value": 1}',
                "",
            ]
        )
    )

    result = run_just(ROOT / "justfiles" / "python.just", project, "_pytest")

    output = result.stdout + result.stderr
    assert result.returncode == 0, output


def test_pytest_with_coverage_generates_xml_without_total_threshold(
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

    cache_home = tmp_path / "cache"
    result = run_just(
        ROOT / "justfiles" / "python.just",
        project,
        "_pytest_with_coverage",
        env=os.environ | {"XDG_CACHE_HOME": str(cache_home)},
    )

    output = result.stdout + result.stderr
    project_slug = re.sub(r"[^A-Za-z0-9._-]", "_", str(project.resolve()))
    coverage_xml = cache_home / "quality-control" / "coverage" / project_slug / "coverage.xml"
    assert result.returncode == 0, output
    assert coverage_xml.exists()
    assert "Coverage XML report:" in output


def write_import_linter_project(
    project: pathlib.Path,
    *,
    import_sibling: bool = False,
    local_importlinter_override: bool = False,
) -> None:
    package_a = project / "src" / "import_linter_a"
    package_b = project / "src" / "import_linter_b"
    tests_dir = project / "tests"
    package_a.mkdir(parents=True)
    package_b.mkdir(parents=True)
    tests_dir.mkdir()
    pyproject_lines = [
        "[project]",
        'name = "import-linter-project"',
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
    if local_importlinter_override:
        pyproject_lines.extend(
            [
                "[tool.importlinter]",
                'root_packages = ["import_linter_a"]',
                "",
            ]
        )
    (project / "pyproject.toml").write_text("\n".join(pyproject_lines))
    package_a_init = "from import_linter_b import VALUE as SIBLING_VALUE\nVALUE = SIBLING_VALUE\n" if import_sibling else "VALUE = 1\n"
    (package_a / "__init__.py").write_text(package_a_init)
    (package_b / "__init__.py").write_text("VALUE = 2\n")
    (tests_dir / "test_import_linter_project.py").write_text(
        "\n".join(
            [
                "from import_linter_a import VALUE",
                "",
                "",
                "def test_value() -> None:",
                "    assert VALUE",
                "",
            ]
        )
    )


def test_python_preflight_rejects_local_importlinter_pyproject_override(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "local-importlinter-project"
    project.mkdir()
    write_import_linter_project(project, local_importlinter_override=True)

    result = run_just(ROOT / "justfiles" / "python.just", project, "_check-python-project")
    output = result.stdout + result.stderr

    assert result.returncode != 0, output
    assert r"\[tool\.importlinter" in output
    assert TRIAGE_MARKER in output


def test_import_linter_uses_central_config_without_downstream_override(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "central-importlinter-project"
    project.mkdir()
    write_import_linter_project(project)

    result = run_just(ROOT / "justfiles" / "python.just", project, "_import-linter")
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "First-party packages are independent KEPT" in output


def test_import_linter_blocks_sibling_imports_without_local_override(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "central-importlinter-failure-project"
    project.mkdir()
    write_import_linter_project(project, import_sibling=True)

    result = run_just(ROOT / "justfiles" / "python.just", project, "_import-linter")
    output = result.stdout + result.stderr

    assert result.returncode != 0, output
    assert "First-party packages are independent BROKEN" in output
    assert "import_linter_a is not allowed to import import_linter_b" in output
    assert TRIAGE_MARKER in output


def test_import_linter_ignores_local_override_when_recipe_is_called_directly(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "ignored-local-importlinter-project"
    project.mkdir()
    write_import_linter_project(
        project,
        import_sibling=True,
        local_importlinter_override=True,
    )

    result = run_just(ROOT / "justfiles" / "python.just", project, "_import-linter")
    output = result.stdout + result.stderr

    assert result.returncode != 0, output
    assert "First-party packages are independent BROKEN" in output
    assert "import_linter_a is not allowed to import import_linter_b" in output


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
                '    "markdown-it-py>=3",',
                '    "python-frontmatter>=1.3",',
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
                "import frontmatter",
                "import yaml",
                "from markdown_it import MarkdownIt",
                "from slugify import slugify",
                "",
                'VALUE = yaml.safe_dump({"html": MarkdownIt().render("# A"), "metadata": frontmatter.Post("").metadata, "slug": slugify("A B")})',
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


def test_deptry_allows_framework_required_import_invisible_dependencies(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "framework-runtime-dependency-project"
    package_dir = project / "src" / "framework_runtime_dependency_project"
    package_dir.mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "framework-runtime-dependency-project"',
                'version = "0.1.0"',
                'requires-python = ">=3.14"',
                "dependencies = [",
                '    "fastapi>=0.115",',
                '    "python-multipart>=0.0.20",',
                "]",
                "",
            ]
        )
    )
    (package_dir / "__init__.py").write_text(
        "\n".join(
            [
                "from fastapi import FastAPI, File",
                "",
                "app = FastAPI()",
                "",
                '@app.post("/upload")',
                "async def upload(payload: bytes = File(...)) -> int:",
                "    return len(payload)",
                "",
            ]
        )
    )

    result = run_just(ROOT / "justfiles" / "python.just", project, "_deptry")
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "DEP002" not in output


def test_deptry_still_blocks_missing_import_dependencies(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "missing-dependency-project"
    package_dir = project / "src" / "missing_dependency_project"
    package_dir.mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "missing-dependency-project"',
                'version = "0.1.0"',
                'requires-python = ">=3.14"',
                "dependencies = []",
                "",
            ]
        )
    )
    (package_dir / "__init__.py").write_text(
        "\n".join(
            [
                "import requests",
                "",
                'VALUE = requests.get("https://example.com", timeout=1).status_code',
                "",
            ]
        )
    )

    result = run_just(ROOT / "justfiles" / "python.just", project, "_deptry")
    output = result.stdout + result.stderr

    assert result.returncode != 0, output
    assert "DEP001" in output
    assert "missing/import dependency issues" in output
    assert TRIAGE_MARKER in output


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


def test_deptry_checks_non_src_python_files_in_src_layout(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "mixed-root-project"
    package_dir = project / "src" / "mixed_root_project"
    tools_dir = project / "tools"
    package_dir.mkdir(parents=True)
    tools_dir.mkdir()
    (project / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "mixed-root-project"',
                'version = "0.1.0"',
                'requires-python = ">=3.14"',
                "dependencies = []",
                "",
            ]
        )
    )
    (package_dir / "__init__.py").write_text("VALUE = 42\n")
    (tools_dir / "uses_slugify.py").write_text(
        "\n".join(
            [
                "from slugify import slugify",
                "",
                'VALUE = slugify("A B")',
                "",
            ]
        )
    )

    result = run_just(ROOT / "justfiles" / "python.just", project, "_deptry")
    output = result.stdout + result.stderr

    assert result.returncode != 0, output
    assert TRIAGE_MARKER in output


def test_deptry_accepts_multiple_declared_first_party_modules(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "multi-first-party-project"
    app_dir = project / "src" / "multi_first_party_project"
    plugin_a_dir = project / "first_party" / "plugin_a"
    plugin_b_dir = project / "first_party" / "plugin_b"
    app_dir.mkdir(parents=True)
    plugin_a_dir.mkdir(parents=True)
    plugin_b_dir.mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "multi-first-party-project"',
                'version = "0.1.0"',
                'requires-python = ">=3.14"',
                "dependencies = []",
                "",
                "[tool.hatch.build.targets.wheel]",
                'packages = ["first_party/plugin_a", "first_party/plugin_b"]',
                "",
            ]
        )
    )
    (app_dir / "__init__.py").write_text(
        "\n".join(
            [
                "from plugin_a import VALUE_A",
                "from plugin_b import VALUE_B",
                "",
                "RESULT = VALUE_A + VALUE_B",
                "",
            ]
        )
    )
    (plugin_a_dir / "__init__.py").write_text("VALUE_A = 20\n")
    (plugin_b_dir / "__init__.py").write_text("VALUE_B = 22\n")

    result = run_just(ROOT / "justfiles" / "python.just", project, "_deptry")

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


def test_commit_gate_stops_at_doctor_preflight_before_typechecking(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "missing-pyproject-project"
    package_dir = project / "src" / "missing_pyproject_project"
    tests_dir = project / "tests"
    package_dir.mkdir(parents=True)
    tests_dir.mkdir()
    (package_dir / "__init__.py").write_text("import yaml\n")
    (tests_dir / "test_placeholder.py").write_text("def test_placeholder() -> None:\n    assert True\n")

    (project / "justfile").write_text((ROOT / "scaffolds" / "python" / "justfile").read_text())

    result = run_just(ROOT / "justfiles" / "python.just", project, "test-commit")
    output = result.stdout + result.stderr

    assert result.returncode != 0, output
    assert "QC doctor preflight failed" in output
    assert "does not satisfy its declared 'python' profile; missing: pyproject.toml" in output
    assert "Running: mypy type checking" not in output
    assert 'Library stubs not installed for "yaml"' not in output


def test_python_subgate_doctor_preflight_accepts_central_bun_python_profile(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "composite-project"
    project.mkdir()
    (project / "pyproject.toml").write_text('[project]\nname = "composite-project"\nversion = "0.1.0"\n')
    (project / "package.json").write_text('{"scripts": {}}\n')
    (project / "bun.lock").write_text("")
    (project / "justfile").write_text((ROOT / "scaffolds" / "bun-python" / "justfile").read_text())

    result = run_just(ROOT / "justfiles" / "python.just", project, "_doctor-preflight")
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "QC doctor preflight passed" in output


def test_mypy_private_recipe_does_not_apply_python_project_preflight_to_sage_pass(
    tmp_path: pathlib.Path,
) -> None:
    project = project_with_sage_file(tmp_path)
    (project / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "sage-support"',
                'version = "0.1.0"',
                'requires-python = ">=3.14"',
                "dependencies = []",
                "",
                "[build-system]",
                'requires = ["setuptools"]',
                'build-backend = "setuptools.build_meta"',
                "",
            ]
        )
    )
    (project / "support.py").write_text("VALUE: int = 1\n")

    result = run_just(ROOT / "justfiles" / "python.just", project, "_mypy")
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "Python project preflight check" not in output


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


def test_mypy_ignores_pep723_script_without_dependencies(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "empty-script-metadata-project"
    package_dir = project / "src" / "empty_script_metadata_project"
    script_dir = project / "tool-artifacts" / "scripts"
    package_dir.mkdir(parents=True)
    script_dir.mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "empty-script-metadata-project"',
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
    (package_dir / "__init__.py").write_text("VALUE: int = 42\n")
    (script_dir / "read_config.py").write_text(
        "\n".join(
            [
                "# /// script",
                "# ///",
                "",
                "from pathlib import Path",
                "",
                "",
                "def read_config(path: Path) -> str:",
                "    return path.read_text()",
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
    assert "Unexpected '\"'" not in output


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
        env=os.environ | {"AI_REVIEW_CI_FAILURE_MODE": "triage"},
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


# Regression for #17: just >= 1.46 binds JUST_WORKING_DIRECTORY to
# -d/--working-directory, which then requires --justfile — so any consumer that
# exported JUST_WORKING_DIRECTORY (the old delegated-gate routing hint) could no
# longer run a bare public gate. The scaffolds resolve this by routing with an
# explicit `-d .` and never exporting JUST_WORKING_DIRECTORY, so the bare
# entrypoint keeps working. These tests lock both halves of that contract.

SCAFFOLD_DELEGATES = {
    "python": ("python.just",),
    "rust": ("rust.just",),
    "bun": ("bun.just",),
    "bun-playwright": ("bun.just",),
    "bun-python": ("python.just", "bun.just"),
    "sage": ("sage.just",),
}


def test_direct_failure_mode_forbids_review_ceremony() -> None:
    result = subprocess.run(
        [str(ROOT / "tool-artifacts" / "scripts" / "emit-triage-directive.sh")],
        env=os.environ | {"AI_REVIEW_CI_FAILURE_MODE": "direct"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "DIRECT REPAIR REQUIRED" in result.stdout
    assert "does not enter returned-PR-feedback triage" in result.stdout
    assert "TRIAGE REQUIRED" not in result.stdout
    assert "subagent" in result.stdout


def test_ci_failure_mode_retains_anti_golfing_triage() -> None:
    result = subprocess.run(
        [str(ROOT / "tool-artifacts" / "scripts" / "emit-triage-directive.sh")],
        env=os.environ | {"AI_REVIEW_CI_FAILURE_MODE": "triage"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "QC FAILURE — TRIAGE REQUIRED" in result.stdout
    assert "golf" in result.stdout
    assert "subagent" in result.stdout


@pytest.mark.parametrize("language", sorted(SCAFFOLD_DELEGATES))
@pytest.mark.parametrize("recipe", ["test-commit", "test-push", "test-ci"])
def test_scaffold_bare_just_entrypoint_survives_working_directory_binding(
    tmp_path: pathlib.Path,
    language: str,
    recipe: str,
) -> None:
    """A bare `just <recipe>` in a scaffold consumer parses and routes under
    just >= 1.46 without a JUST_WORKING_DIRECTORY export (#17)."""
    project = tmp_path / f"{language}-project"
    project.mkdir()
    (project / "justfile").write_text((ROOT / "scaffolds" / language / "justfile").read_text())

    clean_env = {k: v for k, v in os.environ.items() if k != "JUST_WORKING_DIRECTORY"}
    result = subprocess.run(
        ["just", "--dry-run", recipe],
        cwd=project,
        env=clean_env,
        text=True,
        capture_output=True,
        check=False,
    )
    output = result.stdout + result.stderr
    # The bug manifested as a just arg-parse failure ("required ... --justfile")
    # before any recipe ran; a clean parse + route is the fix.
    assert result.returncode == 0, output
    for justfile_name in SCAFFOLD_DELEGATES[language]:
        assert f"-f ~/ai-review-ci/justfiles/{justfile_name}" in output
    assert "-d ." in output
    assert recipe in output


@pytest.mark.parametrize("language", sorted(SCAFFOLD_DELEGATES))
def test_scaffold_does_not_export_working_directory_routing_hint(language: str) -> None:
    """No scaffold may reintroduce a JUST_WORKING_DIRECTORY export: under just
    >= 1.46 that env var alone breaks bare `just` argument parsing (#17)."""
    scaffold = (ROOT / "scaffolds" / language / "justfile").read_text()
    assert "JUST_WORKING_DIRECTORY" not in scaffold


# The collision itself (JUST_WORKING_DIRECTORY set -> bare `just` fails at
# arg-parse) is covered with the real delegated chain by
# test_python_scaffold_bare_just_test_breaks_when_just_working_directory_is_exported.


def test_docs_and_configs_qc_routes_formatting_and_link_validation(tmp_path: pathlib.Path) -> None:
    commit = subprocess.run(
        [
            "just",
            "--dry-run",
            "--justfile",
            str(ROOT / "justfiles" / "docs-and-configs.just"),
            "-d",
            str(tmp_path),
            "test-commit",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    push = subprocess.run(
        [
            "just",
            "--dry-run",
            "--justfile",
            str(ROOT / "justfiles" / "docs-and-configs.just"),
            "-d",
            str(tmp_path),
            "test-push",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    links = subprocess.run(
        [
            "just",
            "--dry-run",
            "--justfile",
            str(ROOT / "justfiles" / "docs-and-configs.just"),
            "-d",
            str(tmp_path),
            "_check-links",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    profile_justfile = str(ROOT / "justfiles" / "docs-and-configs.just")

    assert commit.returncode == 0, commit.stderr
    assert f"--justfile {profile_justfile} _format-structured-text" in commit.stderr
    assert push.returncode == 0, push.stderr
    assert f"--justfile {profile_justfile} _check-links" in push.stderr
    assert links.returncode == 0, links.stderr
    assert "lychee --no-progress" in links.stderr
