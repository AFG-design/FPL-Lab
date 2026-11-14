"""FL-161: proper scores per scoring part (backtest.part_scores) and the pooled paired intervals (bench.pooled)."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import backtest  # noqa: E402
import bench  # noqa: E402

SCORING = {"goals_scored": {"GKP": 10, "DEF": 6, "MID": 5, "FWD": 4}, "assists": 3,
           "clean_sheets": {"GKP": 4, "DEF": 4, "MID": 1, "FWD": 0}, "saves": 1,
           "defensive_contribution": {"GKP": 0, "DEF": 2, "MID": 2, "FWD": 2}}


def stats(**kw):
    s = {"minutes": 90, "starts": 1, "goals_scored": 0, "assists": 0, "clean_sheets": 0, "bonus": 0, "saves": 0}
    s.update(kw)
    return s


def ctx():
    # 1: DEF, one fixture; 2: FWD, one fixture; 3: DEF in a double (skipped); 4: DEF not in the pool (skipped)
    els = {1: {"element_type": 2, "team": 1}, 2: {"element_type": 4, "team": 1},
           3: {"element_type": 2, "team": 2}, 4: {"element_type": 2, "team": 1}}
    played = {g: {"minutes": 90} for g in (4, 5, 6)}
    pstats = {1: {**played, 7: stats(clean_sheets=1, goals_scored=1)}, 2: {**played, 7: stats(minutes=30, starts=0)},
              3: {**played, 7: stats()}, 4: {7: stats()}}
    fixtures = [{"event": 7, "team_h": 1, "team_a": 3}, {"event": 7, "team_h": 2, "team_a": 4},
                {"event": 7, "team_h": 2, "team_a": 5}]
    return {"elements": els, "pstats": pstats, "fixtures": fixtures, "scoring": SCORING, "dc_hit": {1: {7: True}}}


def res():
    det = {"goals": 0.6, "assists": 0.3, "cs": 1.6, "dc": 1.0, "bonus": 0.5}
    r = {"detail": {7: det}, "ps_next": 0.8, "p60_next": 0.7}
    return {1: r, 2: dict(r, detail={7: dict(det, cs=0.0)}), 3: r, 4: r}


class PartScores(unittest.TestCase):
    def test_values(self):
        out = backtest.part_scores(ctx(), 7, res())
        self.assertEqual(sorted(out), [1, 2])   # the double and the out-of-pool player are left out
        d = out[1]
        self.assertAlmostEqual(d["cs"], -math.log(0.4))            # chance 1.6 / 4 = 0.4, kept a clean sheet
        self.assertAlmostEqual(d["start"], (0.8 - 1) ** 2)
        self.assertAlmostEqual(d["p60"], (0.7 - 1) ** 2)
        self.assertAlmostEqual(d["goals"], 2 * (math.log(1 / 0.1) - (1 - 0.1)))   # 0.6 / 6 = 0.1 expected, scored 1
        self.assertAlmostEqual(d["assists"], 2 * 0.1)              # 0.3 / 3 = 0.1 expected, none: 2 * mu
        self.assertAlmostEqual(d["dc"], (0.5 - 1) ** 2)            # 1.0 / 2 = 0.5, hit
        self.assertAlmostEqual(d["bonus"], 0.25)
        self.assertNotIn("saves", d)                               # outfield
        self.assertNotIn("cs", out[2])                             # forwards score nothing for a clean sheet
        self.assertAlmostEqual(out[2]["start"], 0.64)

    def test_zero_chance_that_comes_off_is_finite(self):
        self.assertAlmostEqual(backtest._logloss(0.0, True), -math.log(1e-6))
        self.assertTrue(math.isfinite(backtest._poisson_dev(0.0, 2)))


def season(diffs, base=1.0):
    """{gw: {pid: {key: loss}}} for two variants, one player-week per gw, cand - base = diffs[gw]."""
    a = {g: {1: {"cs": base}} for g in range(len(diffs))}
    b = {g: {1: {"cs": base + d}} for g, d in enumerate(diffs)}
    return a, b


class PooledCI(unittest.TestCase):
    def test_identical_is_exactly_zero(self):
        a, _ = season([0] * 10)
        ci = backtest.scores_ci({"s": a}, {"s": a})["cs"]
        self.assertEqual(ci[:3], (0.0, 0.0, 0.0))

    def test_pools_player_weeks(self):
        a1, b1 = season([0.1] * 10)
        a2, b2 = season([-0.1] * 30)
        ci = backtest.scores_ci({"x": a1, "y": a2}, {"x": b1, "y": b2})["cs"]
        self.assertAlmostEqual(ci[0], (10 * 0.1 - 30 * 0.1) / 40)
        self.assertAlmostEqual(ci[1], ci[0]); self.assertAlmostEqual(ci[2], ci[0])   # no spread within a season
        self.assertEqual(ci[3], 40)

    def test_bench_pooled_picks(self):
        h = lambda per: {"_per": per}
        res = {s: {"_h5": {"current model": h({k: 19.0 for k in range(30)}),
                           "candidate": h({k: 19.0 + d for k in range(30)})},
                   "current model": {"_scores": season([0] * 3)[0]}, "candidate": {"_scores": season([0] * 3)[1]}}
               for s, d in (("2025-26", 0.2), ("2024-25", 0.0))}
        bench.pooled(res, ["current model", "candidate"], quiet=True)
        m, lo, hi, n = res["_pooled"]["candidate"]["h5_picks"]
        self.assertAlmostEqual(m, 0.1); self.assertAlmostEqual(lo, 0.1); self.assertAlmostEqual(hi, 0.1)
        self.assertEqual(n, 60)

    def test_one_season_missing_is_not_pooled(self):
        res = {"2025-26": {}}
        bench.pooled(res, ["current model", "candidate"], quiet=True)
        self.assertNotIn("_pooled", res)


if __name__ == "__main__":
    unittest.main()
