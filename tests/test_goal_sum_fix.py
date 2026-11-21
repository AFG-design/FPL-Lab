"""FL-237: opt-in --goal-sum-fix team goal/assist share reallocation in fplmodel.py."""
from collections import defaultdict
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


def _make_ctx(double_gw6=False):
    teams = [{"id": 1, "short_name": "ARS", "name": "Arsenal"},
             {"id": 2, "short_name": "BRE", "name": "Brentford"},
             {"id": 3, "short_name": "CHE", "name": "Chelsea"}]
    elements = [
        {"id": 1, "element_type": 1, "team": 1, "web_name": "GK1", "status": "a", "chance_of_playing_next_round": None, "now_cost": 55, "penalties_order": None},
        {"id": 2, "element_type": 2, "team": 1, "web_name": "DEF1", "status": "a", "chance_of_playing_next_round": None, "now_cost": 60, "penalties_order": None},
        {"id": 3, "element_type": 3, "team": 1, "web_name": "MID1", "status": "a", "chance_of_playing_next_round": None, "now_cost": 90, "penalties_order": 1},
        {"id": 4, "element_type": 4, "team": 1, "web_name": "FWD1", "status": "a", "chance_of_playing_next_round": None, "now_cost": 85, "penalties_order": None},
        {"id": 5, "element_type": 3, "team": 2, "web_name": "MID2", "status": "a", "chance_of_playing_next_round": None, "now_cost": 70, "penalties_order": None},
        {"id": 6, "element_type": 4, "team": 2, "web_name": "FWD2", "status": "a", "chance_of_playing_next_round": None, "now_cost": 75, "penalties_order": None},
        {"id": 7, "element_type": 3, "team": 3, "web_name": "MID3", "status": "a", "chance_of_playing_next_round": None, "now_cost": 80, "penalties_order": None},
    ]
    fixtures = []
    fid = 1
    for g in range(1, 7):
        fixtures.append({
            "id": fid, "event": g, "team_h": 1 if g % 2 else 2, "team_a": 2 if g % 2 else 1,
            "team_h_score": 2 if g < 6 else None, "team_a_score": 1 if g < 6 else None,
            "team_h_difficulty": 3, "team_a_difficulty": 3,
            "kickoff_time": f"2026-09-{g:02d}T14:00:00Z", "finished": g < 6,
        })
        fid += 1
    if double_gw6:
        fixtures.append({
            "id": fid, "event": 6, "team_h": 1, "team_a": 3,
            "team_h_score": None, "team_a_score": None,
            "team_h_difficulty": 3, "team_a_difficulty": 3,
            "kickoff_time": "2026-09-09T19:45:00Z", "finished": False,
        })
    boot = {"elements": elements, "teams": teams,
            "game_config": {"scoring": _scoring()},
            "events": [{"id": g, "finished": g < 6, "deadline_time": f"2026-09-{g:02d}T11:30:00Z"} for g in range(1, 7)]}
    live = {}
    for g in range(1, 6):
        live[g] = {"elements": [
            {"id": 1, "stats": {"minutes": 90, "starts": 1, "goals_scored": 0, "assists": 0, "clean_sheets": 0, "goals_conceded": 1, "saves": 3, "bonus": 0, "yellow_cards": 0, "red_cards": 0, "total_points": 3, "expected_goals": "0.00", "expected_assists": "0.00", "defensive_contribution": 0}, "explain": []},
            {"id": 2, "stats": {"minutes": 90, "starts": 1, "goals_scored": 0, "assists": 0, "clean_sheets": 0, "goals_conceded": 1, "saves": 0, "bonus": 0, "yellow_cards": 0, "red_cards": 0, "total_points": 2, "expected_goals": "0.08", "expected_assists": "0.05", "defensive_contribution": 10}, "explain": []},
            {"id": 3, "stats": {"minutes": 85, "starts": 1, "goals_scored": 1, "assists": 1, "clean_sheets": 0, "goals_conceded": 1, "saves": 0, "bonus": 3, "yellow_cards": 0, "red_cards": 0, "total_points": 13, "expected_goals": "0.55", "expected_assists": "0.40", "defensive_contribution": 4}, "explain": []},
            {"id": 4, "stats": {"minutes": 80, "starts": 1, "goals_scored": 1, "assists": 0, "clean_sheets": 0, "goals_conceded": 1, "saves": 0, "bonus": 1, "yellow_cards": 0, "red_cards": 0, "total_points": 7, "expected_goals": "0.60", "expected_assists": "0.15", "defensive_contribution": 2}, "explain": []},
            {"id": 5, "stats": {"minutes": 90, "starts": 1, "goals_scored": 0, "assists": 1, "clean_sheets": 0, "goals_conceded": 2, "saves": 0, "bonus": 0, "yellow_cards": 0, "red_cards": 0, "total_points": 5, "expected_goals": "0.25", "expected_assists": "0.35", "defensive_contribution": 5}, "explain": []},
            {"id": 6, "stats": {"minutes": 90, "starts": 1, "goals_scored": 1, "assists": 0, "clean_sheets": 0, "goals_conceded": 2, "saves": 0, "bonus": 2, "yellow_cards": 0, "red_cards": 0, "total_points": 8, "expected_goals": "0.50", "expected_assists": "0.10", "defensive_contribution": 2}, "explain": []},
            {"id": 7, "stats": {"minutes": 90, "starts": 1, "goals_scored": 0, "assists": 0, "clean_sheets": 0, "goals_conceded": 0, "saves": 0, "bonus": 0, "yellow_cards": 0, "red_cards": 0, "total_points": 2, "expected_goals": "0.30", "expected_assists": "0.20", "defensive_contribution": 4}, "explain": []},
        ]}
    return fplmodel.prepare(boot, fixtures, live)


class GoalSumFixTest(unittest.TestCase):
    def test_invalid_goal_sum_fix_raises(self):
        ctx = _make_ctx()
        with self.assertRaises(ValueError):
            fplmodel.project(ctx, 6, horizon=1, params={"goal_sum_fix": 1, "xmins": False})

    def test_default_is_bit_for_bit_identical(self):
        ctx = _make_ctx()
        r_omit = fplmodel.project(ctx, 6, horizon=1, params={"xmins": False})
        r_off = fplmodel.project(ctx, 6, horizon=1, params={"goal_sum_fix": False, "xmins": False})
        self.assertEqual(r_omit["players"], r_off["players"])

    def test_player_totals_add_up_to_team_total_within_1pct_every_fixture(self):
        """Player expected goals (and assists) must match team totals within 1% for every team-GW, incl. doubles."""
        for double in (False, True):
            ctx = _make_ctx(double_gw6=double)
            proj = fplmodel.project(ctx, 6, horizon=1, params={"goal_sum_fix": True, "xmins": False})
            res, up = proj["players"], proj["upcoming"]
            sc = ctx["scoring"]
            team_mu = {tid: sum(mf for _o, _h, mf, _ma, _f in up[tid].get(6, ())) for tid in up if up[tid].get(6)}
            team_eg = defaultdict(float)
            team_ea = defaultdict(float)
            for pid, r in res.items():
                e = ctx["elements"][pid]
                pos = fplmodel.POS[e["element_type"]]
                d = r["detail"].get(6, {})
                team_eg[e["team"]] += d.get("goals", 0.0) / sc["goals_scored"][pos]
                team_ea[e["team"]] += d.get("assists", 0.0) / sc["assists"]
            for tid, mu in team_mu.items():
                self.assertGreater(mu, 0.0)
                rel_g = abs(team_eg[tid] - mu) / mu
                target_a = fplmodel.GOAL_SUM_ASSIST_RATIO * mu
                rel_a = abs(team_ea[tid] - target_a) / target_a
                self.assertLess(rel_g, 0.01, f"team {tid} goals off by {rel_g:.4%}")
                self.assertLess(rel_a, 0.01, f"team {tid} assists off by {rel_a:.4%}")

    def test_ignores_set_piece_data(self):
        """Goal-sum reallocation must not depend on Understat set-piece data."""
        ctx1 = _make_ctx()
        ctx2 = _make_ctx()
        ctx2["sp"] = {"player": {3: {1: 0.4, 2: 0.4}}, "against": {2: {1: 1.5, 2: 1.5}}}
        r1 = fplmodel.project(ctx1, 6, horizon=1, params={"goal_sum_fix": True, "xmins": False, "sp_match": 0.5})["players"]
        r2 = fplmodel.project(ctx2, 6, horizon=1, params={"goal_sum_fix": True, "xmins": False, "sp_match": 0.5})["players"]
        self.assertEqual(r1[3]["detail"][6]["goals"], r2[3]["detail"][6]["goals"])
        self.assertEqual(r1[3]["xp"][6], r2[3]["xp"][6])

    def test_zero_squad_weight_returns_zero_cleanly(self):
        ctx = _make_ctx()
        for e in ctx["elements"].values():
            if e["team"] == 2:
                e["status"] = "i"
                e["chance_of_playing_next_round"] = 0
        proj = fplmodel.project(ctx, 6, horizon=1, params={"goal_sum_fix": True, "xmins": False, "use_flags": True})
        for pid in (5, 6):
            self.assertEqual(proj["players"][pid]["detail"][6]["goals"], 0.0)
            self.assertEqual(proj["players"][pid]["detail"][6]["assists"], 0.0)


if __name__ == "__main__":
    unittest.main()
