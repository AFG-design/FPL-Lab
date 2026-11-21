"""FL-236: opt-in 3-bucket minutes model (--minutes-model=3bucket) in fplmodel.py."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fplmodel  # noqa: E402


def _scoring():
    return {
        "long_play": 2, "short_play": 1,
        "goals_scored": {"GKP": 10, "DEF": 6, "MID": 5, "FWD": 4},
        "assists": 3,
        "clean_sheets": {"GKP": 4, "DEF": 4, "MID": 1, "FWD": 0},
        "goals_conceded": {"GKP": -1, "DEF": -1, "MID": 0, "FWD": 0},
        "saves": 1, "yellow_cards": -1, "red_cards": -3,
        "defensive_contribution": {"GKP": 0, "DEF": 2, "MID": 2, "FWD": 2},
    }


def _make_ctx(congestion=(), status_log=None):
    teams = [{"id": 1, "short_name": "ARS", "name": "Arsenal"},
             {"id": 2, "short_name": "BRE", "name": "Brentford"}]
    elements = [
        {"id": 1, "element_type": 1, "team": 1, "web_name": "Keeper", "status": "a",
         "chance_of_playing_next_round": None, "now_cost": 55, "penalties_order": None},
        {"id": 2, "element_type": 2, "team": 1, "web_name": "Defender", "status": "a",
         "chance_of_playing_next_round": None, "now_cost": 60, "penalties_order": None},
        {"id": 3, "element_type": 3, "team": 1, "web_name": "Midfielder", "status": "a",
         "chance_of_playing_next_round": None, "now_cost": 80, "penalties_order": None},
        {"id": 4, "element_type": 4, "team": 2, "web_name": "Forward", "status": "a",
         "chance_of_playing_next_round": None, "now_cost": 75, "penalties_order": None},
    ]
    fixtures = []
    for g in range(1, 7):
        fixtures.append({
            "id": g, "event": g, "team_h": 1 if g % 2 else 2, "team_a": 2 if g % 2 else 1,
            "team_h_score": 1 if g < 6 else None, "team_a_score": 0 if g < 6 else None,
            "team_h_difficulty": 3, "team_a_difficulty": 3,
            "kickoff_time": f"2026-09-{g:02d}T14:00:00Z", "finished": g < 6,
        })
    boot = {"elements": elements, "teams": teams,
            "game_config": {"scoring": _scoring()},
            "events": [{"id": g, "finished": g < 6, "deadline_time": f"2026-09-{g:02d}T11:30:00Z"} for g in range(1, 7)]}
    live = {}
    for g in range(1, 6):
        live[g] = {"elements": [
            {"id": 1, "stats": {"minutes": 90, "starts": 1, "goals_scored": 0, "assists": 0, "clean_sheets": 1,
                                "goals_conceded": 0, "saves": 3, "bonus": 0, "yellow_cards": 0, "red_cards": 0,
                                "total_points": 7, "expected_goals": "0.00", "expected_assists": "0.00",
                                "defensive_contribution": 0}, "explain": []},
            {"id": 2, "stats": {"minutes": 90, "starts": 1, "goals_scored": 0, "assists": 0, "clean_sheets": 1,
                                "goals_conceded": 0, "saves": 0, "bonus": 0, "yellow_cards": 0, "red_cards": 0,
                                "total_points": 6, "expected_goals": "0.10", "expected_assists": "0.05",
                                "defensive_contribution": 10}, "explain": []},
            {"id": 3, "stats": {"minutes": 72 if g != 5 else 0, "starts": 1 if g != 5 else 0,
                                "goals_scored": 0, "assists": 0, "clean_sheets": 0, "goals_conceded": 0,
                                "saves": 0, "bonus": 0, "yellow_cards": 0, "red_cards": 0,
                                "total_points": 2 if g != 5 else 0, "expected_goals": "0.30", "expected_assists": "0.20",
                                "defensive_contribution": 4}, "explain": []},
            {"id": 4, "stats": {"minutes": 25 if g % 2 else 88, "starts": 0 if g % 2 else 1,
                                "goals_scored": 0, "assists": 0, "clean_sheets": 0, "goals_conceded": 1,
                                "saves": 0, "bonus": 0, "yellow_cards": 0, "red_cards": 0,
                                "total_points": 1 if g % 2 else 2, "expected_goals": "0.40", "expected_assists": "0.10",
                                "defensive_contribution": 2}, "explain": []},
        ]}
    ctx = fplmodel.prepare(boot, fixtures, live, status_log=status_log)
    ctx["congestion"] = set(congestion)
    return ctx


class ThreeBucketMinutesTest(unittest.TestCase):
    def test_invalid_minutes_model_raises(self):
        ctx = _make_ctx()
        with self.assertRaises(ValueError):
            fplmodel.project(ctx, 6, horizon=1, params={"minutes_model": "bogus", "xmins": False})

    def test_default_is_bit_for_bit_identical(self):
        ctx = _make_ctx()
        r_omit = fplmodel.project(ctx, 6, horizon=1, params={"xmins": False})
        r_def = fplmodel.project(ctx, 6, horizon=1, params={"minutes_model": "default", "xmins": False})
        self.assertEqual(r_omit["players"], r_def["players"])
        for p in r_def["players"].values():
            self.assertNotIn("p_play_next", p)
            self.assertNotIn("p90_next", p)

    def test_nested_probabilities_and_exact_xmin_and_parts(self):
        ctx = _make_ctx()
        res = fplmodel.project(ctx, 6, horizon=1, params={"minutes_model": "3bucket", "xmins": False})
        m_short, m_mid, m_full = fplmodel.THREE_BUCKET_MEANS
        for pid, r in res["players"].items():
            pp, p60, p90 = r["p_play_next"], r["p60_next"], r["p90_next"]
            self.assertGreaterEqual(p90, 0.0)
            self.assertLessEqual(p90, p60 + 1e-12)
            self.assertLessEqual(p60, pp + 1e-12)
            self.assertLessEqual(pp, 1.0 + 1e-12)
            # xMin is derived directly from (p_play, p_60, p_90)
            expected_xmin = (pp - p60) * m_short + (p60 - p90) * m_mid + p90 * m_full
            self.assertAlmostEqual(r["xmin"], expected_xmin, places=9)
            # Appearance points come straight from p_play and p_60
            self.assertAlmostEqual(r["detail"][6]["mins"], pp * 1.0 + p60 * 1.0, places=9)
            # Clean sheet eligibility comes straight from p_60
            tid = ctx["elements"][pid]["team"]
            pos = fplmodel.POS[ctx["elements"][pid]["element_type"]]
            mu_a = res["upcoming"][tid][6][0][3]
            pcs = math.exp(-fplmodel.DEFAULTS["cs_k"] * mu_a)
            cs_pts = ctx["scoring"]["clean_sheets"][pos]
            self.assertAlmostEqual(r["detail"][6]["cs"], pcs * p60 * cs_pts, places=9)

    def test_european_turnaround_cuts_outfield_but_keepers_barely_affected(self):
        ctx_no = _make_ctx(congestion=())
        ctx_eu = _make_ctx(congestion={(1, 6)})
        r_no = fplmodel.project(ctx_no, 6, horizon=1, params={"minutes_model": "3bucket", "xmins": False})["players"]
        r_eu = fplmodel.project(ctx_eu, 6, horizon=1, params={"minutes_model": "3bucket", "xmins": False})["players"]

        # Keeper (pid 1): barely affected (1% cut vs 7% for outfield)
        gkp_drop = 1.0 - r_eu[1]["p60_next"] / r_no[1]["p60_next"]
        def_drop = 1.0 - r_eu[2]["p60_next"] / r_no[2]["p60_next"]
        self.assertAlmostEqual(gkp_drop, 1.0 - fplmodel.THREE_BUCKET_GKP_EU_CUT, places=6)
        self.assertAlmostEqual(def_drop, 1.0 - fplmodel.DEFAULTS["eu_cut"], places=6)
        self.assertLess(gkp_drop, def_drop / 3)

    def test_pre_deadline_flags_and_return_ramp_no_hindsight(self):
        # Player 3 was flagged out at GW5 deadline (status_log), cleared for GW6 -> returning ramp applies at GW6
        slog = {"gws": {"5": {"3": ["i", 0]}}}
        ctx = _make_ctx(status_log=slog)
        ctx_plain = _make_ctx(status_log=None)
        r_ret = fplmodel.project(ctx, 6, horizon=1, params={"minutes_model": "3bucket", "xmins": False, "use_flags": False})["players"][3]
        r_pln = fplmodel.project(ctx_plain, 6, horizon=1, params={"minutes_model": "3bucket", "xmins": False, "use_flags": False})["players"][3]
        self.assertTrue(r_ret["returning"])
        self.assertFalse(r_pln["returning"])
        self.assertLess(r_ret["p60_next"], r_ret["p_play_next"])
        self.assertLessEqual(r_ret["p90_next"], r_ret["p60_next"])

        # Flag at GW6 deadline zeros GW6 projection (pre-deadline flag, no hindsight into GW5)
        slog6 = {"gws": {"6": {"2": ["i", 0]}}}
        ctx6 = _make_ctx(status_log=slog6)
        r6 = fplmodel.project(ctx6, 6, horizon=1, params={"minutes_model": "3bucket", "xmins": False, "use_flags": False})["players"][2]
        self.assertEqual(r6["p_play_next"], 0.0)
        self.assertEqual(r6["p60_next"], 0.0)
        self.assertEqual(r6["p90_next"], 0.0)
        self.assertEqual(r6["xmin"], 0.0)
        # Projecting GW5 must NOT see GW6's flag (no hindsight)
        r5_with = fplmodel.project(ctx6, 5, horizon=1, params={"minutes_model": "3bucket", "xmins": False, "use_flags": False})["players"][2]
        r5_none = fplmodel.project(ctx_plain, 5, horizon=1, params={"minutes_model": "3bucket", "xmins": False, "use_flags": False})["players"][2]
        self.assertEqual(r5_with["xmin"], r5_none["xmin"])


if __name__ == "__main__":
    unittest.main()
