import json
import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest
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


def test_check_pr_description_reads_target_checkout_not_infra() -> None:
    # Wiring contract (#155/cubic P1): the pr-description gate detects the target
    # repo's installed PR template, so it must read the target checkout
    # (control_repo := GITHUB_WORKSPACE), not the infra clone the recipe runs from.
    # Without --repo-root the process cwd is the infra checkout and an installed
    # template is never detected in CI.
    runner = Path("ci/runner.just").read_text()

    assert 'control_repo := env_var("GITHUB_WORKSPACE")' in runner
    recipe = runner.split("check-pr-description pr_number:", 1)[1].split("\n\n", 1)[0]
    assert '--repo-root "{{control_repo}}"' in recipe


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


def test_opencode_config_from_env_requires_every_value() -> None:
    # Acceptance #1: the opencode seams are a *required* config surface — a missing
    # value crashes at the boundary, it does not fall back to a baked-in default.
    from ai_review_ci.harness import OpencodeConfig

    complete = {
        "AI_REVIEW_OPENCODE_BIN": "/usr/local/bin/opencode",
        "AI_REVIEW_OPENCODE_TIMEOUT": "600",
        "AI_REVIEW_MAX_ATTEMPTS": "5",
        "AI_REVIEW_BACKOFF": "5",
    }
    config = OpencodeConfig.from_env(complete)
    assert config.binary == Path("/usr/local/bin/opencode")
    assert config.timeout == 600

    for missing in complete:
        with pytest.raises(KeyError):
            OpencodeConfig.from_env({k: v for k, v in complete.items() if k != missing})


def _write_review_inputs(repo: Path) -> dict[str, Path]:
    """Minimal real reviewer inputs for a non-diff (repo-sweep) run."""
    reviews = repo / "reviews"
    (reviews / "general").mkdir(parents=True)
    manifest = reviews / "general" / "manifest.txt"
    manifest.write_text("doc.md\n")
    (reviews / "doc.md").write_text("review doctrine\n")
    template = repo / "template.md"
    template.write_text("write the report\n")
    scope = repo / "scope-general.md"
    scope.write_text("sweep the whole repo\n")
    context = repo / "context.md"
    context.write_text("no prior findings\n")
    return {"template": template, "scope": scope, "manifest": manifest, "context": context}


def test_run_review_final_fatal_reflects_only_last_attempt_outcome(tmp_path: Path) -> None:
    # Regression lock for the last_timeout reset (commit 47a605b): attempt 1 times out,
    # attempt 2 fails by producing no artifact (no timeout). The terminal FATAL must
    # report ONLY the final attempt's outcome — a missing artifact — not the earlier
    # timeout. Real subprocess, real TimeoutExpired, no mocks.
    repo = tmp_path / "repo"
    repo.mkdir()
    inputs = _write_review_inputs(repo)

    # Fake opencode: first attempt (`run`) hangs past the timeout; the retry (`run -c`)
    # exits cleanly without ever writing the report artifact.
    fake = tmp_path / "opencode"
    fake.write_text(
        dedent(
            """\
            #!/usr/bin/env bash
            for a in "$@"; do
              [ "$a" = "-c" ] && exit 0
            done
            sleep 30
            """
        )
    )
    fake.chmod(0o755)

    env = os.environ | {
        "AI_REVIEW_OPENCODE_BIN": str(fake),
        "AI_REVIEW_OPENCODE_TIMEOUT": "1",
        "AI_REVIEW_MAX_ATTEMPTS": "2",
        "AI_REVIEW_BACKOFF": "0",
    }
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            ("import sys; from pathlib import Path; from ai_review_ci.harness import run_review; run_review(*(Path(arg) for arg in sys.argv[1:]))"),
            str(inputs["template"]),
            str(inputs["scope"]),
            str(inputs["manifest"]),
            str(inputs["context"]),
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    fatal = [line for line in result.stderr.splitlines() if line.startswith("FATAL:")]
    assert fatal == ["FATAL: No report artifact after 2 attempts"]


def test_qc_doctor_upload_runs_after_failed_gate_without_weakening_gate() -> None:
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "_gates.yml").read_text())
    steps = workflow["jobs"]["qc-doctor"]["steps"]
    check_step = next(step for step in steps if step.get("name") == "Check QC doctor")
    upload_step = next(step for step in steps if step.get("name") == "Upload QC doctor payload")

    assert "continue-on-error" not in check_step
    assert upload_step["if"] == "${{ always() }}"
    assert upload_step["with"]["path"] == ".ai-review-ci-doctor.json"
