"""Space icons: the manifest icon form, the save-time image checks and the stored image (build-space icon-guide.md).

A Space names its icon in `space.json` as a kit glyph string (`"book"`, legacy names included) or as an object
`{"image": "assets/icon.webp", "glyph": "book"}`. The image is one generated symbol on a flat accent field. At save
the host normalises it to 512 px, runs the acceptance checks once and records the result on the Space, so the shell
never re-checks on render. A failing or missing image is never shown: the shell falls back to the glyph, then to a
deterministic sigil. Pillow ships with Hermes; without it every image fails the checks and the glyph shows.
"""
import io
import math
import re
import warnings

from .errors import SpacesError

# The host ramp's mid stop per accent. The prompt template asks for exactly this field colour.
FIELD = {"blue": "#2A61D7", "green": "#238B66", "amber": "#B06A2A", "purple": "#7E71BA",
         "teal": "#00879E", "rose": "#D83F63", "orange": "#C16235", "grey": "#7C7C85"}

LIMITS = {
    "min_px": 512, "max_px": 2048, "max_bytes": 512 * 1024,
    "formats": ("PNG", "WEBP"),
    "ring": 0.06,                 # outer ring sampled as the field
    "field_flat_max": 0.025,      # OKLab spread across the ring: no gradient, vignette or frame
    "corner_match_max": 0.05,     # each corner vs the ring: no model-drawn tile or white corners
    "field_palette_max": 0.09,    # ring vs the accent's field colour
    "subject_delta": 0.12,        # OKLab distance from the field that counts as the mark
    "safe_lo": 0.12, "safe_hi": 0.88,
    "centre_max": 0.08,
    "cover_min": 0.10, "cover_max": 0.50,
    "contrast_min": 3.0,
    "solidity20_min": 0.40,       # at 20 px: solid mark pixels / touched mark pixels
    "mass20_min": 0.12,           # at 20 px: solid mark pixels / all pixels
}
STORED_PX = 512
IMAGE_PATH = re.compile(r"assets/[a-z0-9._-]+\.(?:webp|png)\Z")
GLYPH_NAME = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
DEFAULT = "layers"
# The shell's fallback kit (src/desktop/ui/marks.mjs KIT and LEGACY). A test keeps the two lists equal.
KIT = ("graph", "seismo", "plane", "book", "weather", "dice", "coins", "pulse", "sprout", "vinyl", "briefcase", "chart",
       "calendar", "pin", "peaks", "target", "flask", "home", "camera", "compass", "chat", "shield", "bolt", "key")
LEGACY = {"brain": "graph", "globe": "seismo", "globe-alt": "compass", "checklist": "calendar", "graph-line": "chart",
          "heart": "pulse", "device-camera": "camera", "beaker": "flask", "zap": "bolt", "comment-discussion": "chat",
          "location": "pin", "music": "vinyl", "game": "dice"}


def manifest_icon(value):
    """The normalised manifest icon. A malformed string keeps today's fallback; a malformed object is refused."""
    if not isinstance(value, dict):
        return value if isinstance(value, str) and GLYPH_NAME.fullmatch(value) else DEFAULT
    icon = {}
    if "glyph" in value:
        if not isinstance(value["glyph"], str) or not GLYPH_NAME.fullmatch(value["glyph"]):
            raise SpacesError("invalid", "icon.glyph must be a kit glyph name such as \"book\"")
        icon["glyph"] = value["glyph"]
    if "image" in value:
        image = value["image"]
        if not isinstance(image, str) or not IMAGE_PATH.fullmatch(image) or ".." in image:
            raise SpacesError("invalid", "icon.image must be a file in this Space such as \"assets/icon.webp\" "
                                         "(assets/<name>.webp or .png; no URL, data URI or ..)")
        icon["image"] = image
    return icon or DEFAULT


def glyph(icon):
    """The glyph name kept in the Space summary: the fallback the shell resolves when no image passes."""
    return icon if isinstance(icon, str) else icon.get("glyph", DEFAULT)


def image_path(icon):
    return icon.get("image") if isinstance(icon, dict) else None


def _pil():
    try:
        from PIL import Image
        return Image
    except ImportError:
        return None


def _open(Image, raw):
    """Open an image's header only: no pixels are decoded, so the size checks run before any allocation."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)
        return Image.open(io.BytesIO(raw))


def _structure(image):
    """Fails readable from the header alone, before any pixel is allocated."""
    fails = []
    width, height = image.size
    if image.format not in LIMITS["formats"]:
        fails.append(f"format {image.format} (PNG or WebP only)")
    if width != height:
        fails.append(f"not square {width}x{height}")
    if min(width, height) < LIMITS["min_px"]:
        fails.append(f"too small {min(width, height)}px (min {LIMITS['min_px']})")
    if max(width, height) > LIMITS["max_px"]:
        fails.append(f"too large {max(width, height)}px (max {LIMITS['max_px']})")
    if getattr(image, "n_frames", 1) > 1:
        fails.append("animated (one still image only)")
    return fails


def _transparent(image):
    """Whether a decoded image has any pixel a viewer could see through. An opaque alpha channel is not one."""
    if "A" not in image.getbands() and "transparency" not in image.info:
        return False
    return image.convert("RGBA").getchannel("A").getextrema()[0] < 250  # type: ignore[index]


def _stored(path, image):
    return (image.size == (STORED_PX, STORED_PX) and image.format == ("WEBP" if path.endswith(".webp") else "PNG")
            and getattr(image, "n_frames", 1) == 1)


def prepare(path, raw):
    """The bytes to store at the icon path. An image already in the stored form (512 px, the path's format) is kept
    byte for byte, so a read-back rewrite changes nothing. A valid, opaque, still PNG or WebP of a usable size is
    re-encoded at 512 px. Anything else is stored as given and fails the checks."""
    Image = _pil()
    if Image is None or not isinstance(raw, (bytes, bytearray)):
        return raw
    try:
        image = _open(Image, raw)
        if _stored(path, image) or _structure(image):
            return raw
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image.load()
        if _transparent(image):
            return raw
        out = io.BytesIO()
        image = image.convert("RGB").resize((STORED_PX, STORED_PX), Image.Resampling.LANCZOS)
        if path.endswith(".webp"):
            image.save(out, "WEBP", quality=88, method=6)
        else:
            image.save(out, "PNG", optimize=True)
        return out.getvalue()
    except Exception:
        return raw


def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _oklab(r, g, b):
    r, g, b = _lin(r), _lin(g), _lin(b)
    l = math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m = math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s = math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def _lum(r, g, b):
    return _lin(r) * 0.2126 + _lin(g) * 0.7152 + _lin(b) * 0.0722


def _median(values):
    values = sorted(values)
    n = len(values)
    return values[n // 2] if n % 2 else (values[n // 2 - 1] + values[n // 2]) / 2


def _median3(points):
    return tuple(_median([p[k] for p in points]) for k in range(3))


def _dist(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def check(raw, accent):
    """Run every acceptance check on stored bytes. Returns {pass, fails, metrics}; fails are plain sentences."""
    fails: list = []
    metrics: dict = {"bytes": len(raw)}
    result: dict = {"pass": False, "fails": fails, "metrics": metrics}
    Image = _pil()
    if Image is None:
        fails.append("image checks are unavailable on this host (Pillow is missing)")
        return result
    try:
        image = _open(Image, raw)
    except Image.DecompressionBombError:
        fails.append(f"too large (over the decoder's pixel limit; max {LIMITS['max_px']}px)")
        return result
    except Exception:
        fails.append("unreadable: not a PNG or WebP image")
        return result
    metrics["format"], metrics["size"] = image.format, list(image.size)
    if len(raw) > LIMITS["max_bytes"]:
        fails.append(f"file {len(raw) // 1024} KiB > {LIMITS['max_bytes'] // 1024} KiB")
    structural = _structure(image)
    if structural:
        fails[:0] = structural
        return result
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image.load()
    except Exception:
        fails.append("unreadable: not a PNG or WebP image")
        return result
    if _transparent(image):
        fails.append("has transparency (the field must be opaque, edge to edge)")
    n = 256
    data = image.convert("RGB").resize((n, n), Image.Resampling.LANCZOS).tobytes()
    rgb = [(data[i] / 255, data[i + 1] / 255, data[i + 2] / 255) for i in range(0, len(data), 3)]
    memo = {}
    lab = [memo.get(p) or memo.setdefault(p, _oklab(*p)) for p in rgb]
    r = int(n * LIMITS["ring"])
    ring = [y * n + x for y in range(n) for x in range(n) if not (r <= x < n - r and r <= y < n - r)]
    med = _median3([lab[i] for i in ring])
    ring_d = [_dist(lab[i], med) for i in ring]
    mean = sum(ring_d) / len(ring_d)
    spread = math.sqrt(sum((d - mean) ** 2 for d in ring_d) / len(ring_d))
    deviation = sum(abs(lab[i][k] - med[k]) for i in ring for k in range(3)) / (3 * len(ring))
    flat = spread + deviation
    metrics["field_flat"] = round(flat, 4)
    if flat > LIMITS["field_flat_max"]:
        fails.append(f"field not flat ({flat:.3f}): gradient, vignette or frame")
    corners = [[lab[y * n + x] for y in ys for x in xs]
               for ys in (range(r), range(n - r, n)) for xs in (range(r), range(n - r, n))]
    corner = max(_dist(_median3(c), med) for c in corners)
    metrics["corner_delta"] = round(corner, 4)
    if corner > LIMITS["corner_match_max"]:
        fails.append("corners differ from the field: the model drew its own tile")
    field = FIELD.get(accent, FIELD["blue"])
    palette = _dist(med, _oklab(*(int(field[i:i + 2], 16) / 255 for i in (1, 3, 5))))
    metrics["field_vs_accent"] = round(palette, 4)
    if palette > LIMITS["field_palette_max"]:
        fails.append(f"field off-palette for {accent} ({palette:.3f}): use {field}")
    mask = [_dist(p, med) > LIMITS["subject_delta"] for p in lab]
    marked = [i for i, on in enumerate(mask) if on]
    cover = len(marked) / len(mask)
    metrics["cover"] = round(cover, 3)
    if not marked:
        fails.append("no mark found")
        return result
    xs, ys = [i % n for i in marked], [i // n for i in marked]
    box = [min(xs) / n, min(ys) / n, (max(xs) + 1) / n, (max(ys) + 1) / n]
    metrics["bbox"] = [round(v, 3) for v in box]
    if min(box) < LIMITS["safe_lo"] or max(box) > LIMITS["safe_hi"]:
        fails.append("mark leaves the safe area (outer 12% must be empty)")
    cx, cy = sum(xs) / len(xs) / n - 0.5, sum(ys) / len(ys) / n - 0.5
    bx, by = (box[0] + box[2]) / 2 - 0.5, (box[1] + box[3]) / 2 - 0.5
    offset = max(math.hypot(cx, cy), math.hypot(bx, by))
    metrics["centre_offset"] = round(offset, 3)
    if offset > LIMITS["centre_max"]:
        fails.append(f"mark off-centre ({offset:.2f})")
    if cover < LIMITS["cover_min"]:
        fails.append(f"mark too small ({cover:.0%} of the tile)")
    if cover > LIMITS["cover_max"]:
        fails.append(f"mark too big or busy ({cover:.0%} of the tile)")
    field_l = _lum(*_median3([rgb[i] for i in ring]))
    mark_l = _median([_lum(*rgb[i]) for i in marked])
    contrast = (max(field_l, mark_l) + 0.05) / (min(field_l, mark_l) + 0.05)
    metrics["contrast"] = round(contrast, 2)
    if contrast < LIMITS["contrast_min"]:
        fails.append(f"mark contrast {contrast:.2f}:1 < 3:1")
    small = Image.frombytes("L", (n, n), bytes(255 if on else 0 for on in mask)).resize((20, 20), Image.Resampling.BOX).tobytes()
    solid = sum(v / 255 > 0.6 for v in small)
    touched = sum(v / 255 > 0.15 for v in small)
    solidity, mass = solid / max(touched, 1), solid / 400
    metrics["solidity20"], metrics["mass20"] = round(solidity, 3), round(mass, 3)
    if solidity < LIMITS["solidity20_min"] or mass < LIMITS["mass20_min"]:
        fails.append(f"illegible at 20 px (solidity {solidity:.2f}, mass {mass:.2f}): thin or fussy detail")
    result["pass"] = not fails
    return result


def evaluate(load, previous, manifest, files):
    """The icon image record for a revision: {path, sha, accent, pass, fails, metrics, attempt}, or None.

    An unchanged image under an unchanged accent keeps its earlier result, so a code-only edit never re-checks.
    `attempt` counts consecutive tries: it grows while new images keep failing and restarts after a pass.
    """
    path = image_path(manifest["icon"])
    if path is None:
        return None
    sha, accent = files.get(path), manifest["accent"]
    if previous and previous.get("path") == path and previous.get("sha") == sha and previous.get("accent") == accent:
        return previous
    if sha is None:
        result = {"pass": False, "fails": [f"{path} is not in this Space's files"], "metrics": {}}
    else:
        result = check(load(sha), accent)
    attempt = previous["attempt"] + 1 if previous and not previous.get("pass") else 1
    return {"path": path, "sha": sha, "accent": accent, **result, "attempt": attempt}


def build_result(manifest, record):
    """`icon_check` for a write result, telling the bot whether to regenerate once or stop. None without an image."""
    if record is None:
        return None
    name = glyph(manifest["icon"])
    name = name if name in KIT else LEGACY.get(name)
    fallback = f"glyph:{name}" if name else "sigil"
    out = {"pass": record["pass"], "attempt": record["attempt"], "fails": record["fails"], "fallback": fallback}
    if record["pass"]:
        out["next"] = "The icon passed. The host shows it."
    elif record["attempt"] < 2:
        out["next"] = ("Regenerate the icon once with the icon-guide prompt template, fixing the causes in fails, "
                       "and save it at the same path. Until then the host shows the fallback.")
    else:
        out["next"] = ("Stop regenerating. The host shows the fallback; tell the user in one line that the icon "
                       "did not pass the checks.")
    return out


def image_data(raw):
    """A stored image as a data URL for the shell. The format comes from the bytes, never from the path."""
    import base64
    mime = "image/webp" if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP" else "image/png"
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
