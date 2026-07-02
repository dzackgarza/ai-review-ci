import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tool-artifacts/scripts/refresh-consumed-skills.py"

MANIFEST = """
[owned.x]
source_path = "skills/x"
vendor_layout = "flat"

[consumed.demo]
upstream_repo = "acme/demo"
upstream_path = "skills/demo/SKILL.md"
vendor_path = "demo.md"
"""


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)


def _make_upstream(tmp_path: Path, content: str) -> Path:
    repo = tmp_path / "upstream"
    repo.mkdir()
    _git(repo, "init", "-q")
    # This machine sets core.hooksPath globally; a throwaway fixture repo must not run those hooks.
    _git(repo, "config", "core.hooksPath", "/dev/null")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    skill = repo / "skills/demo/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    return repo


def _refresh(source: Path, vendor: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "--vendor-root", str(vendor)],
        capture_output=True,
        text=True,
    )


def test_refresh_pulls_consumed_from_upstream_and_is_idempotent(tmp_path: Path) -> None:
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (vendor / "MANIFEST.toml").write_text(MANIFEST)
    (vendor / "demo.md").write_text("STALE\n")
    upstream = _make_upstream(tmp_path, "UPSTREAM CONTENT\n")

    first = _refresh(upstream, vendor)
    assert first.returncode == 0, first.stderr
    assert "refreshed demo" in first.stdout
    assert (vendor / "demo.md").read_text() == "UPSTREAM CONTENT\n"

    second = _refresh(upstream, vendor)
    assert second.returncode == 0, second.stderr
    assert "already current" in second.stdout


def test_refresh_fails_loud_when_source_is_not_a_checkout(tmp_path: Path) -> None:
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (vendor / "MANIFEST.toml").write_text(MANIFEST)

    result = _refresh(tmp_path / "not-a-repo", vendor)
    assert result.returncode != 0
    assert "not a git checkout" in result.stderr


def test_refresh_fails_loud_when_upstream_path_missing(tmp_path: Path) -> None:
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    # consumed doc points at a path that does not exist in the upstream commit
    (vendor / "MANIFEST.toml").write_text(MANIFEST.replace("skills/demo/SKILL.md", "skills/gone/SKILL.md"))
    upstream = _make_upstream(tmp_path, "UPSTREAM CONTENT\n")

    result = _refresh(upstream, vendor)
    assert result.returncode != 0
    assert "failed" in result.stderr
