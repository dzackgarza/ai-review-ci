"""Fixture for no-dynamic-import-python (#219): static literal is a hidden
dependency (flag); a name derived from data is dynamic-by-design (ok)."""

import importlib
from importlib import import_module


def _loaders(module_name, node, pkg, sub, dyn):
    # ruleid: no-dynamic-import-python
    importlib.import_module("numpy")
    # ok: no-dynamic-import-python
    importlib.import_module(module_name)
    # ok: no-dynamic-import-python
    importlib.import_module(node.module)
    # ok: no-dynamic-import-python
    importlib.import_module(f"{pkg}.{sub}")
    # ruleid: no-dynamic-import-python
    import_module("scipy")
    # ok: no-dynamic-import-python
    import_module(module_name)
    # A static-literal first arg is a hidden dependency even with a package arg
    # (relative import, positional package): still flag.
    # ruleid: no-dynamic-import-python
    importlib.import_module(".sibling", package=__name__)
    # ruleid: no-dynamic-import-python
    import_module("pkg.mod", pkg)
    # A data first arg stays dynamic-by-design even with a package arg: the
    # kind:string / not-interpolation constraint must still exempt it.
    # ok: no-dynamic-import-python
    importlib.import_module(module_name, package=pkg)
    # ok: no-dynamic-import-python
    import_module(f"{pkg}.{sub}", package=pkg)
    # ruleid: no-dynamic-import-python
    __import__("os")
    # ok: no-dynamic-import-python
    __import__(dyn)
