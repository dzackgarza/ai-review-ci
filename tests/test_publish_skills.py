import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLISH_SCRIPT = REPO_ROOT / "tool-artifacts/scripts/publish-skills.py"
SKILLS_ROOT = REPO_ROOT / "skills"


def _publish(target: Path) -> list[str]:
    result = subprocess.run(
        [sys.executable, str(PUBLISH_SCRIPT), "--skills-root", str(SKILLS_ROOT), "--target", str(target)],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def test_publish_installs_owned_skills_faithfully_and_is_idempotent(tmp_path: Path) -> None:
    # Owned enforcement skills are authored under skills/ and published into a downstream
    # skills hub (e.g. ~/ai). Publishing must reproduce the source byte-for-byte, and a
    # second run against an up-to-date hub must be a no-op (writes nothing).
    target = tmp_path / "hub"
    (target / "opencode" / "skills").mkdir(parents=True)

    first = _publish(target)
    assert first, "first publish wrote nothing — expected owned skills to be installed"

    published_hub = target / "opencode" / "skills"
    source_files = sorted(SKILLS_ROOT.rglob("*.md"))
    assert source_files, "no owned skill source files found under skills/"
    for source_file in source_files:
        relative = source_file.relative_to(SKILLS_ROOT)
        installed = published_hub / relative
        assert installed.read_text() == source_file.read_text(), f"published {relative} is not byte-faithful"

    second = _publish(target)
    assert second == [], f"re-publish to an up-to-date hub was not a no-op: {second}"


def test_publish_fails_loudly_when_target_missing(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    result = subprocess.run(
        [sys.executable, str(PUBLISH_SCRIPT), "--skills-root", str(SKILLS_ROOT), "--target", str(missing)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "target skills hub does not exist" in result.stderr
