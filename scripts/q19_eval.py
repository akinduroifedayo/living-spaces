#!/usr/bin/env python3
"""Offline Q19 evaluation harness: frozen plan, deterministic oracles, spend ledger and candidate gates.

This module never calls a model. Generation sessions are run by a separately approved executor that feeds
usage and observations back through Ledger.record() and grade(). Without an approved executor there is no
code path here that spends anything.
"""

import argparse
import csv
import json
import math
import random
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "tests/integration/q19"
CONDITIONS = ("baseline", "candidate")
REPEATS = 3
DIMENSIONS = ("task_hierarchy", "readability", "identity", "state_completeness", "interaction_clarity")

# Frozen per-session limits (APPROVAL-PACKET section 4). Reaching a limit fails the session; it is never retried.
BUDGETS = {
    "build": {"input_tokens": 3_000_000, "output_tokens": 80_000, "tool_calls": 60, "minutes": 20},
    "edit": {"input_tokens": 1_500_000, "output_tokens": 40_000, "tool_calls": 30, "minutes": 10},
    "review": {"input_tokens": 200_000, "output_tokens": 10_000},
}
# USD per million tokens, from ~/.hermes/hermes-agent/agent/usage_pricing.py snapshots.
PRICING = {
    "gpt-6.1-sol": {"input": 2.0, "output": 10.0, "cache_read": 0.10, "long_input": 4.0, "long_output": 15.0},
    "claude-opus-5-5": {"input": 4.0, "output": 20.0, "cache_read": 0.20, "long_input": 4.0, "long_output": 20.0},
}
LONG_REQUEST_TOKENS = 272_000
CAP_USD = 860.0
PAUSE_FRACTION = 0.8
# A comparison is only meaningful when these are pinned before the first session (ACCEPTANCE "Generation profile").
REQUIRED_CONTROLS = ("baseline_sha", "candidate_sha", "builder_route", "builder_effort", "reviewer_a_route",
                     "reviewer_b", "skills_sha256", "environment")


def load_briefs():
    return json.loads((SUITE / "briefs.json").read_text())["briefs"]


def plan(seed, controls):
    """Every build with its edit, in randomized condition order. Failures stay in this denominator."""
    missing = [key for key in REQUIRED_CONTROLS if not controls.get(key)]
    if missing:
        raise ValueError(f"plan cannot be frozen without controls: {', '.join(missing)}")
    if controls["baseline_sha"] == controls["candidate_sha"]:
        raise ValueError("baseline and candidate must be different commits")
    rng = random.Random(seed)
    sessions = [{"brief": brief["id"], "condition": condition, "repeat": repeat}
                for brief in load_briefs() for condition in CONDITIONS for repeat in range(1, REPEATS + 1)]
    rng.shuffle(sessions)
    for index, session in enumerate(sessions):
        session["order"] = index
        session["blind_id"] = f"a{rng.getrandbits(32):08x}"
    return {"seed": seed, "controls": dict(controls), "budgets": BUDGETS, "cap_usd": CAP_USD, "builds": sessions}


def artifacts(frozen):
    """Every scored artifact: each build and its edited successor."""
    return {f"{b['blind_id']}:{phase}": (b["brief"], b["condition"]) for b in frozen["builds"] for phase in PHASES}


PHASES = ("build", "edit")


def session_cost(model, usage, *, worst_case=False):
    """List-price equivalent. Unless every request is known to be under the long-context threshold, bill all
    input at the long-context rate with no cache discount; the ledger must never under-count toward the cap."""
    price = PRICING[model]
    largest = usage.get("max_request_input_tokens")
    if worst_case or largest is None or largest > LONG_REQUEST_TOKENS:
        return (usage.get("input_tokens", 0) * price["long_input"] + usage.get("output_tokens", 0) * price["long_output"]) / 1e6
    uncached = usage.get("input_tokens", 0) - usage.get("cached_tokens", 0)
    return (uncached * price["input"] + usage.get("cached_tokens", 0) * price["cache_read"]
            + usage.get("output_tokens", 0) * price["output"]) / 1e6


def worst_case_total():
    builds = len(load_briefs()) * len(CONDITIONS) * REPEATS
    scored = len(PHASES) * builds
    sol = lambda kind: session_cost("gpt-6.1-sol", BUDGETS[kind], worst_case=True)
    # Reviewer A (Opus) and reviewer B (fresh Sol) each judge every artifact.
    return round(builds * (sol("build") + sol("edit"))
                 + scored * session_cost("claude-opus-5-5", BUDGETS["review"], worst_case=True)
                 + scored * sol("review"), 2)


class StopRun(Exception):
    pass


class Ledger:
    """Running list-price-equivalent spend with the packet's stop conditions."""

    def __init__(self, cap=CAP_USD):
        self.cap, self.spent, self.harness_failures, self.entries, self.paused = cap, 0.0, 0, [], False

    def record(self, *, model, kind, usage, outcome):
        limits = BUDGETS[kind]
        reached = [key for key, limit in limits.items() if usage.get(key, 0) >= limit]
        cost = session_cost(model, usage)
        self.spent += cost
        self.entries.append({"model": model, "kind": kind, "usage": usage, "cost": round(cost, 4),
                             "outcome": "budget_reached" if reached else outcome, "reached": reached})
        if outcome in ("quota_refused", "entitlement_refused"):
            raise StopRun(f"{outcome}: stop and record; no route switch")
        if outcome == "escaped_profile":
            raise StopRun("a build touched state outside the disposable profile")
        self.harness_failures = self.harness_failures + 1 if outcome == "harness_error" else 0
        if self.harness_failures >= 2:
            raise StopRun("two consecutive harness failures; fix the harness before continuing")
        if self.spent >= self.cap:
            raise StopRun(f"cap reached at ${self.spent:.2f}")
        if self.spent >= PAUSE_FRACTION * self.cap and not self.paused:
            self.paused = True
            raise StopRun(f"paused at ${self.spent:.2f}, 80% of the ${self.cap:.0f} cap; report before continuing")
        return outcome == "ok" and not reached


# Deterministic oracles. Expected values are computed from the public fixtures and the brief's scripted scenario,
# then compared with what the generated app saved or displayed. Model prose is never an input.

def _fixture(name):
    return SUITE / "fixtures" / name


def _json(name):
    return json.loads(_fixture(name).read_text())


def _brief(brief_id):
    return next(brief for brief in load_briefs() if brief["id"] == brief_id)


def oracle_trip(phase):
    tasks = {task["id"]: task for task in _json("trip-tasks.json")["tasks"]}
    is_open = lambda task: task["status"] != "done"
    blocked = {tid: task["blocked_by"] for tid, task in tasks.items()
               if is_open(task) and task["blocked_by"] and is_open(tasks[task["blocked_by"]])}
    ready = sorted((task["due"], tid) for tid, task in tasks.items() if is_open(task) and tid not in blocked)
    if phase == "build":
        return {"next": ready[0][1], "blocked": blocked}
    bags = {}
    for item in _json("packing.json")["items"]:
        bags[item["bag"]] = bags.get(item["bag"], 0) + 1
    return {"bags": bags}


def oracle_feed(phase):
    text = _fixture("feed.xml").read_text()
    ids = re.findall(r"<guid>([^<]+)</guid>", text)
    source = re.search(r"<channel><title>([^<]+)</title>", text).group(1)
    scenario = _brief("rss-desk")["scenario"]
    unread = len(set(ids) - set(scenario["mark_read"]))
    if phase == "build":
        return {"total": len(ids), "unread": unread}
    return {"unread_by_source": {source: unread}, "saved_filter": [i for i in ids if i in scenario["save"]]}


def oracle_spending(phase):
    with _fixture("spending.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    if phase == "build":
        totals = {}
        for row in rows:
            totals[row["category"]] = round(totals.get(row["category"], 0.0) + float(row["amount"]), 2)
        return totals
    budgets, monthly = _json("budgets.json")["budgets"], {}
    for row in rows:
        key = (row["date"][:7], row["category"])
        monthly[key] = monthly.get(key, 0.0) + float(row["amount"])
    overspent = {}
    for (month, category), total in sorted(monthly.items()):
        if category in budgets and round(total, 2) > budgets[category]:
            overspent.setdefault(month, []).append(category)
    return {"overspent": overspent}


def oracle_memory(phase):
    games = _json("memory-games.json")["games"]

    def best(mode, score):
        winners = {}
        for game in games:   # fixture order is play order; a tie keeps the earlier record
            if game["mode"] == mode and (game["size"] not in winners or game[score] < winners[game["size"]][score]):
                winners[game["size"]] = game
        return {size: game["id"] for size, game in winners.items()}

    result = {"best": best("classic", "moves")}
    if phase == "edit":
        result["timed_best"] = best("timed", "seconds")
    return result


def oracle_document(phase):
    lines, fenced, counts, positions = _fixture("long-document.md").read_text().splitlines(), False, {"h2": 0, "h3": 0}, {}
    for number, line in enumerate(lines):
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and line.startswith(("## ", "### ")):
            counts["h3" if line.startswith("### ") else "h2"] += 1
            positions[line.split(" ", 1)[1]] = number
    if phase == "build":
        return counts
    highlights = sorted(_json("highlights.json")["highlights"], key=lambda h: positions[h["heading"]])
    return {"export": [[h["id"], h["note"]] for h in highlights]}


def oracle_weather(phase, window=6, threshold=60):
    places = _json("forecast.json")["places"]
    if phase == "build":
        return {"hours": {name: len(data["precip_probability"]) for name, data in places.items()},
                "peak": {name: max(data["precip_probability"]) for name, data in places.items()}}
    warn = sorted(name for name, data in places.items() if max(data["precip_probability"][:window]) > threshold)
    return {"warn": warn, "quiet": sorted(set(places) - set(warn))}


ORACLES = {"trip-tracker": oracle_trip, "rss-desk": oracle_feed, "csv-spending": oracle_spending,
           "memory-game": oracle_memory, "long-document": oracle_document, "weather-board": oracle_weather}


def grade(brief_id, phase, observed):
    """Compare an app's observed end state with the oracle. A missing observation is a failure, not a skip."""
    expected = ORACLES[brief_id](phase)
    if observed is None:
        return {"brief": brief_id, "phase": phase, "pass": False, "reason": "no observation"}
    mismatched = sorted(key for key in expected if observed.get(key) != expected[key])
    return {"brief": brief_id, "phase": phase, "pass": not mismatched, "mismatched": mismatched}


def visual_gate(scores, frozen, min_reviewers=2):
    """ACCEPTANCE 'Judge visuals'. scores: [{artifact, reviewer, critical, <dimension>: 1..5}] keyed by the
    plan's blind artifact ids. Any planned artifact without enough reviewers makes the gate incomplete."""
    expected = artifacts(frozen)
    reviewers = {}
    for row in scores:
        if row["artifact"] not in expected:
            raise ValueError(f"unplanned artifact {row['artifact']}")
        reviewers.setdefault(row["artifact"], set()).add(row["reviewer"])
    incomplete = sorted(a for a in expected if len(reviewers.get(a, ())) < min_reviewers)
    rows = [{**row, "brief": expected[row["artifact"]][0], "condition": expected[row["artifact"]][1]} for row in scores]
    median = lambda subset, d: statistics.median([row[d] for row in subset])
    by = lambda **match: [row for row in rows if all(row[k] == v for k, v in match.items())]
    declines = []
    for brief in sorted({brief for brief, _ in expected.values()}):
        base, cand = by(brief=brief, condition="baseline"), by(brief=brief, condition="candidate")
        if base and cand:
            declines += [(brief, d) for d in DIMENSIONS if median(cand, d) < median(base, d)]
    base, cand = by(condition="baseline"), by(condition="candidate")
    improved = [d for d in DIMENSIONS if base and cand and median(cand, d) > median(base, d)]
    critical = sum(1 for row in rows if row.get("critical"))
    groups = {}
    for row in rows:
        groups.setdefault(row["artifact"], []).append(row)
    disagreement = sum(1 for group in groups.values() if len(group) > 1 and any(
        max(r[d] for r in group) - min(r[d] for r in group) >= 2 for d in DIMENSIONS))
    return {"pass": not incomplete and not declines and len(improved) >= 2 and not critical,
            "incomplete": incomplete, "brief_declines": declines, "improved_dimensions": improved,
            "critical": critical, "disagreements": disagreement, "judgments": len(rows)}


def time_gate(results, frozen):
    """results: {blind_id: usable_seconds or None}. A planned build with no result is a failure."""
    def times(condition):
        return sorted(results.get(b["blind_id"]) if results.get(b["blind_id"]) is not None else float("inf")
                      for b in frozen["builds"] if b["condition"] == condition)
    base, cand = times("baseline"), times("candidate")
    base_median, cand_median = statistics.median(base), statistics.median(cand)
    tail = lambda values: values[len(values) - max(1, len(values) // 4):]
    return {"pass": math.isfinite(base_median) and math.isfinite(cand_median) and cand_median <= 1.10 * base_median,
            "baseline_median": base_median, "candidate_median": cand_median,
            "baseline_slowest_quartile": tail(base), "candidate_slowest_quartile": tail(cand),
            "failures": {"baseline": base.count(float("inf")), "candidate": cand.count(float("inf"))}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("cost", help="print the worst-case list-price total for the frozen plan")
    p = sub.add_parser("plan", help="write the randomized frozen plan")
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--controls", type=Path, required=True, help="JSON file with every REQUIRED_CONTROLS key")
    sub.add_parser("oracles", help="print every oracle's expected values")
    args = parser.parse_args()
    if args.command == "cost":
        print(json.dumps({"worst_case_usd": worst_case_total(), "cap_usd": CAP_USD}))
    elif args.command == "plan":
        print(json.dumps(plan(args.seed, json.loads(args.controls.read_text())), indent=1))
    else:
        print(json.dumps({brief: {phase: fn(phase) for phase in PHASES} for brief, fn in ORACLES.items()}, indent=1))


if __name__ == "__main__":
    main()
