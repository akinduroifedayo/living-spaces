"""Seed a public probe project into the isolated home. This is a test fixture, not real-chat acceptance.

Usage: seed.py <fixture-dir> <name> [--replace KEY=VALUE ...]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('fixture', type=Path)
    p.add_argument('name')
    p.add_argument('--replace', action='append', default=[])
    a = p.parse_args()
    home = Path(os.environ['HERMES_HOME']).resolve()
    live = (Path.home() / '.hermes').resolve()
    if home == live or live in home.parents:
        raise SystemExit('refusing to seed a live Hermes profile')
    package = home / 'plugins' / 'living-spaces'
    spec = importlib.util.spec_from_file_location('ls_fixture_loader', package / '_core.py')
    if spec is None or spec.loader is None:
        raise SystemExit('plugin loader unavailable')
    loader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loader)
    core = loader.load_core()
    manifest = json.loads((a.fixture / 'space.json').read_text())
    swaps = [tuple(s.split('=', 1)) for s in a.replace]
    files = {}
    for path in sorted(a.fixture.rglob('*')):
        if not path.is_file() or path.name == 'space.json':
            continue
        data = path.read_bytes()
        for key, value in swaps:
            data = data.replace(key.encode(), value.encode())
        try:
            data = data.decode('utf-8')
        except UnicodeDecodeError:
            pass
        files[path.relative_to(a.fixture).as_posix()] = data
    result = core.projects.create_space(a.name, owner='Probe fixture', author='user',
                                        description='Synthetic isolated acceptance probe', files=files,
                                        manifest=manifest, libraries=[])
    print(json.dumps(result))


if __name__ == '__main__':
    main()
