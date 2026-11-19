"""FL-223: league_sim.py on a tiny made-up league: shared scorelines, auto-subs, captain/vice and the odds' sums."""
import unittest

import numpy as np

import league_sim
from fplmodel import DEFAULTS

SCORING = {"short_play": 1, "long_play": 2, "goals_scored": {"GKP": 10, "DEF": 6, "MID": 5, "FWD": 4}, "assists": 3,
           "clean_sheets": {"GKP": 4, "DEF": 4, "MID": 1, "FWD": 0}, "goals_conceded": {"GKP": -1, "DEF": -1, "MID": 0, "FWD": 0},
           "saves": 1, "defensive_contribution": {"GKP": 0, "DEF": 2, "MID": 2, "FWD": 2}}
RUNS = 4000


def fx(pos, h, a, home, g90=0.4, ps=0.95):
    """One fixture's _sim_fixture inputs, as fplmodel.project(fx_out) records them."""
    return {"h": h, "a": a, "home": home, "args": (pos, ps, 0.0, 0.9, 85, 20, g90, 0.2, 1.4, 1.2,
                                                   2.5 if pos == "GKP" else 0.0, (0.3, 0.05), 0.4, 0.1)}


class LeagueSimTests(unittest.TestCase):
    def setUp(self):
        self.upcoming = {1: {5: [(2, True, 1.4, 1.2, 3)]}, 2: {5: [(1, False, 1.2, 1.4, 3)]}}
        self.goals = league_sim._fixture_goals(self.upcoming, [5], RUNS, DEFAULTS["cs_k"])

    def pts(self, pid, f, xp=5.0):
        proj = {pid: {"xp": {5: xp}, "fx": {5: [f]}}}
        return league_sim.player_points(pid, proj, [5], self.goals, SCORING, DEFAULTS, RUNS)[5]

    def test_teammates_share_the_scoreline(self):
        a, _ = self.pts(10, fx("FWD", 1, 2, True))
        b, _ = self.pts(11, fx("FWD", 1, 2, True))
        gk_opp, _ = self.pts(20, fx("GKP", 1, 2, False))
        self.assertGreater(np.corrcoef(a, b)[0, 1], 0.05)          # team-mates move together
        self.assertLess(np.corrcoef(a, gk_opp)[0, 1], -0.05)       # the other side's keeper loses when they score

    def test_mean_matches_xp(self):
        p, _ = self.pts(10, fx("MID", 1, 2, True), xp=4.3)
        self.assertAlmostEqual(p.mean(), 4.3, delta=0.05)

    def test_clean_sheet_chance_follows_cs_k(self):
        gh, ga, ch, ca = self.goals[(5, 1, 2, 0)]
        self.assertAlmostEqual((ch == 0).mean(), np.exp(-DEFAULTS["cs_k"] * 1.2), delta=0.03)   # home defence v 1.2
        self.assertTrue((ch <= ga).all() and (ca <= gh).all())      # conceded: the other side's goals, thinned

    def _squad(self):
        pos = {1: "GKP", 2: "DEF", 3: "DEF", 4: "DEF", 5: "MID", 6: "MID", 7: "MID", 8: "MID", 9: "FWD", 10: "FWD",
               11: "FWD", 12: "GKP", 13: "DEF", 14: "MID", 15: "FWD"}
        order = list(range(1, 12)) + [12, 14, 13, 15]     # bench: keeper, then MID 14 before DEF 13
        return [[i, 2 if i == 9 else 1] for i in order], pos

    def test_autosub_formation_and_vice(self):
        p, pos = self._squad()
        ones, zeros = np.ones(4), np.zeros(4)
        pp = {i: {5: (ones * 2, ones.astype(bool))} for i in range(1, 16)}
        pp[2] = {5: (zeros, zeros.astype(bool))}        # a defender doesn't play (3 DEF: only a defender may come on)
        pp[9] = {5: (zeros, zeros.astype(bool))}        # the captain doesn't play: the vice doubles
        xp = {9: 9, 10: 8}.get
        tot = league_sim._xi_points(p, pos, pp, lambda el: xp(el, 1), 5, 4)
        # 9 starters who play (18), DEF 13 on for DEF 2 (+2: MID 14 is first on the bench but would leave 2 DEF),
        # MID 14 on for the captain (+2: 2 FWD left is legal), vice 10 doubled (+2)
        self.assertTrue((tot == 24).all(), tot)
        self.assertTrue((league_sim._xi_points(p, pos, pp, lambda el: xp(el, 1), 5, 4, cap_override=5) == 24).all())

    def test_odds_sum_to_one(self):
        p, pos = self._squad()
        proj = {i: {"xp": {5: 3.0}, "fx": {5: [fx(pos[i], 1, 2, True) if i % 2 else fx(pos[i], 1, 2, False)]}}
                for i in range(1, 16)}
        q = [[i + 1 if i < 15 else i - 14, m] for i, m in p]   # the same squad, shifted by one player
        picks = {100: (p, None), 200: (q, None), 300: (None, "picks didn't load")}
        lgs = [{"id": 1, "size": 3, "members": [100, 200, 300]}, {"id": 2, "size": 50, "members": [100, 200]}]
        odds, means = league_sim.league_odds(lgs, picks.get, lambda l, e: 500, pos, proj, self.upcoming, [5], SCORING,
                                             DEFAULTS, 100, 4, False, runs=500)
        o = odds[1]
        self.assertTrue(o["ok"])
        self.assertEqual((o["n"], o["m"], [x["entry"] for x in o["left_out"]]), (2, 3, [300]))
        self.assertAlmostEqual(sum(r["p1"] for r in o["rows"]), 1, places=3)
        self.assertAlmostEqual(sum(r["plast"] for r in o["rows"]), 1, places=3)
        self.assertEqual(len(o["captain"]["options"]), 3)
        self.assertFalse(odds[2]["ok"])                  # part-sampled league: no odds, a reason
        self.assertIn("too big", odds[2]["why"])


if __name__ == "__main__":
    unittest.main()
