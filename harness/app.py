"""Isolated Hermes Desktop instance for Living Spaces acceptance runs.

  app.py prepare           # isolated home: config, plugin symlink (to the repo checkout), enable switches
  app.py start | stop | status
  app.py enable-desktop    # flips the Capabilities toggle (renderer localStorage decision) and reloads

Never touches ~/.hermes: refuses to run unless HERMES_HOME resolves outside it."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(os.environ.get("LS_RUN_ROOT", "/Volumes/Expansion/Development/Build/living-spaces-r1"))
HOME = ROOT / "home"
USERDATA = ROOT / "userdata"
LOGS = ROOT / "logs"
REPO = Path(__file__).resolve().parent.parent
PLUGIN_SRC = Path(os.environ.get("LS_PLUGIN_SRC", REPO / "src" / "living-spaces"))
APP = "/Applications/Hermes.app/Contents/MacOS/Hermes"
CDP_PORT = int(os.environ.get("LS_CDP_PORT", "9341"))
LIVE = Path.home() / ".hermes"

assert not str(HOME.resolve()).startswith(str(LIVE.resolve())), "isolated home must live outside ~/.hermes"


def env() -> dict:
    e = {k: v for k, v in os.environ.items() if not k.startswith("HERMES_")}
    e.update(HERMES_HOME=str(HOME), HERMES_DESKTOP_USER_DATA_DIR=str(USERDATA),
             HERMES_DESKTOP_ISOLATED_BACKEND="1", HERMES_DESKTOP_APP_NAME="Hermes Living Spaces R1")
    return e


def prepare() -> None:
    import yaml  # hermes venv has PyYAML

    HOME.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    cfg_path = HOME / "config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
    cfg = cfg or {}
    enabled = set((cfg.get("plugins") or {}).get("enabled") or [])
    enabled |= {"living-spaces", "claude-subscription-directsdk-experimental"}
    cfg.setdefault("plugins", {})["enabled"] = sorted(enabled)
    cfg.setdefault("model", {}).update(default="claude-sonnet-5-5", provider="claude-subscription-directsdk-experimental",
                                       base_url="process://claude-subscription-directsdk-experimental",
                                       api_mode="chat_completions")
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False))
    link = HOME / "plugins" / "living-spaces"
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink() or link.exists():
        if link.is_symlink() and Path(os.readlink(link)) == PLUGIN_SRC:
            pass
        else:
            if link.is_symlink():
                link.unlink()
            else:
                raise SystemExit(f"{link} exists and is not a symlink; remove it by hand")
            link.symlink_to(PLUGIN_SRC)
    else:
        link.symlink_to(PLUGIN_SRC)
    print(json.dumps({"home": str(HOME), "plugin": f"{link} -> {os.readlink(link)}", "enabled": sorted(enabled)}))


def pidfile() -> Path:
    return ROOT / "app.pid"


def running() -> int | None:
    try:
        pid = int(pidfile().read_text())
        os.kill(pid, 0)
        return pid
    except Exception:
        return None


def cdp_targets() -> list:
    return json.load(urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/list", timeout=2))


def start(wait: float = 90) -> None:
    if running():
        print(json.dumps({"already": running()}))
        return
    log = open(LOGS / f"app-{int(time.time())}.log", "wb")
    p = subprocess.Popen([APP, f"--remote-debugging-port={CDP_PORT}"], env=env(), stdout=log, stderr=log,
                         start_new_session=True, cwd=str(ROOT))
    pidfile().write_text(str(p.pid))
    deadline = time.time() + wait
    while time.time() < deadline:
        try:
            if any(t["type"] == "page" and "/dist/index.html" in t["url"] for t in cdp_targets()):
                break
        except Exception:
            pass
        time.sleep(1)
    print(json.dumps({"pid": p.pid, "cdp": CDP_PORT, "log": log.name, "ready": time.time() < deadline}))


def stop() -> None:
    pid = running()
    if pid:
        os.kill(pid, signal.SIGTERM)
        for _ in range(30):
            if not running():
                break
            time.sleep(1)
    gw = subprocess.run(["hermes", "gateway", "stop"], env=env(), capture_output=True, text=True, timeout=60)
    print(json.dumps({"stopped_app": pid, "gateway_stop_rc": gw.returncode, "gateway_out": gw.stdout[-300:]}))


def status() -> None:
    gw = subprocess.run(["hermes", "gateway", "status"], env=env(), capture_output=True, text=True, timeout=60)
    print(json.dumps({"app_pid": running(), "gateway": gw.stdout[-600:]}))


def enable_desktop() -> None:
    sys.path.insert(0, str(Path(__file__).parent))
    from cdp import evaluate
    print(evaluate(
        "(() => { const k='hermes.desktop.pluginDecisions.v2'; const d=JSON.parse(localStorage.getItem(k)||'{}');"
        " d['living-spaces']=true; localStorage.setItem(k, JSON.stringify(d)); location.reload(); return d })()"))


if __name__ == "__main__":
    {"prepare": prepare, "start": start, "stop": stop, "status": status, "enable-desktop": enable_desktop}[sys.argv[1]]()
