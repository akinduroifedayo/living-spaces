import asyncio
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.python.test_agent_adapters import AdapterCase, PACKAGE, ROOT, SID, load


class RestDocumentTests(AdapterCase):
    def test_bundle_adds_only_the_fixed_document_without_mutating_core(self):
        project = self.core.bundle.return_value.copy()
        first = self.request("GET", f"/spaces/{SID}/bundle")
        second = self.request("GET", f"/spaces/{SID}/bundle")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.json(), first.json())
        wire = first.json()
        self.assertEqual(wire.pop("sandbox"), {
            "format": 2,
            "shell_srcdoc": (PACKAGE / "guest" / "space-host.html").read_text(encoding="utf-8"),
            "partition_off": (PACKAGE / "guest" / "partition-off.html").read_text(encoding="utf-8"),
            "partition_https": (PACKAGE / "guest" / "partition-https.html").read_text(encoding="utf-8"),
        })
        self.assertEqual(wire, project)
        self.assertEqual(self.core.bundle.return_value, project)
        self.core.bundle.assert_called_with(SID)

    def test_request_and_project_fields_cannot_supply_the_document_policy_or_path(self):
        marker = "untrusted-document-marker"
        self.core.bundle.return_value = {
            "space": {"id": SID, "name": marker}, "rev": 2,
            "manifest": {"entry": "guest/space-host.html", "sandbox": marker},
            "files": [{"path": path, "text": marker} for path in
                      ("guest/space-host.html", "space-host.html", "dashboard/_sandbox.py", "src/guest/loader.mjs")],
            "sandbox": {"format": 1, "shell_srcdoc": marker},
        }
        project = self.core.bundle.return_value.copy()
        response = self.request("GET", f"/spaces/{SID}/bundle", params={
            "shell_srcdoc": marker, "path": "guest/space-host.html", "policy": marker,
        }, json={"sandbox": marker, "shell_srcdoc": marker, "path": marker})
        self.assertEqual(response.status_code, 200)
        wire = response.json()
        self.assertNotIn(marker, wire["sandbox"]["shell_srcdoc"])
        self.assertEqual(wire["sandbox"]["shell_srcdoc"],
                         (PACKAGE / "guest" / "space-host.html").read_text(encoding="utf-8"))
        self.assertEqual(wire["files"], project["files"])
        self.assertEqual(self.core.bundle.return_value, project)
        self.core.bundle.assert_called_once_with(SID)

    def test_missing_unreadable_and_empty_document_are_visible_unavailable_errors(self):
        for error in (FileNotFoundError(), PermissionError(), UnicodeError(), ValueError()):
            with self.subTest(error=type(error).__name__), patch.object(
                self.api._sandbox, "trusted_document", side_effect=error
            ):
                response = self.request("GET", f"/spaces/{SID}/bundle")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()["error"]["code"], "unavailable")
                self.assertIn("Reinstall Living Spaces", response.json()["error"]["message"])
                self.assertNotIn("sandbox", response.json())


class InstalledDocumentTests(unittest.TestCase):
    def test_reader_uses_its_installed_sibling_asset_and_has_no_path_parameter(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".run") as directory:
            package = Path(directory) / "installed"
            (package / "dashboard").mkdir(parents=True)
            (package / "guest").mkdir()
            reader = package / "dashboard" / "_sandbox.py"
            reader.write_bytes((PACKAGE / "dashboard" / "_sandbox.py").read_bytes())
            asset = package / "guest" / "space-host.html"
            expected = (PACKAGE / "guest" / "space-host.html").read_bytes()
            asset.write_bytes(expected)
            variants = {}
            for key, filename in (("partition_off", "partition-off.html"), ("partition_https", "partition-https.html")):
                contents = (PACKAGE / "guest" / filename).read_bytes()
                (package / "guest" / filename).write_bytes(contents)
                variants[key] = contents.decode("utf-8")
            module = load("installed_document_reader", reader)
            first = module.trusted_document()
            self.assertEqual(first, module.trusted_document())
            self.assertEqual(first, {"format": 2, "shell_srcdoc": expected.decode("utf-8"), **variants})
            with self.assertRaises(TypeError):
                module.trusted_document("untrusted-path")
            asset.unlink()
            with self.assertRaises(FileNotFoundError):
                module.trusted_document()
            asset.write_text(" \n\t", encoding="utf-8")
            with self.assertRaises(ValueError):
                module.trusted_document()
            asset.write_bytes(b"\xff")
            with self.assertRaises(UnicodeError):
                module.trusted_document()

    def test_real_project_asset_names_do_not_change_rest_document_or_core_bundle(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".run") as directory:
            with patch.dict(os.environ, {"HERMES_HOME": directory,
                                         "LIVING_SPACES_DB": str(Path(directory) / "spaces.db")}):
                spec = importlib.util.spec_from_file_location("document_real_api", PACKAGE / "dashboard" / "plugin_api.py")
                api = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(api)
                core = api.load_core()
                marker = "project-asset-marker"
                files = {path: marker for path in ("index.html", "guest/space-host.html", "space-host.html",
                                                   "dashboard/_sandbox.py", "src/guest/loader.mjs")}
                created = core.create_space("Document provenance", owner="Fixture", author="user", files=files,
                                            manifest={"entry": "index.html", "sandbox": marker})
                sid = created["id"]
                before = core.bundle(sid)
                wire = asyncio.run(api.space_bundle(sid))
                self.assertEqual(wire.pop("sandbox"), api._sandbox.trusted_document())
                self.assertEqual(wire, before)
                self.assertEqual(core.bundle(sid), before)
                self.assertNotIn("sandbox", before)
                self.assertTrue(set(files).issubset({file["path"] for file in before["files"]}))
                self.assertNotIn(marker, api._sandbox.trusted_document()["shell_srcdoc"])
                core.write_files(sid, files={"guest/space-host.html": marker + "-changed"}, author="user", summary="Fixture edit")
                self.assertEqual(asyncio.run(api.space_bundle(sid))["sandbox"], api._sandbox.trusted_document())
