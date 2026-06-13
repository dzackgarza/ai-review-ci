import subprocess
import sys
from pathlib import Path


def test_diff_scope_prompt_inlines_diff_and_skips_repo_docs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("irrelevant repository overview\n")
    (repo / "AGENTS.md").write_text("run tree before every local exploration\n")
    (repo / ".reviewer-diff.patch").write_text("diff --git a/src/app.py b/src/app.py\n--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-old\n+new\n")

    scope = tmp_path / "scope-diff.md"
    scope.write_text("Read the diff first.\n")
    reviews_root = tmp_path / "reviews"
    manifest_dir = reviews_root / "slop"
    manifest_dir.mkdir(parents=True)
    manifest = manifest_dir / "manifest.txt"
    manifest.write_text("manifest-doc.md\n")
    (reviews_root / "manifest-doc.md").write_text("review doctrine\n")
    context = tmp_path / "context.md"
    context.write_text("prior alert context\n")
    template = tmp_path / "template.md"
    template.write_text("write submitted.json\n")

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "from pathlib import Path; "
                "from ai_review_ci.harness import build_initial_prompt; "
                "print("
                "build_initial_prompt(*(Path(arg) for arg in sys.argv[1:])), "
                "end=''"
                ")"
            ),
            str(template),
            str(scope),
            str(manifest),
            str(context),
            str(repo),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    prompt = result.stdout

    assert "## Pull Request Unified Diff" in prompt
    assert "diff --git a/src/app.py b/src/app.py" in prompt
    assert "irrelevant repository overview" not in prompt
    assert "run tree before every local exploration" not in prompt


def test_reviewer_path_contract_does_not_expose_just() -> None:
    runner = Path("ci/runner.just").read_text()

    assert 'PATH="{{reviewer_home}}/bin:/usr/bin:/bin"' in runner
    assert "/usr/local/bin/opencode --version" in runner
    assert "/usr/local/bin/uv run --project {{reviewer_infra}}" in runner
