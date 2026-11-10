"""Load living_spaces_core by file path. plugin_api.py is imported as a loose module and the cron shim runs
as a bare script, so neither can rely on package-relative imports; all three entry points share this."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_NAME = "living_spaces_core"


def load_core():
    mod = sys.modules.get(_NAME)
    if mod is not None:
        return mod
    pkg = Path(__file__).resolve().parent / _NAME
    spec = importlib.util.spec_from_file_location(_NAME, pkg / "__init__.py", submodule_search_locations=[str(pkg)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_NAME] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop(_NAME, None)
        raise
    return mod
