"""FL-175: guard xMins against all-NaN history_gws==0 inputs (which produced ~0.94 start chance)."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fplmodel  # noqa: E402
import validate  # noqa: E402
import xmins  # noqa: E402
from build_harness import TEAM_ID, offline_build  # noqa: E402


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
        # pid 4: has 3 history rows, all excluded as out-weeks (wsum == 0, prior start_rate 0.6)
        {"id": 4, "element_type": 3, "team": 2, "web_name": "AllOutHistory", "status": "a",
         "chance_of_playing_next_round": None, "now_cost": 65, "penalties_order": None},
    ]
    fixtures = [
        {"id": g, "event": g, "team_h": 1 if g % 2 else 2, "team_a": 2 if g % 2 else 1,
         "team_h_score": 1 if g < 4 else None, "team_a_score": 0 if g < 4 else None,
         "team_h_difficulty": 3, "team_a_difficulty": 3,
         "kickoff_time": f"2026-09-{1 + (g - 1) * 7:02d}T14:00:00Z", "finished": g < 4}
        for g in range(1, 5)
    ]
    boot = {"elements": elements, "teams": teams, "game_config": {"scoring": _scoring()},
            "events": [{"id": g, "finished": g < 4, "deadline_time": f"2026-09-{1 + (g - 1) * 7:02d}T11:30:00Z"} for g in range(1, 5)]}
    live = {
        g: {"elements": [
            {"id": 1, "stats": {"minutes": 90, "starts": 1, "goals_scored": 0, "assists": 0, "clean_sheets": 1,
                                "goals_conceded": 0, "saves": 0, "bonus": 0, "yellow_cards": 0, "red_cards": 0,
                                "total_points": 6, "expected_goals": "0.05", "expected_assists": "0.05",
                                "defensive_contribution": 10}, "explain": []},
            {"id": 4, "stats": {"minutes": 0, "starts": 0, "goals_scored": 0, "assists": 0, "clean_sheets": 0,
                                "goals_conceded": 0, "saves": 0, "bonus": 0, "yellow_cards": 0, "red_cards": 0,
                                "total_points": 0, "expected_goals": "0.00", "expected_assists": "0.00",
                                "defensive_contribution": 0}, "explain": []},
        ]}
        for g in range(1, 4)
    }
    priors = {"players": {
        "2": {"season": "2025-26", "mins": 180, "start_rate": 0.05, "xg90": 0.02, "xa90": 0.02,
              "bonus90": 0.1, "saves90": 0.0, "dc90": 5.0, "dc_mins": 180, "yc90": 0.1, "pts90": 2.0},
        "4": {"season": "2025-26", "mins": 2100, "start_rate": 0.60, "xg90": 0.25, "xa90": 0.20,
              "bonus90": 0.4, "saves90": 0.0, "dc90": 4.0, "dc_mins": 2100, "yc90": 0.1, "pts90": 4.5},
    }}
    ctx = fplmodel.prepare(boot, fixtures, live, priors=priors)
    ctx["out"] = {4: {1, 2, 3}}   # all 3 of pid 4's history GWs excluded as out-weeks -> wsum == 0
    return ctx


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
        # With guard on: BackupPrior gets last season's start_rate (0.05), p_sub 0.0, min_src "no_history"
        self.assertAlmostEqual(r_new[2]["p_start"], 0.05, places=6)
        self.assertEqual(r_new[2]["p_sub"], 0.0)
        self.assertEqual(r_new[2]["min_src"], "no_history")

        # Cheap arrival with no prior gets FL-030 ARRIVAL_START (0.07), p_sub 0.0, min_src "no_history"
        self.assertAlmostEqual(r_new[3]["p_start"], 0.07, places=6)
        self.assertEqual(r_new[3]["p_sub"], 0.0)
        self.assertEqual(r_new[3]["min_src"], "no_history")

        # Players WITH history (pid 1 and pid 4) are bit-for-bit identical
        self.assertEqual(r_old[1], r_new[1])
        self.assertEqual(r_old[4], r_new[4])
        self.assertEqual(r_new[4]["min_src"], "xmins")

    def test_counts_only_and_excluded_history_players_untouched(self):
        """P2: counts-only (xmins=False) and players with history excluded as out-weeks must not be moved."""
        ctx = _make_ctx()
        c_off = fplmodel.project(ctx, 4, horizon=1, params={"xmins": False, "xmins_no_hist_guard": False})["players"]
        c_on = fplmodel.project(ctx, 4, horizon=1, params={"xmins": False, "xmins_no_hist_guard": True})["players"]
        self.assertEqual(c_off, c_on)
        # Specifically pid 4 (3 history rows all in out-weeks -> wsum == 0, prior 0.6) stays 0.0, not 0.6
        self.assertEqual(c_on[4]["p_start"], 0.0)
        self.assertEqual(c_on[4]["min_src"], "counts")

    def test_xmins_features_require_history_skips_zero_rows(self):
        ctx = _make_ctx()
        up = {1: {4: [(2, True, 1.5, 1.0, 3)]}, 2: {4: [(1, False, 1.0, 1.5, 3)]}}
        tg = {1: {1, 2, 3, 4}, 2: {1, 2, 3, 4}}
        skipped = set()
        fv_all = xmins.features(ctx, 4, tg, {}, up, require_history=False)
        fv_req = xmins.features(ctx, 4, tg, {}, up, require_history=True, skipped_no_hist=skipped)
        self.assertEqual(sorted(fv_all), [1, 2, 3, 4])
        self.assertEqual(sorted(fv_req), [1, 4])
        self.assertEqual(skipped, {2, 3})


class Gw1BuildAndValidateTest(unittest.TestCase):
    """P1: on GW1 (all players have zero history), build.py + validate.py must pass with min_src='no_history',
    while unexpected min_src='counts' fallbacks still fail validate.py."""

    @classmethod
    def setUpClass(cls):
        def prep(repo):
            (repo / "crowd" / "latest.json").unlink(missing_ok=True)
            (repo / "history" / "awards.json").unlink(missing_ok=True)

        def to_gw1(api):
            boot = api["/bootstrap-static/"]
            for e in boot["events"]:
                e["is_current"] = False
                e["is_next"] = (e["id"] == 1)
                e["finished"] = False
                e["data_checked"] = False
            for el in boot["elements"]:
                for k in ("minutes", "starts", "total_points", "goals_scored", "assists", "clean_sheets",
                          "goals_conceded", "saves", "bonus", "bps", "yellow_cards", "red_cards",
                          "defensive_contribution"):
                    if k in el:
                        el[k] = 0
                for k in ("expected_goals", "expected_assists", "expected_goal_involvements",
                          "expected_goals_conceded"):
                    if k in el:
                        el[k] = "0.00"
            for f in api["/fixtures/"]:
                f["finished"] = f["finished_provisional"] = f["started"] = False
                f["team_h_score"] = f["team_a_score"] = None
                f["stats"] = []
            api[f"/entry/{TEAM_ID}/"]["current_event"] = None
            api[f"/entry/{TEAM_ID}/history/"]["current"] = []
            api[f"/entry/{TEAM_ID}/history/"]["chips"] = []
            for k in list(api):
                if "/live/" in k or "/picks/" in k:
                    del api[k]

        cls.repo, cls.D, cls.rc, _ = offline_build(cls, prepare=prep, api_change=to_gw1)

    def test_gw1_passes_validation_with_no_history_source(self):
        mm = self.D["meta"]["minutes_model"]
        self.assertTrue(mm["xmins_on"])
        self.assertEqual(mm["xmins"], 0)
        self.assertEqual(mm["counts"], 0)
        self.assertGreater(mm["no_history"], 600)
        self.assertEqual(mm["no_history"], mm["fixture_players"])
        self.assertEqual(self.rc, 0, self.D["health"]["errors"])

    def test_unexpected_counts_fallback_still_fails_validation(self):
        # Simulate the old P1 bug (no_history players mislabelled as counts): validate.py must reject it
        bad = json.loads((self.repo / "site" / "data.json").read_text())
        mm = bad["meta"]["minutes_model"]
        mm["counts"], mm["no_history"] = mm["no_history"], 0
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.json"
            p.write_text(json.dumps(bad))
            rc = validate.main(str(p))
            out = json.loads(p.read_text())
        self.assertEqual(rc, 1)
        self.assertTrue(any("fell back to the old counts" in e for e in out["health"]["errors"]),
                        out["health"]["errors"])


if __name__ == "__main__":
    unittest.main()
