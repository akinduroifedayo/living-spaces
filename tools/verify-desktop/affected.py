"""List the Desktop journeys to re-drive for a change, from tools/verify-desktop/coverage.json.

Usage: python3 tools/verify-desktop/affected.py [BASE]   (default BASE: origin/main; compares BASE...HEAD plus the working tree)
Exit 0 when nothing mapped changed, 3 when a driven journey must be re-driven. Unmapped source files are listed, never ignored;
renamed or moved files count at both their old and new paths."""
import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
def git(*a):  # NUL-delimited: no quoting of unusual names, no splitting on spaces
    out = subprocess.run(["git", "-C", str(root), *a], capture_output=True, check=True).stdout
    return [p.decode("utf-8", "surrogateescape") for p in out.split(b"\0") if p]
# --no-renames reports a move as delete + add, so both the old and the new path are checked
changed = sorted(set(git("diff", "-z", "--no-renames", "--name-only", f"{base}...HEAD"))
                 | set(git("diff", "-z", "--no-renames", "--name-only", "HEAD"))
                 | set(git("ls-files", "-z", "--others", "--exclude-standard")))
cov = json.loads((root / "tools/verify-desktop/coverage.json").read_text())
hit = lambda paths, f: any(f == p or (p.endswith("/") and f.startswith(p)) or f.startswith(p + "/") for p in paths)
prereq = [f for f in changed if hit(cov["prerequisites"]["paths"], f)]
redrive, unmapped = {}, []
for f in changed:
    names = [n for n, j in cov["journeys"].items() if hit(j["paths"], f)]
    for n in names: redrive.setdefault(n, []).append(f)
    if not names and f not in prereq and f.startswith("src/"): unmapped.append(f)
if prereq:
    print("prerequisites changed (re-drive every journey):", *prereq, sep="\n  ")
    for n in cov["journeys"]: redrive.setdefault(n, [])
for n, files in redrive.items():
    print(f"{n} [{cov['journeys'][n]['status']}]:", *(files or ["(prerequisite change)"]), sep="\n  ")
if unmapped:
    print("source changes with no mapped journey (extend coverage.json or record why none applies):", *unmapped, sep="\n  ")
sys.exit(3 if any(cov["journeys"][n]["status"] == "driven" for n in redrive) else 0)
