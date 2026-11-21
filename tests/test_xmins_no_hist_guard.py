"""FL-175: guard xMins against all-NaN history_gws==0 inputs (which produced ~0.94 start chance)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fplmodel  # noqa: E402
import xmins  # noqa: E402


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


def _make_ctx():
    teams = [{"id": 1, "short_name": "ARS", "name": "Arsenal"},
             {"id": 2, "short_name": "BRE", "name": "Brentford"}]
    elements = [
        # pid 1: has 3 GWs of history (must be untouched by FL-175)
        {"id": 1, "element_type": 2, "team": 1, "web_name": "Regular", "status": "a",
         "chance_of_playing_next_round": None, "now_cost": 60, "penalties_order": None},
        # pid 2: zero history rows, has prior with start_rate 0.05 (unused backup)
        {"id": 2, "element_type": 2, "team": 1, "web_name": "BackupPrior", "status": "a",
         "chance_of_playing_next_round": None, "now_cost": 45, "penalties_order": None},
        # pid 3: zero history rows, no prior (cheap arrival -> ARRIVAL_START 0.07)
        {"id": 3, "element_type": 3, "team": 2, "web_name": "CheapArrival", "status": "a",
         "chance_of_playing_next_round": None, "now_cost": 45, "penalties_order": None},
    ]
    fixtures = [
        {"id": g, "event": g, "team_h": 1 if g % 2 else 2, "team_a": 2 if g % 2 else 1,
         "team_h_score": 1 if g < 4 else None, "team_a_score": 0 if g < 4 else None,
         "team_h_difficulty": 3, "team_a_difficulty": 3,
         "kickoff_time": f"2026-09-{g:02d}T14:00:00Z", "finished": g < 4}
        for g in range(1, 5)
    ]
    boot = {"elements": elements, "teams": teams, "game_config": {"scoring": _scoring()},
            "events": [{"id": g, "finished": g < 4, "deadline_time": f"2026-09-{g:02d}T11:30:00Z"} for g in range(1, 5)]}
    live = {
        g: {"elements": [
            {"id": 1, "stats": {"minutes": 90, "starts": 1, "goals_scored": 0, "assists": 0, "clean_sheets": 1,
                                "goals_conceded": 0, "saves": 0, "bonus": 0, "yellow_cards": 0, "red_cards": 0,
                                "total_points": 6, "expected_goals": "0.05", "expected_assists": "0.05",
                                "defensive_contribution": 10}, "explain": []},
        ]}
        for g in range(1, 4)
    }
    priors = {"players": {
        "2": {"season": "2025-26", "mins": 180, "start_rate": 0.05, "xg90": 0.02, "xa90": 0.02,
              "bonus90": 0.1, "saves90": 0.0, "dc90": 5.0, "dc_mins": 180, "yc90": 0.1, "pts90": 2.0},
    }}
    return fplmodel.prepare(boot, fixtures, live, priors=priors)


class XminsNoHistGuardTest(unittest.TestCase):
    def test_invalid_flag_raises(self):
        ctx = _make_ctx()
        with self.assertRaises(ValueError):
            fplmodel.project(ctx, 4, horizon=1, params={"xmins_no_hist_guard": 1})

    def test_no_history_players_use_prior_not_094_and_history_players_untouched(self):
        ctx = _make_ctx()
        r_old = fplmodel.project(ctx, 4, horizon=1, params={"xmins_no_hist_guard": False})["players"]
        r_new = fplmodel.project(ctx, 4, horizon=1, params={"xmins_no_hist_guard": True})["players"]

        # Bug reproduction with guard off: BackupPrior got >0.90 start chance from all-NaN xMins
        self.assertGreater(r_old[2]["p_start"], 0.90)
        # With guard on: BackupPrior gets last season's start_rate (0.05), p_sub 0.0
        self.assertAlmostEqual(r_new[2]["p_start"], 0.05, places=6)
        self.assertEqual(r_new[2]["p_sub"], 0.0)
        self.assertEqual(r_new[2]["min_src"], "counts")

        # Cheap arrival with no prior gets FL-030 ARRIVAL_START (0.07) and p_sub 0.0 (not 0.54+ all-NaN cameo)
        self.assertAlmostEqual(r_new[3]["p_start"], 0.07, places=6)
        self.assertEqual(r_new[3]["p_sub"], 0.0)

        # Player WITH history (pid 1) is bit-for-bit identical
        self.assertEqual(r_old[1], r_new[1])

    def test_xmins_features_require_history_skips_zero_rows(self):
        ctx = _make_ctx()
        up = {1: {4: [(2, True, 1.5, 1.0, 3)]}, 2: {4: [(1, False, 1.0, 1.5, 3)]}}
        tg = {1: {1, 2, 3, 4}, 2: {1, 2, 3, 4}}
        fv_all = xmins.features(ctx, 4, tg, {}, up, require_history=False)
        fv_req = xmins.features(ctx, 4, tg, {}, up, require_history=True)
        self.assertEqual(sorted(fv_all), [1, 2, 3])
        self.assertEqual(sorted(fv_req), [1])


if __name__ == "__main__":
    unittest.main()
