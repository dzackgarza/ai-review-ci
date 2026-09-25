import json
import os
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_gate_recipes_use_the_target_checkout() -> None:
    runner = (ROOT / "ci" / "runner.just").read_text()

    assert 'control_repo := env_var("GITHUB_WORKSPACE")' in runner
    for recipe_name in ("check-pr-description pr_number:", "check-review-threads pr_number:"):
        recipe = runner.split(recipe_name, 1)[1].split("\n\n", 1)[0]
        assert '--repo-root "{{control_repo}}"' in recipe


def test_qc_doctor_recipe_emits_its_machine_readable_result(tmp_path: Path) -> None:
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


def test_qc_doctor_artifact_is_uploaded_after_the_gate_runs() -> None:
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "_gates.yml").read_text())
    steps = workflow["jobs"]["qc-doctor"]["steps"]
    check_step = next(step for step in steps if step.get("name") == "Check QC doctor")
    upload_step = next(step for step in steps if step.get("name") == "Upload QC doctor payload")

    assert "continue-on-error" not in check_step
    assert upload_step["if"] == "${{ always() }}"
    assert upload_step["with"]["path"] == ".ai-review-ci-doctor.json"
