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
from pydantic import TypeAdapter

ROOT = pathlib.Path(__file__).resolve().parents[1]
TRIAGE_MARKER = "QC FAILURE"
LINT_STAGED_CONFIG = TypeAdapter(dict[str, list[str]])


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


def project_with_sage_file(tmp_path: pathlib.Path) -> pathlib.Path:
    project = tmp_path / "sage-project"
    project.mkdir()
    (project / "example.sage").write_text("x = 1\n")
    return project


def test_no_bypass_ignores_preexisting_markers_when_staging_other_changes(tmp_path: pathlib.Path) -> None:
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


def test_python_ast_grep_uses_official_cli_and_central_rules(
    tmp_path: pathlib.Path,
) -> None:
    project = tmp_path / "python-project"
    project.mkdir()
    (project / "app.py").write_text("CONFIG_VALUE = Field(default=1)\n")

    result = run_just(ROOT / "justfiles" / "python.just", project, "_ast-grep")

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "no-field-default" in output


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


def test_vibecheck_ignores_g22_non_empty_except_handlers(tmp_path: pathlib.Path) -> None:
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


def test_slop_scan_ignores_non_gating_structural_heuristics(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "slop-project"
    project.mkdir()
    (project / "app.ts").write_text("export const value = 1;\n")
    shutil.copy(ROOT / "tool-configs" / "slop-scan.config.json", project / "slop-scan.config.json")
    payload = {
        "summary": {"findingCount": 2},
        "findings": [
            {"ruleId": "structure.pass-through-wrappers", "severity": "strong", "path": "app.ts", "location": {"line": 1}},
            {"ruleId": "structure.directory-fanout-hotspot", "severity": "medium", "path": "src", "location": {"line": 1}},
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
    shutil.copy(ROOT / "tool-configs" / "slop-scan.config.json", project / "slop-scan.config.json")
    payload = {
        "summary": {"findingCount": 2},
        "findings": [
            {"ruleId": "structure.pass-through-wrappers", "severity": "strong", "path": "app.ts", "location": {"line": 1}},
            {"ruleId": "errors.swallowed", "severity": "strong", "path": "app.ts", "location": {"line": 2}},
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
            "SAGE_BIN must be set",
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
            "test",
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


def test_bun_playwright_scaffold_delegates_app_boot_to_global_qc(tmp_path: pathlib.Path) -> None:
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
        ("bun.just", ("test", "test-ci")),
        ("python.just", ("test", "test-ci")),
        ("rust.just", ("test", "test-ci")),
        ("sage.just", ("test", "test-ci")),
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
