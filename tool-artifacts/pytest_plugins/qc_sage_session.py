r"""Collect ``test_*.sage`` files in place, as Sage sessions.

Loaded by ``_sage-pytest`` and ``_sage-pytest-coverage`` (``-p
qc_sage_session``), which run pytest from the project root. That keeps the
project's ``conftest.py`` files, its ``[tool.pytest.ini_options]`` and the helper
modules beside its tests.

A ``.sage`` test is a Sage script. It is lowered by ``sage.repl.preparse.
preparse_file`` at collection time, after the project's conftests have run.
That is Sage's own preparser, or the one a project installs in its place, as
``sageparse`` does. It runs with ``sage.all_cmdline`` in scope, which is what
Sage's ``sage-preparse`` prepends to a script. Those names sit in the module's
builtins scope, so the file's own bindings take precedence and pytest does not
collect Sage's ``TestSuite`` from the module namespace. pytest's assertion
rewriting is applied to the lowered tree, as its import hook does for a ``.py``
test module. The test's directory goes first on ``sys.path``, as pytest's
default ``prepend`` import mode does for a module outside a package.

pytest documents ``pytest_collect_file`` as the hook for collecting non-Python
test files (https://docs.pytest.org/en/stable/example/nonpython.html), and
sagemath/sage#30738 proposes the same hook for Sage's own ``.sage`` files.
"""

import ast
import builtins
import sys
from pathlib import Path
from types import ModuleType

import pytest

SUFFIX = ".sage"


def _sage_scope() -> dict[str, object]:
    import sage.all_cmdline

    scope = dict(vars(builtins))
    scope.update({name: value for name, value in vars(sage.all_cmdline).items() if not name.startswith("_")})
    return scope


class SageSession(pytest.Module):
    r"""A ``test_*.sage`` file, lowered and executed as a Sage script."""

    def _getobj(self) -> ModuleType:
        from _pytest.assertion.rewrite import rewrite_asserts
        from sage.repl import preparse

        directory = str(self.path.parent)
        if directory not in sys.path:
            sys.path.insert(0, directory)
        name = ".".join(self.path.relative_to(self.config.rootpath).with_suffix("").parts)
        lowered = preparse.preparse_file(self.path.read_text())
        tree = ast.parse(lowered, filename=str(self.path))
        rewrite_asserts(tree, lowered.encode("utf-8"), str(self.path), self.config)
        module = ModuleType(name)
        module.__file__ = str(self.path)
        module.__dict__["__builtins__"] = _sage_scope()
        sys.modules[name] = module
        exec(compile(tree, str(self.path), "exec", dont_inherit=True), module.__dict__)
        self.config.pluginmanager.consider_module(module)
        return module


def pytest_collect_file(file_path: Path, parent: pytest.Collector) -> pytest.Module | None:
    if file_path.suffix == SUFFIX and file_path.name.startswith("test_"):
        return SageSession.from_parent(parent, path=file_path)
    return None
