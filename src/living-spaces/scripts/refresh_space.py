from __future__ import annotations

import importlib.util
from pathlib import Path

PACKAGE = __LIVING_SPACES_PACKAGE__
SID = __LIVING_SPACES_SID__


def main():
    try:
        spec = importlib.util.spec_from_file_location("living_spaces_loader", Path(PACKAGE) / "_core.py")
        loader = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loader)
        core = loader.load_core()
        from importlib import import_module

        runs = import_module(core.__name__ + ".runs")
        run = runs.start_refresh(SID, trigger="schedule", actor="upkeep:schedule", wait=True)
        if run["status"] != "succeeded":
            message = run.get("error") or run.get("detail", {}).get("reason") or run["status"]
            print("Living Spaces refresh: " + " ".join(str(message).splitlines()))
            return 1
        return 0
    except Exception as exc:
        print("Living Spaces refresh: " + " ".join(str(exc).splitlines()))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
