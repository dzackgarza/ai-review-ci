import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLISH_SCRIPT = REPO_ROOT / "tool-artifacts/scripts/publish-skills.py"
SKILLS_ROOT = REPO_ROOT / "skills"
MANIFEST = REPO_ROOT / "reviews/vendor/MANIFEST.toml"


def _owned() -> dict[str, Any]:
    return cast(dict[str, Any], tomllib.loads(MANIFEST.read_text())["owned"])


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
    # skills hub (e.g. ~/ai). Publishing must reproduce each owned skill byte-for-byte, and a
    # second run against an up-to-date hub must be a no-op (writes nothing).
    target = tmp_path / "hub"
    (target / "opencode" / "skills").mkdir(parents=True)

    first = _publish(target)
    assert first, "first publish wrote nothing — expected owned skills to be installed"

    published_hub = target / "opencode" / "skills"
    owned = _owned()
    assert owned, "no owned skills declared in MANIFEST"
    for name, spec in owned.items():
        source = REPO_ROOT / spec["source_path"]
        source_files = sorted(source.rglob("*.md"))
        assert source_files, f"{name}: owned skill has no markdown source"
        for source_file in source_files:
            installed = published_hub / name / source_file.relative_to(source)
            assert installed.read_text() == source_file.read_text(), f"published {name} not byte-faithful"

    second = _publish(target)
    assert second == [], f"re-publish to an up-to-date hub was not a no-op: {second}"


def test_publish_excludes_repo_local_skills_not_in_manifest(tmp_path: Path) -> None:
    # skills/ also holds repo-local skills (e.g. quality-control) that are NOT owned enforcement
    # skills and must never be pushed to the shared hub. Only [owned.*] entries publish.
    target = tmp_path / "hub"
    (target / "opencode" / "skills").mkdir(parents=True)
    _publish(target)

    published = {p.name for p in (target / "opencode" / "skills").iterdir()}
    assert published == set(_owned()), f"published set diverged from owned set: {published}"

    local_only = {p.name for p in SKILLS_ROOT.iterdir() if p.is_dir()} - set(_owned())
    assert local_only, "expected at least one repo-local skill not in the owned set"
    assert not (published & local_only), f"repo-local skills wrongly published: {published & local_only}"


def test_publish_fails_loudly_when_target_missing(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    result = subprocess.run(
        [sys.executable, str(PUBLISH_SCRIPT), "--skills-root", str(SKILLS_ROOT), "--target", str(missing)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "target skills hub does not exist" in result.stderr
