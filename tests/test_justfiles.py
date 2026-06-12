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
