"""Decision journal entries (decision_journal.py, D5a). Run: python3 -m unittest discover tests"""
import json, os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from decision_journal import entry, compare
from fpl_score import best_suggestion

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
        from fpl_score import pair_moves
        b = best_suggestion(dl["plans"], 10)
        pos = {40: "MID", 115: "DEF", 4: "DEF", 183: "MID"}               # Rogers, De Cuyper out; Gabriel, Rudoni in
        b["out"], b["in"] = pair_moves(b["out"], b["in"], pos)
        e = entry(10, dl, None, [], PICKS, [], b, {})
        self.assertEqual(sorted(e["skipped"]), [[40, 183], [115, 4]])
        self.assertEqual(len(e["skipped"]), len(e["model"]["moves"]))      # no moves made yet: every suggestion skipped
        self.assertTrue(all(str(i) in e["players"] for mv in e["skipped"] for i in mv))


if __name__ == "__main__":
    unittest.main()
