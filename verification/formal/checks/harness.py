"""Shared setup for the real-code checks: an isolated Hermes home and the Living Spaces core from --src."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


class Violation(Exception):
    """The property failed. The message is the counterexample in the code's own words."""


def load(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True, help="repo root whose src/living-spaces is checked")
    args = parser.parse_args(argv)
    home = Path(tempfile.mkdtemp(prefix="ls-fv-home-", dir=os.environ.get("TMPDIR")))
    os.environ["HERMES_HOME"] = str(home)
    os.environ["LIVING_SPACES_DB"] = str(home / "spaces.db")
    sys.path.insert(0, str(Path(args.src).resolve() / "src" / "living-spaces"))
    import living_spaces_core as core
    return core, home


def space(core, name="Checked Space", *, entry=True):
    files = {"index.html": "<!doctype html><title>x</title>"} if entry else None
    return core.create_space(name, owner="Bjorn", files=files, author="agent")["id"]


def main(check):
    """Run check(core, home) -> summary dict. Exit 0 pass, 1 property violated, 2 harness error."""
    home = None
    try:
        core, home = load()
        summary = check(core, home)
    except Violation as exc:
        print(f"VIOLATION: {exc}")
        sys.exit(1)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"ERROR: {type(exc).__name__}: {exc}")
        sys.exit(2)
    finally:
        if home is not None:
            shutil.rmtree(home, ignore_errors=True)
    print("PASS " + json.dumps(summary, sort_keys=True))
