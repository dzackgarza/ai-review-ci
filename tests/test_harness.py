import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


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


def test_real_diff_scope_prompt_names_submission_contract(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".reviewer-diff.patch").write_text("diff --git a/src/app.py b/src/app.py\n")
    context = tmp_path / "context.md"
    context.write_text("No prior findings.\n")

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
            "reviews/slop/template.md",
            "reviews/scope-diff.md",
            "reviews/slop/manifest.txt",
            str(context),
            str(repo),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    prompt = result.stdout

    assert ".agents/review-runner/candidates/submitted.json" in prompt
    assert "/home/reviewer/bin/submit-candidate --help" in prompt
    assert "Then run `/home/reviewer/bin/submit-candidate`" in prompt
    assert "Do not inspect `quality-control/ci`" in prompt
    assert "npx submit-candidate" not in prompt
    assert "uvx submit-candidate" not in prompt
    assert "opx submit-candidate" not in prompt


def test_retry_prompt_uses_absolute_submit_candidate_path(tmp_path: Path) -> None:
    from ai_review_ci.harness import retry_prompt

    submitted = tmp_path / ".agents" / "review-runner" / "candidates" / "submitted.json"
    prompt = retry_prompt(submitted)

    assert str(submitted) in prompt
    assert "/home/reviewer/bin/submit-candidate with no arguments" in prompt
    assert "run submit-candidate with no arguments" not in prompt


def test_reviewer_path_contract_does_not_expose_just() -> None:
    runner = Path("ci/runner.just").read_text()

    assert 'PATH="{{reviewer_home}}/bin:/usr/bin:/bin"' in runner
    assert "/usr/local/bin/opencode --version" in runner
    assert "/usr/local/bin/uv run --project {{reviewer_infra}}" in runner


def test_qc_doctor_runner_emits_fenced_payload_and_preserves_failure(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    subprocess.run(["git", "init", "-q", str(target)], check=True)
    env = os.environ | {"GITHUB_WORKSPACE": str(target)}

    result = subprocess.run(
        ["just", "-f", str(ROOT / "ci" / "runner.just"), "check-qc-doctor"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    payload_text = (target / ".ai-review-ci-doctor.json").read_text()
    payload = json.loads(payload_text)
    assert result.returncode == 1
    assert payload["global_status"] == "misconfigured"
    assert f"```ai-review-ci-doctor-json\n{payload_text}" in result.stdout
    assert result.stdout.rstrip().endswith("```")


def test_qc_doctor_upload_runs_after_failed_gate_without_weakening_gate() -> None:
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "_gates.yml").read_text())
    steps = workflow["jobs"]["qc-doctor"]["steps"]
    check_step = next(step for step in steps if step.get("name") == "Check QC doctor")
    upload_step = next(step for step in steps if step.get("name") == "Upload QC doctor payload")

    assert "continue-on-error" not in check_step
    assert upload_step["if"] == "${{ always() }}"
    assert upload_step["with"]["path"] == ".ai-review-ci-doctor.json"
