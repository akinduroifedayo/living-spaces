#!/usr/bin/env python3
"""Check the optional vendored shelf offline, without loading the plugin."""

import argparse
import base64
import binascii
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
LIBRARIES = {
    "htm": ("htm", "Apache-2.0", {"vendor/htm.mjs": "dist/htm.mjs"}),
    "lucide": ("lucide", "ISC AND MIT", {
        "vendor/lucide.mjs": "dist/esm/lucide.mjs (bundled with esbuild)",
    }),
    **{f"font:{font}": (f"@fontsource/{font}", "OFL-1.1", {
        f"vendor/fonts/{font}.css": "latin-400.css + latin-700.css (adapted relative URLs)",
        **{f"vendor/fonts/{font}-latin-{weight}-normal.woff2":
           f"files/{font}-latin-{weight}-normal.woff2" for weight in (400, 700)},
    }) for font in ("inter", "dm-sans")},
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def object_fields(value, fields, label):
    require(isinstance(value, dict), f"{label} must be an object")
    require(set(value) == set(fields), f"{label} has missing or unknown fields")


def safe_path(value):
    require(isinstance(value, str) and 0 < len(value) <= 200
            and re.fullmatch(r"[A-Za-z0-9._/-]+", value)
            and all(part not in ("", ".", "..") for part in value.split("/")),
            f"Unsafe relative path: {value!r}")
    return value


def checked_path(runtime, relative):
    path = runtime
    for part in safe_path(relative).split("/"):
        path = path / part
        require(not path.is_symlink(), f"Symlink is not allowed: {relative}")
    require(path.is_file(), f"Missing file: {relative}")
    return path


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def check_shelf(runtime):
    runtime = Path(runtime).resolve(strict=True)
    manifest = checked_path(runtime, "vendor/SHELF.json")
    require(manifest.stat().st_size <= 1024 * 1024, "SHELF.json exceeds 1 MiB")
    shelf = json.loads(manifest.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    object_fields(shelf, ("schema", "libraries", "files", "sources"), "shelf")
    require(type(shelf["schema"]) is int and shelf["schema"] == 1, "Unsupported shelf schema")
    object_fields(shelf["libraries"], LIBRARIES, "libraries")
    require(isinstance(shelf["files"], dict) and shelf["files"], "files must be a nonempty object")
    files = shelf["files"]
    for relative, metadata in files.items():
        safe_path(relative)
        object_fields(metadata, ("sha256", "bytes", "source", "package", "version", "license"), relative)
        require(isinstance(metadata["sha256"], str)
                and re.fullmatch(r"[0-9a-f]{64}", metadata["sha256"]), f"Invalid SHA-256: {relative}")
        require(type(metadata["bytes"]) is int and 0 < metadata["bytes"] <= 8 * 1024 * 1024,
                f"Invalid byte count: {relative}")
        for field in ("source", "package", "version", "license"):
            require(isinstance(metadata[field], str) and 0 < len(metadata[field]) <= 200,
                    f"Invalid {field}: {relative}")

    require(isinstance(shelf["sources"], list) and len(shelf["sources"]) == len(LIBRARIES),
            "sources must contain one entry per package")
    sources = {}
    for source in shelf["sources"]:
        object_fields(source, ("name", "version", "url", "integrity"), "source")
        for field, value in source.items():
            require(isinstance(value, str) and 0 < len(value) <= 500, f"Invalid source {field}")
        name, version = source["name"], source["version"]
        require(name not in sources, f"Duplicate source package: {name}")
        require(re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version), f"Invalid source version: {name}")
        url = urlsplit(source["url"])
        require(url.scheme == "https" and url.hostname and not url.username and not url.password,
                f"Invalid source URL: {name}")
        require(source["integrity"].startswith("sha512-"), f"Invalid source integrity: {name}")
        try:
            digest = base64.b64decode(source["integrity"][7:], validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError(f"Invalid source integrity: {name}") from exc
        require(len(digest) == 64, f"Invalid source integrity: {name}")
        sources[name] = source

    expected_files = set()
    require(set(sources) == {spec[0] for spec in LIBRARIES.values()}, "Source packages disagree with libraries")
    for name, (package, license_name, payload) in LIBRARIES.items():
        library = shelf["libraries"][name]
        module = not name.startswith("font:")
        fields = ("version", "license", "files", "imports") if module else ("version", "license", "files")
        object_fields(library, fields, f"library {name}")
        require(library["version"] == sources[package]["version"], f"Library version disagrees with source: {name}")
        require(library["license"] == license_name, f"Incorrect library license: {name}")
        require(isinstance(library["files"], list), f"Library files must be an array: {name}")
        for relative in library["files"]:
            safe_path(relative)
        license_path = f"vendor/licenses/{name.removeprefix('font:')}-LICENSE"
        expected = {**payload, license_path: "LICENSE"}
        require(len(library["files"]) == len(expected) and set(library["files"]) == set(expected),
                f"Library must include its payload and license exactly once: {name}")
        if module:
            require(isinstance(library["imports"], dict), f"Library imports must be an object: {name}")
            for relative in library["imports"].values():
                safe_path(relative)
            require(library["imports"] == {name: f"vendor/{name}.mjs"}, f"Incorrect library imports: {name}")
        for relative, upstream in expected.items():
            require(relative in files, f"Missing file metadata: {relative}")
            metadata = files[relative]
            require(metadata["package"] == package and metadata["version"] == library["version"]
                    and metadata["license"] == license_name and metadata["source"] == upstream,
                    f"File provenance disagrees with library/source: {relative}")
        expected_files.update(expected)
    require(set(files) == expected_files, "File metadata contains unreferenced payload")

    paths = {relative: checked_path(runtime, relative) for relative in files}
    total = 0
    for relative, path in paths.items():
        metadata = files[relative]
        require(path.stat().st_size == metadata["bytes"], f"Byte count mismatch: {relative}")
        raw = path.read_bytes()
        require(len(raw) == metadata["bytes"], f"Byte count mismatch: {relative}")
        require(hashlib.sha256(raw).hexdigest() == metadata["sha256"], f"SHA-256 mismatch: {relative}")
        total += len(raw)
    return len(files), total


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, default=ROOT / "src/living-spaces/runtime")
    args = parser.parse_args(argv)
    try:
        count, total = check_shelf(args.runtime)
    except (OSError, ValueError, RuntimeError, RecursionError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"PASS: shelf verified ({count} files, {total:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
