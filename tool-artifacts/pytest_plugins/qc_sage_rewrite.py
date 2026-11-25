"""Cache native pytest rewriting of the freshly prepared Python, never execution.

The active Sage preparser still runs on every collection. Its exact output,
filename, pytest compiler, assertion-pass configuration and Python ABI identify
the derived bytecode. A project replacing pytest's rewriter takes the original
uncached compilation path. Native pytest owns bytecode validation and writes.
"""

from __future__ import annotations

import ast
import sys
from hashlib import sha256
from pathlib import Path
from types import CodeType, FunctionType

import pytest
from _pytest.assertion import rewrite

_NATIVE_FUNCTION = rewrite.rewrite_asserts
_NATIVE_CODE = _NATIVE_FUNCTION.__code__
_NATIVE_CLASS = rewrite.AssertionRewriter
_NATIVE_MEMBERS = dict(vars(_NATIVE_CLASS))
_NATIVE_METHODS = tuple((name, value.__code__) for name, value in _NATIVE_MEMBERS.items() if isinstance(value, FunctionType))
_REWRITE_PATH = Path(rewrite.__file__).resolve()
_COMPILER_HASH = sha256(Path(__file__).read_bytes()).hexdigest()
_REWRITER_HASH = sha256(_REWRITE_PATH.read_bytes()).hexdigest()


def _uses_native_rewriter() -> bool:
    if rewrite.rewrite_asserts is not _NATIVE_FUNCTION or rewrite.rewrite_asserts.__code__ is not _NATIVE_CODE:
        return False
    if rewrite.AssertionRewriter is not _NATIVE_CLASS or vars(_NATIVE_CLASS) != _NATIVE_MEMBERS:
        return False
    methods = tuple((name, value.__code__) for name, value in vars(_NATIVE_CLASS).items() if isinstance(value, FunctionType))
    return methods == _NATIVE_METHODS and Path(_NATIVE_CODE.co_filename).resolve() == _REWRITE_PATH


def _compile_current(path: Path, lowered: str, config: pytest.Config) -> CodeType:
    filename = str(path)
    tree = ast.parse(lowered, filename=filename)
    rewrite.rewrite_asserts(tree, lowered.encode("utf-8"), filename, config)
    return compile(tree, filename, "exec", dont_inherit=True)


def compile_rewritten(path: Path, lowered: str, config: pytest.Config, cache_dir: Path) -> CodeType:
    source = lowered.encode("utf-8")
    if sys.dont_write_bytecode or not _uses_native_rewriter():
        return _compile_current(path, lowered, config)
    signature = repr(
        (
            str(path),
            pytest.__version__,
            sys.implementation.cache_tag,
            sys.flags.optimize,
            config.getini("enable_assertion_pass_hook"),
            _COMPILER_HASH,
            _REWRITER_HASH,
        )
    ).encode("utf-8")
    key = sha256(signature + b"\0" + source).hexdigest()
    cache_dir.mkdir(parents=True, exist_ok=True)
    prepared = cache_dir / f"{key}.py"
    bytecode = prepared.with_suffix(".pyc")
    if not prepared.exists() or prepared.read_bytes() != source:
        prepared.write_bytes(source)
    cached = rewrite._read_pyc(prepared, bytecode)
    if cached is not None:
        return cached
    code = _compile_current(path, lowered, config)
    state = config.stash[rewrite.assertstate_key]
    if not rewrite._write_pyc(state, code, prepared.stat(), bytecode):
        raise OSError(f"pytest could not write prepared Sage bytecode: {bytecode}")
    return code
