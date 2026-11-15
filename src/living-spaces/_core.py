"""Load living_spaces_core by file path. plugin_api.py is imported as a loose module and the cron shim runs
as a bare script, so neither can rely on package-relative imports; all three entry points share this.

One process can host several Hermes profiles (a multiplexed gateway), each with its own copy of this plugin.
The core is cached per copy: a module loaded from another directory is never reused, because that would run
another profile's code (possibly an older version, or one whose profile has since been deleted)."""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

_NAME = "living_spaces_core"
_PKG = Path(__file__).resolve().parent / _NAME


def _ours(mod) -> bool:
    origin = getattr(mod, "__file__", None)
    # A module without a file is a test double installed on purpose; keep honouring it.
    return origin is None or Path(origin).resolve().parent == _PKG


def load_core():
    mod = sys.modules.get(_NAME)
    if mod is not None and _ours(mod):
        return mod
    name = _NAME
    if mod is not None:
        # Another copy owns the plain name in this process: load ours under a name unique to this directory.
        name = f"{_NAME}_{hashlib.sha256(str(_PKG).encode()).hexdigest()[:12]}"
        cached = sys.modules.get(name)
        if cached is not None:
            return cached
    spec = importlib.util.spec_from_file_location(name, _PKG / "__init__.py", submodule_search_locations=[str(_PKG)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return mod
