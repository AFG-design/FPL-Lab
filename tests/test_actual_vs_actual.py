"""FL-109: You vs the model scored actual v actual: your points against what the suggested team really scored, with
its bench, so auto-subs apply. Run: python3 -m unittest discover tests

Before FL-109 the target was the suggestion's projected score (GW10: 50), and its actual points were worked out from
the XI only, with no bench and no auto-subs (shown for interest)."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import fpl_score
from fpl_score import recommended_suggestion, suggested_team, suggested_target, result

with open(os.path.join(HERE, "..", "history", "deadline_gw10.json")) as f:
    GW10 = json.load(f)
with open(os.path.join(HERE, "fixtures", "gw10_suggested_played.json")) as f:
    FX = json.load(f)
POS = {int(k): v for k, v in FX["pos"].items()}
PLAYED = {int(k): tuple(v) for k, v in FX["played"].items()}


class RealGW10(unittest.TestCase):
    def test_bench_rebuilt_from_the_saved_snapshot(self):
        sug = recommended_suggestion(GW10, 10)
        t = suggested_team(GW10, sug, 10, POS)
        self.assertEqual(t["bench_src"], "derived")                # the GW10 snapshot saved no bench
        squad = (set(GW10["squad"]) - {40, 115}) | {4, 183}       # Rogers, De Cuyper out; Gabriel, Rudoni in
        self.assertEqual(set(t["xi"]) | set(t["bench"]), squad)
        self.assertEqual(len(t["bench"]), 4)
        self.assertEqual(POS[t["bench"][0]], "GKP")                # spare keeper first, as the optimiser orders it
        self.assertNotIn(t["vice"], (t["captain"], None))

    def test_actual_v_actual_gw10(self):
        sug = recommended_suggestion(GW10, 10)
        tgt = suggested_target(GW10, sug, 10, PLAYED, POS)
        # the audit's figure: the suggested team actually scored 77 (Gabriel captain); all 11 played, no auto-subs
        self.assertEqual((tgt["pts"], tgt["actual"], tgt["par"], tgt["subs"], tgt["armband"]), (77, 77, 77, [], 4))
        self.assertEqual(tgt["exp"], 50.5)                         # its projection, kept for information
        self.assertEqual(result(68, tgt["par"]), "L")              # you scored 68: a defeat (it was a win against 50)


def snap(bench=None, vice=None):
    """A two-week plan from a 15 of ids 1-15 (1, 2 keepers; 3-7 DEF; 8-12 MID; 13-15 FWD); week 1 signs 16 for 12."""
    w1 = {"gw": 10, "out": [12], "in": [16], "hits": 1, "captain": 8, "xp": 50.0,
          "xi": [1, 3, 4, 5, 6, 8, 9, 10, 11, 13, 16]}
    if bench is not None:
        w1.update(bench=bench, vice=vice)
    return {"squad": list(range(1, 16)), "plan_gws": [10, 11],
            "xp": {str(i): [10 - i * 0.5 if i != 16 else 6.0, 1] for i in range(1, 17)},
            "plans": {"two": {"vs_roll": 1, "weeks": [w1, {"gw": 11, "out": [], "in": [], "hits": 0, "captain": 8,
                                                           "xi": w1["xi"], "xp": 40}]}}}


POS16 = {**{1: "GKP", 2: "GKP"}, **{i: "DEF" for i in range(3, 8)}, **{i: "MID" for i in range(8, 13)},
         **{i: "FWD" for i in (13, 14, 15)}, 16: "MID"}


class Rules(unittest.TestCase):
    def test_auto_sub_and_vice_count(self):
        s = snap()
        sug = fpl_score.plan_suggestion(s["plans"], "two", 10)
        played = {i: (90, 2) for i in range(1, 17)}
        played[8] = (0, 0)       # the captain doesn't play: the vice gets the armband
        played[6] = (0, 0)       # a defender doesn't play: the first bench outfielder who keeps a legal side comes on
        t = suggested_target(s, sug, 10, played, POS16)
        self.assertEqual(t["bench_src"], "derived")
        self.assertEqual(t["bench"][0], 2)                      # keeper first
        self.assertEqual(t["vice"], 1)                           # highest xP in the XI after the captain
        self.assertEqual(t["armband"], 1)
        self.assertEqual(len(t["subs"]), 2)                      # both non-players replaced from the bench
        self.assertEqual(t["pts"], 11 * 2 + 2)                   # 11 players x 2, vice doubled
        self.assertEqual((t["actual"], t["par"]), (t["pts"] - 4, t["pts"] - 4))   # its hit comes off

    def test_saved_bench_wins(self):
        s = snap(bench=[2, 15, 14, 7], vice=9)
        sug = fpl_score.plan_suggestion(s["plans"], "two", 10)
        t = suggested_team(s, sug, 10, POS16)
        self.assertEqual((t["bench"], t["vice"], t["bench_src"]), ([2, 15, 14, 7], 9, "saved"))

    def test_squad_that_does_not_add_up_scores_the_xi_only(self):
        s = snap()
        s["plans"]["two"]["weeks"][0]["in"] = [16, 17]          # two in, one out: not a squad of 15
        sug = fpl_score.plan_suggestion(s["plans"], "two", 10)
        t = suggested_team(s, sug, 10, {**POS16, 17: "MID"})
        self.assertEqual((t["bench"], t["vice"], t["bench_src"]), ([], None, "missing"))


if __name__ == "__main__":
    unittest.main()
