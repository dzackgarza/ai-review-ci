from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_reviewer_model_probe_enters_reviewer_home_before_privilege_drop() -> None:
    runner = (ROOT / "ci" / "runner.just").read_text()
    recipe = runner.split("check-reviewer-model:", 1)[1].split("stage-context-packet", 1)[0]

    assert 'available_models="$(cd "{{reviewer_home}}" && sudo -u reviewer -H env \\' in recipe
