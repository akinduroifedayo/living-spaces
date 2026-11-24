"""Space icons: manifest forms, save-time image checks, the regenerate-once build result and the local icon route."""
import base64
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

try:
    from PIL import Image, ImageDraw
except ImportError:  # Hermes ships Pillow; a bare interpreter skips these cases instead of failing to import.
    raise unittest.SkipTest("Pillow is not installed")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "living-spaces"))
from living_spaces_core import db, icons, projects, SpacesError  # noqa: E402

TEAL = icons.FIELD["teal"]


def icon(field=TEAL, mark="#ffffff", radius=0.3, size=1024, fmt="PNG", centre=(0.5, 0.5), corners=None):
    """A synthetic icon: one solid disc on a flat field, the shape the prompt template asks for."""
    image = Image.new("RGB", (size, size), field)
    draw = ImageDraw.Draw(image)
    cx, cy, r = centre[0] * size, centre[1] * size, radius * size
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=mark)
    if corners:
        for x, y in ((0, 0), (size - 40, 0), (0, size - 40), (size - 40, size - 40)):
            draw.rectangle((x, y, x + 40, y + 40), fill=corners)
    out = io.BytesIO()
    image.save(out, fmt)
    return out.getvalue()


class IconCase(unittest.TestCase):
    def setUp(self):
        (ROOT / ".run").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".run")
        self.addCleanup(self.temp.cleanup)
        environment = patch.dict(os.environ, {"LIVING_SPACES_DB": str(Path(self.temp.name) / "spaces.db"),
                                              "HERMES_HOME": self.temp.name})
        environment.start()
        self.addCleanup(environment.stop)

    def create(self, icon_value, files=None, accent="teal"):
        return projects.create_space("Faultline Atlas", owner="Demo", author="agent:demo",
                                     files={"index.html": "<h1>x</h1>", **(files or {})},
                                     manifest={"accent": accent, "icon": icon_value})

    def write(self, sid, **kwargs):
        return projects.write_files(sid, author="agent:demo", summary="edit", **kwargs)


class ManifestForms(IconCase):
    def test_string_icon_stays_valid_and_needs_no_image(self):
        space = self.create("globe")
        self.assertEqual(space["icon"], "globe")
        self.assertIsNone(space["icon_image"])
        self.assertIsNone(projects.icon_check(space["id"]))

    def test_malformed_string_keeps_todays_fallback(self):
        self.assertEqual(self.create('book" onclick="x')["icon"], "layers")

    def test_object_glyph_form_reports_the_glyph(self):
        space = self.create({"glyph": "sprout"})
        self.assertEqual(space["icon"], "sprout")
        self.assertIsNone(space["icon_image"])

    def test_image_paths_are_local_assets_only(self):
        for bad in ("https://example.invalid/icon.png", "data:image/png;base64,AAAA", "../icon.png", "assets/../x.png",
                    "/assets/icon.png", "assets/icon.svg", "assets/Icon.PNG", "icon.webp", "assets/sub/icon.webp", 7):
            with self.subTest(bad=bad), self.assertRaises(SpacesError) as caught:
                self.create({"image": bad, "glyph": "graph"})
            self.assertEqual(caught.exception.code, "invalid")
            self.assertIn("assets/icon.webp", caught.exception.message)

    def test_bad_object_glyph_is_refused(self):
        with self.assertRaises(SpacesError):
            self.create({"glyph": "Not A Glyph"})


class Checks(IconCase):
    def test_a_template_icon_passes_and_is_stored_normalised(self):
        space = self.create({"image": "assets/icon.webp", "glyph": "graph"}, {"assets/icon.webp": icon()})
        self.assertTrue(space["icon_image"]["pass"], space["icon_image"])
        stored = base64.b64decode(projects.read_file(space["id"], "assets/icon.webp")["b64"])
        image = Image.open(io.BytesIO(stored))
        self.assertEqual((image.format, image.size), ("WEBP", (512, 512)), "a 1024 px PNG is stored as 512 px WebP")
        check = projects.icon_check(space["id"])
        self.assertEqual((check["pass"], check["attempt"], check["fallback"]), (True, 1, "glyph:graph"))

    def test_an_opaque_rgba_icon_over_the_size_cap_is_normalised_and_passes(self):
        # A template icon with per-channel grain, as provider PNGs carry, saved RGBA with every alpha at 255.
        image = Image.open(io.BytesIO(icon())).convert("RGB")
        def grain(channel):
            mask = Image.effect_noise(image.size, 64).convert("L").point(lambda v: 255 if v > 128 else 0)
            return Image.composite(channel.point(lambda v: min(255, v + 2)), channel, mask)
        image = Image.merge("RGBA", (*map(grain, image.split()), Image.new("L", image.size, 255)))
        out = io.BytesIO()
        image.save(out, "PNG")
        raw = out.getvalue()
        self.assertGreater(len(raw), icons.LIMITS["max_bytes"], "the fixture must exceed the cap before normalising")
        space = self.create({"image": "assets/icon.png", "glyph": "graph"}, {"assets/icon.png": raw})
        self.assertTrue(space["icon_image"]["pass"], space["icon_image"])
        stored = Image.open(io.BytesIO(base64.b64decode(projects.read_file(space["id"], "assets/icon.png")["b64"])))
        self.assertEqual(stored.size, (512, 512), "an opaque alpha channel does not skip normalisation")

    def test_a_see_through_rgba_icon_is_stored_as_given_and_fails(self):
        image = Image.open(io.BytesIO(icon())).convert("RGBA")
        image.putalpha(200)
        out = io.BytesIO()
        image.save(out, "PNG")
        space = self.create({"image": "assets/icon.png", "glyph": "graph"}, {"assets/icon.png": out.getvalue()})
        self.assertFalse(space["icon_image"]["pass"])
        self.assertTrue(any("transparency" in f for f in space["icon_image"]["fails"]), space["icon_image"])

    def test_every_failure_is_a_plain_sentence(self):
        cases = {
            "format": (icon(fmt="JPEG"), "format JPEG"),
            "too small": (icon(size=256), "too small 256px"),
            "too large": (icon(size=2304), "too large 2304px"),
            "off palette": (icon(field="#ff0000"), "field off-palette for teal"),
            "own tile": (icon(corners="#ffffff"), "corners differ"),
            "contrast": (icon(mark="#d05050"), "contrast"),
            "tiny mark": (icon(radius=0.08), "mark too small"),
            "off centre": (icon(radius=0.18, centre=(0.3, 0.3)), "off-centre"),
            "safe area": (icon(radius=0.45), "safe area"),
        }
        for name, (raw, expected) in cases.items():
            with self.subTest(name):
                result = icons.check(raw, "teal")
                self.assertFalse(result["pass"])
                self.assertTrue(any(expected in fail for fail in result["fails"]), result["fails"])

    def test_size_cap(self):
        noisy = Image.effect_noise((2048, 2048), 128).convert("RGB")
        out = io.BytesIO()
        noisy.save(out, "PNG")
        self.assertTrue(any("KiB" in fail for fail in icons.check(out.getvalue(), "teal")["fails"]))

    def test_unreadable_bytes_fail_without_raising(self):
        self.assertEqual(icons.check(b"not an image", "teal")["fails"], ["unreadable: not a PNG or WebP image"])

    def test_a_missing_image_file_fails_and_the_glyph_shows(self):
        space = self.create({"image": "assets/icon.webp", "glyph": "book"})
        self.assertFalse(space["icon_image"]["pass"])
        self.assertIn("not in this Space's files", space["icon_image"]["fails"][0])


class ReviewRegressions(IconCase):
    def test_a_huge_header_is_refused_before_any_pixel_is_decoded(self):
        import struct, zlib
        small = io.BytesIO(); Image.new("RGB", (1, 1)).save(small, "PNG"); raw = bytearray(small.getvalue())
        ihdr = struct.pack(">II", 12000, 12000) + bytes(raw[24:29])
        raw[16:29] = ihdr
        raw[29:33] = struct.pack(">I", zlib.crc32(b"IHDR" + ihdr) & 0xFFFFFFFF)
        with patch.object(Image.Image, "load", side_effect=AssertionError("decoded")):
            self.assertIn("too large 12000px (max 2048)", icons.check(bytes(raw), "teal")["fails"])
            self.assertEqual(icons.prepare("assets/icon.png", bytes(raw)), bytes(raw))

    def test_animated_and_palette_transparent_images_fail(self):
        frames = [Image.open(io.BytesIO(icon())), Image.new("RGB", (1024, 1024), "#ff0000")]
        out = io.BytesIO(); frames[0].save(out, "PNG", save_all=True, append_images=frames[1:])
        self.assertIn("animated (one still image only)", icons.check(out.getvalue(), "teal")["fails"])
        palette = Image.open(io.BytesIO(icon(size=512))).convert("P")
        out = io.BytesIO(); palette.save(out, "PNG", transparency=palette.getpixel((256, 256)))
        self.assertTrue(any("transparency" in f for f in icons.check(out.getvalue(), "teal")["fails"]))

    def test_selecting_an_existing_asset_normalises_it(self):
        space = self.create("globe", {"assets/big.png": icon()})
        self.write(space["id"], files={}, manifest={"name": "Faultline Atlas", "accent": "teal", "icon": {"image": "assets/big.png"}})
        stored = base64.b64decode(projects.read_file(space["id"], "assets/big.png")["b64"])
        self.assertEqual(Image.open(io.BytesIO(stored)).size, (512, 512))
        self.assertTrue(projects.icon_check(space["id"])["pass"])

    def test_writing_back_the_stored_bytes_is_not_a_regeneration(self):
        space = self.create({"image": "assets/icon.webp", "glyph": "graph"}, {"assets/icon.webp": icon(mark="#d05050")})
        stored = base64.b64decode(projects.read_file(space["id"], "assets/icon.webp")["b64"])
        self.write(space["id"], files={"assets/icon.webp": stored})
        after = base64.b64decode(projects.read_file(space["id"], "assets/icon.webp")["b64"])
        self.assertEqual(after, stored, "stored-form bytes are kept byte for byte")
        self.assertEqual(projects.icon_check(space["id"])["attempt"], 1)


class RegenerateOnce(IconCase):
    def plugin(self):
        path = ROOT / "src/living-spaces/__init__.py"
        spec = importlib.util.spec_from_file_location("icon_plugin", path, submodule_search_locations=[str(path.parent)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def call(self, plugin, fn, args):
        return json.loads(plugin._handler(fn)(args))

    def b64(self, raw):
        return {"b64": base64.b64encode(raw).decode(), "mime": "image/png"}

    def test_failed_checks_ask_for_one_regeneration_then_stop(self):
        plugin = self.plugin()
        bad = icon(mark="#d05050")
        manifest = json.dumps({"name": "Atlas", "accent": "teal", "icon": {"image": "assets/icon.webp", "glyph": "graph"}})
        first = self.call(plugin, plugin.spaces_create, {"name": "Atlas", "libraries": [],
                                                         "files": {"index.html": "x", "space.json": manifest, "assets/icon.webp": self.b64(bad)}})
        self.assertTrue(first["ok"], first)
        result = first["result"]
        sid = result["space"]
        self.assertEqual((result["icon_check"]["pass"], result["icon_check"]["attempt"]), (False, 1))
        self.assertIn("Regenerate the icon once", result["icon_check"]["next"])
        self.assertTrue(any("Icon image failed the checks" in w for w in result["warnings"]))

        second = self.call(plugin, plugin.spaces_write_files, {"space": sid, "summary": "icon", "files": {"assets/icon.webp": self.b64(icon(mark="#e06666"))}})
        self.assertEqual(second["result"]["icon_check"]["attempt"], 2)
        self.assertIn("Stop regenerating", second["result"]["icon_check"]["next"])
        self.assertEqual(second["result"]["icon_check"]["fallback"], "glyph:graph")

        code_only = self.call(plugin, plugin.spaces_write_files, {"space": sid, "summary": "code", "files": {"index.html": "y"}})
        self.assertEqual(code_only["result"]["icon_check"]["attempt"], 2, "an unchanged image is not re-checked")

        fixed = self.call(plugin, plugin.spaces_write_files, {"space": sid, "summary": "icon", "files": {"assets/icon.webp": self.b64(icon())}})
        self.assertTrue(fixed["result"]["icon_check"]["pass"], "a later passing image is shown")
        again = self.call(plugin, plugin.spaces_write_files, {"space": sid, "summary": "icon", "files": {"assets/icon.webp": self.b64(bad)}})
        self.assertEqual(again["result"]["icon_check"]["attempt"], 1, "after a pass the count restarts")

    def test_a_string_icon_build_has_no_icon_check(self):
        plugin = self.plugin()
        response = self.call(plugin, plugin.spaces_create, {"name": "Plain", "libraries": [], "files": {"index.html": "x"}})
        self.assertNotIn("icon_check", response["result"])

    def test_changing_the_accent_rechecks_the_same_image(self):
        space = self.create({"image": "assets/icon.webp", "glyph": "graph"}, {"assets/icon.webp": icon()})
        self.assertTrue(space["icon_image"]["pass"])
        self.write(space["id"], files={}, manifest={"name": "Faultline Atlas", "accent": "rose", "icon": {"image": "assets/icon.webp", "glyph": "graph"}})
        record = projects.icon_check(space["id"])
        self.assertFalse(record["pass"])
        self.assertTrue(any("off-palette for rose" in fail for fail in record["fails"]))


class IconRoute(IconCase):
    def client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        path = ROOT / "src/living-spaces/dashboard/plugin_api.py"
        spec = importlib.util.spec_from_file_location("icon_api", path)
        api = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(api)
        app = FastAPI()
        app.include_router(api.router)
        return TestClient(app)

    def test_only_a_passing_image_is_served_and_only_as_a_raster_data_url(self):
        good = self.create({"image": "assets/icon.webp", "glyph": "graph"}, {"assets/icon.webp": icon()})
        bad = self.create({"image": "assets/icon.webp", "glyph": "graph"}, {"assets/icon.webp": icon(mark="#d05050")})
        plain = self.create("globe")
        with self.client() as client:
            response = client.get(f"/spaces/{good['id']}/icon")
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["sha"], good["icon_image"]["sha"])
            self.assertTrue(body["image"].startswith("data:image/webp;base64,"))
            for sid in (bad["id"], plain["id"]):
                self.assertEqual(client.get(f"/spaces/{sid}/icon").status_code, 404)
            listed = {space["id"]: space for space in client.get("/spaces").json()["spaces"]}
            self.assertTrue(listed[good["id"]]["icon_image"]["pass"])
            self.assertFalse(listed[bad["id"]]["icon_image"]["pass"])
            self.assertIsNone(listed[plain["id"]]["icon_image"])

    def test_deleting_a_space_drops_its_icon_record(self):
        space = self.create({"image": "assets/icon.webp"}, {"assets/icon.webp": icon()})
        with patch.object(projects.upkeep, "on_delete", return_value=False):
            projects.delete_space(space["id"], actor="owner", confirm=space["id"])
        with db.read() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM icon_checks").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
