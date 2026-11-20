"""FL-160: unit tests for def_bonus_mult (validation, DEF/GKP-only scaling in all 3 places, 1.0 identity)."""
import math
import unittest

import fplmodel


def _mini_ctx():
    elements = {
        1: {"id": 1, "web_name": "GK1", "element_type": 1, "team": 1, "now_cost": 50, "status": "a", "news": "", "chance_of_playing_next_round": 100},
        2: {"id": 2, "web_name": "DF1", "element_type": 2, "team": 1, "now_cost": 55, "status": "a", "news": "", "chance_of_playing_next_round": 100},
        3: {"id": 3, "web_name": "MD1", "element_type": 3, "team": 1, "now_cost": 70, "status": "a", "news": "", "chance_of_playing_next_round": 100},
        4: {"id": 4, "web_name": "FW1", "element_type": 4, "team": 1, "now_cost": 80, "status": "a", "news": "", "chance_of_playing_next_round": 100},
    }
    teams = {
        1: {"id": 1, "name": "TeamA", "short_name": "TMA", "strength_attack_home": 1200, "strength_attack_away": 1200, "strength_defence_home": 1200, "strength_defence_away": 1200},
        2: {"id": 2, "name": "TeamB", "short_name": "TMB", "strength_attack_home": 1200, "strength_attack_away": 1200, "strength_defence_home": 1200, "strength_defence_away": 1200},
    }
    pstats = {}
    for pid in elements:
        pstats[pid] = {
            g: {
                "minutes": 90, "starts": 1, "expected_goals": "0.15", "expected_assists": "0.15",
                "bonus": 1, "saves": 3 if pid == 1 else 0, "yellow_cards": 0, "defensive_contribution": 8,
            }
            for g in (1, 2, 3)
        }
    fix_list = [
        {"id": 1, "event": 1, "team_h": 1, "team_a": 2, "team_h_score": 1, "team_a_score": 0, "finished": True, "team_h_difficulty": 3, "team_a_difficulty": 3},
        {"id": 2, "event": 2, "team_h": 2, "team_a": 1, "team_h_score": 1, "team_a_score": 1, "finished": True, "team_h_difficulty": 3, "team_a_difficulty": 3},
        {"id": 3, "event": 3, "team_h": 1, "team_a": 2, "team_h_score": 2, "team_a_score": 1, "finished": True, "team_h_difficulty": 3, "team_a_difficulty": 3},
        {"id": 4, "event": 4, "team_h": 1, "team_a": 2, "team_h_score": None, "team_a_score": None, "finished": False, "team_h_difficulty": 3, "team_a_difficulty": 3},
    ]
    team_fix = {
        1: [(1, 2, True, fix_list[0]), (2, 2, False, fix_list[1]), (3, 2, True, fix_list[2]), (4, 2, True, fix_list[3])],
        2: [(1, 1, False, fix_list[0]), (2, 1, True, fix_list[1]), (3, 1, False, fix_list[2]), (4, 1, False, fix_list[3])],
    }
    return {
        "elements": elements,
        "teams": teams,
        "pstats": pstats,
        "pts_gw": {pid: {1: 6, 2: 4, 3: 5} for pid in elements},
        "dc_hit": {pid: {1: False, 2: False, 3: False} for pid in elements},
        "team_fix": team_fix,
        "team_gw_xg": {1: {1: 1.2, 2: 1.0, 3: 1.5}, 2: {1: 0.8, 2: 1.0, 3: 1.1}},
        "pending_team_gws": set(),
        "team_gws": {1: {1, 2, 3}, 2: {1, 2, 3}},
        "opp_of": {1: {1: 2, 2: 2, 3: 2}, 2: {1: 1, 2: 1, 3: 1}},
        "fixtures": fix_list,
        "scoring": {
            "short_play": 1, "long_play": 2,
            "goals_scored": {"GKP": 10, "DEF": 6, "MID": 5, "FWD": 4},
            "assists": 3,
            "clean_sheets": {"GKP": 4, "DEF": 4, "MID": 1, "FWD": 0},
            "goals_conceded": {"GKP": -1, "DEF": -1, "MID": 0, "FWD": 0},
            "saves": 1,
            "defensive_contribution": {"GKP": 0, "DEF": 2, "MID": 2, "FWD": 2},
        },
        "priors": {},
        "out": {},
        "moved": {},
        "market": [],
        "market_fx": {},
        "congestion": {},
        "sp": None,
        "news": {},
        "dc_thr": {"DEF": 10, "MID": 12, "FWD": 12},
    }


class TestDefBonusMult(unittest.TestCase):
    def test_default_is_one(self):
        self.assertEqual(fplmodel.DEFAULTS["def_bonus_mult"], 1.0)

    def test_invalid_values_raise(self):
        ctx = _mini_ctx()
        for bad in (0, 0.0, -1.0, None, True, False, "1.2", float("nan"), float("inf")):
            with self.assertRaises(ValueError, msg=f"expected ValueError for {bad!r}"):
                fplmodel.project(ctx, 4, 1, {"def_bonus_mult": bad})

    def test_scales_def_and_gkp_only_in_all_three_places(self):
        ctx = _mini_ctx()
        r1 = fplmodel.project(ctx, 4, 1, {"def_bonus_mult": 1.0, "fx_out": True, "sim": 200})["players"]
        r2 = fplmodel.project(ctx, 4, 1, {"def_bonus_mult": 1.2, "fx_out": True, "sim": 200})["players"]
        for pid in (1, 2):  # GKP, DEF
            b1 = r1[pid]["detail"][4]["bonus"]
            b2 = r2[pid]["detail"][4]["bonus"]
            self.assertGreater(b1, 0)
            self.assertAlmostEqual(b2 / b1, 1.2, places=9)
            fx1 = r1[pid]["fx"][4][0]["args"][12]
            fx2 = r2[pid]["fx"][4][0]["args"][12]
            self.assertAlmostEqual(fx2 / fx1, 1.2, places=9)
            self.assertGreater(r2[pid]["xp"][4], r1[pid]["xp"][4])
        for pid in (3, 4):  # MID, FWD untouched
            self.assertEqual(r1[pid]["detail"][4]["bonus"], r2[pid]["detail"][4]["bonus"])
            self.assertEqual(r1[pid]["fx"][4][0]["args"][12], r2[pid]["fx"][4][0]["args"][12])
            self.assertEqual(r1[pid]["xp"][4], r2[pid]["xp"][4])


if __name__ == "__main__":
    unittest.main()
