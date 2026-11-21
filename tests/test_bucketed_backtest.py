"""FL-235: opt-in --bucketed four-area backtest (per-season and pooled) in backtest.py."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import backtest  # noqa: E402


def _make_season_a():
    """Synthetic season A: positive play_cal (+0.20), positive xP bias (+1.0), positive Top-50 Spearman (+1.0)."""
    return {
        "season": "2024-25",
        "gws": [4, 5],
        # (p_play, y_play, p60, y60, xmin, act_mins)
        "minutes": [
            (0.90, 1.0, 0.80, 1.0, 80.0, 90.0),
            (0.50, 0.0, 0.20, 0.0, 30.0, 0.0),
        ],
        "team_cs": [(0.40, 1.0), (0.30, 0.0)],
        "player_cs": [(0.35, 1.0), (0.25, 0.0)],
        # (eg, ag, ea, aa)
        "ga": [
            (0.60, 1.0, 0.20, 0.0),
            (0.10, 0.0, 0.40, 1.0),
        ],
        # GW4 & GW5: strictly increasing actuals with predicted xP -> Spearman = +1.0
        "xp_by_gw": {
            4: [(1, 6.0, 5.0), (2, 4.0, 3.0), (3, 2.0, 1.0), (4, 1.0, 0.0)],
            5: [(1, 5.0, 4.0), (2, 3.0, 2.0), (3, 2.0, 1.0), (4, 1.0, 0.0)],
        },
    }


def _make_season_b():
    """Synthetic season B: different sample size, negative play_cal, negative xP bias, negative Top-50 Spearman."""
    return {
        "season": "2025-26",
        "gws": [4, 5, 6],
        "minutes": [
            (0.60, 1.0, 0.50, 1.0, 60.0, 90.0),
            (0.70, 1.0, 0.60, 1.0, 70.0, 80.0),
            (0.40, 1.0, 0.30, 0.0, 45.0, 20.0),
            (0.10, 0.0, 0.05, 0.0, 10.0, 0.0),
        ],
        "team_cs": [(0.20, 0.0), (0.50, 0.0), (0.60, 1.0)],
        "player_cs": [(0.10, 0.0), (0.50, 0.0), (0.70, 1.0)],
        "ga": [
            (0.20, 0.0, 0.10, 0.0),
            (0.80, 2.0, 0.50, 0.0),
            (0.05, 0.0, 0.05, 0.0),
        ],
        # Strictly reversed order -> Spearman = -1.0; negative bias (pred < act)
        "xp_by_gw": {
            4: [(1, 5.0, 2.0), (2, 4.0, 5.0), (3, 3.0, 7.0), (4, 2.0, 9.0)],
            5: [(1, 5.0, 1.0), (2, 4.0, 4.0), (3, 3.0, 8.0), (4, 2.0, 10.0)],
            6: [(1, 5.0, 3.0), (2, 4.0, 6.0), (3, 3.0, 9.0), (4, 2.0, 12.0)],
        },
    }


class BucketedBacktestTest(unittest.TestCase):
    def test_exact_four_area_metrics(self):
        obs = _make_season_a()
        res = backtest.summarize_bucketed(obs)

        # 1. Minutes
        m = res["minutes"]
        self.assertEqual(m["n"], 2)
        self.assertAlmostEqual(m["play_brier"], ((0.9 - 1.0) ** 2 + (0.5 - 0.0) ** 2) / 2)
        self.assertAlmostEqual(m["play_cal"], ((0.9 - 1.0) + (0.5 - 0.0)) / 2)  # +0.20
        self.assertAlmostEqual(m["p60_brier"], ((0.8 - 1.0) ** 2 + (0.2 - 0.0) ** 2) / 2)
        self.assertAlmostEqual(m["p60_cal"], ((0.8 - 1.0) + (0.2 - 0.0)) / 2)   # 0.0
        self.assertAlmostEqual(m["xmin_mae"], (10.0 + 30.0) / 2)
        self.assertAlmostEqual(m["xmin_rmse"], math.sqrt((10.0 ** 2 + 30.0 ** 2) / 2))

        # 2. Clean sheets
        c = res["clean_sheets"]
        self.assertEqual(c["team_n"], 2)
        self.assertAlmostEqual(c["team_brier"], ((0.4 - 1.0) ** 2 + (0.3 - 0.0) ** 2) / 2)
        self.assertAlmostEqual(c["team_logloss"], (-math.log(0.4) - math.log(0.7)) / 2)
        self.assertEqual(c["player_n"], 2)
        self.assertAlmostEqual(c["player_brier"], ((0.35 - 1.0) ** 2 + (0.25 - 0.0) ** 2) / 2)
        self.assertAlmostEqual(c["player_logloss"], (-math.log(0.35) - math.log(0.75)) / 2)

        # 3. Goals & assists
        g = res["goals_assists"]
        self.assertEqual(g["n"], 2)
        self.assertAlmostEqual(g["goals_mae"], (0.4 + 0.1) / 2)
        self.assertAlmostEqual(g["goals_rmse"], math.sqrt((0.4 ** 2 + 0.1 ** 2) / 2))
        self.assertAlmostEqual(g["assists_mae"], (0.2 + 0.6) / 2)
        self.assertAlmostEqual(g["assists_rmse"], math.sqrt((0.2 ** 2 + 0.6 ** 2) / 2))
        self.assertAlmostEqual(g["ga_mae"], (abs(0.8 - 1.0) + abs(0.5 - 1.0)) / 2)
        self.assertAlmostEqual(g["ga_rmse"], math.sqrt(((0.8 - 1.0) ** 2 + (0.5 - 1.0) ** 2) / 2))

        # 4. Total xP
        x = res["xp"]
        self.assertEqual(x["n"], 8)
        self.assertEqual(x["gws"], 2)
        self.assertAlmostEqual(x["mae"], 1.0)
        self.assertAlmostEqual(x["rmse"], 1.0)
        self.assertAlmostEqual(x["bias"], 1.0)
        self.assertAlmostEqual(x["top50_spearman"], 1.0)

    def test_seasons_computed_independently_never_copied_or_derived_from_pooled(self):
        """Fails if any season row is copied from another season or derived from pooled numbers."""
        data = {"2024-25": _make_season_a(), "2025-26": _make_season_b()}
        report = backtest.bucketed_eval(
            seasons=("2024-25", "2025-26"),
            collector=lambda s, params=None, gws=None: data[s],
        )
        s1 = report["seasons"]["2024-25"]
        s2 = report["seasons"]["2025-26"]
        pooled = report["pooled"]

        # Each season must match its own standalone calculation exactly
        self.assertEqual(s1, backtest.summarize_bucketed(_make_season_a()))
        self.assertEqual(s2, backtest.summarize_bucketed(_make_season_b()))

        # Every headline metric must differ across 2024-25, 2025-26, and pooled (catches copy-paste or pooling leakage)
        checks = [
            ("minutes", "play_brier"), ("minutes", "play_cal"),
            ("minutes", "p60_brier"), ("minutes", "p60_cal"),
            ("minutes", "xmin_mae"), ("minutes", "xmin_rmse"),
            ("clean_sheets", "team_brier"), ("clean_sheets", "team_logloss"),
            ("clean_sheets", "player_brier"), ("clean_sheets", "player_logloss"),
            ("goals_assists", "goals_rmse"), ("goals_assists", "goals_mae"),
            ("goals_assists", "assists_rmse"), ("goals_assists", "assists_mae"),
            ("goals_assists", "ga_rmse"), ("goals_assists", "ga_mae"),
            ("xp", "rmse"), ("xp", "mae"), ("xp", "bias"), ("xp", "top50_spearman"),
        ]
        for area, metric in checks:
            v1, v2, vp = s1[area][metric], s2[area][metric], pooled[area][metric]
            self.assertNotAlmostEqual(v1, v2, places=6, msg=f"{area}.{metric} identical across seasons")
            self.assertNotAlmostEqual(v1, vp, places=6, msg=f"{area}.{metric} 2024-25 equals pooled")
            self.assertNotAlmostEqual(v2, vp, places=6, msg=f"{area}.{metric} 2025-26 equals pooled")

        # Pooled Top-50 Spearman must weight by GW count (2 GWs at +1.0, 3 GWs at -1.0 -> -0.2), NOT (1 - 1)/2 = 0.0
        self.assertAlmostEqual(pooled["xp"]["top50_spearman"], (2 * 1.0 + 3 * (-1.0)) / 5)

        # Mutating 2025-26 must change 2025-26 and pooled, while leaving 2024-25 bit-for-bit identical
        data_mut = {"2024-25": _make_season_a(), "2025-26": _make_season_b()}
        data_mut["2025-26"]["xp_by_gw"][4] = [(1, 5.0, 20.0), (2, 4.0, 10.0), (3, 3.0, 5.0), (4, 2.0, 0.0)]
        report_mut = backtest.bucketed_eval(
            seasons=("2024-25", "2025-26"),
            collector=lambda s, params=None, gws=None: data_mut[s],
        )
        self.assertEqual(report_mut["seasons"]["2024-25"], s1)
        self.assertNotEqual(report_mut["seasons"]["2025-26"]["xp"], s2["xp"])
        self.assertNotEqual(report_mut["pooled"]["xp"], pooled["xp"])

    def test_top50_tie_break_uses_pid_not_actuals(self):
        """Top-50 selection must never peek at actual points when breaking predicted xP ties."""
        # 51 players all tied at xP=4.0 except pid 1..50; pid 51 has huge actual points (20)
        rows = [(pid, 4.0 + (0.01 if pid <= 49 else 0.0), float(pid)) for pid in range(1, 50)]
        # pid 50 and pid 51 tie on predicted xP=4.0; pid 50 has actual=0, pid 51 has actual=100
        rows.append((51, 4.0, 100.0))
        rows.append((50, 4.0, 0.0))
        obs = {"minutes": [], "team_cs": [], "player_cs": [], "ga": [], "xp_by_gw": {4: rows}}
        sp1 = backtest.summarize_bucketed(obs)["xp"]["top50_spearman"]

        # Reversing input order must give the exact same Spearman (pid 50 picked over pid 51, not actual=100)
        obs2 = {"minutes": [], "team_cs": [], "player_cs": [], "ga": [], "xp_by_gw": {4: list(reversed(rows))}}
        sp2 = backtest.summarize_bucketed(obs2)["xp"]["top50_spearman"]
        self.assertAlmostEqual(sp1, sp2)

    def test_empty_observations_return_none_not_zero(self):
        obs = {"minutes": [], "team_cs": [], "player_cs": [], "ga": [], "xp_by_gw": {}}
        res = backtest.summarize_bucketed(obs)
        self.assertEqual(res["minutes"]["n"], 0)
        self.assertIsNone(res["minutes"]["play_brier"])
        self.assertIsNone(res["clean_sheets"]["team_brier"])
        self.assertIsNone(res["goals_assists"]["ga_rmse"])
        self.assertIsNone(res["xp"]["top50_spearman"])


if __name__ == "__main__":
    unittest.main()
