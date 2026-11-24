"""TLC runs for verification/formal/refresh/RefreshOneShot.tla: the baseline and every broken variant."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1] / ".fv-tools"
TLA_VERSION = "1.7.4"
TLA_URL = f"https://github.com/tlaplus/tlaplus/releases/download/v{TLA_VERSION}/tla2tools.jar"
TLA_SHA256 = "936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88"
MODEL = HERE / "refresh" / "RefreshOneShot.tla"
INVARIANTS = ("TypeOK", "AtMostOnce", "NoSuccessForSkippedRun", "NoFalseRefusal", "NoRefusalAfterSuccessfulRun")
FLAGS = ("FreshOnly", "NoUserAction", "AllowLongRun", "BrokenNoResume", "BrokenNoSkipCheck", "BrokenNoConsume",
         "BrokenNoBackgroundConsume", "BrokenNoPostRunCleanup", "BrokenSlotDueAtCreate", "BrokenVerifyAsRefused")

RUNS = {
    "baseline": ((), "pass", INVARIANTS),
    "a-no-resume": (("FreshOnly", "NoUserAction", "BrokenNoResume", "BrokenNoSkipCheck"), "NoSuccessForSkippedRun", INVARIANTS),
    "a-no-skip-check": (("BrokenNoSkipCheck",), "NoSuccessForSkippedRun", INVARIANTS),
    "b-no-consume": (("BrokenNoConsume",), "AtMostOnce", INVARIANTS),
    "c-background-not-consumed": (("BrokenNoBackgroundConsume",), "AtMostOnce", INVARIANTS),
    "c-db-error-no-cleanup": (("BrokenNoPostRunCleanup",), "AtMostOnce", INVARIANTS),
    # Due-at-resume scheduler execution followed by a manual skip/refusal. This does NOT model
    # the historical dispatch-limit-mid-run retirement.
    "d-slot-due-at-create": (("BrokenSlotDueAtCreate",), "NoFalseRefusal", ("TypeOK", "NoFalseRefusal")),
    # F1 was fixed (b57f3cc/f56321d); this control restores the old mapping of a refused verification list to
    # native_refused and must trip the property the baseline now holds.
    "f1-verify-refusal-reported-as-refused": (("BrokenVerifyAsRefused",), "NoRefusalAfterSuccessfulRun",
                                              ("TypeOK", "NoRefusalAfterSuccessfulRun")),
    # Known residual (docs/architecture/F3-MAINTENANCE-COORDINATION.md "Limits"): a run longer than the 7-day
    # slot can be claimed again.
    "residual-run-outlasts-slot": (("AllowLongRun",), "AtMostOnce", INVARIANTS),
}


TRACE_SIGNATURES = {
    "a-no-resume": {"created": "TRUE", "manualRan": "FALSE", "reply": '"skipped"', "userOp": '"none"'},
    "a-no-skip-check": {"manualRan": "FALSE", "reply": '"skipped"'},
    "b-no-consume": {"created": "TRUE", "execs": "2", "reply": '"inline_ok"', "result": '"ok"'},
    "c-background-not-consumed": {"created": "TRUE", "execs": "2", "reply": '"background"'},
    "c-db-error-no-cleanup": {"created": "TRUE", "execs": "2", "err": '"post_run"'},
    "d-slot-due-at-create": {"slotDue": "TRUE", "okExecs": "1", "result": '"err_refused"'},
    "f1-verify-refusal-reported-as-refused": {"okExecs": "1", "result": '"err_verify_refused"', "verifyFailed": "TRUE"},
    "residual-run-outlasts-slot": {"execs": "2", "pc": '"run_reply"', "reply": '"inline_ok"'},
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
    evidence = TOOLS / "model-evidence"
    scratch = TOOLS / "scratch"
    evidence.mkdir(parents=True, exist_ok=True)
    scratch.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="ls-tlc-", dir=scratch) as tmp:
        shutil.copy(MODEL, tmp)
        cfg = ["SPECIFICATION Spec", "CONSTANTS"]
        cfg += [f"    {flag} = {'TRUE' if flag in flags else 'FALSE'}" for flag in FLAGS]
        cfg += [f"INVARIANT {inv}" for inv in invariants]
        config = "\n".join(cfg) + "\n"
        Path(tmp, "RefreshOneShot.cfg").write_text(config)
        command = ["java", "-XX:+UseParallelGC", f"-Djava.io.tmpdir={tmp}", "-cp", str(jar()),
                   "tlc2.TLC", "-workers", "1", "-fp", "0",
                   "-coverage", "1",
                   "-cleanup", "-metadir", str(Path(tmp, "states")),
                   "-config", "RefreshOneShot.cfg", "RefreshOneShot.tla"]
        timed_out = False
        try:
            proc = subprocess.run(command, cwd=tmp, capture_output=True, text=True, timeout=600)
            stdout, stderr, code = proc.stdout, proc.stderr, proc.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = exc.stdout or b""
            stderr = exc.stderr or b""
            stdout = stdout.decode() if isinstance(stdout, bytes) else stdout
            stderr = stderr.decode() if isinstance(stderr, bytes) else stderr
            code = None
    out = stdout + stderr
    violated = re.search(r"Invariant (\w+) is violated", out)
    counts = re.findall(r"(?m)^([\d,]+) states generated, ([\d,]+) distinct states found,", out)
    generated, states = (int(n.replace(",", "")) for n in counts[-1]) if counts else (None, None)
    trace = re.split(r"(?m)^State \d+:", out)[1:]
    last = dict(re.findall(r"(?m)^/\\ (\w+) = (.*)$", trace[-1])) if trace else {}
    signature = TRACE_SIGNATURES.get(name, {})
    signature_ok = all(last.get(key) == value for key, value in signature.items())
    coverage = {action: [int(new), int(total)] for action, new, total in
                re.findall(r"(?m)^<(\w+) line[^\n]+>: (\d+):(\d+)$", out)}
    required_actions = ("UserStart", "UserList", "UserMutate", "UserVerify", "UserFinalList", "UserCommit",
                        "UserAbort", "RunReceipt", "RunFence", "RecheckList", "RecheckTxn", "RefusedFence",
                        "ConsumeFence", "CleanupTxn", "NativePause", "NativePauseVerify",
                        "NativeRemove", "NativeRemoveVerify", "CleanupLinked", "ClockReachesSlot",
                        "SchedulerClaim", "SchedulerExecute", "SchedulerRetire", "BackgroundRelease",
                        "ReturnOk") if name == "baseline" else ()
    coverage_ok = all(coverage.get(action, [0])[0] > 0 for action in required_actions)
    if not timed_out and code == 0 and "Model checking completed. No error has been found." in out:
        actual = "pass"
    elif not timed_out and code == 12 and violated:
        actual = violated.group(1)
    else:
        actual = "timeout" if timed_out else "error"
    result = {"name": name, "expected": expected, "actual": actual,
              "ok": actual == expected and signature_ok and coverage_ok and generated is not None and states is not None and generated >= states,
              "distinct_states": states, "generated_states": generated,
              "trace_signature": signature, "trace_signature_ok": signature_ok,
              "action_coverage": coverage, "required_actions_reached": coverage_ok,
              "exit_code": code, "seconds": round(time.monotonic() - started, 3),
              "command": command, "model_sha256": hashlib.sha256(MODEL.read_bytes()).hexdigest(),
              "output_path": str(evidence / f"{name}.out")}
    (evidence / f"{name}.cfg").write_text(config)
    (evidence / f"{name}.stdout").write_text(stdout)
    (evidence / f"{name}.stderr").write_text(stderr)
    (evidence / f"{name}.out").write_text(out)
    (evidence / f"{name}.json").write_text(json.dumps(result, indent=2) + "\n")
    return {**result, "output": out}
