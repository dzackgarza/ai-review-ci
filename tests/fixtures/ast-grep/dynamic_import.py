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
    # ruleid: no-dynamic-import-python
    __import__("os")
    # ok: no-dynamic-import-python
    __import__(dyn)
