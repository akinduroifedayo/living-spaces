import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
import wave


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src/living-spaces"
sys.path.insert(0, str(PACKAGE))
import living_spaces_core as core
from living_spaces_core import limits

spec = importlib.util.spec_from_file_location("c_tools_plugin", PACKAGE / "__init__.py",
                                            submodule_search_locations=[str(PACKAGE)])
plugin = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = plugin
spec.loader.exec_module(plugin)
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=")
HTML = "<!doctype html><title>Public demo</title><main>Assets</main>"
KIT_LINK = '<link rel="stylesheet" href="kit/spaces-kit.css">'
SHELF = json.loads((PACKAGE / "runtime/vendor/SHELF.json").read_text())["libraries"]


def descriptor(raw, **extra):
    return {"b64": base64.b64encode(raw).decode("ascii"), **extra}


def contents(file):
    return base64.b64decode(file["b64"], validate=True) if "b64" in file else file["text"].encode("utf-8")


class ToolCase(unittest.TestCase):
    def setUp(self):
        (ROOT / ".run").mkdir(exist_ok=True)
        temp = tempfile.TemporaryDirectory(prefix="c-tools-", dir=ROOT / ".run")
        self.addCleanup(temp.cleanup)
        env = patch.dict(os.environ, {"HERMES_HOME": temp.name,
                                     "LIVING_SPACES_DB": str(Path(temp.name) / "spaces.db")})
        env.start()
        self.addCleanup(env.stop)
        loader = patch.object(plugin._core, "load_core", return_value=core)
        loader.start()
        self.addCleanup(loader.stop)
        ctx = types.SimpleNamespace(register_tool=Mock(), register_skill=Mock())
        plugin.register(ctx)
        self.tools = {call.kwargs["name"]: call.kwargs for call in ctx.register_tool.call_args_list}

    def call(self, tool_name, **args):
        return json.loads(self.tools[tool_name]["handler"](args, profile_name="Public Demo"))

    def ok(self, tool_name, **args):
        reply = self.call(tool_name, **args)
        self.assertTrue(reply["ok"], reply)
        return reply["result"]

    def create(self, **args):
        return self.ok("spaces_create", **{"name": "Asset Demo", "description": "Public assets",
                                           "files": {"index.html": HTML}, "libraries": [], **args})

    def write(self, sid, **args):
        return self.ok("spaces_write_files", **{"space": sid, "files": {}, "summary": "Update assets", **args})

    def invalid(self, tool_name, **args):
        reply = self.call(tool_name, **args)
        self.assertFalse(reply["ok"], reply)
        self.assertEqual(reply["error"]["code"], "invalid", reply)
        return reply["error"]


class BinaryTests(ToolCase):
    def test_png_and_wav_round_trip_create_read_write_bundle(self):
        output = io.BytesIO()
        with wave.open(output, "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(1)
            audio.setframerate(8000)
            audio.writeframes(bytes([0, 128, 255, 128]) * 20)
        assets = {"images/demo.png": PNG, "audio/demo.wav": output.getvalue()}
        result = self.create(files={"index.html": HTML, **{path: descriptor(raw) for path, raw in assets.items()}})
        sid = result["space"]
        writes = {}
        for path, raw in assets.items():
            read = self.ok("spaces_read_file", space=sid, path=path)
            self.assertEqual(contents(read), raw)
            self.assertEqual(read["size"], len(raw))
            self.assertEqual(read["sha"], hashlib.sha256(raw).hexdigest())
            writes["copies/" + path] = {"b64": read["b64"]}
        result = self.write(sid, files=json.dumps(writes), base_rev=result["rev"])
        bundle = core.bundle(sid)
        self.assertEqual(bundle["rev"], result["rev"])
        files = {file["path"]: file for file in bundle["files"]}
        for path, raw in assets.items():
            self.assertEqual(contents(files[path]), raw)
            self.assertEqual(contents(files["copies/" + path]), raw)

    def test_optional_mime_empty_and_utf8_bytes(self):
        result = self.create(files={"index.html": HTML, "a.png": descriptor(PNG, mime="image/png"),
                                    "empty.bin": descriptor(b""), "text.bin": descriptor("héllo".encode())})
        files = {file["path"]: file for file in core.bundle(result["space"])["files"]}
        self.assertEqual(contents(files["a.png"]), PNG)
        self.assertEqual(files["a.png"]["mime"], "image/png")
        self.assertEqual(contents(files["empty.bin"]), b"")
        self.assertEqual(contents(files["text.bin"]), "héllo".encode())

    def test_bad_base64_names_path_and_does_not_write(self):
        sid = self.create()["space"]
        for b64 in ("!", "a", "YWJj\n", "é", "Zg=", "Zg==garbage"):
            for name in ("spaces_create", "spaces_write_files"):
                with self.subTest(b64=b64, tool=name):
                    error = self.invalid(name, name="Bad Asset", description="Public demo", space=sid,
                                         summary="Bad asset", libraries=[],
                                         files={"good.txt": "must not persist", "bad.png": {"b64": b64}})
                    self.assertIn("bad.png", error["message"])
                    self.assertEqual(core.get_space(sid)["head_rev"], 1)
                    self.assertEqual(len(core.list_spaces()), 1)

    def test_malformed_descriptors_are_invalid(self):
        sid = self.create()["space"]
        for value in ({}, {"mime": "image/png"}, {"b64": None}, {"b64": 3},
                      {"b64": "", "mime": None}, {"b64": "", "extra": True}, [], 42, True):
            for tool in ("spaces_create", "spaces_write_files"):
                with self.subTest(value=value, tool=tool):
                    error = self.invalid(tool, name="Bad Asset", description="Public demo", space=sid,
                                         summary="Bad asset", libraries=[], files={"bad.png": value})
                    self.assertIn("bad.png", error["message"])

    def test_noncanonical_base64_is_rejected(self):
        sid = self.create()["space"]
        for b64 in ("YWJj=", "YWJj====", "Zh=="):
            for tool in ("spaces_create", "spaces_write_files"):
                with self.subTest(b64=b64, tool=tool):
                    error = self.invalid(tool, name="Bad Padding", space=sid, summary="Bad padding",
                                         libraries=[], files={"bad.png": {"b64": b64}})
                    self.assertIn("bad.png", error["message"])

    def test_null_is_delete_only_and_binary_paths_are_validated(self):
        self.invalid("spaces_create", name="Bad", files={"image.png": None}, libraries=[])
        sid = self.create(files={"index.html": HTML, "image.png": descriptor(PNG)})["space"]
        self.write(sid, files={"image.png": None})
        self.assertEqual([f["path"] for f in core.list_files(sid)], ["index.html"])
        self.invalid("spaces_write_files", space=sid, summary="Bad path",
                     files={"../escape.png": descriptor(PNG)})

    def test_limits_count_decoded_bytes_and_preserve_failed_revision(self):
        with patch.object(limits, "FILE_BYTES", 1024), patch.object(limits, "PROJECT_BYTES", 2050):
            raw = b"\xff" * 1024
            sid = self.create(files={"one.bin": descriptor(raw), "two.bin": descriptor(raw)})["space"]
            self.assertEqual(core.read_file(sid, "one.bin")["size"], 1024)
            for files, resource, actual in (({"big.bin": descriptor(raw + b"x")}, "file bytes", 1025),
                                             ({"three.bin": descriptor(b"123")}, "project bytes", 2051)):
                with self.subTest(resource=resource):
                    reply = self.call("spaces_write_files", space=sid, summary="Too large", files=files)
                    self.assertEqual(reply["error"]["code"], "limit", reply)
                    self.assertEqual(reply["error"]["resource"], resource)
                    self.assertEqual(reply["error"]["actual"], actual)
                    self.assertEqual(core.get_space(sid)["head_rev"], 1)
            reply = self.call("spaces_create", name="Too Big", libraries=[], files={"big": descriptor(raw + b"x")})
            self.assertEqual(reply["error"]["code"], "limit", reply)

    def test_binary_schema_and_agent_guidance(self):
        for name in ("spaces_create", "spaces_write_files"):
            with self.subTest(tool=name):
                tool = self.tools[name]
                schema = tool["schema"]["parameters"]["properties"]["files"]["additionalProperties"]
                binary = next(choice for choice in schema["anyOf"] if choice.get("type") == "object")
                self.assertEqual(binary["required"], ["b64"])
                self.assertEqual(binary["properties"]["b64"]["type"], "string")
                self.assertEqual(binary["properties"]["mime"]["type"], "string")
                self.assertFalse(binary["additionalProperties"])
                self.assertIn("b64", tool["description"])
                self.assertIn("Hermes", tool["description"])

    def test_binary_manifest_is_extracted_with_decoded_size_limit(self):
        manifest = json.dumps({"theme": {"preset": "terminal"}}).encode()
        sid = self.create(files={"index.html": HTML, "space.json": descriptor(manifest)})["space"]
        self.assertEqual(core.get_space(sid)["manifest"]["theme"], {"preset": "terminal"})
        with patch.object(limits, "FILE_BYTES", 1024):
            reply = self.call("spaces_write_files", space=sid, summary="Too large",
                              files={"space.json": descriptor(manifest + b" " * 1024)})
            self.assertEqual(reply["error"]["code"], "limit", reply)
            self.assertEqual(core.get_space(sid)["head_rev"], 1)


class ThemeTests(ToolCase):
    def test_valid_presets_tokens_and_both_survive_create_and_write(self):
        themes = [{"preset": preset} for preset in ("editorial", "terminal", "playful", "minimal", "data", "journal", "game")]
        themes += [{}, {"tokens": {}}, {"tokens": {"bg": "#fff", "font-body": "Inter, sans-serif"}},
                   {"preset": "editorial", "tokens": {"text": "rgb(1 2 3)"}},
                   {"tokens": {"a" * 40: "x" * 200}},
                   {"tokens": {f"token-{n}": "" for n in range(64)}}]
        for theme in themes:
            with self.subTest(theme=theme):
                manifest = {"theme": theme, "accent": "rose"}
                sid = self.create(manifest=manifest)["space"]
                self.assertEqual(core.get_space(sid)["manifest"]["theme"], theme)
                self.assertEqual(core.get_space(sid)["manifest"]["accent"], "rose")
                self.write(sid, files={"space.json": json.dumps(manifest)})
                read = self.ok("spaces_read_file", space=sid, path="space.json")
                self.assertEqual(json.loads(read["text"])["theme"], theme)
                self.assertEqual(manifest, {"theme": theme, "accent": "rose"})

    def test_absent_theme_stays_absent(self):
        sid = self.create()["space"]
        self.assertNotIn("theme", core.get_space(sid)["manifest"])

    def test_theme_shape_preset_and_unknown_keys_rejected(self):
        for theme in (None, [], "terminal", 1, True, {"unknown": "x"}, {"preset": None},
                      {"preset": []}, {"preset": 1}, {"preset": "unknown"}, {"preset": "Terminal"},
                      {"preset": "terminal "}, {"tokens": None}, {"tokens": []}, {"tokens": "x"}):
            with self.subTest(theme=theme):
                self.invalid("spaces_create", name="Theme Demo", files={"index.html": HTML},
                             libraries=[], manifest={"theme": theme})

    def test_invalid_token_names_rejected(self):
        for name in ("", "A", "0x", "-bg", "--space-bg", "a_b", "a b", "é", "a" * 41, "x\n"):
            with self.subTest(name=name):
                self.invalid("spaces_create", name="Theme Demo", files={"index.html": HTML},
                             libraries=[], manifest={"theme": {"tokens": {name: "red"}}})

    def test_invalid_token_values_rejected_without_revision(self):
        sid = self.create()["space"]
        for value in (None, 1, True, [], {}, "a" * 201, "red;", "{red", "red}", "<red", "red>",
                      "\\72 ed", "url(x)", "URL(x)", "x @import y", "@IMPORT x", "expression(x)", "EXPRESSION(x)"):
            with self.subTest(value=value):
                self.invalid("spaces_write_files", space=sid, summary="Bad theme",
                             files={"space.json": json.dumps({"theme": {"tokens": {"bg": value}}})})
                self.assertEqual(core.get_space(sid)["head_rev"], 1)

    def test_more_than_64_tokens_rejected(self):
        self.invalid("spaces_create", name="Theme Demo", files={"index.html": HTML}, libraries=[],
                     manifest={"theme": {"tokens": {f"token-{n}": "red" for n in range(65)}}})


class ShelfTests(ToolCase):
    def assert_group(self, sid, name):
        group = SHELF[name]
        bundle = core.bundle(sid)
        files = {file["path"]: contents(file) for file in bundle["files"]}
        self.assertEqual(set(files), {"index.html", *group["files"]})
        for path in group["files"]:
            self.assertEqual(files[path], (PACKAGE / "runtime" / path).read_bytes())
        self.assertEqual(bundle["manifest"]["imports"], group.get("imports", {}))

    def test_create_copies_exact_group_with_license_and_aliases(self):
        for name in SHELF:
            with self.subTest(library=name):
                sid = self.create(libraries=[name])["space"]
                self.assert_group(sid, name)

    def test_write_copies_exact_group_with_license_and_aliases(self):
        for name in SHELF:
            with self.subTest(library=name):
                sid = self.create()["space"]
                self.write(sid, libraries=[name], base_rev=1)
                self.assert_group(sid, name)

    def test_no_shelf_copied_without_request(self):
        sid = self.create()["space"]
        self.write(sid)
        self.assertEqual([file["path"] for file in core.list_files(sid)], ["index.html"])
        args = {"name": "Default Demo", "files": {"index.html": HTML}}
        sid = self.ok("spaces_create", **args)["space"]
        self.assertEqual({file["path"] for file in core.list_files(sid)},
                         {"index.html", "vendor/preact.mjs", "vendor/hooks.mjs", "kit/spaces-kit.mjs", "kit/spaces-kit.css"})

    def test_library_reselection_preserves_existing_and_explicit_files_and_aliases(self):
        sid = self.create(libraries=["htm"], files={"index.html": HTML, "vendor/htm.mjs": "custom"},
                          manifest={"imports": {"htm": "custom.mjs"}})["space"]
        self.write(sid, libraries=["htm", "font:inter"])
        self.assertEqual(core.read_file(sid, "vendor/htm.mjs")["text"], "custom")
        self.assertEqual(core.get_space(sid)["manifest"]["imports"]["htm"], "custom.mjs")
        self.write(sid, files={"vendor/htm.mjs": "replacement"}, libraries=["htm"])
        self.assertEqual(core.read_file(sid, "vendor/htm.mjs")["text"], "replacement")
        self.write(sid, files={"vendor/htm.mjs": None}, libraries=["htm"])
        self.assertNotIn("vendor/htm.mjs", {file["path"] for file in core.list_files(sid)})

    def test_write_library_conflict_and_invalid_selection_are_atomic(self):
        sid = self.create()["space"]
        self.write(sid, files={"note.txt": "retained"})
        before = core.bundle(sid)
        reply = self.call("spaces_write_files", space=sid, summary="Stale", files={}, libraries=["htm"], base_rev=1)
        self.assertEqual(reply["error"]["code"], "conflict", reply)
        for libraries in (["unknown"], [True], [{}], "unknown"):
            with self.subTest(libraries=libraries):
                self.invalid("spaces_write_files", space=sid, summary="Invalid", files={}, libraries=libraries)
                self.assertEqual(core.bundle(sid), before)

    def test_write_library_selection_with_manifest_replacement(self):
        sid = self.create()["space"]
        self.write(sid, files={"space.json": json.dumps({"theme": {"preset": "minimal"}})}, libraries=["htm"])
        manifest = core.get_space(sid)["manifest"]
        self.assertEqual(manifest["theme"], {"preset": "minimal"})
        self.assertEqual(manifest["imports"], {"htm": "vendor/htm.mjs"})

    def test_schema_advertises_same_libraries_for_both_tools(self):
        for tool in ("spaces_create", "spaces_write_files"):
            with self.subTest(tool=tool):
                enum = self.tools[tool]["schema"]["parameters"]["properties"]["libraries"]["items"]["enum"]
                self.assertEqual(set(enum), {"preact", "preact/hooks", "lightweight-charts", "spaces-kit", *SHELF})

    def test_kit_selection_gives_exact_link_without_editing_html(self):
        for operation in ("create", "write"):
            with self.subTest(operation=operation):
                result = self.create(libraries=["spaces-kit"] if operation == "create" else [])
                sid = result["space"]
                if operation == "write":
                    result = self.write(sid, libraries=["spaces-kit"])
                self.assertTrue(any(KIT_LINK in note for note in [*result["warnings"], *result.get("notes", [])]), result)
                self.assertEqual(core.read_file(sid, "index.html")["text"], HTML)
                self.assertEqual(contents(core.read_file(sid, "kit/spaces-kit.css")),
                                 (PACKAGE / "runtime/kit/spaces-kit.css").read_bytes())


if __name__ == "__main__":
    unittest.main()
