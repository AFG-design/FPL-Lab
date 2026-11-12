"""Pre-deadline snapshot (deadline_snapshot.py). Run: python3 -m unittest discover tests"""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from deadline_snapshot import build, write

GWS = [11, 12, 13]


def player(xp, dist=True, **kw):
    p = {"xp": dict(zip(GWS, xp)), "p_start": 0.9, "psub": 0.05, "start_next": 0.45, "sub_next": 0.03, "xmin": 81,
         "dist": {11: [0.12, 0.35, 0.4, 1, 9]} if dist else {}}
    p.update(kw)
    return p


PLAYERS = {1: player([5.1, 4.0, 0]), 2: player([0, 0, 0]), 3: player([0, 0, 0], dist=False), 4: player([0, 1.2, 3.3])}
FIX = [{"id": 101, "event": 11, "team_h": 1, "team_a": 2}, {"id": 102, "event": 12, "team_h": 3, "team_a": 4},
       {"id": 103, "event": 14, "team_h": 1, "team_a": 3}]
MARKET = {"built": "2026-11-06T18:00:00Z", "matches": [{"fixture": 101, "lam_h": 1.8, "lam_a": 0.9, "p_over": 0.55}]}
PLANS = {"roll": {"xp_total": 250.1, "ft_left": 2, "vs_roll": 0,
                  "weeks": [{"gw": 11, "out": [], "in": [], "hits": 0, "captain": 1, "xi": [1], "xp": 50.0, "bench": [3],
                                "vice": 1, "spread": 4.2}]}}


class Snapshot(unittest.TestCase):
    def test_keeps_plan_weeks_minutes_and_outcomes(self):
        s = build(11, GWS, PLAYERS, [1, 3], 1.5, 2, PLANS, MARKET, FIX, built="t")
        self.assertEqual(s["xp"]["1"], [5.1, 4.0, 0])
        self.assertEqual(s["xp"]["4"], [0, 1.2, 3.3])            # xP only in a later plan week still kept
        self.assertNotIn("2", s["xp"])                            # no xP and not yours: dropped
        self.assertIn("3", s["xp"])                               # yours, even with no xP
        self.assertEqual(s["mins"]["1"], [0.45, 0.03, 81])        # as the forecast used them, not p_start / psub
        self.assertEqual(s["dist"]["1"], [0.12, 0.35, 0.4])
        self.assertNotIn("3", s["dist"])                          # no simulation: no row, not a made-up one
        self.assertEqual((s["squad"], s["bank"], s["ft"], s["plan_gws"]), ([1, 3], 1.5, 2, GWS))

    def test_blank_or_missing_start_chance_stays_none(self):
        blank = {1: player([0, 4.0, 0], start_next=None, sub_next=None)}
        self.assertEqual(build(11, GWS, blank, [1], 0, 1, PLANS, MARKET, FIX, built="t")["mins"]["1"], [None, None, 81])
        old = {1: {"xp": {12: 4.0}, "p_start": 0.9, "psub": 0.05, "xmin": 81}}   # never falls back to the figure before flags
        self.assertEqual(build(11, GWS, old, [1], 0, 1, PLANS, MARKET, FIX, built="t")["mins"]["1"], [None, None, 81])

    def test_odds_as_they_stood_and_gaps_recorded(self):
        s = build(11, GWS, PLAYERS, [1], 0, 1, PLANS, MARKET, FIX, built="t")
        self.assertEqual([o["fixture"] for o in s["odds"]], [101])
        self.assertEqual(s["missing"]["odds_fixtures"], [102])   # plan-week fixture with no odds yet; GW14 not a plan week
        self.assertEqual(s["odds_built"], MARKET["built"])
        none = build(11, GWS, PLAYERS, [1], 0, 1, PLANS, None, FIX, built="t")
        self.assertEqual(none["odds"], [])
        self.assertIn("odds", none["missing"])

    def test_plans_kept_compactly_and_missing_said(self):
        s = build(11, GWS, PLAYERS, [1], 0, 1, PLANS, MARKET, FIX, built="t")
        w = s["plans"]["roll"]["weeks"][0]
        self.assertEqual((w["captain"], w["xi"], w["hits"]), (1, [1], 0))
        self.assertEqual((w["bench"], w["vice"]), ([3], 1))      # FL-109: saved so auto-subs can be applied
        self.assertNotIn("spread", w)                              # still compact: only what scoring needs
        self.assertEqual(build(11, GWS, PLAYERS, [], 0, 1, {}, MARKET, FIX, built="t")["missing"]["plans"], "no squad")
        self.assertEqual(build(11, GWS, PLAYERS, [1], 0, 1, {}, MARKET, FIX, built="t")["missing"]["plans"],
                         "no plans built this build")

    def test_written_as_json_per_gameweek(self):
        with tempfile.TemporaryDirectory() as d:
            path = write(d, build(11, GWS, PLAYERS, [1], 0, 1, PLANS, MARKET, FIX, built="t"))
            self.assertTrue(path.endswith("deadline_gw11.json"))
            self.assertEqual(json.load(open(path))["gw"], 11)


if __name__ == "__main__":
    unittest.main()
