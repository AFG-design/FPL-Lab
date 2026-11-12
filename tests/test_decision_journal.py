"""Decision journal entries (decision_journal.py, D5a). Run: python3 -m unittest discover tests"""
import json, os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from decision_journal import entry, compare
from fpl_score import plan_suggestion
best_suggestion = lambda plans, gw: plan_suggestion(plans, "two", gw)   # the plan these entries are checked against

DL = {"plan_gws": [10, 11, 12, 13, 14], "xp": {"1": [4, 4, 4, 4, 4], "2": [2, 2, 2, 2, 2], "3": [6, 5, 5, 5, 5],
                                               "4": [5, 5, 5, 5, 5], "9": [8, 7, 7, 7, 7]},
      "mins": {"1": [0.9, 0.05, 80], "3": [0.8, 0.1, 70]},
      "plans": {"roll": {"weeks": [{"gw": 10, "out": [], "in": [], "hits": 0, "captain": 9, "xi": [], "xp": 40}]},
                "two": {"weeks": [{"gw": 10, "out": [2, 1], "in": [3, 4], "hits": 0, "captain": 9, "xi": [], "xp": 45}]}}}
PROJ = {"players": {"1": [4, 4.1, "a", None], "3": [6, 5.0, "d", 75]}}
FX = [{"event": 10, "team_h": 1, "team_a": 2}, {"event": 11, "team_h": 2, "team_a": 1}]
TEAM = {1: 1, 2: 2, 3: 1, 4: 2, 9: 1, 7: 2}
PICKS = {"picks": [{"element": 9, "is_captain": True, "is_vice_captain": False}], "active_chip": None,
         "entry_history": {"event_transfers_cost": 4}}


class Journal(unittest.TestCase):
    def test_compare_needs_same_out_and_in(self):
        both, yours, skipped = compare([[2, 3], [7, 4]], [[2, 3], [1, 4]])
        self.assertEqual((both, yours, skipped), ([[2, 3]], [[7, 4]], [[1, 4]]))

    def test_entry_against_best_plan(self):
        e = entry(10, DL, PROJ, [[2, 3], [7, 4]], PICKS, FX, best_suggestion(DL["plans"], 10), TEAM)
        self.assertEqual(e["model"]["plan"], "two")
        self.assertEqual((e["both"], e["yours"], e["skipped"]), ([[2, 3]], [[7, 4]], [[1, 4]]))
        self.assertEqual((e["hits"], e["you"]["captain"]), (4, 9))
        p3 = e["players"]["3"]
        self.assertEqual((p3["xp1"], p3["xp5"], p3["start"], p3["status"], p3["chance"], p3["fx"]), (6, 26, 0.8, "d", 75, [[2, 1]]))

    def test_missing_player_and_minutes_are_marked_not_zeroed(self):
        e = entry(10, DL, PROJ, [[7, 4]], PICKS, FX, None, TEAM)
        self.assertTrue(e["players"]["7"]["absent"])
        self.assertIsNone(e["players"]["4"]["start"])          # in the xP but no minutes row: unknown, not 0
        self.assertIsNone(e["model"]); self.assertEqual(e["skipped"], [])
        self.assertEqual(e["players"]["4"]["fx"], [[1, 0]])     # away at club 1

    def test_real_gw10_snapshot(self):
        with open(os.path.join(HERE, "..", "history", "deadline_gw10.json")) as f:
            dl = json.load(f)
        from fpl_score import pair_moves, recommended_suggestion
        b = recommended_suggestion(dl, 10)                                   # FL-108: the recommended plan, "two"
        pos = {40: "MID", 115: "DEF", 4: "DEF", 183: "MID"}               # Rogers, De Cuyper out; Gabriel, Rudoni in
        b["out"], b["in"] = pair_moves(b["out"], b["in"], pos)
        e = entry(10, dl, None, [], PICKS, [], b, {})
        self.assertEqual(sorted(e["skipped"]), [[40, 183], [115, 4]])
        self.assertEqual(len(e["skipped"]), len(e["model"]["moves"]))      # no moves made yet: every suggestion skipped
        self.assertTrue(all(str(i) in e["players"] for mv in e["skipped"] for i in mv))


class Outcome(unittest.TestCase):
    def entry(self, chip=None):
        pk = {**PICKS, "active_chip": chip}
        return entry(10, DL, PROJ, [[7, 4]], pk, FX, best_suggestion(DL["plans"], 10), TEAM)

    def test_nothing_finished_yet(self):
        from decision_journal import outcome
        self.assertIsNone(outcome(self.entry(), {}, []))

    def test_two_weeks_in(self):
        from decision_journal import outcome
        played = {10: {4: (90, 8, 1), 7: (0, 0, 0), 9: (90, 2, 1), 3: (60, 6, 1), 2: (90, 1, 1)},
                  11: {4: (90, 2, 1), 7: (90, 6, 1), 3: (90, 3, 1)}}
        o = outcome(self.entry(), played, [10, 11])
        self.assertEqual((o["gws"], o["of"]), ([10, 11], 5))
        m = o["moves"]["7-4"]                       # yours: 7 out (not in the forecast), 4 in
        self.assertEqual((m["in_pts"], m["out_pts"], m["gain"], m["proj_gain"]), (10, 6, 4, 10))
        self.assertEqual(m["check"]["out"], {"started": False, "mins": 0, "start_chance": None, "xmin": None})
        self.assertIn("2-3", o["moves"])            # the model's moves are judged too (2 had 1 pt, 3 had 9)
        self.assertEqual(o["moves"]["2-3"]["gain"], 9 - 1)
        self.assertEqual((o["captain"]["you_pts"], o["captain"]["model_pts"]), (2, 2))

    def test_free_hit_is_one_week(self):
        from decision_journal import outcome
        played = {10: {4: (90, 8, 1)}, 11: {4: (90, 20, 1)}}
        o = outcome(self.entry("freehit"), played, [10, 11])
        self.assertEqual((o["gws"], o["of"], o["moves"]["7-4"]["in_pts"]), ([10], 1, 8))


if __name__ == "__main__":
    unittest.main()
