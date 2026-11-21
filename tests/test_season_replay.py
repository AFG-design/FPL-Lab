"""FL-230 unit tests: causal projections & chip calendars, consecutive FH ban, GW16 FT top-up, and full FPL rule audit."""
import copy
import unittest

import fplmodel
import optimise
import strategy_replay as sr


def _synthetic_raw(n_gws=10):
    """Build raw (boot, fixtures, live, priors, price) for an 18-player, 6-team league over n_gws weeks.
    18 players: 2 GKP, 6 DEF, 6 MID, 4 FWD — enough for a legal 15-man squad + 3 spares.
    """
    elements = []
    spec = [(1, 2, 45), (2, 6, 50), (3, 6, 70), (4, 4, 80)]  # (element_type, count, now_cost)
    pid = 1
    for etype, cnt, cost in spec:
        for _ in range(cnt):
            elements.append({
                "id": pid, "element_type": etype, "team": ((pid - 1) % 6) + 1,
                "web_name": f"P{pid}", "now_cost": cost, "status": "a", "news": "",
            })
            pid += 1
    teams = [
        {"id": tid, "short_name": f"T{tid:02d}",
         "strength_attack_home": 1150 + 10 * tid, "strength_attack_away": 1100 + 10 * tid,
         "strength_defence_home": 1150, "strength_defence_away": 1100}
        for tid in range(1, 7)
    ]
    boot = {
        "elements": elements,
        "teams": teams,
        "events": [
            {"id": g, "deadline_time": f"2025-08-{g:02d}T10:00:00Z", "finished": g <= 6}
            for g in range(1, n_gws + 1)
        ],
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
    fid = 1
    for g in range(1, n_gws + 1):
        pairs = [(1, 2), (3, 4), (5, 6)] if g % 2 else [(2, 1), (4, 3), (6, 5)]
        ko = f"2025-08-{g:02d}T14:00:00Z"
        for h, a in pairs:
            fixtures.append({
                "id": fid, "event": g, "team_h": h, "team_a": a, "kickoff_time": ko,
                "team_h_difficulty": 3, "team_a_difficulty": 3,
                "finished": g <= 6, "team_h_score": 2 if g <= 6 else None, "team_a_score": 1 if g <= 6 else None,
            })
            fid += 1
        if g <= 6:
            live[g] = {
                "elements": [
                    {
                        "id": e["id"],
                        "stats": {
                            "minutes": 90,
                            "goals_scored": 1 if e["element_type"] >= 3 and g % 2 else 0,
                            "assists": 1 if e["element_type"] == 3 else 0,
                            "clean_sheets": 1 if e["element_type"] <= 2 and g % 2 else 0,
                            "goals_conceded": 1, "saves": 3 if e["element_type"] == 1 else 0, "bonus": 1,
                            "expected_goals": "0.35" if e["element_type"] >= 3 else "0.05",
                            "expected_assists": "0.20" if e["element_type"] == 3 else "0.05",
                            "expected_goals_conceded": "1.0",
                            "starts": 1, "defensive_contribution": 12 if e["element_type"] == 2 else 4,
                            "total_points": 6 if e["element_type"] >= 3 else 5,
                            "yellow_cards": 0, "red_cards": 0, "penalties_missed": 0, "own_goals": 0,
                        },
                        "explain": [{"fixture": (g - 1) * 3 + 1, "stats": [{"identifier": "minutes", "points": 2, "value": 90}]}],
                    }
                    for e in elements
                ]
            }
    priors = {
        "players": {
            str(e["id"]): {
                "xg90": 0.35 if e["element_type"] >= 3 else 0.05, "xa90": 0.2, "mins": 2500, "starts": 30,
                "bonus90": 0.4, "saves90": 3.0 if e["element_type"] == 1 else 0.0, "yc90": 0.1,
                "dc90": 10.0 if e["element_type"] == 2 else 4.0,
            }
            for e in elements
        }
    }
    price = {g: {e["id"]: e["now_cost"] / 10 for e in elements} for g in range(1, n_gws + 1)}
    return boot, fixtures, live, priors, price


def _dummy_players(gws):
    """Minimal 18-player pool (valid 15-man squad + 3 spares) for chip & audit tests."""
    pl = {}
    spec = [("GKP", 2, 4.5), ("DEF", 6, 5.0), ("MID", 6, 7.0), ("FWD", 4, 7.5)]
    pid = 1
    for pos, cnt, price in spec:
        for _ in range(cnt):
            pl[pid] = {
                "pos": pos, "team": (pid % 10) + 1, "price": price,
                "xp": {g: (8.0 if pid == 15 else 4.5) for g in gws},
                "ok": True, "p10": {g: 0.1 for g in gws}, "nailed": 95, "name": f"P{pid}",
            }
            pid += 1
    # 15-man squad: 2 GKP (1,2), 5 DEF (3..7), 5 MID (9..13), 3 FWD (15..17)
    squad = [1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 15, 16, 17]
    return pl, squad


def _season_2425_fixtures(gw33_dgw_teams=4, gw34_bgw_teams=4):
    """Build a 20-team, 38-GW fixture list with real 2024-25 GW24/GW31/GW33/GW34 dates.
    GW24 has a 2-team DGW (confirmed 2025-01-13); GW33 has `gw33_dgw_teams` DGW (confirmed 2025-04-03);
    GW34 has `gw34_bgw_teams` BGW (confirmed 2025-04-03).
    """
    from datetime import datetime, timedelta, timezone

    # Realistic weekly anchor dates so GW24 is 2025-02-01, GW31 is 2025-04-05, GW33 is 2025-04-19
    anchors = {
        24: "2025-02-01T12:30:00Z",
        31: "2025-04-05T11:30:00Z",
        33: "2025-04-19T14:00:00Z",
        34: "2025-04-26T11:30:00Z",
    }
    base_dt = datetime(2024, 8, 17, 14, 0, tzinfo=timezone.utc)
    fixtures = []
    fid = 1
    for g in range(1, 39):
        ko = anchors.get(g, (base_dt + timedelta(days=7 * (g - 1))).strftime("%Y-%m-%dT%H:%M:%SZ"))
        pairs = [(2 * i + 1, 2 * i + 2) for i in range(10)]
        if g == 34 and gw34_bgw_teams > 0:
            pairs = pairs[gw34_bgw_teams // 2:]
        for h, a in pairs:
            fixtures.append({"id": fid, "event": g, "team_h": h, "team_a": a, "kickoff_time": ko})
            fid += 1
        if g == 24:
            # 2-team DGW (teams 1 and 2 play twice)
            fixtures.append({"id": fid, "event": g, "team_h": 2, "team_a": 1, "kickoff_time": ko})
            fid += 1
        if g == 33 and gw33_dgw_teams > 0:
            for i in range(gw33_dgw_teams // 2):
                fixtures.append({"id": fid, "event": g, "team_h": 2 * i + 2, "team_a": 2 * i + 1, "kickoff_time": ko})
                fid += 1
    return fixtures


class TestNoLookahead(unittest.TestCase):
    def test_replay_path_ignores_gw_k_and_later_before_prepare(self):
        """Mutating raw live stats (xG, minutes, points), match results, and unconfirmed future fixtures for
        g >= k BEFORE fplmodel.prepare() must leave every GW k projection and chip decision identical.
        """
        boot_b, fix_b, live_b, priors, price = _synthetic_raw(n_gws=10)
        team_at = lambda pid, g: next(e["team"] for e in boot_b["elements"] if e["id"] == pid)
        squad = [1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 15, 16, 17]
        avail = {"WC1": (1, 10), "FH": (1, 10), "BB": (1, 10), "TC": (1, 10)}

        for k in (1, 3, 5):
            ctx_base = fplmodel.prepare(boot_b, fix_b, live_b, priors=priors)
            pl1, gws1 = sr.make_projections(ctx_base, team_at, price, k, last=10, sim=0)
            sell1 = {i: pl1[i]["price"] for i in squad}
            base_plan1 = optimise.solve(pl1, squad, sell1, 2.0, 2, gws1, max_hits=0, time_limit=15)
            dgw1, bgw1 = sr.causal_fixture_calendar(fix_b, "synthetic", k, conf_dates={}, boot=boot_b, last_gw=10)
            chip_s1, _ = sr.choose_chip("simple", k, pl1, gws1, squad, sell1, 2.0, 2, base_plan1,
                                        avail, dgw1, bgw1, season="2024-25")
            chip_v1, _ = sr.choose_chip("solver", k, pl1, gws1, squad, sell1, 2.0, 2, base_plan1,
                                        avail, dgw1, bgw1, season="2024-25")

            # Mutate RAW inputs for g >= k BEFORE fplmodel.prepare()
            boot_m = copy.deepcopy(boot_b)
            fix_m = copy.deepcopy(fix_b)
            live_m = copy.deepcopy(live_b)
            for g in range(k, 11):
                live_m[g] = {
                    "elements": [
                        {
                            "id": e["id"],
                            "stats": {
                                "minutes": 90, "goals_scored": 9, "assists": 9, "clean_sheets": 1,
                                "goals_conceded": 0, "saves": 20, "bonus": 3,
                                "expected_goals": "9.90", "expected_assists": "9.90",
                                "expected_goals_conceded": "0.00",
                                "starts": 1, "defensive_contribution": 50, "total_points": 99,
                                "yellow_cards": 0, "red_cards": 0, "penalties_missed": 0, "own_goals": 0,
                            },
                            "explain": [{"fixture": (g - 1) * 3 + 1,
                                         "stats": [{"identifier": "minutes", "points": 2, "value": 90}]}],
                        }
                        for e in boot_m["elements"]
                    ]
                }
            for f in fix_m:
                if f["event"] >= k:
                    f["finished"] = True
                    f["team_h_score"] = 9
                    f["team_a_score"] = 0
            # Add an unconfirmed future double & blank in GW10 (outside the 5-GW window k..k+4)
            fix_m = [f for f in fix_m if not (f["event"] == 10 and f["team_h"] in (5, 6))]
            fix_m.append({
                "id": 999, "event": 10, "team_h": 1, "team_a": 2, "kickoff_time": "2025-08-10T14:00:00Z",
                "team_h_difficulty": 3, "team_a_difficulty": 3, "finished": True,
                "team_h_score": 9, "team_a_score": 0,
            })

            ctx_mut = fplmodel.prepare(boot_m, fix_m, live_m, priors=priors)
            # Confirm the pre-prepare mutation actually changed prepared stats for g >= k (not a no-op)
            self.assertNotEqual(ctx_base["team_gw_xg"][1].get(k, 0.0), ctx_mut["team_gw_xg"][1].get(k, 0.0))

            pl2, gws2 = sr.make_projections(ctx_mut, team_at, price, k, last=10, sim=0)
            self.assertEqual(gws1, gws2)
            for pid in pl1:
                self.assertEqual(pl1[pid]["xp"], pl2[pid]["xp"],
                                 f"GW{k} projection for player {pid} leaked data from GW >= {k}")
                self.assertEqual(pl1[pid]["nailed"], pl2[pid]["nailed"],
                                 f"GW{k} nailed for player {pid} leaked data from GW >= {k}")

            sell2 = {i: pl2[i]["price"] for i in squad}
            base_plan2 = optimise.solve(pl2, squad, sell2, 2.0, 2, gws2, max_hits=0, time_limit=15)
            dgw2, bgw2 = sr.causal_fixture_calendar(fix_m, "synthetic", k, conf_dates={}, boot=boot_m, last_gw=10)
            chip_s2, _ = sr.choose_chip("simple", k, pl2, gws2, squad, sell2, 2.0, 2, base_plan2,
                                        avail, dgw2, bgw2, season="2024-25")
            chip_v2, _ = sr.choose_chip("solver", k, pl2, gws2, squad, sell2, 2.0, 2, base_plan2,
                                        avail, dgw2, bgw2, season="2024-25")
            self.assertEqual(chip_s1, chip_s2, f"GW{k} simple chip decision leaked future data")
            self.assertEqual(chip_v1, chip_v2, f"GW{k} solver chip decision leaked future data")

    def test_causal_chip_calendar_ignores_unconfirmed_future_dgw_and_bgw(self):
        """Changing an unconfirmed future double/blank (GW33/GW34 in 2024-25, confirmed 3 Apr before GW31)
        must NOT change GW24 chip decisions for either simple or solver.
        """
        gws = [24, 25, 26, 27, 28]
        pl, squad = _dummy_players(gws)
        # Borderline captain xP = 11.5: above 10.5 (no big future DGW) and below 13.0 (if GW33 DGW4 leaked!)
        pl[15]["xp"][24] = 11.5
        sell = {i: pl[i]["price"] for i in squad}
        base_plan = optimise.solve(pl, squad, sell, 1.0, 2, gws, max_hits=0, time_limit=15)
        self.assertIsNotNone(base_plan)

        avail = sr.season_chips("2024-25")
        conf = sr.load_fixture_dates()

        decisions = []
        for gw33_n, gw34_n in ((4, 4), (0, 0), (12, 8)):
            fx = _season_2425_fixtures(gw33_dgw_teams=gw33_n, gw34_bgw_teams=gw34_n)
            dgw24, bgw24 = sr.causal_fixture_calendar(fx, "2024-25", 24, conf_dates=conf, last_gw=38)
            # At GW24 (1 Feb), GW24 DGW is confirmed (13 Jan), GW33/34 are NOT confirmed (3 Apr)
            self.assertEqual(dgw24[24], 2)
            self.assertEqual(dgw24[33], 0)
            self.assertEqual(bgw24[34], 0)

            c_simple, _ = sr.choose_chip("simple", 24, pl, gws, squad, sell, 1.0, 2, base_plan,
                                         avail, dgw24, bgw24, season="2024-25")
            c_solver, _ = sr.choose_chip("solver", 24, pl, gws, squad, sell, 1.0, 2, base_plan,
                                         avail, dgw24, bgw24, season="2024-25")
            decisions.append((c_simple, c_solver))

        self.assertEqual(decisions[0], decisions[1], "GW24 chip decision moved when GW33/34 changed (4->0)")
        self.assertEqual(decisions[0], decisions[2], "GW24 chip decision moved when GW33/34 changed (4->12)")

        # After 3 Apr (at GW31, 5 Apr), GW33 DGW4 and GW34 BGW4 ARE confirmed and visible
        fx_real = _season_2425_fixtures(gw33_dgw_teams=4, gw34_bgw_teams=4)
        dgw31, bgw31 = sr.causal_fixture_calendar(fx_real, "2024-25", 31, conf_dates=conf, last_gw=38)
        self.assertEqual(dgw31[33], 4)
        self.assertEqual(bgw31[34], 4)


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

    def test_2025_26_gw16_afcon_ft_topup(self):
        """Official 2025-26 AFCON rule: team enters GW16 with 5 FTs regardless of GW15 transfers."""
        for ft_after_gw15 in (1, 2, 3, 4, 5):
            self.assertEqual(sr.apply_ft_topup(ft_after_gw15, "2025-26", 16), 5)
        # No top-up in GW15 or in 2024-25 GW16
        self.assertEqual(sr.apply_ft_topup(1, "2025-26", 15), 1)
        self.assertEqual(sr.apply_ft_topup(1, "2024-25", 16), 1)

        # Audit catches missing GW16 top-up in 2025-26
        pl, squad = _dummy_players([16])
        xi = [1, 3, 4, 5, 6, 9, 10, 11, 12, 15, 16]
        bench = [2, 7, 13, 17]
        pool = sr.season_chips("2025-26")
        errs_ok = sr.audit_week(16, squad, 0.5, 4, xi, bench, 15, pl, 2, None, pool, set(), 0, False, {},
                                ft_before=5, season="2025-26")
        self.assertEqual(errs_ok, [])
        errs_miss = sr.audit_week(16, squad, 0.5, 1, xi, bench, 15, pl, 1, None, pool, set(), 0, False, {},
                                  ft_before=1, season="2025-26")
        self.assertTrue(any("FT top-up" in e for e in errs_miss))

    def test_no_consecutive_free_hits(self):
        """Free Hit cannot be played in consecutive gameweeks (e.g. FH1 in GW19 followed by FH2 in GW20)."""
        gws = [20, 21, 22, 23, 24]
        pl, squad = _dummy_players(gws)
        xi = [1, 3, 4, 5, 6, 9, 10, 11, 12, 15, 16]
        bench = [2, 7, 13, 17]
        pool = sr.season_chips("2025-26")

        # Audit rejects FH2@GW20 when prev_fh_gw == 19
        errs = sr.audit_week(20, squad, 0.5, 3, xi, bench, 15, pl, 5, "FH2", pool, {"FH1"}, 0, False, {},
                             ft_before=3, prev_fh_gw=19, season="2025-26")
        self.assertTrue(any("consecutive Free Hit" in e for e in errs))

        # Legal if previous FH was GW18
        errs_ok = sr.audit_week(20, squad, 0.5, 3, xi, bench, 15, pl, 5, "FH2", pool, {"FH1"}, 0, False, {},
                                ft_before=3, prev_fh_gw=18, season="2025-26")
        self.assertEqual(errs_ok, [])

        # Both simple and solver choose_chip refuse FH2@GW20 when prev_fh_gw == 19, even with a big BGW20
        sell = {i: pl[i]["price"] for i in squad}
        base_plan = optimise.solve(pl, squad, sell, 1.0, 2, gws, max_hits=0, time_limit=15)
        avail = {"FH2": (20, 38)}
        dgw = {g: 0 for g in range(1, 39)}
        bgw = {g: (10 if g == 20 else 0) for g in range(1, 39)}
        c_simple, _ = sr.choose_chip("simple", 20, pl, gws, squad, sell, 1.0, 2, base_plan,
                                     avail, dgw, bgw, prev_fh_gw=19, season="2025-26")
        c_solver, _ = sr.choose_chip("solver", 20, pl, gws, squad, sell, 1.0, 2, base_plan,
                                     avail, dgw, bgw, prev_fh_gw=19, season="2025-26")
        self.assertIsNone(c_simple)
        self.assertIsNone(c_solver)

    def test_audit_week_enforces_fpl_chip_and_transfer_accounting(self):
        """audit_week must catch illegal transfer accounting sequences, WC/FH FT preservation, cap of 5, and hits."""
        gws = [20]
        pl, squad = _dummy_players(gws)
        xi = [1, 3, 4, 5, 6, 9, 10, 11, 12, 15, 16]
        bench = [2, 7, 13, 17]
        pool = sr.season_chips("2025-26")

        # Legal WC2 preserving 3 banked FTs -> 0 violations
        errs = sr.audit_week(20, squad, 0.5, 3, xi, bench, 15, pl, 5, "WC2", pool, set(), 0, False, {}, ft_before=3)
        self.assertEqual(errs, [])

        # WC2 failing to preserve banked FTs (dropping 3 -> 1) -> violation
        errs = sr.audit_week(20, squad, 0.5, 1, xi, bench, 15, pl, 5, "WC2", pool, set(), 0, False, {}, ft_before=3)
        self.assertTrue(any("WC ft_after" in e for e in errs))

        # FH2 charging a hit or incrementing banked FTs (3 -> 4) -> violations
        errs = sr.audit_week(20, squad, 0.5, 4, xi, bench, 15, pl, 5, "FH2", pool, set(), 1, True, {}, ft_before=3)
        self.assertTrue(any("FH charged" in e for e in errs))
        self.assertTrue(any("FH ft_after" in e for e in errs))

        # Normal week: rolled with 5 FTs stays capped at 5 -> legal
        errs = sr.audit_week(20, squad, 0.5, 5, xi, bench, 15, pl, 0, None, pool, set(), 0, False, {}, ft_before=5)
        self.assertEqual(errs, [])

        # Normal week: FT > 5 -> violation
        errs = sr.audit_week(20, squad, 0.5, 6, xi, bench, 15, pl, 0, None, pool, set(), 0, False, {}, ft_before=5)
        self.assertTrue(any("ft 6" in e for e in errs))

        # Normal week: 2 moves with 1 FT and 0 hits claimed -> violation
        errs = sr.audit_week(20, squad, 0.5, 1, xi, bench, 15, pl, 2, None, pool, set(), 0, True, {}, ft_before=1)
        self.assertTrue(any("hits 0 != expected 1" in e for e in errs))

        # Normal week: 1 hit taken with 2 FTs (3 moves) must reset ft_after to 1 (claiming 2 -> violation)
        errs = sr.audit_week(20, squad, 0.5, 2, xi, bench, 15, pl, 3, None, pool, set(), 1, True, {}, ft_before=2)
        self.assertTrue(any("ft_after 2 != expected 1" in e for e in errs))

        # Normal week: 0 moves with 2 FTs must bank to 3 (claiming 2 -> violation)
        errs = sr.audit_week(20, squad, 0.5, 2, xi, bench, 15, pl, 0, None, pool, set(), 0, False, {}, ft_before=2)
        self.assertTrue(any("ft_after 2 != expected 3" in e for e in errs))

        # First-half chip used in GW20 -> violation
        errs = sr.audit_week(20, squad, 0.5, 3, xi, bench, 15, pl, 1, "WC1", pool, set(), 0, False, {}, ft_before=3)
        self.assertTrue(any("outside window" in e for e in errs))

        # Unexpected hit on Balanced -> violation
        errs = sr.audit_week(20, squad, 0.5, 1, xi, bench, 15, pl, 2, None, pool, set(), 1, False, {}, ft_before=1)
        self.assertTrue(any("unexpected hit" in e for e in errs))

        # Negative bank -> violation
        errs = sr.audit_week(20, squad, -0.2, 2, xi, bench, 15, pl, 1, None, pool, set(), 0, False, {}, ft_before=2)
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
        for ev in boot_mut["events"]:
            if ev["id"] >= 12:
                ev["finished"] = True
                ev["average_entry_score"] = 9999
        avgs_base = sr.real_avg_table(boot_base)
        avgs_mut = sr.real_avg_table(boot_mut)
        self.assertNotIn(15, avgs_base)
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
