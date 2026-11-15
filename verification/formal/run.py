"""One command for Living Spaces formal verification: every check, then every negative control.

    python3 verification/formal/run.py                  # this tree, checks and controls
    python3 verification/formal/run.py --src DIR        # another checkout (same layout), e.g. a candidate
    python3 verification/formal/run.py --only records_integrity --no-controls

Exit 0 only when every check passes (known findings allowed and listed) and every control fails as expected.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import tla  # noqa: E402
from mutants import MUTANTS  # noqa: E402

CHECKS = ("refresh_one_shot", "refresh_concurrency", "records_integrity", "bridge_authority", "delete_residue", "net_boundary",
          "inspection_readonly")
CORE = Path("src/living-spaces/living_spaces_core")
SCRATCH = ROOT / ".fv-tools" / "scratch"


def run_check(name, src):
    started = time.monotonic()
    SCRATCH.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run([sys.executable, str(HERE / "checks" / f"{name}.py"), "--src", str(src)],
                          capture_output=True, text=True, timeout=900, cwd=HERE / "checks",
                          env={**os.environ, "TMPDIR": str(SCRATCH)})
    line = next((l for l in reversed(proc.stdout.splitlines()) if l.startswith(("PASS", "VIOLATION", "ERROR"))),
                proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "no output")
    summary = json.loads(line.removeprefix("PASS ")) if line.startswith("PASS ") else {}
    return {"code": proc.returncode, "line": line, "seconds": round(time.monotonic() - started, 1),
            "findings": summary.get("known_findings", {})}


def scratch_with(src, edits):
    SCRATCH.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="ls-fv-mutant-", dir=SCRATCH))
    shutil.copytree(Path(src) / "src" / "living-spaces", tmp / "src" / "living-spaces",
                    ignore=shutil.ignore_patterns("__pycache__", "node_modules"))
    for file, old, new in edits:
        path = tmp / CORE / file
        text = path.read_text()
        if text.count(old) != 1:
            shutil.rmtree(tmp)
            return None, f"{file}: mutant text found {text.count(old)} times (code drifted; update mutants.py)"
        path.write_text(text.replace(old, new))
    return tmp, None


def drift(src):
    coverage = json.loads((HERE / "COVERAGE.json").read_text())
    notes = []
    for name, entry in coverage["checks"].items():
        files = list(entry["covers"])
        if not (src / files[0]).exists():
            continue
        proc = subprocess.run(["git", "-C", str(src), "diff", "--stat", entry["sync_commit"], "--", *files],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            notes.append(f"{name}: cannot compare with sync commit {entry['sync_commit'][:7]} ({proc.stderr.strip()[:80]})")
        elif proc.stdout.strip():
            notes.append(f"{name}: covered files changed since sync {entry['sync_commit'][:7]}: "
                         + "; ".join(l.strip() for l in proc.stdout.strip().splitlines()[:-1]))
    return notes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", default=str(ROOT))
    parser.add_argument("--only", choices=CHECKS + ("refresh_model",))
    parser.add_argument("--no-controls", action="store_true")
    parser.add_argument("--json", help="write the full receipt here")
    args = parser.parse_args()
    src = Path(args.src).resolve()
    verifier_paths = sorted(HERE.rglob("*.py")) + [HERE / "COVERAGE.json", tla.MODEL,
                     ROOT / ".cursor/skills/verify-living-spaces-formal/SKILL.md"]
    source_paths = sorted((src / "src/living-spaces").rglob("*.py"))
    def hashes(paths, base):
        return {str(p.relative_to(base)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    top = subprocess.run(["git", "-C", str(src), "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()
    is_checkout = bool(top) and Path(top).resolve() == src
    head = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() if is_checkout else ""
    dirty = subprocess.run(["git", "-C", str(src), "status", "--porcelain", "--", "src"], capture_output=True, text=True).stdout.strip() if is_checkout else None
    print(f"Living Spaces formal verification: {src} at {head or 'unknown'}{' (src has uncommitted changes)' if dirty else ''}")
    receipt = {"src": str(src), "head": head, "src_dirty": bool(dirty) if is_checkout else None,
               "checks": {}, "controls": {}, "drift": drift(src) if is_checkout else ["source directory is not a checkout root; source identity requires file hashes"]}
    receipt["verifier_sha256"] = hashes(verifier_paths, ROOT)
    receipt["source_sha256"] = hashes(source_paths, src)
    for note in receipt["drift"]:
        print(f"  DRIFT {note}")
    ok = True
    started = time.monotonic()

    if args.only in (None, "refresh_model"):
        names = ["baseline"] if args.no_controls else list(tla.RUNS)
        for name in names:
            r = tla.run(name)
            r.pop("output")
            kind = "checks" if name == "baseline" else "controls"
            receipt[kind][f"refresh_model:{name}"] = r
            ok &= r["ok"]
            print(f"  {'ok ' if r['ok'] else 'BAD'} refresh_model:{name:34} expected {r['expected']:28} got {r['actual']} "
                  f"({r['distinct_states']} states)")

    for name in CHECKS:
        if args.only not in (None, name):
            continue
        r = run_check(name, src)
        r["ok"] = r["code"] == 0 and r["line"].startswith("PASS ")
        receipt["checks"][name] = r
        ok &= r["ok"]
        print(f"  {'ok ' if r['ok'] else 'BAD'} {name:47} {r['seconds']:6}s  {r['line'][:400]}")

    if not args.no_controls:
        for mid, m in MUTANTS.items():
            if args.only not in (None, m["check"]):
                continue
            if m.get("requires") and not (src / CORE / m["requires"]).exists():
                receipt["controls"][mid] = {"ok": True, "line": f"not applicable: no {m['requires']}"}
                print(f"  n/a control {mid:39} (this tree has no {m['requires']})")
                continue
            tmp, error = scratch_with(src, m["edits"])
            if error:
                r = {"ok": False, "line": error}
            else:
                assert tmp is not None
                r = run_check(m["check"], tmp)
                shutil.rmtree(tmp)
                r["ok"] = (r["code"] == 1 and r["line"].startswith("VIOLATION:")
                           and any(m["expect"] in story and all(part in story for part in m.get("signatures", ()))
                                   for story in r["line"].split(" | ")))
                r["mechanism_signatures"] = m.get("signatures", ())
            receipt["controls"][mid] = r
            ok &= r["ok"]
            print(f"  {'ok ' if r['ok'] else 'BAD'} control {mid:39} must fail with {m['expect']!r}: {r['line'][:220]}")

    receipt["inputs_unchanged"] = (receipt["verifier_sha256"] == hashes(verifier_paths, ROOT)
                                   and receipt["source_sha256"] == hashes(source_paths, src))
    ok &= receipt["inputs_unchanged"]
    if not receipt["inputs_unchanged"]:
        print("  BAD verification or product source changed during the run")
    receipt["ok"] = ok
    receipt["known_findings"] = {fid: details for result in receipt["checks"].values()
                                 for fid, details in result.get("findings", {}).items()}
    receipt["seconds"] = round(time.monotonic() - started, 1)
    if receipt["known_findings"]:
        print("  UNRESOLVED " + ", ".join(receipt["known_findings"]) + "; PASS does not mean these properties hold")
    print(f"{'PASS' if ok else 'FAIL'} in {receipt['seconds']}s")
    if args.json:
        Path(args.json).write_text(json.dumps(receipt, indent=2))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
