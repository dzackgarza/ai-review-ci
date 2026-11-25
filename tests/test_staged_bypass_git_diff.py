"""Exercise the bypass gate on real Git patches."""

import json
import subprocess
from contextlib import chdir
from pathlib import Path

import pytest

from ai_review_ci.gates import check_staged_bypass


def git(project: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(project), *args], check=True, capture_output=True).stdout


@pytest.fixture(params=[b"\r", b"\v", b"\f", b"\x1c", b"\x1d", b"\x1e", "\x85".encode(), "\u2028".encode(), "\u2029".encode(), b"\xff"])
def damaged_repository(tmp_path: Path, request: pytest.FixtureRequest) -> Path:
    git(tmp_path, "init", "--quiet")
    source = tmp_path / "app.py"
    source.write_bytes(b"# damaged " + request.param + b" payload\npass\n")
    (tmp_path / "binary.dat").write_bytes(b"before\0")
    git(tmp_path, "add", "app.py", "binary.dat")
    tree = git(tmp_path, "write-tree").decode().strip()
    commit = git(tmp_path, "-c", "user.name=QC test", "-c", "user.email=qc@example.test", "commit-tree", tree, "-m", "baseline").decode().strip()
    git(tmp_path, "update-ref", "HEAD", commit)
    (tmp_path / "binary.dat").write_bytes(b"after\0")
    git(tmp_path, "add", "binary.dat")
    return tmp_path


def test_staged_bypass_accepts_repairing_control_byte_damage(damaged_repository: Path) -> None:
    (damaged_repository / "app.py").write_text("# repaired\npass\n")
    git(damaged_repository, "add", "app.py")

    with chdir(damaged_repository):
        check_staged_bypass()


def test_damaged_removed_text_does_not_silence_added_bypass(damaged_repository: Path, capsys: pytest.CaptureFixture[str]) -> None:
    marker = "# pragma: no cov" + "er"
    (damaged_repository / "app.py").write_text(f"# repaired\npass  {marker}\n")
    git(damaged_repository, "add", "app.py")

    with chdir(damaged_repository):
        with pytest.raises(SystemExit) as error:
            check_staged_bypass()
    assert error.value.code == 1
    assert "app.py:2: no-coverage-pragma:" in capsys.readouterr().err


def test_staged_data_is_not_source_but_real_bypasses_still_fail(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    git(tmp_path, "init", "--quiet")
    noqa = "# no" + "qa"
    cast = "as un" + "known as"
    payload = f"{noqa}; value {cast} string"
    quoted = json.dumps(payload)
    data = {
        "conversation.json": json.dumps({"content": payload}),
        "conversation.JSON": json.dumps({"content": payload}),
        "settings.jsonc": f"{{{quoted}: true}}",
        "records.jsonl": json.dumps({"content": payload}),
        "records.ndjson": json.dumps({"content": payload}),
        "table.csv": f"content\n{quoted}",
        "table.tsv": f"content\n{payload}",
        "settings.yaml": f"content: {quoted}",
        "settings.yml": f"content: {quoted}",
        "record.xml": f"<content>{payload}</content>",
        "fixture.sql": f"INSERT INTO messages VALUES ('{payload}');",
        "settings.toml": f"content = {quoted}",
        "settings.ini": f"[record]\ncontent = {payload}",
        "settings.cfg": f"[record]\ncontent = {payload}",
        "transcript.txt": payload,
        "transcript.log": payload,
        "example.md": f"`{payload}`",
    }
    for name, content in data.items():
        (tmp_path / name).write_text(content + "\n")
    git(tmp_path, "add", "--", *data)
    with chdir(tmp_path):
        check_staged_bypass()
    assert "No bypass comments detected" in capsys.readouterr().out

    python_source = "\n".join((
        f"import os  {noqa}",
        "value: int = 'text'  # type: ign" + "ore",
        "pass  # pragma: no cov" + "er",
        "",
    ))
    ts_source = "\n".join((
        f"const value = 1 {cast} string;",
        "// @ts-ign" + "ore",
        "const wrong: number = 'text';",
        "// @ts-expect-err" + "or",
        "const other: number = 'text';",
        "// eslint-dis" + "able-next-line no-console",
        "console.log(value);",
        "// istanbul ign" + "ore next",
        "export function f() {}",
        "",
    ))
    (tmp_path / "app.py").write_text(python_source)
    (tmp_path / "app.ts").write_text(ts_source)
    (tmp_path / "script").write_text(f"#!/usr/bin/env python3\nimport os  {noqa}\n")
    git(tmp_path, "add", "app.py", "app.ts", "script")
    with chdir(tmp_path), pytest.raises(SystemExit) as error:
        check_staged_bypass()
    assert error.value.code == 1
    findings = [line for line in capsys.readouterr().err.splitlines() if line.startswith("- ")]
    assert findings == [
        "- app.py:1: no-noqa: POLICY.NO_QC_SILENCING",
        "- app.py:2: no-type-ignore: POLICY.NO_QC_SILENCING",
        "- app.py:3: no-coverage-pragma: POLICY.NO_QC_SILENCING",
        "- app.ts:1: no-double-cast: POLICY.NO_TYPE_ESCAPE",
        "- app.ts:2: no-ts-ignore: POLICY.NO_QC_SILENCING",
        "- app.ts:4: no-unjustified-ts-expect-error: POLICY.NO_QC_SILENCING",
        "- app.ts:6: no-eslint-disable: POLICY.NO_QC_SILENCING",
        "- app.ts:8: no-istanbul-ignore: POLICY.NO_QC_SILENCING",
        "- script:2: no-noqa: POLICY.NO_QC_SILENCING",
    ]
