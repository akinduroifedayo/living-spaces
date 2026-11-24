"""Two Refresh now requests at once, through the real entry runs.start_refresh, against the fake public cron.

The contract says "One non-terminal run per Space is allowed: a second request returns the same run"
(docs/contracts/CONTRACTS.md:190), and R1-11 says "repeated refresh/retry does not multiply effects"
(docs/spec/SPEC.md:76). For agent upkeep runs.start_refresh calls upkeep.refresh_now, whose admission is
maintenance.acquire: one refresh_claims row per Space, inserted in one write transaction; a second request finds
the held claim and maintenance.join returns the saved native reply without another dispatch (b57f3cc, f56321d).

Each scenario makes two requests overlap: both are inside their native run at the same time (a barrier in the fake
cron's run), from the trigger pairs a person can produce: Desktop and chat, or two Desktop windows. The Desktop
view's own lock (src/desktop/ui/space.jsx:127) stops a second press only within one view, so it is not modeled.

  OneRunAtATime  overlapping requests for one Space start at most one native execution
(The feed side of the guard is already covered by tests/python/test_upkeep_runs.py:208 and needs the network.)

F3 (each overlapping request ran) was fixed by that admission; OneRunAtATime is now a hard property.
"""
from __future__ import annotations

import threading

from harness import Violation, main
from refresh_one_shot import FakeCron

AGENT = {"upkeep": {"handler": "agent", "prompt": "Update the list"}}
PAIRS = (("manual", "chat"), ("manual", "manual"), ("chat", "chat"))


def overlap(core, cron, sid, pair):
    from living_spaces_core import runs
    barrier = threading.Barrier(2)
    original = cron.dispatch_tool
    lock = threading.Lock()

    def dispatch(name, args):
        if args.get("action") == "run":
            try:
                barrier.wait(timeout=3)
            except threading.BrokenBarrierError:
                pass
        with lock:
            return original(name, args)

    cron.dispatch_tool = dispatch
    replies = []
    errors = []

    def press(trigger, who):
        try:
            replies.append(runs.start_refresh(sid, trigger=trigger, actor=who, wait=True))
        except core.SpacesError as exc:
            replies.append(exc.to_dict())
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=press, args=(t, f"{t}-{i}")) for i, t in enumerate(pair)]
    [t.start() for t in threads]
    [t.join(timeout=30) for t in threads]
    cron.dispatch_tool = original
    if any(t.is_alive() for t in threads) or len(replies) != 2 or errors:
        raise Violation(f"ProbeCompleted: concurrent probe did not finish both requests: replies={replies}, errors={errors}")
    return replies


def check(core, home):
    from living_spaces_core import upkeep
    for n, pair in enumerate(PAIRS):
        scenario = {"n": n, "faults": frozenset(), "outcome": "inline_ok", "during_run": None, "post_run_db": False}
        cron = FakeCron(scenario, core)
        upkeep.configure_context(cron)
        sid = core.create_space(f"Concurrent {n}", owner="Bjorn", files={"index.html": "<p>x</p>"},
                                manifest=AGENT, author="agent")["id"]
        scenario["sid"] = sid
        replies = overlap(core, cron, sid, pair)
        ran = [e for e in cron.executions if e[2]]
        if len(ran) != 1:
            raise Violation(f"OneRunAtATime: start_refresh({sid!r}, trigger={pair[0]!r}) and start_refresh({sid!r}, "
                            f"trigger={pair[1]!r}) at once started {len(ran)} native runs {ran}; replies {replies}")
    return {"pairs": [list(p) for p in PAIRS], "known_findings": {}}


if __name__ == "__main__":
    main(check)
