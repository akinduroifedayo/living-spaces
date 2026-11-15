"""_core.load_core in a process that hosts several profiles, each with its own plugin copy (multiplexed gateway).

Frozen regression (lsri-r1 real-app check): the live gateway had `living_spaces_core` cached from a deleted
profile's older copy, so the new profile's spaces_inspect handler got that module and failed with AttributeError."""
import importlib.util
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "living-spaces"


def load_loader(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CoreLoaderTests(unittest.TestCase):
    def setUp(self):
        self.saved = {name: module for name, module in sys.modules.items() if name.startswith("living_spaces_core")}
        for name in self.saved:
            del sys.modules[name]
        (ROOT / ".run").mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=ROOT / ".run")
        self.addCleanup(temporary.cleanup)
        # An older copy of the plugin, as another profile would have installed it: same module name, no inspect().
        self.other = Path(temporary.name) / "living-spaces"
        shutil.copytree(PACKAGE, self.other, ignore=shutil.ignore_patterns("__pycache__"))
        init = self.other / "living_spaces_core" / "__init__.py"
        text = init.read_text()
        init.write_text(text[:text.index("\n\ndef inspect(")] + "\n")

    def tearDown(self):
        for name in [n for n in sys.modules if n.startswith("living_spaces_core")]:
            del sys.modules[name]
        sys.modules.update(self.saved)

    def test_another_profiles_cached_core_is_not_reused(self):
        stale = load_loader(self.other / "_core.py", "other_profile_loader").load_core()
        self.assertFalse(hasattr(stale, "inspect"))
        self.assertIs(sys.modules["living_spaces_core"], stale)
        ours = load_loader(PACKAGE / "_core.py", "this_profile_loader").load_core()
        self.assertIsNot(ours, stale)
        self.assertTrue(hasattr(ours, "inspect"))
        self.assertEqual(Path(ours.__file__).resolve().parent, (PACKAGE / "living_spaces_core").resolve())
        self.assertIs(sys.modules["living_spaces_core"], stale)          # the other profile keeps its own copy
        again = load_loader(PACKAGE / "_core.py", "this_profile_loader_2").load_core()
        self.assertIs(again, ours)                                        # cached per copy, loaded once
        self.assertIs(ours.projects, sys.modules[ours.__name__ + ".projects"])   # submodules bound to our copy
        self.assertEqual(Path(ours.projects.__file__).resolve().parent, (PACKAGE / "living_spaces_core").resolve())

    def test_control_single_copy_still_uses_the_plain_name(self):
        core = load_loader(PACKAGE / "_core.py", "single_loader").load_core()
        self.assertEqual(core.__name__, "living_spaces_core")
        self.assertIs(load_loader(PACKAGE / "_core.py", "single_loader_2").load_core(), core)

    def test_control_test_double_without_a_file_is_honoured(self):
        double = types.ModuleType("living_spaces_core")
        sys.modules["living_spaces_core"] = double
        self.assertIs(load_loader(PACKAGE / "_core.py", "double_loader").load_core(), double)


if __name__ == "__main__":
    unittest.main()
