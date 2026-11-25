"""Native pytest bytecode retains current prepared text and executes every time."""

from __future__ import annotations

import ast
import cProfile
import pstats
import traceback
from pathlib import Path

import pytest
from _pytest.assertion import rewrite

from qc_sage_rewrite import compile_rewritten


def test_prepared_unicode_ignores_encoding_cookie_on_miss_and_hit(tmp_path: Path, pytestconfig: pytest.Config) -> None:
    filename = tmp_path / "original.sage"
    source = "# coding: latin-1\nletter = 'é'\n"
    filename.write_text(source)
    expected: dict[str, object] = {}
    exec(compile(ast.parse(source), str(filename), "exec", dont_inherit=True), expected)
    for _ in range(2):
        actual: dict[str, object] = {}
        exec(compile_rewritten(filename, source, pytestconfig, tmp_path / "compiled"), actual)
        assert actual["letter"] == expected["letter"] == "é"


def test_prepared_bytecode_reuses_rewriting_but_not_execution(tmp_path: Path, pytestconfig: pytest.Config) -> None:
    filename = tmp_path / "original.sage"
    source = "executions.append(7)\nx = 7\nassert x == 7\n"
    filename.write_text(source)
    cache = tmp_path / "compiled"
    executions: list[int] = []
    first = compile_rewritten(filename, source, pytestconfig, cache)
    exec(first, {"executions": executions})
    profile = cProfile.Profile()
    with profile:
        second = compile_rewritten(filename, source, pytestconfig, cache)
    exec(second, {"executions": executions})
    assert executions == [7, 7]
    assert first.co_filename == second.co_filename == str(filename)
    assert not any(name == "rewrite_asserts" for _, _, name in pstats.Stats(profile).stats)

    # The source file has the SAME size and stat: only the active preparser's
    # supplied Python changes. That prepared text must invalidate bytecode.
    changed = source.replace("x = 7", "x = 8")
    third = compile_rewritten(filename, changed, pytestconfig, cache)
    with pytest.raises(AssertionError, match="assert 8 == 7") as failure:
        exec(third, {"executions": executions})
    assert executions == [7, 7, 7]
    assert traceback.extract_tb(failure.value.__traceback__)[-1].filename == str(filename)


def test_truncated_native_bytecode_is_recompiled(tmp_path: Path, pytestconfig: pytest.Config) -> None:
    filename = tmp_path / "original.sage"
    source = "value = 8\nassert value == 7\n"
    filename.write_text(source)
    cache = tmp_path / "compiled"
    compile_rewritten(filename, source, pytestconfig, cache)
    bytecode, = cache.glob("*.pyc")
    bytecode.write_bytes(b"truncated")
    rebuilt = compile_rewritten(filename, source, pytestconfig, cache)
    with pytest.raises(AssertionError, match="assert 8 == 7"):
        exec(rebuilt, {})


def test_project_rewriter_runs_on_every_compilation(
    tmp_path: Path, pytestconfig: pytest.Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = rewrite.rewrite_asserts
    revisions: list[int] = []

    def project_rewriter(tree: ast.Module, source: bytes, module_path: str, config: pytest.Config) -> None:
        original(tree, source, module_path, config)
        revisions.append(len(revisions) + 1)
        tree.body.extend(ast.parse(f"project_revision = {revisions[-1]}").body)

    monkeypatch.setattr(rewrite, "rewrite_asserts", project_rewriter)
    filename = tmp_path / "original.sage"
    source = "assert 7 == 7\n"
    filename.write_text(source)
    cache = tmp_path / "compiled"
    first_namespace: dict[str, object] = {}
    second_namespace: dict[str, object] = {}
    exec(compile_rewritten(filename, source, pytestconfig, cache), first_namespace)
    exec(compile_rewritten(filename, source, pytestconfig, cache), second_namespace)
    assert first_namespace["project_revision"] == 1
    assert second_namespace["project_revision"] == 2
    assert revisions == [1, 2]
