import base64
import copy
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("check_shelf", ROOT / "scripts/check-shelf.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class ShelfTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".run").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".run")
        self.addCleanup(self.temp.cleanup)
        self.runtime = Path(self.temp.name) / "runtime"
        self.manifest = self.runtime / "vendor/SHELF.json"
        self.shelf = {"schema": 1, "libraries": {}, "files": {}, "sources": []}
        for name, package, license_name, payload in (
            ("htm", "htm", "Apache-2.0", {"vendor/htm.mjs": "dist/htm.mjs"}),
            ("lucide", "lucide", "ISC AND MIT", {
                "vendor/lucide.mjs": "dist/esm/lucide.mjs (bundled with esbuild)",
            }),
            ("font:inter", "@fontsource/inter", "OFL-1.1", self.font_files("inter")),
            ("font:dm-sans", "@fontsource/dm-sans", "OFL-1.1", self.font_files("dm-sans")),
        ):
            payload[f"vendor/licenses/{name.removeprefix('font:')}-LICENSE"] = "LICENSE"
            library = {"version": "1.2.3", "license": license_name, "files": list(payload)}
            if not name.startswith("font:"):
                library["imports"] = {name: f"vendor/{name}.mjs"}
            self.shelf["libraries"][name] = library
            self.shelf["sources"].append({
                "name": package, "version": "1.2.3",
                "url": f"https://registry.npmjs.org/{package}/-/{package.rsplit('/', 1)[-1]}-1.2.3.tgz",
                "integrity": "sha512-" + base64.b64encode(b"x" * 64).decode(),
            })
            for relative, upstream in payload.items():
                raw = f"fixture {relative}\n".encode()
                path = self.runtime / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
                self.shelf["files"][relative] = {
                    "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                    "source": upstream, "package": package, "version": "1.2.3", "license": license_name,
                }
        self.write_manifest()

    def font_files(self, name):
        return {
            f"vendor/fonts/{name}.css": "latin-400.css + latin-700.css (adapted relative URLs)",
            f"vendor/fonts/{name}-latin-400-normal.woff2": f"files/{name}-latin-400-normal.woff2",
            f"vendor/fonts/{name}-latin-700-normal.woff2": f"files/{name}-latin-700-normal.woff2",
        }

    def write_manifest(self):
        self.manifest.write_text(json.dumps(self.shelf), encoding="utf-8")

    def assert_invalid(self, message):
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, message):
            checker.check_shelf(self.runtime)

    def test_valid_shelf(self):
        self.assertEqual(checker.check_shelf(self.runtime),
                         (12, sum(file["bytes"] for file in self.shelf["files"].values())))

    def test_cli_success_and_failure_have_exit_codes(self):
        for valid in (True, False):
            with self.subTest(valid=valid):
                self.shelf["schema"] = 1 if valid else True
                self.write_manifest()
                output, errors = io.StringIO(), io.StringIO()
                with redirect_stdout(output), redirect_stderr(errors):
                    status = checker.main(["--runtime", str(self.runtime)])
                self.assertEqual(status, 0 if valid else 1)
                self.assertIn("PASS:" if valid else "FAIL:", output.getvalue() + errors.getvalue())
                self.assertNotIn("Traceback", errors.getvalue())

    def test_malformed_json_and_duplicate_keys_fail_cleanly(self):
        for raw in (b"{", b"\xff", b'{"schema":1,"schema":1}', b"[" * 2000):
            with self.subTest(raw=raw[:30]):
                self.manifest.write_bytes(raw)
                with redirect_stderr(io.StringIO()) as errors:
                    self.assertEqual(checker.main(["--runtime", str(self.runtime)]), 1)
                self.assertIn("FAIL:", errors.getvalue())
                self.assertNotIn("Traceback", errors.getvalue())

    def test_wrong_shapes_fail_cleanly(self):
        baseline = copy.deepcopy(self.shelf)
        for field, value in (("schema", True), ("schema", 2), ("libraries", []), ("files", []),
                             ("sources", {}), ("sources", [None] * 4)):
            with self.subTest(field=field, value=value):
                self.shelf = copy.deepcopy(baseline)
                self.shelf[field] = value
                self.assert_invalid(".")

    def test_missing_and_unknown_fields(self):
        for target in (self.shelf, self.shelf["libraries"]["htm"],
                       self.shelf["files"]["vendor/htm.mjs"], self.shelf["sources"][0]):
            with self.subTest(target=list(target)):
                target["unknown"] = 1
                self.assert_invalid("missing or unknown fields")
                del target["unknown"]
                key = next(iter(target))
                value = target.pop(key)
                self.assert_invalid("missing or unknown fields")
                target[key] = value

    def test_invalid_hash_and_byte_counts(self):
        metadata = self.shelf["files"]["vendor/htm.mjs"]
        for field, values in (("sha256", (None, "f" * 63, "Z" * 64)),
                              ("bytes", (True, -1, 0, 1.5, "12", 8 * 1024 * 1024 + 1))):
            original = metadata[field]
            for value in values:
                with self.subTest(field=field, value=value):
                    metadata[field] = value
                    self.assert_invalid("Invalid")
            metadata[field] = original

    def test_unsafe_paths_are_rejected_before_payload_reads(self):
        baseline = copy.deepcopy(self.shelf)
        for relative in ("../secret", "/secret", "vendor/../secret", "vendor//htm.mjs",
                         "vendor/./htm.mjs", "vendor\\secret", "C:/secret", "a" * 201, "", None):
            for location in ("files", "library", "imports"):
                with self.subTest(relative=relative, location=location):
                    self.shelf = copy.deepcopy(baseline)
                    if location == "files":
                        self.shelf["files"][relative] = self.shelf["files"].pop("vendor/htm.mjs")
                    elif location == "library":
                        self.shelf["libraries"]["htm"]["files"][0] = relative
                    else:
                        self.shelf["libraries"]["htm"]["imports"]["htm"] = relative
                    self.write_manifest()
                    with patch.object(Path, "read_bytes", side_effect=AssertionError("payload read")):
                        with self.assertRaises(ValueError):
                            checker.check_shelf(self.runtime)

    def test_symlink_payload_and_directory_are_rejected_before_reads(self):
        for relative in ("vendor/htm.mjs", "vendor/fonts"):
            with self.subTest(relative=relative):
                path = self.runtime / relative
                destination = Path(self.temp.name) / path.name
                path.rename(destination)
                path.symlink_to(destination, target_is_directory=destination.is_dir())
                with patch.object(Path, "read_bytes", side_effect=AssertionError("payload read")):
                    with self.assertRaisesRegex(ValueError, "Symlink"):
                        checker.check_shelf(self.runtime)
                path.unlink()
                destination.rename(path)

    def test_symlink_manifest_is_rejected(self):
        destination = Path(self.temp.name) / "other.json"
        self.manifest.rename(destination)
        self.manifest.symlink_to(destination)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            checker.check_shelf(self.runtime)

    def test_missing_payload(self):
        (self.runtime / "vendor/htm.mjs").unlink()
        with self.assertRaisesRegex(ValueError, "Missing file"):
            checker.check_shelf(self.runtime)

    def test_modified_payload_same_size(self):
        path = self.runtime / "vendor/htm.mjs"
        path.write_bytes(b"x" * path.stat().st_size)
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            checker.check_shelf(self.runtime)

    def test_wrong_byte_count(self):
        self.shelf["files"]["vendor/htm.mjs"]["bytes"] += 1
        self.assert_invalid("Byte count mismatch")

    def test_each_library_requires_its_license(self):
        for name, library in self.shelf["libraries"].items():
            with self.subTest(name=name):
                license_path = library["files"].pop()
                self.assert_invalid("payload and license")
                library["files"].append(license_path)

    def test_each_physical_license_must_exist(self):
        for library in self.shelf["libraries"].values():
            path = self.runtime / library["files"][-1]
            with self.subTest(path=path.name):
                raw = path.read_bytes()
                path.unlink()
                with self.assertRaisesRegex(ValueError, "Missing file"):
                    checker.check_shelf(self.runtime)
                path.write_bytes(raw)

    def test_each_physical_license_must_match_its_hash(self):
        for library in self.shelf["libraries"].values():
            path = self.runtime / library["files"][-1]
            with self.subTest(path=path.name):
                raw = path.read_bytes()
                path.write_bytes(b"x" * len(raw))
                with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                    checker.check_shelf(self.runtime)
                path.write_bytes(raw)

    def test_duplicate_library_files_and_wrong_imports(self):
        library = self.shelf["libraries"]["htm"]
        library["files"].append("vendor/htm.mjs")
        self.assert_invalid("exactly once")
        library["files"].pop()
        library["imports"]["htm"] = "vendor/lucide.mjs"
        self.assert_invalid("Incorrect library imports")

    def test_file_provenance_must_match_library_and_source(self):
        for path in ("vendor/htm.mjs", "vendor/licenses/htm-LICENSE"):
            metadata = self.shelf["files"][path]
            for field, value in (("package", "lucide"), ("version", "9.9.9"),
                                 ("license", "MIT"), ("source", "../LICENSE")):
                with self.subTest(path=path, field=field):
                    original = metadata[field]
                    metadata[field] = value
                    self.assert_invalid("provenance disagrees")
                    metadata[field] = original

    def test_source_package_version_url_and_integrity(self):
        source = self.shelf["sources"][0]
        for field, value in (("name", "unknown"), ("version", "9.9.9"), ("url", "http://example.com/a"),
                             ("integrity", "sha512-notbase64"), ("integrity", "sha512-eA=="),
                             ("integrity", "sha256-" + "a" * 64), ("version", None)):
            with self.subTest(field=field, value=value):
                original = source[field]
                source[field] = value
                self.assert_invalid(".")
                source[field] = original

    def test_duplicate_source_and_missing_file_metadata(self):
        original = self.shelf["sources"][1]
        self.shelf["sources"][1] = self.shelf["sources"][0]
        self.assert_invalid("Duplicate source")
        self.shelf["sources"][1] = original
        del self.shelf["files"]["vendor/htm.mjs"]
        self.assert_invalid("Missing file metadata")

    def test_orphan_file_metadata(self):
        self.shelf["files"]["vendor/orphan.mjs"] = self.shelf["files"]["vendor/htm.mjs"].copy()
        self.assert_invalid("unreferenced")


if __name__ == "__main__":
    unittest.main()
