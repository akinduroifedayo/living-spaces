#!/usr/bin/env python3
"""Compare the catalog draft with the package manifest; allow an unpinned draft."""

import argparse
from pathlib import Path
import re
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--draft", type=Path, default=ROOT / "docs/submission/catalog-entry.draft.yaml")
parser.add_argument("--manifest", type=Path, default=ROOT / "src/living-spaces/plugin.yaml")
args = parser.parse_args()

try:
    draft = yaml.safe_load(args.draft.read_text(encoding="utf-8"))
    manifest = yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
except (OSError, yaml.YAMLError) as exc:
    sys.exit(f"FAIL: {exc}")
if not isinstance(draft, dict) or not isinstance(manifest, dict):
    sys.exit("FAIL: draft and manifest must be YAML mappings")

errors = []
for field in ("name", "version", "requires_hermes"):
    if not isinstance(draft.get(field), str) or draft[field] != manifest.get(field):
        errors.append(f"{field} disagrees with plugin.yaml")

expected = {field: manifest.get(field, []) for field in
            ("provides_tools", "provides_hooks", "provides_middleware", "requires_env")}
if draft.get("capabilities") != expected:
    errors.append("capabilities (tools/hooks/middleware/env) disagree with plugin.yaml")
# Host permissions and the catalog's registration summary are different schemas.
if manifest.get("capabilities") != []:
    errors.append("manifest host capabilities changed; review the draft's no-host-capabilities disclosure")

pin = draft.get("sha")
if not isinstance(pin, str) or not (pin == "PIN_40_CHAR_SHA_AT_FINAL_COMMIT" or re.fullmatch(r"[0-9a-fA-F]{40}", pin)):
    errors.append("sha must be PIN_40_CHAR_SHA_AT_FINAL_COMMIT or a 40-hex SHA")
for field in ("repo", "description", "maintainer"):
    if not isinstance(draft.get(field), str) or not draft[field].strip():
        errors.append(f"missing required field: {field}")
if draft.get("category") != "desktop" or draft.get("subdir") != "src/living-spaces":
    errors.append("expected desktop category and src/living-spaces subdir")
if not (args.manifest.parent / "desktop/plugin.js").is_file():
    errors.append("Desktop entrypoint desktop/plugin.js is missing")

if errors:
    sys.exit("\n".join(f"FAIL: {error}" for error in errors))
print(f"PASS: catalog draft matches plugin.yaml ({len(expected['provides_tools'])} tools); pin syntax accepted")
