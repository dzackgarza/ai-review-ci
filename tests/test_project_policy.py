"""Project-tag exceptions use live GitHub metadata and the real scanner."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.gh_boundary
def test_database_topic_exempts_only_field_defaults(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    subprocess.run(["git", "remote", "add", "origin", "https://github.com/dzackgarza/lattice-database.git"], cwd=tmp_path, check=True)
    source = tmp_path / "record.py"
    source.write_text("from pydantic import BaseModel, Field\nclass Record(BaseModel):\n    unknown: int | None = Field(default=None)\n")
    subprocess.run(["git", "add", "record.py"], cwd=tmp_path, check=True)
    command = ["just", "-f", str(ROOT / "justfiles" / "python.just"), "-d", str(tmp_path), "_ast-grep"]
    tagged = subprocess.run(command, capture_output=True, text=True, check=False)
    assert tagged.returncode == 0, tagged.stdout + tagged.stderr
    source.write_text(source.read_text() + "\ndef configure(verbose: bool) -> None:\n    pass\n")
    subprocess.run(["git", "add", "record.py"], cwd=tmp_path, check=True)
    other_rule = subprocess.run(command, capture_output=True, text=True, check=False)
    assert other_rule.returncode != 0
    assert "no-boolean-param" in other_rule.stdout + other_rule.stderr
    assert "error[no-field-default]" not in other_rule.stdout + other_rule.stderr
    subprocess.run(["git", "remote", "set-url", "origin", "https://github.com/dzackgarza/ai-review-ci.git"], cwd=tmp_path, check=True)
    untagged = subprocess.run(command, capture_output=True, text=True, check=False)
    assert untagged.returncode != 0
    assert "no-field-default" in untagged.stdout + untagged.stderr
    subprocess.run(["git", "remote", "set-url", "origin", "https://github.com/dzackgarza/ai-review-ci-missing-topic-proof-20261016.git"], cwd=tmp_path, check=True)
    unavailable = subprocess.run(command, capture_output=True, text=True, check=False)
    assert unavailable.returncode != 0
    assert "HTTP Error 404" in unavailable.stdout + unavailable.stderr
    assert "exempts no-field-default" not in unavailable.stdout + unavailable.stderr
