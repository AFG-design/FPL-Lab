"""FL-074: plans still work when a real move between Premier League clubs leaves you with four from one club.

FPL (game_settings.squad_team_limit = 3) lets you keep the extra player but takes no transfer until you're back to 3
from that club. Before FL-074 the optimiser capped every week at 3, so a squad holding 4 had no legal plan at all.
Run: python3 -m unittest discover tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import optimise  # noqa: E402

POS = ["GKP"] * 3 + ["DEF"] * 7 + ["MID"] * 7 + ["FWD"] * 5
GWS = [11, 12, 13]


def setup(xp_of=None):
    """22 players on their own clubs (ids 1-22), except the squad's 3, 4, 11 and 12 who all play for club 1.
    Squad: 1-2 (GKP), 4-8 (DEF), 11-15 (MID), 18-20 (FWD)."""
    players = {}
    for k, pos in enumerate(POS, start=1):
        team = 1 if k in (3, 4, 11, 12) else 100 + k
        x = (xp_of or {}).get(k, 4.0)
        players[k] = {"pos": pos, "team": team, "price": 5.0, "xp": {g: x for g in GWS}, "ok": True}
    squad = [1, 2, 4, 5, 6, 7, 8, 11, 12, 13, 14, 15, 18, 19, 20]
    players[3]["team"] = 300      # the spare keeper isn't from club 1: four from club 1 = 4, 11, 12 and 5
    players[5]["team"] = 1
    return players, squad


def club1(players, ids):
    return sum(players[i]["team"] == 1 for i in ids)


class ClubLimit(unittest.TestCase):
    def test_holding_four_still_gets_a_plan(self):
        players, squad = setup()
        self.assertEqual(optimise.club_over(squad, players), {1: 1})
        # rolling this week (no transfer) has to keep all four: before FL-074 that was infeasible, and so was keeping
        # the squad, so strategy_plans returned no plans at all
        r = optimise.solve(players, squad, {}, 0.0, 1, GWS, week1_moves=0, time_limit=20)
        self.assertIsNotNone(r)
        plans, notes = optimise.strategy_plans(players, squad, {}, 0.0, 1, GWS, [("roll", 0), ("one", 1)], time_limit=20)
        self.assertIn("roll", plans, notes)

    def test_any_week_with_a_transfer_ends_at_three(self):
        players, squad = setup({9: 9.0})               # 9, a defender from another club, is worth signing
        r = optimise.solve(players, squad, {}, 0.0, 1, GWS, time_limit=20)
        have = set(squad)
        for wk in r["weeks"]:
            have = (have - set(wk["out"])) | set(wk["in"])
            if wk["in"]:
                self.assertLessEqual(club1(players, have), 3, wk)
            else:
                self.assertLessEqual(club1(players, have), 4, wk)
        self.assertIn(9, have)

    def test_keeping_the_squad_keeps_the_four(self):
        players, squad = setup()
        r = optimise.solve(players, squad, {}, 0.0, 1, GWS, week1_moves=0, freeze_after=0, time_limit=20)
        self.assertIsNotNone(r)
        self.assertEqual(club1(players, r["weeks"][-1]["xi"] + r["weeks"][-1]["bench"]), 4)

    def test_never_goes_above_what_you_hold(self):
        # 3 is a club-1 keeper again: buying him would make 5 from club 1 even though he's worth a lot
        players, squad = setup({3: 30.0})
        players[3]["team"] = 1
        r = optimise.solve(players, squad, {}, 0.0, 1, GWS, time_limit=20)
        have = set(squad)
        for wk in r["weeks"]:
            have = (have - set(wk["out"])) | set(wk["in"])
            self.assertLessEqual(club1(players, have), 3 if wk["in"] else 4)


if __name__ == "__main__":
    unittest.main()
