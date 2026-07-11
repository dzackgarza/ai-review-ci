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


def _prompt_inputs(tmp_path: Path, scope_name: str) -> dict[str, Path]:
    """Real prompt-assembly inputs for direct build_initial_prompt calls."""
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    scope = tmp_path / scope_name
    scope.write_text("scope instructions\n")
    reviews_root = tmp_path / "reviews"
    manifest_dir = reviews_root / "general"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest_dir / "manifest.txt"
    manifest.write_text("manifest-doc.md\n")
    (reviews_root / "manifest-doc.md").write_text("review doctrine\n")
    context = tmp_path / "context.md"
    context.write_text("prior alert context\n")
    template = tmp_path / "template.md"
    template.write_text("write submitted.json\n")
    return {"repo": repo, "scope": scope, "manifest": manifest, "context": context, "template": template}


def test_policy_docs_and_focus_prompt_are_inlined(tmp_path: Path) -> None:
    from ai_review_ci.harness import build_initial_prompt

    inputs = _prompt_inputs(tmp_path, "scope-repo.md")
    docs = inputs["repo"] / "docs"
    docs.mkdir()
    (docs / "STYLE.md").write_text("terminology must match the drift dictionary\n")
    (inputs["repo"] / "AGENTS.md").write_text("repo agents doc\n")

    prompt = build_initial_prompt(
        inputs["template"],
        inputs["scope"],
        inputs["manifest"],
        inputs["context"],
        inputs["repo"],
        policy_paths="# comment line\ndocs/STYLE.md\n\n",
        focus_prompt="Focus on mathematical correctness of lattice invariants.",
    )

    assert "## Repository Review Focus" in prompt
    assert "Focus on mathematical correctness of lattice invariants." in prompt
    assert "### Policy document: docs/STYLE.md" in prompt
    assert "terminology must match the drift dictionary" in prompt
    # Declared policy docs and focus text precede the task template.
    assert prompt.index("Focus on mathematical correctness") < prompt.index("write submitted.json")
    assert prompt.index("terminology must match") < prompt.index("write submitted.json")


def test_policy_docs_are_inlined_even_in_diff_scope(tmp_path: Path) -> None:
    # PR-diff scope skips auto-collected README/AGENTS docs, but explicitly
    # declared policy documents are repo-owned configuration and must reach
    # the reviewer in every scope.
    from ai_review_ci.harness import build_initial_prompt

    inputs = _prompt_inputs(tmp_path, "scope-diff.md")
    (inputs["repo"] / ".reviewer-diff.patch").write_text("diff --git a/x b/x\n")
    (inputs["repo"] / "README.md").write_text("auto-collected repo overview\n")
    (inputs["repo"] / "POLICY.md").write_text("declared policy content\n")

    prompt = build_initial_prompt(
        inputs["template"],
        inputs["scope"],
        inputs["manifest"],
        inputs["context"],
        inputs["repo"],
        policy_paths="POLICY.md",
        focus_prompt="",
    )

    assert "declared policy content" in prompt
    assert "auto-collected repo overview" not in prompt
    assert "## Repository Review Focus" not in prompt


def test_context_packet_is_inlined_with_prompt_first(tmp_path: Path) -> None:
    from ai_review_ci.harness import build_initial_prompt

    inputs = _prompt_inputs(tmp_path, "scope-repo.md")
    packet = inputs["repo"] / ".review-context"
    (packet / "policies").mkdir(parents=True)
    (packet / "PROMPT.md").write_text("Review focus: lattice invariants against the spec.\n")
    (packet / "policies" / "terminology.md").write_text("saturation and discriminant triple are distinct terms\n")
    (packet / "fixtures.json").write_text("{}\n")

    prompt = build_initial_prompt(
        inputs["template"],
        inputs["scope"],
        inputs["manifest"],
        inputs["context"],
        inputs["repo"],
    )

    assert "## Repository Review Packet" in prompt
    assert "Review focus: lattice invariants against the spec." in prompt
    assert "### Review packet document: policies/terminology.md" in prompt
    assert "saturation and discriminant triple are distinct terms" in prompt
    assert "- .review-context/fixtures.json" in prompt
    # PROMPT.md leads the packet section, before the inlined documents.
    assert prompt.index("Review focus: lattice invariants") < prompt.index("### Review packet document:")
    assert prompt.index("## Repository Review Packet") < prompt.index("write submitted.json")


def test_absent_context_packet_adds_nothing_and_empty_packet_is_fatal(tmp_path: Path) -> None:
    from ai_review_ci.harness import build_initial_prompt, context_packet_section

    inputs = _prompt_inputs(tmp_path, "scope-repo.md")
    prompt = build_initial_prompt(
        inputs["template"],
        inputs["scope"],
        inputs["manifest"],
        inputs["context"],
        inputs["repo"],
    )
    assert "## Repository Review Packet" not in prompt

    # A staged-but-empty packet is a broken assembly, not a valid no-op.
    (inputs["repo"] / ".review-context").mkdir()
    with pytest.raises(SystemExit):
        context_packet_section(inputs["repo"])


def test_review_workflow_stages_context_packet_conditionally() -> None:
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "_review.yml").read_text())
    inputs = workflow[True]["workflow_call"]["inputs"]
    assert inputs["context_archive"]["type"] == "string"
    assert inputs["context_archive"]["default"] == ""

    steps = workflow["jobs"]["review"]["steps"]
    stage = next(step for step in steps if step.get("name") == "Stage review context packet")
    assert stage["if"] == "inputs.context_archive != ''"
    assert "stage-context-packet" in stage["run"]
    # The packet is staged after prepare (which rsyncs the reviewer repo copy)
    # and before the review runs, so the exploded tree survives into the run.
    names = [step.get("name") for step in steps]
    assert names.index("Prepare reviewer") < names.index("Stage review context packet") < names.index("Run review")


def test_missing_policy_doc_is_fatal(tmp_path: Path) -> None:
    from ai_review_ci.harness import policy_docs_section

    repo = tmp_path / "repo"
    repo.mkdir()

    with pytest.raises(SystemExit):
        policy_docs_section("docs/DOES_NOT_EXIST.md", repo)


def test_review_workflow_advisory_skips_only_enforcement() -> None:
    # Advisory mode must not let findings determine the workflow conclusion,
    # while every infrastructure step still runs and can fail the run.
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "_review.yml").read_text())
    inputs = workflow[True]["workflow_call"]["inputs"]

    assert inputs["advisory"]["type"] == "boolean"
    assert inputs["advisory"]["default"] is False
    assert inputs["policy_paths"]["type"] == "string"
    assert inputs["focus_prompt"]["type"] == "string"

    steps = workflow["jobs"]["review"]["steps"]
    enforce = next(step for step in steps if step.get("name") == "Enforce review status")
    assert enforce["if"] == "${{ !inputs.advisory }}"
    guarded = [step["name"] for step in steps if "!inputs.advisory" in str(step.get("if", ""))]
    assert guarded == ["Enforce review status"]


def test_retry_prompt_uses_absolute_submit_candidate_path(tmp_path: Path) -> None:
    from ai_review_ci.harness import retry_prompt

    submitted = tmp_path / ".agents" / "review-runner" / "candidates" / "submitted.json"
    prompt = retry_prompt(submitted)

    assert str(submitted) in prompt
    assert "/home/reviewer/bin/submit-candidate with no arguments" in prompt
    assert "run submit-candidate with no arguments" not in prompt


def test_ensure_blocking_stdio_restores_blocking_streams() -> None:
    # Node (run as `opencode --version` in the same shell) sets O_NONBLOCK on
    # the shared stdio file description and never restores it; a non-blocking
    # stdout makes CPython's exit-time flush fail with EAGAIN and exit 120
    # AFTER a report was successfully submitted. The harness must restore
    # blocking mode before writing the large captured transcript and exiting.
    code = (
        "import os, sys; "
        "os.set_blocking(sys.stdout.fileno(), False); "
        "os.set_blocking(sys.stderr.fileno(), False); "
        "from ai_review_ci.harness import ensure_blocking_stdio; "
        "ensure_blocking_stdio(); "
        "print(os.get_blocking(sys.stdout.fileno()), os.get_blocking(sys.stderr.fileno()))"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "True True"


def test_reviewer_opencode_config_denies_wasteful_probing() -> None:
    # The reviewer's opencode permission config must deny the observed
    # time-wasters: git in a .git-less copy, direct sudo around the
    # submit-candidate wrapper, and probing the review infrastructure.
    config = json.loads(Path("ci/reviewer_home/.config/opencode/opencode.json").read_text())
    bash = config["permission"]["bash"]
    assert bash["git *"] == "deny"
    assert bash["sudo *"] == "deny"
    assert bash["*/opt/ai-review*"] == "deny"
    assert config["permission"]["webfetch"] == "deny"
    # The submission wrapper itself stays callable.
    assert bash["*"] == "allow"


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


def test_opencode_config_from_env_rejects_malformed_and_out_of_range() -> None:
    # Acceptance #2: the config boundary is fail-loud on invalid *values*, not just
    # missing keys. A non-numeric value and every degenerate range value must raise at
    # construction — never be accepted into a run. ValidationError subclasses ValueError,
    # as does int('x'), so ValueError covers both. Assert on type, not message strings.
    from ai_review_ci.harness import OpencodeConfig

    base = {
        "AI_REVIEW_OPENCODE_BIN": "/usr/local/bin/opencode",
        "AI_REVIEW_OPENCODE_TIMEOUT": "600",
        "AI_REVIEW_MAX_ATTEMPTS": "5",
        "AI_REVIEW_BACKOFF": "5",
    }
    invalid_values = [
        ("AI_REVIEW_OPENCODE_TIMEOUT", "not-a-number"),  # non-numeric
        ("AI_REVIEW_OPENCODE_TIMEOUT", "0"),  # timeout must be strictly positive
        ("AI_REVIEW_OPENCODE_TIMEOUT", "-1"),
        ("AI_REVIEW_MAX_ATTEMPTS", "0"),  # < 1 makes range(1, n+1) empty
        ("AI_REVIEW_MAX_ATTEMPTS", "-3"),
        ("AI_REVIEW_BACKOFF", "-0.5"),  # backoff must be non-negative
        ("AI_REVIEW_BACKOFF", "inf"),  # non-finite escapes ge=0; would hang time.sleep mid-loop
        ("AI_REVIEW_BACKOFF", "nan"),
    ]
    for key, bad in invalid_values:
        with pytest.raises(ValueError):
            OpencodeConfig.from_env({**base, key: bad})

    # Boundary values that ARE valid: zero backoff is allowed, one attempt is allowed.
    edge = OpencodeConfig.from_env({**base, "AI_REVIEW_BACKOFF": "0", "AI_REVIEW_MAX_ATTEMPTS": "1"})
    assert edge.backoff == 0
    assert edge.max_attempts == 1


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

    # Attempt 1 must genuinely take the timeout path — otherwise the terminal-FATAL
    # equality below is vacuous, since the non-timeout FATAL is also emitted by a run
    # where nothing ever timed out. The harness prints a per-attempt timeout diagnostic
    # to stderr; its presence is the observable proof the timeout branch was hit.
    assert any(line.startswith("--- opencode timed out:") for line in result.stderr.splitlines())

    # ...and after that timeout, the per-attempt reset means the terminal FATAL reports
    # only the last attempt's outcome (a missing artifact), not the earlier timeout.
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
