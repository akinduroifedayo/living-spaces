import base64
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from .test_c_tools import PACKAGE, PNG, ROOT, core, plugin

from living_spaces_core import limits, net

HTML = "<!doctype html><title>Public demo</title><img src=\"images/art.png\">"
PUBLIC = "93.184.216.34"


class Response:
    def __init__(self, body=b"", status=200, headers=None):
        self.status = status
        self.length = None
        self.headers = headers or {"Content-Type": "application/octet-stream"}
        self.stream = io.BytesIO(body)

    def getheaders(self):
        return list(self.headers.items())

    def getheader(self, name, default=None):
        return next((v for k, v in self.headers.items() if k.lower() == name.lower()), default)

    def read1(self, amount):
        return self.stream.read(amount)

    def close(self):
        self.stream.close()


class FileRefCase(unittest.TestCase):
    def setUp(self):
        (ROOT / ".run").mkdir(exist_ok=True)
        temp = tempfile.TemporaryDirectory(prefix="file-refs-", dir=ROOT / ".run")
        self.addCleanup(temp.cleanup)
        base = Path(os.path.realpath(temp.name))
        self.hermes, self.home, self.tmp, self.outside = (base / n for n in ("hermes", "home", "tmp", "outside"))
        for directory in (self.hermes, self.home, self.tmp, self.outside):
            directory.mkdir()
        env = patch.dict(os.environ, {"HERMES_HOME": str(self.hermes), "HOME": str(self.home),
                                     "LIVING_SPACES_DB": str(self.hermes / "spaces.db")})
        env.start()
        self.addCleanup(env.stop)
        tmp = patch.object(tempfile, "tempdir", str(self.tmp))
        tmp.start()
        self.addCleanup(tmp.stop)
        loader = patch.object(plugin._core, "load_core", return_value=core)
        loader.start()
        self.addCleanup(loader.stop)
        ctx = types.SimpleNamespace(register_tool=Mock(), register_skill=Mock())
        plugin.register(ctx)
        self.tools = {call.kwargs["name"]: call.kwargs for call in ctx.register_tool.call_args_list}

        self.resolver = Mock(return_value=[PUBLIC])
        self.responses = []
        self.connections = []

        def connect(host, port, ip, timeout):
            conn = Mock()
            conn.getresponse.side_effect = lambda: self.responses.pop(0)
            self.connections.append((host, port, ip, conn))
            return conn

        for name, value in (("_resolve", self.resolver), ("_connection", connect)):
            seam = patch.object(net, name, value)
            seam.start()
            self.addCleanup(seam.stop)

    def call(self, tool_name, **args):
        return json.loads(self.tools[tool_name]["handler"](args, profile_name="Public Demo"))

    def ok(self, tool_name, **args):
        reply = self.call(tool_name, **args)
        self.assertTrue(reply["ok"], reply)
        return reply["result"]

    def refused(self, code, tool_name, **args):
        reply = self.call(tool_name, **args)
        self.assertFalse(reply["ok"], reply)
        self.assertEqual(reply["error"]["code"], code, reply)
        return reply["error"]

    def place(self, directory, name, content=PNG):
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return str(path)

    def create(self, files):
        return self.ok("spaces_create", name="Art Demo", description="Public art",
                       files={"index.html": HTML, **files}, libraries=[])

    def read_bytes(self, sid, path):
        file = self.ok("spaces_read_file", space=sid, path=path)
        return base64.b64decode(file["b64"]) if "b64" in file else file["text"].encode()


class FromPathTests(FileRefCase):
    def test_png_round_trips_through_create_write_and_read(self):
        generated = self.place(self.hermes, "cache/images/generated.png")
        sid = self.create({"images/art.png": {"from_path": generated}})["space"]
        self.assertEqual(self.read_bytes(sid, "images/art.png"), PNG)
        second = PNG + b"\x00extra"
        self.ok("spaces_write_files", space=sid, summary="New art",
                files={"images/art2.png": {"from_path": self.place(self.tmp, "art2.png", second), "mime": "image/png"}})
        self.assertEqual(self.read_bytes(sid, "images/art2.png"), second)
        bundle = core.bundle(sid)
        self.assertEqual({f["path"]: f["mime"] for f in bundle["files"]}["images/art2.png"], "image/png")

    def test_all_three_roots_are_accepted(self):
        for root in (self.hermes, self.home, self.tmp):
            with self.subTest(root=root.name):
                self.create({"images/art.png": {"from_path": self.place(root, "pic.png")}})

    def test_mixed_b64_and_from_path_in_one_call(self):
        raw = b"\x89inline"
        sid = self.create({"images/art.png": {"from_path": self.place(self.home, "a.png")},
                           "images/small.webp": {"b64": base64.b64encode(raw).decode()}})["space"]
        self.assertEqual(self.read_bytes(sid, "images/art.png"), PNG)
        self.assertEqual(self.read_bytes(sid, "images/small.webp"), raw)

    def test_deny_rules(self):
        cases = {
            ".env file": (self.place(self.hermes, ".env", b"KEY=x"), "blocked"),
            "auth.json": (self.place(self.hermes, "auth.json", b"{}"), "blocked"),
            "token file": (self.place(self.home, "github_token.txt", b"x"), "blocked"),
            "secret file": (self.place(self.home, "client-secret.json", b"x"), "blocked"),
            "key file": (self.place(self.home, "server.key", b"x"), "blocked"),
            ".ssh": (self.place(self.home, ".ssh/id_ed25519.png", b"x"), "blocked"),
            "Spaces database": (str(self.hermes / "spaces.db"), "blocked"),
            "outside roots": (self.place(self.outside, "art.png"), "blocked"),
            "relative path": ("art.png", "invalid"),
            "directory": (str(self.home), "invalid"),
            "missing": (str(self.home / "nope.png"), "invalid"),
        }
        self.create({})
        for label, (path, code) in cases.items():
            with self.subTest(label):
                error = self.refused(code, "spaces_create", name=f"Deny {len(label)}", description="x",
                                     files={"index.html": HTML, "images/art.png": {"from_path": path}})
                self.assertTrue(error["message"].startswith("images/art.png: "), error)

    def test_symlink_escaping_roots_and_symlink_to_credentials_are_refused(self):
        escape = self.home / "escape.png"
        escape.symlink_to(self.place(self.outside, "art-outside.png"))
        error = self.refused("blocked", "spaces_create", name="Link Demo", description="x",
                             files={"index.html": HTML, "a.png": {"from_path": str(escape)}})
        self.assertEqual(error["reason"], "outside_roots")
        disguised = self.home / "art.png"
        disguised.symlink_to(self.place(self.hermes, "auth.json", b"{}"))
        error = self.refused("blocked", "spaces_create", name="Link Demo", description="x",
                             files={"index.html": HTML, "a.png": {"from_path": str(disguised)}})
        self.assertEqual(error["reason"], "denied_path")

    def test_oversize_file_is_refused_before_reading(self):
        big = Path(self.place(self.tmp, "big.png", b""))
        with open(big, "wb") as handle:
            handle.truncate(limits.FILE_BYTES + 1)
        with patch("builtins.open", side_effect=AssertionError("read before size check")):
            error = self.refused("limit", "spaces_create", name="Big Demo", description="x",
                                 files={"index.html": HTML, "big.png": {"from_path": str(big)}})
        self.assertEqual(error["limit"], limits.FILE_BYTES)

    def test_bad_entry_rolls_back_the_whole_write(self):
        sid = self.create({"images/art.png": {"from_path": self.place(self.home, "a.png")}})["space"]
        head = core.get_space(sid)["head_rev"]
        self.refused("blocked", "spaces_write_files", space=sid, summary="Mixed",
                     files={"index.html": "<p>changed</p>", "images/new.png": {"from_path": self.place(self.home, "b.png")},
                            "images/bad.png": {"from_path": self.place(self.hermes, ".env", b"x")}})
        self.assertEqual(core.get_space(sid)["head_rev"], head)
        self.assertEqual(self.read_bytes(sid, "index.html").decode(), HTML)
        self.assertNotIn("images/new.png", {f["path"] for f in core.list_files(sid)})

    def test_descriptor_must_have_exactly_one_source(self):
        path = self.place(self.home, "a.png")
        for value in ({"from_path": path, "from_url": "https://example.com/a.png"},
                      {"from_path": path, "b64": ""}, {"mime": "image/png"}, {"from_path": 1}):
            with self.subTest(value=value):
                self.refused("invalid", "spaces_create", name="Shape Demo", description="x",
                             files={"index.html": HTML, "a.png": value})


class FromUrlTests(FileRefCase):
    URL = "https://fonts.example/inter.woff2"

    def test_places_downloaded_bytes_and_records_provenance(self):
        font = b"wOF2" + bytes(range(256))
        self.responses = [Response(font)]
        result = self.create({"vendor/fonts/inter.woff2": {"from_url": self.URL}})
        self.assertEqual(self.read_bytes(result["space"], "vendor/fonts/inter.woff2"), font)
        host, port, ip, conn = self.connections[0]
        self.assertEqual((host, port, ip), ("fonts.example", 443, PUBLIC))
        headers = conn.request.call_args.kwargs["headers"]
        self.assertFalse({k.lower() for k in headers} & {"cookie", "authorization"})
        summary = core.list_revisions(result["space"])[0]["summary"]
        self.assertIn('https://fonts.example', summary)
        self.assertNotIn(self.URL, summary)
        self.assertIn(hashlib.sha256(font).hexdigest(), summary)

    def test_needs_no_net_grant(self):
        sid = self.create({})["space"]
        core.decide(sid, "net", "revoke")
        self.responses = [Response(PNG)]
        self.ok("spaces_write_files", space=sid, summary="Art", files={"a.png": {"from_url": "https://img.example/a.png"}})
        self.assertEqual(self.read_bytes(sid, "a.png"), PNG)

    def test_refuses_http_loopback_and_private_without_connecting(self):
        for url, ip, reason in (("http://img.example/a.png", PUBLIC, "scheme"),
                                ("https://127.0.0.1/a.png", PUBLIC, "private_address"),
                                ("https://img.example/a.png", "127.0.0.1", "private_address"),
                                ("https://img.example/a.png", "10.0.0.8", "private_address"),
                                ("https://img.example/a.png", "169.254.169.254", "private_address")):
            with self.subTest(url=url, ip=ip):
                self.resolver.return_value = [ip]
                error = self.refused("blocked", "spaces_create", name="Url Demo", description="x",
                                     files={"index.html": HTML, "a.png": {"from_url": url}})
                self.assertEqual(error["reason"], reason)
        self.assertEqual(self.connections, [])

    def test_refuses_over_cap_body(self):
        self.responses = [Response(b"x" * (limits.FILE_BYTES + 1))]
        error = self.refused("limit", "spaces_create", name="Url Demo", description="x",
                             files={"index.html": HTML, "a.png": {"from_url": self.URL}})
        self.assertEqual(error["limit"], limits.FILE_BYTES)

    def test_redirects_are_rechecked(self):
        self.resolver.side_effect = [[PUBLIC], ["10.0.0.8"]]
        self.responses = [Response(status=302, headers={"Location": "https://internal.example/a.png"})]
        error = self.refused("blocked", "spaces_create", name="Url Demo", description="x",
                             files={"index.html": HTML, "a.png": {"from_url": self.URL}})
        self.assertEqual(error["reason"], "private_address")
        self.assertEqual(len(self.connections), 1)
        self.resolver.side_effect = None
        self.resolver.return_value = [PUBLIC]
        self.responses = [Response(status=301, headers={"Location": "http://fonts.example/a.png"})]
        error = self.refused("blocked", "spaces_create", name="Url Demo", description="x",
                             files={"index.html": HTML, "a.png": {"from_url": self.URL}})
        self.assertEqual(error["reason"], "scheme")
        self.responses = [Response(status=302, headers={"Location": "/cdn/a.png"}), Response(PNG)]
        sid = self.create({"a.png": {"from_url": self.URL}})["space"]
        self.assertEqual(self.read_bytes(sid, "a.png"), PNG)

    def test_http_error_status_is_refused(self):
        self.responses = [Response(b"not found", status=404)]
        error = self.refused("blocked", "spaces_create", name="Url Demo", description="x",
                             files={"index.html": HTML, "a.png": {"from_url": self.URL}})
        self.assertEqual(error["status"], 404)


class SchemaTests(unittest.TestCase):
    def test_write_tools_advertise_file_references_and_limits(self):
        schemas = {schema["name"]: schema for _, schema in plugin.TOOLS}
        for name in ("spaces_create", "spaces_write_files"):
            with self.subTest(name):
                files = schemas[name]["parameters"]["properties"]["files"]
                variants = [set(v.get("required", [])) for v in files["additionalProperties"]["anyOf"]]
                self.assertIn({"from_path"}, variants)
                self.assertIn({"from_url"}, variants)
                self.assertIn({"b64"}, variants)
                text = files["description"] + schemas[name]["description"]
                for phrase in ("from_path", "from_url", "8 MB", "25 MB", "600 files"):
                    self.assertIn(phrase, text)

    def test_skill_runtime_leads_with_file_references(self):
        skill = (PACKAGE / "skills/build-space/SKILL.md").read_text()
        self.assertIn("from_path", skill)
        self.assertIn("from_url", skill)
