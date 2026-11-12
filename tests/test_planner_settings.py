"""FL-075: the planner settings the browser reads (data.json plan_rules) are optimise.py's own, in one place.
Run: python3 -m unittest discover tests"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import optimise  # noqa: E402


class PlannerSettings(unittest.TestCase):
    def test_settings_are_optimise_values(self):
        s = optimise.planner_settings(5)
        self.assertEqual(s["pool"], optimise.POOL)
        self.assertEqual((s["decay"], s["bench_w"], s["hit"], s["max_moves_week"]),
                         (optimise.DECAY, optimise.BENCH_W, optimise.HIT, optimise.MAX_MOVES_WEEK))
        self.assertEqual(s["eo_weeks"], optimise.EO_WEEKS or 5)
        for pos, (a, b) in s["variance"].items():
            self.assertAlmostEqual(optimise.variance(pos, 4.0), a * 4 + b * 16)

    def test_build_ships_them(self):
        with open(os.path.join(HERE, "..", "build.py")) as f:
            self.assertIn("**optimise.planner_settings(", f.read())

    def test_js_fixture_matches_optimise(self):
        # tests/fixtures/plan_rules.json feeds the browser-solver tests; it must stay what build.py would write
        with open(os.path.join(HERE, "fixtures", "plan_rules.json")) as f:
            fx = json.load(f)
        want = dict(ft_value=optimise.FT_VALUE, safe_budget=optimise.SAFE_BUDGET, chase_budget=optimise.CHASE_BUDGET,
                    min_profit=optimise.MIN_PROFIT, hit_gain=optimise.HIT_GAIN, max_hits=optimise.MAX_HITS,
                    tie=optimise.TIE, strategy=optimise.STRATEGY, recommend_margin=optimise.RECOMMEND_MARGIN,
                    **optimise.planner_settings(5))
        self.assertEqual(fx, json.loads(json.dumps(want)))

    def test_browser_keeps_no_copies(self):
        with open(os.path.join(HERE, "..", "site", "plan-solver.js")) as f:
            js = f.read()
        for copy in ("GKP: 10, DEF: 26", "1.9 * x + 0.23", "?? 0.9", "?? 0.1", "?? 1.5", "eoWeeks ?? 2"):
            self.assertNotIn(copy, js)


if __name__ == "__main__":
    unittest.main()
