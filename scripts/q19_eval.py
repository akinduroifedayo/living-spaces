#!/usr/bin/env python3
"""Offline Q19 evaluation harness: frozen plan, deterministic oracles, spend ledger and candidate gates.

This module never calls a model. Generation sessions are run by a separately approved executor that feeds
usage and observations back through Ledger.record() and grade(). Without an approved executor there is no
code path here that spends anything.
"""

import argparse
import csv
import json
import random
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "tests/integration/q19"
CONDITIONS = ("baseline", "candidate")
REPEATS = 3
DIMENSIONS = ("task_hierarchy", "readability", "identity", "state_completeness", "interaction_clarity")

# Frozen per-session limits (APPROVAL-PACKET section 4). Hitting one records a failed build; never retried.
BUDGETS = {
    "build": {"input_tokens": 3_000_000, "output_tokens": 80_000, "tool_calls": 60, "minutes": 20},
    "edit": {"input_tokens": 1_500_000, "output_tokens": 40_000, "tool_calls": 30, "minutes": 10},
    "review": {"input_tokens": 200_000, "output_tokens": 10_000},
}
# USD per million tokens, from ~/.hermes/hermes-agent/agent/usage_pricing.py snapshots. The worst case bills
# every input token uncached at the above-272K tier.
PRICING = {
    "gpt-6.1-sol": {"input": 2.0, "output": 10.0, "cache_read": 0.10, "long_input": 4.0, "long_output": 15.0},
    "claude-opus-5-5": {"input": 4.0, "output": 20.0, "cache_read": 0.20, "long_input": 4.0, "long_output": 20.0},
}
CAP_USD = 860.0
PAUSE_FRACTION = 0.8


def load_briefs():
    return json.loads((SUITE / "briefs.json").read_text())["briefs"]


def plan(seed):
    """Every build with its edit, in randomized condition order. Failures stay in this denominator."""
    rng = random.Random(seed)
    sessions = [{"brief": brief["id"], "condition": condition, "repeat": repeat}
                for brief in load_briefs() for condition in CONDITIONS for repeat in range(1, REPEATS + 1)]
    rng.shuffle(sessions)
    for index, session in enumerate(sessions):
        session["order"] = index
        session["blind_id"] = f"a{rng.getrandbits(32):08x}"
    return {"seed": seed, "budgets": BUDGETS, "cap_usd": CAP_USD, "builds": sessions}


def session_cost(model, usage, *, worst_case=False):
    price = PRICING[model]
    uncached = usage.get("input_tokens", 0) - usage.get("cached_tokens", 0)
    if worst_case:
        return (usage.get("input_tokens", 0) * price["long_input"] + usage.get("output_tokens", 0) * price["long_output"]) / 1e6
    return (uncached * price["input"] + usage.get("cached_tokens", 0) * price["cache_read"]
            + usage.get("output_tokens", 0) * price["output"]) / 1e6


def worst_case_total():
    builds = len(load_briefs()) * len(CONDITIONS) * REPEATS
    artifacts = 2 * builds   # each build and its edited successor is scored
    sol = lambda kind: session_cost("gpt-6.1-sol", BUDGETS[kind], worst_case=True)
    # Reviewer A (Opus) and reviewer B (fresh Sol) each judge every artifact.
    return round(builds * (sol("build") + sol("edit"))
                 + artifacts * session_cost("claude-opus-5-5", BUDGETS["review"], worst_case=True)
                 + artifacts * sol("review"), 2)


class StopRun(Exception):
    pass


class Ledger:
    """Running list-price-equivalent spend with the packet's stop conditions."""

    def __init__(self, cap=CAP_USD):
        self.cap, self.spent, self.harness_failures, self.entries, self.paused = cap, 0.0, 0, [], False

    def record(self, *, model, kind, usage, outcome):
        limits = BUDGETS[kind]
        over = [key for key in ("input_tokens", "output_tokens", "tool_calls") if usage.get(key, 0) > limits.get(key, float("inf"))]
        cost = session_cost(model, usage)
        self.spent += cost
        failed = outcome != "ok" or bool(over)
        self.entries.append({"model": model, "kind": kind, "usage": usage, "cost": round(cost, 4),
                             "outcome": "budget_exceeded" if over else outcome, "over": over})
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
        return not failed


# Deterministic oracles: expected values are derived from the public fixtures, then compared with what the
# generated app actually saved or displayed. Model prose is never an input.

def _fixture(name):
    return SUITE / "fixtures" / name


def oracle_trip():
    data = json.loads(_fixture("trip-tasks.json").read_text())
    tasks = {task["id"]: task for task in data["tasks"]}
    is_open = lambda task: task["status"] != "done"
    blocked = {tid: task["blocked_by"] for tid, task in tasks.items()
               if is_open(task) and task["blocked_by"] and is_open(tasks[task["blocked_by"]])}
    ready = sorted((task["due"], tid) for tid, task in tasks.items() if is_open(task) and tid not in blocked)
    return {"next": ready[0][1], "blocked": blocked}


def oracle_feed():
    ids = re.findall(r"<guid>([^<]+)</guid>", _fixture("feed.xml").read_text())
    return {"total": len(ids), "after_marking": ["item-2"], "unread": len(set(ids) - {"item-2"})}


def oracle_spending():
    totals = {}
    with _fixture("spending.csv").open() as handle:
        for row in csv.DictReader(handle):
            totals[row["category"]] = round(totals.get(row["category"], 0.0) + float(row["amount"]), 2)
    return totals


def oracle_memory():
    sequence = [18, 14, 14, 20]
    return {"rule": "fewest moves wins; ties keep the earlier record", "sequence": sequence, "best": min(sequence)}


def oracle_toc():
    counts, fenced = {"h2": 0, "h3": 0}, False
    for line in _fixture("long-document.md").read_text().splitlines():
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and line.startswith("### "):
            counts["h3"] += 1
        elif not fenced and line.startswith("## "):
            counts["h2"] += 1
    return counts


def oracle_weather(window=6, threshold=60):
    places = json.loads(_fixture("forecast.json").read_text())["places"]
    warn = sorted(name for name, data in places.items() if max(data["precip_probability"][:window]) > threshold)
    return {"warn": warn, "quiet": sorted(set(places) - set(warn))}


ORACLES = {"trip-tracker": oracle_trip, "rss-desk": oracle_feed, "csv-spending": oracle_spending,
           "memory-game": oracle_memory, "long-document": oracle_toc, "weather-board": oracle_weather}


def grade(brief_id, observed):
    """Compare an app's observed end state with the oracle. A missing observation is a failure, not a skip."""
    expected = ORACLES[brief_id]()
    if observed is None:
        return {"brief": brief_id, "pass": False, "reason": "no observation"}
    mismatched = sorted(key for key in expected if observed.get(key) != expected[key])
    return {"brief": brief_id, "pass": not mismatched, "mismatched": mismatched}


def visual_gate(scores):
    """scores: [{brief, condition, reviewer, critical, <dimension>: 1..5}]. Applies ACCEPTANCE 'Judge visuals'."""
    def median(rows, dimension):
        return statistics.median([row[dimension] for row in rows])

    by = lambda **match: [row for row in scores if all(row[k] == v for k, v in match.items())]
    declines = []
    for brief in sorted({row["brief"] for row in scores}):
        base, cand = by(brief=brief, condition="baseline"), by(brief=brief, condition="candidate")
        if not base or not cand:
            declines.append((brief, "missing condition"))
            continue
        declines += [(brief, d) for d in DIMENSIONS if median(cand, d) < median(base, d)]
    base, cand = by(condition="baseline"), by(condition="candidate")
    improved = [d for d in DIMENSIONS if base and cand and median(cand, d) > median(base, d)]
    critical = [row for row in scores if row.get("critical")]
    pairs = {}
    for row in scores:
        pairs.setdefault((row["brief"], row["condition"], row.get("artifact")), []).append(row)
    disagreement = sum(1 for rows in pairs.values() if len(rows) > 1 and any(
        max(r[d] for r in rows) - min(r[d] for r in rows) >= 2 for d in DIMENSIONS))
    return {"pass": not declines and len(improved) >= 2 and not critical,
            "brief_declines": declines, "improved_dimensions": improved,
            "critical": len(critical), "disagreements": disagreement, "judgments": len(scores)}


def time_gate(results):
    """results: [{condition, usable_seconds or None}]. Failed builds stay in the denominator as infinite time."""
    def times(condition):
        return sorted(r["usable_seconds"] if r["usable_seconds"] is not None else float("inf")
                      for r in results if r["condition"] == condition)
    base, cand = times("baseline"), times("candidate")
    quartile = lambda values: values[max(0, (3 * len(values) + 3) // 4 - 1)] if values else None
    base_median, cand_median = statistics.median(base), statistics.median(cand)
    return {"pass": cand_median <= 1.10 * base_median,
            "baseline_median": base_median, "candidate_median": cand_median,
            "baseline_slowest_quartile": quartile(base), "candidate_slowest_quartile": quartile(cand),
            "failures": {"baseline": base.count(float("inf")), "candidate": cand.count(float("inf"))}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("cost", help="print the worst-case list-price total for the frozen plan")
    p = sub.add_parser("plan", help="write the randomized frozen plan")
    p.add_argument("--seed", type=int, required=True)
    sub.add_parser("oracles", help="print every oracle's expected values")
    args = parser.parse_args()
    if args.command == "cost":
        print(json.dumps({"worst_case_usd": worst_case_total(), "cap_usd": CAP_USD}))
    elif args.command == "plan":
        print(json.dumps(plan(args.seed), indent=1))
    else:
        print(json.dumps({brief: fn() for brief, fn in ORACLES.items()}, indent=1))


if __name__ == "__main__":
    main()
