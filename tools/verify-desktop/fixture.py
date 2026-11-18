"""Create the synthetic Verification Notebook through the plugin's own spaces_create handler.

This is fixture preparation, not chat creation. Run by drive.py inside the disposable HERMES_HOME.
Usage: python fixture.py <repo> <out> <state>"""
import importlib.util
import json
import os
import sys
from pathlib import Path

repo, out, state = (Path(a).resolve() for a in sys.argv[1:4])
assert Path(os.environ["HERMES_HOME"]).resolve() == state / "home", "fixture must run in the run's disposable home"
package = repo / "src/living-spaces"
spec = importlib.util.spec_from_file_location("verify_living_spaces", package / "__init__.py",
                                              submodule_search_locations=[str(package)])
plugin = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = plugin
spec.loader.exec_module(plugin)
html = (Path(__file__).resolve().parent / "fixtures/notebook.html").read_text()
args = dict(name="Verification Notebook", description="Disposable note persistence check", files={"index.html": html},
            libraries=[], manifest={"entry": "index.html",
                                    "data": {"version": 1, "collections": {"notes": {"description": "Saved user notes"}}}})
reply = json.loads(plugin._handler(plugin.spaces_create)(args))
(out / "fixture-create.json").write_text(json.dumps(dict(evidence_class="fixture preparation, not Desktop chat creation",
                                                          arguments=args, reply=reply), indent=2))
assert reply["ok"], reply
print(json.dumps(reply))
