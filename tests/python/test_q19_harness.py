"""Q19 offline harness: frozen plan, deterministic oracles, spend ledger and gates. No model is called."""
import importlib.util
import math
import unittest

from tests.python.test_core_store import ROOT

spec = importlib.util.spec_from_file_location("q19_eval", ROOT / "scripts/q19_eval.py")
assert spec is not None and spec.loader is not None
q19 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q19)

CONTROLS = {"baseline_sha": "48c8709", "candidate_sha": "398a1ce", "builder_route": "sol-high",
            "builder_effort": "high", "reviewer_a_route": "opus-high", "reviewer_b": "sol-high fresh context",
            "skills_sha256": "0" * 64, "environment": "disposable profile"}


def frozen(seed=7):
    return q19.plan(seed, CONTROLS)


class Q19PlanTests(unittest.TestCase):
    def test_six_briefs_three_repeats_two_conditions_with_edits(self):
        briefs = q19.load_briefs()
        self.assertEqual([b["id"] for b in briefs],
                         ["trip-tracker", "rss-desk", "csv-spending", "memory-game", "long-document", "weather-board"])
        self.assertTrue(all(b["edit"] for b in briefs))
        builds = frozen()["builds"]
        self.assertEqual(len(builds), 36)
        self.assertEqual(len(q19.artifacts(frozen())), 72)
        self.assertEqual({(b["brief"], b["condition"], b["repeat"]) for b in builds},
                         {(b["id"], c, r) for b in briefs for c in q19.CONDITIONS for r in (1, 2, 3)})

    def test_plan_is_reproducible_randomized_and_blind(self):
        self.assertEqual(frozen(7), frozen(7))
        self.assertNotEqual([b["condition"] for b in frozen(7)["builds"]], [b["condition"] for b in frozen(8)["builds"]])
        builds = frozen()["builds"]
        self.assertEqual(len({b["blind_id"] for b in builds}), 36)
        self.assertTrue(all(b["condition"] not in b["blind_id"] for b in builds))

    def test_plan_refuses_to_freeze_without_every_control(self):
        # int-review-06: SHAs, routes, effort, skills and environment must be pinned before any session.
        for key in q19.REQUIRED_CONTROLS:
            with self.subTest(missing=key), self.assertRaises(ValueError):
                q19.plan(7, {k: v for k, v in CONTROLS.items() if k != key})
        with self.assertRaises(ValueError):
            q19.plan(7, {**CONTROLS, "candidate_sha": CONTROLS["baseline_sha"]})
        self.assertEqual(frozen()["controls"], CONTROLS)

    def test_worst_case_matches_the_quoted_cap(self):
        # 853.20 for builds, edits and per-artifact reviews, plus 12 variety groups x 2 reviewers (CREATIVE.md).
        self.assertEqual(q19.worst_case_total(), 859.26)
        self.assertLessEqual(q19.worst_case_total(), q19.CAP_USD)


class Q19OracleTests(unittest.TestCase):
    def test_brief_expectations_are_derived_from_the_fixtures(self):
        for brief in q19.load_briefs():
            for phase in q19.PHASES:
                with self.subTest(brief=brief["id"], phase=phase):
                    self.assertEqual(q19.ORACLES[brief["id"]](phase), brief["oracle"][phase]["expected"])

    def test_every_edit_request_has_its_own_predicate(self):
        # int-review-06: an app that skipped the edit must fail its edit grade.
        for brief in q19.load_briefs():
            with self.subTest(brief=brief["id"]):
                build, edit = q19.ORACLES[brief["id"]]("build"), q19.ORACLES[brief["id"]]("edit")
                self.assertFalse(q19.grade(brief["id"], "edit", build)["pass"])
                self.assertTrue(q19.grade(brief["id"], "edit", edit)["pass"])

    def test_memory_oracle_reads_fixture_ties_sizes_and_modes(self):
        result = q19.oracle_memory("edit")
        self.assertEqual(result["best"]["4x4"], "g2")        # g3 ties g2 at 14 moves; the earlier record stays
        self.assertEqual(result["best"]["6x6"], "g4")        # board sizes are separate records
        self.assertEqual(result["timed_best"], {"4x4": "g6"})  # timed mode ranks by seconds; g7 ties later

    def test_fixtures_are_labelled_public_synthetic(self):
        for path in (q19.SUITE / "fixtures").iterdir():
            if path.suffix != ".csv":
                self.assertIn("PUBLIC SYNTHETIC FIXTURE", path.read_text(), path.name)

    def test_fixtures_have_no_trailing_whitespace(self):
        for path in (q19.SUITE / "fixtures").iterdir():
            self.assertFalse([n for n, line in enumerate(path.read_text().splitlines(), 1) if line != line.rstrip()],
                             path.name)

    def test_grade_fails_on_mismatch_and_missing_observation(self):
        good = q19.ORACLES["csv-spending"]("build")
        self.assertTrue(q19.grade("csv-spending", "build", good)["pass"])
        self.assertEqual(q19.grade("csv-spending", "build", {**good, "refunds": 20.0})["mismatched"], ["refunds"])
        self.assertFalse(q19.grade("csv-spending", "build", None)["pass"])

    def test_toc_ignores_headings_inside_code_fences(self):
        self.assertEqual(q19.oracle_document("build"), {"h2": 12, "h3": 30})


class Q19LedgerTests(unittest.TestCase):
    usage = {"input_tokens": 1000, "output_tokens": 100, "tool_calls": 3, "minutes": 1, "max_request_input_tokens": 1000}

    def test_reaching_any_limit_including_time_fails_without_retry(self):
        # int-review-06: limits are inclusive and elapsed minutes count.
        for key, value in (("tool_calls", 60), ("input_tokens", 3_000_000), ("minutes", 20), ("minutes", 21)):
            with self.subTest(key=key, value=value):
                ledger = q19.Ledger()
                self.assertFalse(ledger.record(model="gpt-6.1-sol", kind="build", usage={**self.usage, key: value}, outcome="ok"))
                self.assertEqual(ledger.entries[0]["outcome"], "budget_reached")
                self.assertEqual(len(ledger.entries), 1)
        self.assertTrue(q19.Ledger().record(model="gpt-6.1-sol", kind="build", usage=self.usage, outcome="ok"))

    def test_long_or_unknown_request_size_is_billed_at_the_long_tier(self):
        # int-review-06: an uncached long-context build must not be recorded at standard rates.
        long = {"input_tokens": 3_000_000, "output_tokens": 80_000, "max_request_input_tokens": 300_000}
        self.assertAlmostEqual(q19.session_cost("gpt-6.1-sol", long), 13.2)
        unknown = {"input_tokens": 3_000_000, "output_tokens": 80_000}
        self.assertAlmostEqual(q19.session_cost("gpt-6.1-sol", unknown), 13.2)
        short = {"input_tokens": 1_000_000, "cached_tokens": 900_000, "output_tokens": 0, "max_request_input_tokens": 100_000}
        self.assertAlmostEqual(q19.session_cost("gpt-6.1-sol", short), 0.29)

    def test_quota_refusal_and_profile_escape_stop_the_run(self):
        for outcome in ("quota_refused", "entitlement_refused", "escaped_profile"):
            with self.subTest(outcome=outcome), self.assertRaises(q19.StopRun):
                q19.Ledger().record(model="gpt-6.1-sol", kind="build", usage=self.usage, outcome=outcome)

    def test_two_consecutive_harness_failures_stop(self):
        ledger = q19.Ledger()
        ledger.record(model="gpt-6.1-sol", kind="build", usage=self.usage, outcome="harness_error")
        ledger.record(model="gpt-6.1-sol", kind="build", usage=self.usage, outcome="ok")
        ledger.record(model="gpt-6.1-sol", kind="build", usage=self.usage, outcome="harness_error")
        with self.assertRaises(q19.StopRun):
            ledger.record(model="gpt-6.1-sol", kind="build", usage=self.usage, outcome="harness_error")

    def test_pause_at_eighty_percent_then_stop_at_cap(self):
        ledger = q19.Ledger(cap=10.0)
        heavy = {"input_tokens": 1_000_000, "output_tokens": 0, "tool_calls": 1, "max_request_input_tokens": 1000}  # $2.00
        for _ in range(3):
            ledger.record(model="gpt-6.1-sol", kind="build", usage=heavy, outcome="ok")
        with self.assertRaisesRegex(q19.StopRun, "80%"):
            ledger.record(model="gpt-6.1-sol", kind="build", usage=heavy, outcome="ok")
        with self.assertRaisesRegex(q19.StopRun, "cap reached"):
            ledger.record(model="gpt-6.1-sol", kind="build", usage=heavy, outcome="ok")


class Q19GateTests(unittest.TestCase):
    def scores(self, plan, baseline, candidate, reviewers=("A", "B"), critical=False, only=None):
        rows = []
        for artifact, (brief, condition) in q19.artifacts(plan).items():
            if only and brief not in only:
                continue
            for reviewer in reviewers:
                value = baseline if condition == "baseline" else candidate
                rows.append({"artifact": artifact, "reviewer": reviewer,
                             "critical": critical and condition == "candidate", **value})
        return rows

    def test_visual_gate_requires_two_improvements_no_decline_no_critical(self):
        plan = frozen()
        base = dict.fromkeys(q19.DIMENSIONS, 3)
        better = {**base, "readability": 4, "identity": 4}
        self.assertTrue(q19.visual_gate(self.scores(plan, base, better), plan)["pass"])
        self.assertFalse(q19.visual_gate(self.scores(plan, base, {**base, "readability": 4}), plan)["pass"])
        self.assertFalse(q19.visual_gate(self.scores(plan, base, {**better, "task_hierarchy": 2}), plan)["pass"])
        self.assertFalse(q19.visual_gate(self.scores(plan, base, better, critical=True), plan)["pass"])

    def test_visual_gate_is_incomplete_without_every_brief_and_two_reviewers(self):
        # int-review-06: one brief, or one reviewer, must never yield PASS.
        plan = frozen()
        base = dict.fromkeys(q19.DIMENSIONS, 3)
        better = {**base, "readability": 4, "identity": 4}
        one_brief = q19.visual_gate(self.scores(plan, base, better, only={"rss-desk"}), plan)
        self.assertFalse(one_brief["pass"])
        self.assertEqual(len(one_brief["incomplete"]), 72 - 12)
        one_reviewer = q19.visual_gate(self.scores(plan, base, better, reviewers=("A",)), plan)
        self.assertFalse(one_reviewer["pass"])
        self.assertEqual(len(one_reviewer["incomplete"]), 72)
        # int-review-07: the two-reviewer minimum cannot be lowered by a caller.
        for weak in (1, 0, float("nan"), 1.5, True, "2"):
            with self.subTest(min_reviewers=weak), self.assertRaises(ValueError):
                q19.visual_gate(self.scores(plan, base, better, reviewers=("A",)), plan, min_reviewers=weak)

    def test_time_gate_counts_omitted_and_failed_builds_and_never_passes_all_failures(self):
        plan = frozen()
        ids = {c: [b["blind_id"] for b in plan["builds"] if b["condition"] == c] for c in q19.CONDITIONS}
        ok = {**{i: 100 for i in ids["baseline"]}, **{i: 105 for i in ids["candidate"]}}
        self.assertTrue(q19.time_gate(ok, plan)["pass"])
        # int-review-06: wholly failed runs must not pass because inf <= inf.
        self.assertFalse(q19.time_gate({}, plan)["pass"])
        omitted = q19.time_gate({i: 100 for i in ids["baseline"]} | {ids["candidate"][0]: 90}, plan)
        self.assertFalse(omitted["pass"])
        self.assertEqual(omitted["failures"]["candidate"], 17)
        slow = q19.time_gate({**ok, ids["candidate"][0]: 900}, plan)
        self.assertIn(900, slow["candidate_slowest_quartile"])
        self.assertTrue(all(math.isfinite(v) for v in slow["candidate_slowest_quartile"]))


if __name__ == "__main__":
    unittest.main()


class Q19CreativeTests(unittest.TestCase):
    """tests/integration/q19/CREATIVE.md gate."""

    def setUp(self):
        self.plan = frozen()
        self.expected = q19.artifacts(self.plan)

    def scores(self, base, cand, *, generic=(False, False), reviewers=("A", "B")):
        return [{"artifact": a, "reviewer": r, "generic": generic[c == "candidate"], **(base if c == "baseline" else cand)}
                for a, (_, c) in self.expected.items() for r in reviewers]

    def variety(self, base, cand, reviewers=("A", "B"), skip_brief=None):
        groups = sorted({(b, c) for b, c in self.expected.values()})
        return [{"brief": b, "condition": c, "reviewer": r, "variety": base if c == "baseline" else cand}
                for b, c in groups if b != skip_brief for r in reviewers]

    def sessions(self, rate_base=1.0, rate_cand=1.0):
        out = {}
        for condition, rate in (("baseline", rate_base), ("candidate", rate_cand)):
            ids = [b["blind_id"] for b in self.plan["builds"] if b["condition"] == condition]
            for i, bid in enumerate(ids):
                out[bid] = {"inspected": i < round(rate * len(ids))}
        return out

    def gate(self, base, cand, **kw):
        return q19.creative_gate(kw.pop("scores", None) or self.scores(base, cand, generic=kw.pop("generic", (True, False))),
                                 kw.pop("variety", None) or self.variety(2, 3), kw.pop("sessions", None) or self.sessions(),
                                 self.plan, **kw)

    def test_passes_only_with_two_creative_improvements(self):
        base = dict.fromkeys(q19.CREATIVE_DIMENSIONS, 3)
        self.assertTrue(self.gate(base, {**base, "distinctiveness": 4, "craft": 4})["pass"])
        self.assertFalse(self.gate(base, {**base, "distinctiveness": 4})["pass"])
        self.assertFalse(self.gate(base, {**base, "distinctiveness": 4, "craft": 4, "coherence": 2})["pass"])

    def test_original_rubric_gain_does_not_satisfy_creative_gate(self):
        # A generic-but-tidy candidate (equal creative scores) fails even if the ACCEPTANCE rubric would pass.
        base = dict.fromkeys(q19.CREATIVE_DIMENSIONS, 3)
        self.assertFalse(self.gate(base, base)["pass"])

    def test_variety_and_generic_rate_and_inspection_are_gated(self):
        base = dict.fromkeys(q19.CREATIVE_DIMENSIONS, 3)
        cand = {**base, "distinctiveness": 4, "craft": 4}
        self.assertFalse(self.gate(base, cand, variety=self.variety(3, 2))["pass"])
        self.assertFalse(self.gate(base, cand, generic=(True, True))["pass"])
        self.assertFalse(self.gate(base, cand, sessions=self.sessions(1.0, 0.5))["pass"])

    def test_incomplete_reviewers_or_variety_never_pass(self):
        base = dict.fromkeys(q19.CREATIVE_DIMENSIONS, 3)
        cand = {**base, "distinctiveness": 4, "craft": 4}
        one = self.gate(base, cand, scores=self.scores(base, cand, generic=(True, False), reviewers=("A",)))
        self.assertFalse(one["pass"])
        self.assertEqual(len(one["incomplete"]), 72)
        gap = self.gate(base, cand, variety=self.variety(2, 3, skip_brief="rss-desk"))
        self.assertFalse(gap["pass"])
        self.assertEqual(len(gap["incomplete_variety"]), 2)
        for weak in (1, 1.5, True):
            with self.subTest(weak=weak), self.assertRaises(ValueError):
                self.gate(base, cand, min_reviewers=weak)

    def test_failed_builds_stay_in_denominator_as_generic_ones(self):
        base = dict.fromkeys(q19.CREATIVE_DIMENSIONS, 3)
        cand = {**base, "distinctiveness": 4, "craft": 4}
        cand_ids = [b["blind_id"] for b in self.plan["builds"] if b["condition"] == "candidate"]
        # Failing every candidate build of every brief must fail the gate even though the surviving scores look good.
        result = self.gate(base, cand, failed=cand_ids)
        self.assertFalse(result["pass"])
        self.assertEqual(result["generic_rate"]["candidate"], 1.0)
        self.assertEqual(result["inspected_rate"]["candidate"], 0.0)

    def test_failed_builds_contribute_variety_one(self):
        # CREATIVE.md: failed builds score 1 on variety too. Two of three candidate builds failing in one brief must
        # drag that brief's candidate variety below baseline even when surviving judges rate the group highly.
        base = dict.fromkeys(q19.CREATIVE_DIMENSIONS, 3)
        cand = {**base, "distinctiveness": 4, "craft": 4}
        self.assertTrue(self.gate(base, cand)["pass"])
        ids = [b["blind_id"] for b in self.plan["builds"] if b["condition"] == "candidate" and b["brief"] == "rss-desk"]
        result = self.gate(base, cand, failed=ids[:2])
        self.assertFalse(result["pass"])
        self.assertIn("rss-desk", result["variety_declines"])

    def test_duplicate_reviewer_rows_are_refused(self):
        base = dict.fromkeys(q19.CREATIVE_DIMENSIONS, 3)
        cand = {**base, "distinctiveness": 4, "craft": 4}
        rows = self.scores(base, cand, generic=(True, False))
        artifact = next(a for a, (_, c) in self.expected.items() if c == "candidate")
        rows.append(next(r for r in rows if r["artifact"] == artifact and r["reviewer"] == "B"))
        with self.assertRaises(ValueError):
            self.gate(base, cand, scores=rows)
        variety = self.variety(2, 3)
        variety.append(dict(variety[0]))
        with self.assertRaises(ValueError):
            self.gate(base, cand, variety=variety)

    def test_absolute_floor_on_coherence_and_craft(self):
        base = dict.fromkeys(q19.CREATIVE_DIMENSIONS, 2)
        weak = {**base, "distinctiveness": 4, "subject_insight": 4}       # beats baseline, still mediocre
        result = self.gate(base, weak)
        self.assertFalse(result["pass"])
        self.assertIn(("overall", "coherence"), result["floor_misses"])
        self.assertTrue(self.gate(base, {**weak, "coherence": 3, "craft": 3})["pass"])

    def test_generic_is_majority_per_artifact_ties_generic(self):
        base = dict.fromkeys(q19.CREATIVE_DIMENSIONS, 3)
        cand = {**base, "distinctiveness": 4, "craft": 4}
        rows = self.scores(base, cand, generic=(True, False))
        for r in rows:                      # split every candidate artifact 1-1: ties count as generic
            if self.expected[r["artifact"]][1] == "candidate" and r["reviewer"] == "A":
                r["generic"] = True
        result = self.gate(base, cand, scores=rows)
        self.assertEqual(result["generic_rate"]["candidate"], 1.0)
        self.assertFalse(result["pass"])

    def test_exploration_is_derived_from_tool_calls(self):
        calls = [{"name": "read_file", "args": {"path": "skills/build-space/SKILL.md"}},
                 {"name": "spaces_create", "args": {"files": {"index.html": "a"}}},
                 {"name": "spaces_write_files", "args": {"files": [{"path": "index.html"}]}},
                 {"name": "spaces_inspect", "args": {}},
                 {"name": "spaces_edit_file", "args": {"path": "index.html"}}]
        self.assertEqual(q19.exploration(calls), {"inspected": True, "revised_after_inspect": True,
                                                  "references_read": 1, "entry_rewrites": 3})
        self.assertEqual(q19.exploration(calls[:2]), {"inspected": False, "revised_after_inspect": False,
                                                      "references_read": 1, "entry_rewrites": 1})
