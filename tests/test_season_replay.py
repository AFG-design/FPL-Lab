"""FL-230 unit tests: no-lookahead projections, no-real-points chip selection, chip windows & FPL rule audit."""
import copy
import unittest

import optimise
import strategy_replay as sr
import fplmodel
from fplmodel import project


def _synthetic_ctx():
    """Minimal self-contained fplmodel context built via fplmodel.build_context()."""
    boot = {
        "elements": [
            {"id": 1, "element_type": 1, "team": 1, "web_name": "GK1", "now_cost": 50, "status": "a", "news": ""},
            {"id": 2, "element_type": 2, "team": 1, "web_name": "DEF1", "now_cost": 55, "status": "a", "news": ""},
            {"id": 3, "element_type": 3, "team": 2, "web_name": "MID1", "now_cost": 80, "status": "a", "news": ""},
            {"id": 4, "element_type": 4, "team": 2, "web_name": "FWD1", "now_cost": 90, "status": "a", "news": ""},
        ],
        "teams": [
            {"id": 1, "short_name": "AAA", "strength_attack_home": 1150, "strength_attack_away": 1100,
             "strength_defence_home": 1150, "strength_defence_away": 1100},
            {"id": 2, "short_name": "BBB", "strength_attack_home": 1200, "strength_attack_away": 1150,
             "strength_defence_home": 1100, "strength_defence_away": 1050},
        ],
        "events": [{"id": g, "deadline_time": f"2025-08-{g:02d}T10:00:00Z", "finished": g <= 6} for g in range(1, 11)],
        "game_config": {
            "scoring": {
                "goals_scored": {"GKP": 10, "DEF": 6, "MID": 5, "FWD": 4}, "assists": 3,
                "clean_sheets": {"GKP": 4, "DEF": 4, "MID": 1, "FWD": 0}, "saves": 1,
                "goals_conceded": {"GKP": -1, "DEF": -1, "MID": 0, "FWD": 0},
                "yellow_cards": -1, "red_cards": -3, "penalties_missed": -2, "own_goals": -2,
                "short_play": 1, "long_play": 2, "clearances_blocks_interceptions": 0,
                "defensive_contribution": {"GKP": 0, "DEF": 2, "MID": 2, "FWD": 2},
            }
        },
    }
    fixtures = []
    live = {}
    for g in range(1, 11):
        h, a = (1, 2) if g % 2 else (2, 1)
        fixtures.append({
            "id": g, "event": g, "team_h": h, "team_a": a,
            "team_h_difficulty": 3, "team_a_difficulty": 3,
            "finished": g <= 6, "team_h_score": 2 if g <= 6 else None, "team_a_score": 1 if g <= 6 else None,
        })
        if g <= 6:
            live[g] = {
                "elements": [
                    {
                        "id": pid,
                        "stats": {
                            "minutes": 90, "goals_scored": 1 if pid >= 3 and g % 2 else 0,
                            "assists": 1 if pid == 3 else 0, "clean_sheets": 1 if pid <= 2 and g % 2 else 0,
                            "goals_conceded": 1, "saves": 3 if pid == 1 else 0, "bonus": 1,
                            "expected_goals": "0.4" if pid >= 3 else "0.05",
                            "expected_assists": "0.25" if pid == 3 else "0.05",
                            "expected_goals_conceded": "1.0",
                            "starts": 1, "defensive_contribution": 12 if pid == 2 else 4,
                            "total_points": 6 if pid >= 3 else 5,
                            "yellow_cards": 0, "red_cards": 0, "penalties_missed": 0, "own_goals": 0,
                        },
                        "explain": [{"fixture": g, "stats": [{"identifier": "minutes", "points": 2, "value": 90}]}],
                    }
                    for pid in (1, 2, 3, 4)
                ]
            }
    priors = {
        "players": {
            str(pid): {"xg90": 0.35 if pid >= 3 else 0.05, "xa90": 0.2, "mins": 2500, "starts": 30,
                       "bonus90": 0.4, "saves90": 3.0 if pid == 1 else 0.0, "yc90": 0.1,
                       "dc90": 10.0 if pid == 2 else 4.0}
            for pid in (1, 2, 3, 4)
        }
    }
    return fplmodel.prepare(boot, fixtures, live, priors=priors)


def _dummy_players(gws):
    """Minimal 18-player pool (valid 15-man squad + 3 spares) for chip & audit tests."""
    pl = {}
    spec = [("GKP", 2, 4.5), ("DEF", 6, 5.0), ("MID", 6, 7.0), ("FWD", 4, 7.5)]
    pid = 1
    for pos, cnt, price in spec:
        for j in range(cnt):
            pl[pid] = {
                "pos": pos, "team": (pid % 10) + 1, "price": price,
                "xp": {g: (8.0 if pid == 15 else 4.5) for g in gws},
                "ok": True, "p10": {g: 0.1 for g in gws}, "nailed": 95, "name": f"P{pid}",
            }
            pid += 1
    # 15-man squad: 2 GKP (1,2), 5 DEF (3..7), 5 MID (9..13), 3 FWD (15..17)
    squad = [1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 15, 16, 17]
    return pl, squad


class TestNoLookahead(unittest.TestCase):
    def test_projections_ignore_gw_k_and_later(self):
        """Mutating all stats, real points, and match scores for g >= k must not change GW k projections."""
        base = _synthetic_ctx()
        mut = copy.deepcopy(base)
        for k in (1, 3, 5):
            # Heavily corrupt every result, stat, and point for g >= k
            for pid in mut["elements"]:
                for g in range(k, 11):
                    mut["pts_gw"][pid][g] = 999
                    mut["pstats"][pid][g] = {
                        "minutes": 90, "goals_scored": 9, "assists": 9, "clean_sheets": 1,
                        "goals_conceded": 0, "saves": 20, "bonus": 3,
                        "expected_goals": 9.9, "expected_assists": 9.9, "expected_goals_conceded": 0.0,
                        "starts": 1, "defensive_contribution": 50,
                    }
            for f in mut["fixtures"]:
                if f["event"] >= k:
                    f["team_h_score"] = 9
                    f["team_a_score"] = 0
            r1 = project(base, k, 5, {"use_flags": False, "sim": 0})["players"]
            r2 = project(mut, k, 5, {"use_flags": False, "sim": 0})["players"]
            for pid in base["elements"]:
                self.assertEqual(r1[pid]["xp"], r2[pid]["xp"],
                                 f"GW{k} projection for player {pid} leaked data from GW >= {k}")
            # Reset mut for next k
            mut = copy.deepcopy(base)

    def test_chip_selection_never_reads_real_points(self):
        """Both simple and solver chip selectors take only projections & fixture calendar (no pts/mins)."""
        gws = [24, 25, 26, 27, 28]
        pl, squad = _dummy_players(gws)
        # Put a strong captain in GW24 so TC triggers on DGW24
        pl[15]["xp"][24] = 14.5
        sell = {i: pl[i]["price"] for i in squad}
        base_plan = optimise.solve(pl, squad, sell, 1.0, 2, gws, max_hits=0, time_limit=15)
        self.assertIsNotNone(base_plan)

        dgw = {g: (4 if g == 33 else (2 if g == 24 else 0)) for g in range(1, 39)}
        bgw = {g: (4 if g == 29 else 0) for g in range(1, 39)}
        avail = sr.season_chips("2024-25")
        sched = sr.simple_chip_schedule("2024-25", dgw, bgw)

        # Simple rule: BB on GW33 (4 DGW teams), TC on GW24 (2 DGW teams), FH on GW29 (4 BGW teams)
        self.assertEqual(sched["BB"], 33)
        self.assertEqual(sched["TC"], 24)
        self.assertEqual(sched["FH"], 29)

        c_simple, _ = sr.choose_chip("simple", 24, pl, gws, squad, sell, 1.0, 2, base_plan, avail, dgw, bgw, sched)
        self.assertEqual(c_simple, "TC")

        c_solver, _ = sr.choose_chip("solver", 24, pl, gws, squad, sell, 1.0, 2, base_plan, avail, dgw, bgw, sched)
        self.assertEqual(c_solver, "TC")


class TestChipRulesAndAudit(unittest.TestCase):
    def test_season_chip_pools(self):
        c24 = sr.season_chips("2024-25")
        self.assertEqual(set(c24), {"WC1", "WC2", "FH", "BB", "TC"})
        self.assertEqual(c24["WC1"], (1, 19))
        self.assertEqual(c24["WC2"], (20, 38))

        c25 = sr.season_chips("2025-26")
        self.assertEqual(len(c25), 8)
        for k in ("WC1", "FH1", "BB1", "TC1"):
            self.assertEqual(c25[k], (1, 19))
        for k in ("WC2", "FH2", "BB2", "TC2"):
            self.assertEqual(c25[k], (20, 38))

    def test_audit_week_enforces_fpl_and_chip_rules(self):
        gws = [20]
        pl, squad = _dummy_players(gws)
        xi = [1, 3, 4, 5, 6, 9, 10, 11, 12, 15, 16]
        bench = [2, 7, 13, 17]
        pool = sr.season_chips("2025-26")

        # Legal week -> 0 violations
        errs = sr.audit_week(20, squad, 0.5, 3, xi, bench, 15, pl, 1, "WC2", pool, set(), 0, False, {})
        self.assertEqual(errs, [])

        # First-half chip used in GW20 -> violation
        errs = sr.audit_week(20, squad, 0.5, 3, xi, bench, 15, pl, 1, "WC1", pool, set(), 0, False, {})
        self.assertTrue(any("outside window" in e for e in errs))

        # FT > 5 -> violation
        errs = sr.audit_week(20, squad, 0.5, 6, xi, bench, 15, pl, 0, None, pool, set(), 0, False, {})
        self.assertTrue(any("ft 6" in e for e in errs))

        # Unexpected hit on Balanced -> violation
        errs = sr.audit_week(20, squad, 0.5, 1, xi, bench, 15, pl, 2, None, pool, set(), 1, False, {})
        self.assertTrue(any("unexpected hit" in e for e in errs))

        # Negative bank -> violation
        errs = sr.audit_week(20, squad, -0.2, 2, xi, bench, 15, pl, 1, None, pool, set(), 0, False, {})
        self.assertTrue(any("negative bank" in e for e in errs))

    def test_switch_mode_preregistered(self):
        self.assertEqual(sr.switch_mode(1, -50, 0), "balanced")
        self.assertEqual(sr.switch_mode(10, 200, 0), "balanced")
        self.assertEqual(sr.switch_mode(15, 520, 400), "safe")
        self.assertEqual(sr.switch_mode(15, 430, 400), "chase")
        self.assertEqual(sr.switch_mode(15, 480, 400), "balanced")
        self.assertEqual(sr.switch_mode(30, 1080, 1000), "chase")

    def test_real_avg_field_ignores_gw_k_and_later(self):
        """Real-average field for GW k must read only completed GWs < k (zero lookahead into GW k or later)."""
        boot_base = {
            "events": [
                {"id": g, "finished": g <= 14, "average_entry_score": 50 + g if g <= 14 else 0}
                for g in range(1, 21)
            ]
        }
        boot_mut = copy.deepcopy(boot_base)
        # Mutate GW 12 and all later GWs to extreme values
        for ev in boot_mut["events"]:
            if ev["id"] >= 12:
                ev["finished"] = True
                ev["average_entry_score"] = 9999
        avgs_base = sr.real_avg_table(boot_base)
        avgs_mut = sr.real_avg_table(boot_mut)
        # Unfinished events (GW15-20) are excluded from boot_base
        self.assertNotIn(15, avgs_base)
        # For every k <= 12, causal_field_sum reads strictly g < k, so mutating g >= 12 changes nothing
        for k in (1, 5, 11, 12):
            self.assertEqual(
                sr.causal_field_sum(avgs_base, k),
                sr.causal_field_sum(avgs_mut, k),
                f"real-avg field at GW{k} leaked data from GW >= {k}",
            )
            self.assertEqual(
                sr.switch_mode(k, 650, sr.causal_field_sum(avgs_base, k)),
                sr.switch_mode(k, 650, sr.causal_field_sum(avgs_mut, k)),
            )


if __name__ == "__main__":
    unittest.main()
