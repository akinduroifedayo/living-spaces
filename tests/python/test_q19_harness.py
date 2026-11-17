"""Q19 offline harness: frozen plan, deterministic oracles, spend ledger and gates. No model is called."""
import importlib.util
import unittest

from tests.python.test_core_store import ROOT

spec = importlib.util.spec_from_file_location("q19_eval", ROOT / "scripts/q19_eval.py")
assert spec is not None and spec.loader is not None
q19 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q19)


class Q19PlanTests(unittest.TestCase):
    def test_six_briefs_three_repeats_two_conditions_with_edits(self):
        briefs = q19.load_briefs()
        self.assertEqual([b["id"] for b in briefs],
                         ["trip-tracker", "rss-desk", "csv-spending", "memory-game", "long-document", "weather-board"])
        self.assertTrue(all(b["edit"] for b in briefs))
        builds = q19.plan(7)["builds"]
        self.assertEqual(len(builds), 36)
        self.assertEqual({(b["brief"], b["condition"], b["repeat"]) for b in builds},
                         {(b["id"], c, r) for b in briefs for c in q19.CONDITIONS for r in (1, 2, 3)})

    def test_plan_is_reproducible_randomized_and_blind(self):
        self.assertEqual(q19.plan(7), q19.plan(7))
        self.assertNotEqual([b["condition"] for b in q19.plan(7)["builds"]], [b["condition"] for b in q19.plan(8)["builds"]])
        builds = q19.plan(7)["builds"]
        self.assertEqual(len({b["blind_id"] for b in builds}), 36)
        self.assertTrue(all(b["condition"] not in b["blind_id"] for b in builds))

    def test_worst_case_matches_the_quoted_cap(self):
        self.assertEqual(q19.worst_case_total(), 853.2)
        self.assertLessEqual(q19.worst_case_total(), q19.CAP_USD)


class Q19OracleTests(unittest.TestCase):
    def test_brief_expectations_are_derived_from_the_fixtures(self):
        for brief in q19.load_briefs():
            with self.subTest(brief=brief["id"]):
                self.assertEqual(q19.ORACLES[brief["id"]](), brief["oracle"]["expected"])

    def test_fixtures_are_labelled_public_synthetic(self):
        for path in (q19.SUITE / "fixtures").iterdir():
            if path.suffix != ".csv":
                self.assertIn("PUBLIC SYNTHETIC FIXTURE", path.read_text(), path.name)

    def test_grade_fails_on_mismatch_and_missing_observation(self):
        good = q19.ORACLES["csv-spending"]()
        self.assertTrue(q19.grade("csv-spending", good)["pass"])
        self.assertEqual(q19.grade("csv-spending", {**good, "refunds": 20.0})["mismatched"], ["refunds"])
        self.assertFalse(q19.grade("csv-spending", None)["pass"])

    def test_toc_ignores_headings_inside_code_fences(self):
        self.assertEqual(q19.oracle_toc(), {"h2": 12, "h3": 30})


class Q19LedgerTests(unittest.TestCase):
    usage = {"input_tokens": 1000, "output_tokens": 100, "tool_calls": 3}

    def test_budget_overrun_is_a_failed_build_not_a_retry(self):
        ledger = q19.Ledger()
        ok = ledger.record(model="gpt-6.1-sol", kind="build", usage={**self.usage, "tool_calls": 61}, outcome="ok")
        self.assertFalse(ok)
        self.assertEqual(ledger.entries[0]["outcome"], "budget_exceeded")
        self.assertEqual(len(ledger.entries), 1)

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
        heavy = {"input_tokens": 1_000_000, "output_tokens": 0, "tool_calls": 1}   # $2.00 each
        for _ in range(3):
            ledger.record(model="gpt-6.1-sol", kind="build", usage=heavy, outcome="ok")
        with self.assertRaisesRegex(q19.StopRun, "80%"):
            ledger.record(model="gpt-6.1-sol", kind="build", usage=heavy, outcome="ok")
        with self.assertRaisesRegex(q19.StopRun, "cap reached"):
            ledger.record(model="gpt-6.1-sol", kind="build", usage=heavy, outcome="ok")


class Q19GateTests(unittest.TestCase):
    def rows(self, baseline, candidate, critical=False):
        rows = []
        for condition, value in (("baseline", baseline), ("candidate", candidate)):
            for reviewer in ("A", "B"):
                rows.append({"brief": "rss-desk", "condition": condition, "reviewer": reviewer, "artifact": condition,
                             "critical": critical and condition == "candidate", **value})
        return rows

    def test_visual_gate_requires_two_improvements_no_decline_no_critical(self):
        base = dict.fromkeys(q19.DIMENSIONS, 3)
        better = {**base, "readability": 4, "identity": 4}
        self.assertTrue(q19.visual_gate(self.rows(base, better))["pass"])
        self.assertFalse(q19.visual_gate(self.rows(base, {**base, "readability": 4}))["pass"])
        self.assertFalse(q19.visual_gate(self.rows(base, {**better, "task_hierarchy": 2}))["pass"])
        self.assertFalse(q19.visual_gate(self.rows(base, better, critical=True))["pass"])

    def test_time_gate_keeps_failures_in_the_denominator(self):
        results = [{"condition": "baseline", "usable_seconds": s} for s in (100, 110, 120)]
        self.assertTrue(q19.time_gate(results + [{"condition": "candidate", "usable_seconds": s} for s in (100, 105, 130)])["pass"])
        failing = q19.time_gate(results + [{"condition": "candidate", "usable_seconds": s} for s in (100, None, None)])
        self.assertFalse(failing["pass"])
        self.assertEqual(failing["failures"]["candidate"], 2)


if __name__ == "__main__":
    unittest.main()
