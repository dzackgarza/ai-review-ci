import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = REPO_ROOT / "tool-artifacts/scripts/build-vendor-skills.py"
SKILLS_ROOT = REPO_ROOT / "skills"
VENDOR_ROOT = REPO_ROOT / "reviews/vendor"
MANIFEST = VENDOR_ROOT / "MANIFEST.toml"


def _manifest() -> dict:
    return tomllib.loads(MANIFEST.read_text())


def _owned_vendor_outputs(name: str, spec: dict) -> list[Path]:
    """The reviews/vendor files an owned skill is responsible for, relative to VENDOR_ROOT."""
    if spec["vendor_layout"] == "nested":
        base = VENDOR_ROOT / name
        return sorted(p.relative_to(VENDOR_ROOT) for p in base.rglob("*") if p.is_file())
    outputs = [Path(f"{name}.md")]
    references = VENDOR_ROOT / f"{name}-references"
    if references.is_dir():
        outputs += [p.relative_to(VENDOR_ROOT) for p in references.rglob("*.md")]
    return sorted(outputs)


def test_manifest_partitions_every_top_level_vendored_doc() -> None:
    # Every doc inlined into the reviewer bundle must be classified owned-or-consumed, so
    # ownership is never ambiguous. Guards against a new vendored doc sneaking in unclassified.
    manifest = _manifest()
    owned = manifest["owned"]
    consumed = manifest["consumed"]

    classified = {f"{name}.md" for name, spec in owned.items() if spec["vendor_layout"] == "flat"}
    classified |= {spec["vendor_path"] for spec in consumed.values()}

    top_level_docs = {p.name for p in VENDOR_ROOT.glob("*.md")}
    assert top_level_docs == classified, f"unclassified/mismatched vendored docs: {top_level_docs ^ classified}"


def test_owned_skills_declare_source_and_layout() -> None:
    for name, spec in _manifest()["owned"].items():
        assert (REPO_ROOT / spec["source_path"]).is_dir(), f"{name}: source_path is not a dir"
        assert spec["vendor_layout"] in {"flat", "nested"}, f"{name}: bad vendor_layout"


def test_consumed_docs_are_not_authored_here() -> None:
    # Consumed docs are vendored from an external upstream; they must NOT have a skills/ source
    # (that would make them owned) and must name where to refresh them from.
    for name, spec in _manifest()["consumed"].items():
        assert spec["upstream_repo"], f"{name}: consumed doc has no upstream_repo"
        assert not (SKILLS_ROOT / name).exists(), f"{name}: consumed doc must not be authored under skills/"


def test_all_owned_skills_rebuild_byte_identical(tmp_path: Path) -> None:
    # The vendored copy of each owned skill must be a faithful build of its skills/ source.
    # Wipe every owned output in a scratch vendor tree, rebuild from source, and require each
    # regenerated file to match the committed vendored copy byte-for-byte. Catches drift in
    # either direction: editing skills/ without rebuilding, or hand-editing the vendored copy.
    scratch = tmp_path / "vendor"
    shutil.copytree(VENDOR_ROOT, scratch)

    manifest = _manifest()
    expected = {name: _owned_vendor_outputs(name, spec) for name, spec in manifest["owned"].items()}
    for outputs in expected.values():
        for relative in outputs:
            (scratch / relative).unlink()

    subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--skills-root", str(SKILLS_ROOT), "--vendor-root", str(scratch)],
        check=True,
    )

    for name, outputs in expected.items():
        assert outputs, f"{name}: produced no vendor outputs"
        for relative in outputs:
            rebuilt = scratch / relative
            assert rebuilt.is_file(), f"{name}: build did not regenerate {relative}"
            assert rebuilt.read_text() == (VENDOR_ROOT / relative).read_text(), f"{relative} rebuild drifted"
