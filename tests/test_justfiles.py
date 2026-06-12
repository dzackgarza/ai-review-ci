import pathlib
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
