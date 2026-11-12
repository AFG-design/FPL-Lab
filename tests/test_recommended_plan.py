"""FL-108: one definition of the recommended plan, worked out once in the build and used by every screen.

Before FL-108 Home and the Planner opened on the fewest-moves plan within 0.5 of the best vs_roll (worked out in the
browser), while the decision journal and You vs the model used the plan with the highest single-week xP across every
saved plan (fpl_score.best_suggestion), which favoured the most transfers. Run: python3 -m unittest discover tests
"""
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
import optimise
from decision_journal import entry
from fpl_score import pair_moves, recommended_suggestion

GW10 = os.path.join(ROOT, "history", "deadline_gw10.json")


def plan(vs_roll, moves, xp=48.0):
    ins = list(range(100, 100 + moves))
    return {"vs_roll": vs_roll, "weeks": [{"gw": 11, "out": list(range(200, 200 + moves)), "in": ins, "hits": 0,
                                           "captain": 1, "xi": [1], "xp": xp}]}


class Rule(unittest.TestCase):
    def test_fewest_moves_within_the_margin(self):
        # the GW11 shape from the audit: three moves score the most next week (+0.19 over 5 GWs), rolling is within 0.5
        plans = {"roll": plan(0.0, 0, 47.72), "one": plan(-0.9, 1, 47.78), "two": plan(0.19, 2, 47.91),
                 "three": plan(0.19, 3, 47.91), "best": plan(0.19, 3, 47.91)}
        self.assertEqual(optimise.recommended(plans), {"balanced": "roll", "safe": None, "chase": None})
        s = recommended_suggestion({"plans": plans}, 11)
        self.assertEqual((s["plan"], s["in"], s["derived"]), ("roll", [], True))

    def test_clear_gain_takes_the_moves(self):
        plans = {"roll": plan(0.0, 0), "one": plan(1.6, 1), "two": plan(2.0, 2),
                 "safe_roll": plan(0.0, 0), "safe_one": plan(0.3, 1)}
        self.assertEqual(optimise.recommended(plans), {"balanced": "one", "safe": "safe_roll", "chase": None})

    def test_missing_inputs(self):
        self.assertEqual(optimise.recommended({}), {"balanced": None, "safe": None, "chase": None})
        self.assertEqual(optimise.recommended(None), {"balanced": None, "safe": None, "chase": None})
        # a plan without vs_roll can't be compared and is left out; "best" is never the recommendation
        self.assertEqual(optimise.recommended({"roll": {"weeks": []}, "best": plan(3, 2)})["balanced"], None)
        self.assertIsNone(recommended_suggestion(None, 10))
        self.assertIsNone(recommended_suggestion({"plans": {}}, 10))

    def test_saved_choice_wins_over_rederiving(self):
        plans = {"roll": plan(0.0, 0), "two": plan(2.0, 2)}
        s = recommended_suggestion({"plans": plans, "recommended": {"balanced": "roll"}}, 11)
        self.assertEqual((s["plan"], s["derived"]), ("roll", False))


class SavedGW10(unittest.TestCase):
    """The plans saved before the GW10 deadline (history/deadline_gw10.json), which the build must never rewrite."""

    def setUp(self):
        with open(GW10, "rb") as f:
            self.raw = f.read()
        self.dl = json.loads(self.raw)

    def test_snapshot_is_untouched(self):
        self.assertNotIn("recommended", self.dl)        # saved before FL-108: read as it is, the rule applied to it

    def test_one_plan_on_every_screen(self):
        rec = optimise.recommended(self.dl["plans"])
        self.assertEqual(rec, {"balanced": "two", "safe": "safe_two", "chase": "chase_two"})
        # You vs the model's target and the journal's model side are the same plan Home and the Planner open on
        tgt = recommended_suggestion(self.dl, 10)
        self.assertEqual((tgt["plan"], tgt["exp"], tgt["hits"], tgt["derived"]), ("two", 50.48, 0, True))
        pos = {40: "MID", 115: "DEF", 4: "DEF", 183: "MID"}
        tgt["out"], tgt["in"] = pair_moves(tgt["out"], tgt["in"], pos)
        picks = {"picks": [{"element": 1, "is_captain": True}], "active_chip": None, "entry_history": {}}
        e = entry(10, self.dl, None, [], picks, [], tgt, {})
        self.assertEqual(e["model"]["plan"], rec["balanced"])
        self.assertEqual(sorted(e["model"]["moves"]), [[40, 183], [115, 4]])


class OneDefinition(unittest.TestCase):
    def test_build_and_browser_use_it(self):
        with open(os.path.join(ROOT, "build.py")) as f:
            build = f.read()
        self.assertNotIn("best_suggestion", build)
        self.assertEqual(len(re.findall(r"fpl_score\.recommended_suggestion\(", build)), 3)   # target, next, journal
        self.assertIn('"recommended": recommended', build)
        with open(os.path.join(ROOT, "site", "js", "core", "plan.js")) as f:
            js = f.read()
        body = js[js.index("function recommendedPlan("):js.index("const mvKey")]
        self.assertIn("D.recommended", body)
        self.assertNotIn("vs_roll", body)                 # no second copy of the rule in the browser


if __name__ == "__main__":
    unittest.main()
