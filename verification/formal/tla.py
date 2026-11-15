"""TLC runs for verification/formal/refresh/RefreshOneShot.tla: the baseline and every broken variant."""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1] / ".fv-tools"
TLA_VERSION = "1.7.4"
TLA_URL = f"https://github.com/tlaplus/tlaplus/releases/download/v{TLA_VERSION}/tla2tools.jar"
TLA_SHA256 = "936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88"
MODEL = HERE / "refresh" / "RefreshOneShot.tla"
INVARIANTS = ("TypeOK", "AtMostOnce", "NoSuccessForSkippedRun", "NoFalseRefusal")
FLAGS = ("AllowLongRun", "BrokenNoResume", "BrokenNoSkipCheck", "BrokenNoConsume",
         "BrokenNoBackgroundConsume", "BrokenNoPostRunCleanup", "BrokenSlotDueAtCreate")

# name -> (flags set TRUE, expected outcome, invariants checked). Expected is "pass" or the invariant
# TLC must report violated. Each broken run reintroduces one historical defect; see SKILL.md.
RUNS = {
    "baseline": ((), "pass", INVARIANTS),
    "a-no-resume": (("BrokenNoResume", "BrokenNoSkipCheck"), "NoSuccessForSkippedRun", INVARIANTS),
    "a-no-skip-check": (("BrokenNoSkipCheck",), "NoSuccessForSkippedRun", INVARIANTS),
    "b-no-consume": (("BrokenNoConsume",), "AtMostOnce", INVARIANTS),
    "c-background-not-consumed": (("BrokenNoBackgroundConsume",), "AtMostOnce", INVARIANTS),
    "c-db-error-no-cleanup": (("BrokenNoPostRunCleanup",), "AtMostOnce", INVARIANTS),
    # A due one-shot also breaks AtMostOnce first; checking NoFalseRefusal alone shows defect (d) itself.
    "d-slot-due-at-create": (("BrokenSlotDueAtCreate",), "NoFalseRefusal", ("TypeOK", "NoFalseRefusal")),
    # Finding F1 in the code at the sync commit; see SKILL.md "Findings".
    "finding-F1-refused-after-success": ((), "NoRefusalAfterSuccessfulRun", ("TypeOK", "NoRefusalAfterSuccessfulRun")),
    # Known residual, documented at upkeep.py:19-23: a run longer than the 7-day slot can be claimed again.
    "residual-run-outlasts-slot": (("AllowLongRun",), "AtMostOnce", INVARIANTS),
}


def jar() -> Path:
    path = TOOLS / f"tla2tools-{TLA_VERSION}.jar"
    if not path.exists():
        TOOLS.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(TLA_URL, timeout=60) as response:
            path.write_bytes(response.read())
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != TLA_SHA256:
        raise SystemExit(f"{path} has sha256 {digest}, expected {TLA_SHA256}; delete it and rerun")
    return path


def run(name: str) -> dict:
    flags, expected, invariants = RUNS[name]
    if shutil.which("java") is None:
        raise SystemExit("java is not on PATH; TLC needs Java 11 or newer")
    with tempfile.TemporaryDirectory(prefix="ls-tlc-") as tmp:
        shutil.copy(MODEL, tmp)
        cfg = ["SPECIFICATION Spec", "CONSTANTS"]
        cfg += [f"    {flag} = {'TRUE' if flag in flags else 'FALSE'}" for flag in FLAGS]
        cfg += [f"INVARIANT {inv}" for inv in invariants]
        Path(tmp, "RefreshOneShot.cfg").write_text("\n".join(cfg) + "\n")
        proc = subprocess.run(
            ["java", "-XX:+UseParallelGC", "-cp", str(jar()), "tlc2.TLC", "-workers", "auto",
             "-cleanup", "-metadir", str(Path(tmp, "states")),
             "-config", "RefreshOneShot.cfg", "RefreshOneShot.tla"],
            cwd=tmp, capture_output=True, text=True, timeout=600)
    out = proc.stdout + proc.stderr
    violated = re.search(r"Invariant (\w+) is violated", out)
    states = re.search(r"([\d,]+) distinct states found", out)
    if "Model checking completed. No error has been found." in out:
        actual = "pass"
    elif violated:
        actual = violated.group(1)
    else:
        actual = "error"
    return {"name": name, "expected": expected, "actual": actual, "ok": actual == expected,
            "distinct_states": states.group(1) if states else None, "output": out}
