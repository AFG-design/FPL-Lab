"""FPL scoring rules (fpl_score.py, F1a). Run: python3 -m unittest discover tests"""
import json, os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from fpl_score import score_team, auto_subs, as_submitted

# a 4-4-2: keeper 1, defenders 2-5, midfielders 6-9, forwards 10-11; bench: keeper 12, then 13 (DEF), 14 (MID), 15 (FWD)
POS = {1: "GKP", **{i: "DEF" for i in (2, 3, 4, 5)}, **{i: "MID" for i in (6, 7, 8, 9)}, 10: "FWD", 11: "FWD",
       12: "GKP", 13: "DEF", 14: "MID", 15: "FWD"}
XI, BENCH = list(range(1, 12)), [12, 13, 14, 15]


def team(cap=10, vice=6, xi=XI, bench=BENCH, pos=POS):
    return {"xi": list(xi), "bench": list(bench), "captain": cap, "vice": vice, "pos": pos}


def played(**over):
    """Everyone played 90 and scored 2, except the players listed as p<id>=(minutes, points)."""
    out = {i: (90, 2) for i in POS}
    out.update({int(k[1:]): v for k, v in over.items()})
    return out


class Basics(unittest.TestCase):
    def test_everyone_plays(self):
        r = score_team(team(), played(p10=(90, 8)))
        self.assertEqual(r["total"], 10 * 2 + 8 * 2)      # ten others on 2, captain 8 doubled
        self.assertEqual(r["subs"], [])

    def test_bench_points_dont_count(self):
        self.assertEqual(score_team(team(), played(p13=(90, 15)))["total"], 11 * 2 + 2)   # +2: captain doubled

    def test_negative_points_count(self):
        self.assertEqual(score_team(team(), played(p5=(90, -2)))["total"], 10 * 2 - 2 + 2)


class Subs(unittest.TestCase):
    def test_first_bench_player_who_played_comes_on(self):
        r = score_team(team(), played(p7=(0, 0)))
        self.assertEqual(r["subs"], [(7, 13)])            # 13 is first outfield on the bench; 4-4-2 -> 5-3-2 is legal

    def test_bench_player_who_didnt_play_is_skipped(self):
        r = score_team(team(), played(p7=(0, 0), p13=(0, 0)))
        self.assertEqual(r["subs"], [(7, 14)])

    def test_keeper_only_for_keeper(self):
        r = score_team(team(), played(p1=(0, 0)))
        self.assertEqual(r["subs"], [(1, 12)])
        r = score_team(team(), played(p1=(0, 0), p12=(0, 0)))
        self.assertEqual(r["subs"], [])                   # no keeper played: the slot stays empty
        self.assertNotIn(13, r["xi"])

    def test_formation_must_stay_legal(self):
        # 3-5-2 with a defender out: the first bench player is a midfielder (would make 2 defenders), so skip to the DEF
        pos = {**POS, 5: "MID", 13: "MID", 14: "DEF"}
        r = score_team(team(pos=pos), played(p2=(0, 0)), None)
        self.assertEqual(r["subs"], [(2, 14)])

    def test_no_legal_sub_leaves_zero(self):
        pos = {**POS, 13: "MID", 14: "MID", 15: "MID", 5: "MID"}   # 3-5-2, bench all midfielders
        r = score_team(team(pos=pos), played(p2=(0, 0)))
        self.assertEqual(r["subs"], [])
        self.assertEqual(r["total"], 10 * 2 + 2)          # the missing defender scores 0

    def test_several_subs_in_xi_order(self):
        r = score_team(team(), played(p3=(0, 0), p8=(0, 0)))
        self.assertEqual(r["subs"], [(3, 13), (8, 14)])

    def test_blank_or_missing_player_plays_zero(self):
        p = played(); del p[9]
        self.assertEqual(score_team(team(), p)["subs"], [(9, 13)])


class Captaincy(unittest.TestCase):
    def test_vice_takes_the_armband(self):
        r = score_team(team(cap=10, vice=6), played(p10=(0, 0), p6=(90, 5)))
        self.assertEqual(r["captain"], 6)
        # 10 is subbed off for 13; the XI: nine on 2, vice 5 doubled, sub 13 on 2
        self.assertEqual(r["total"], 9 * 2 + 5 * 2 + 2)

    def test_neither_plays_nobody_doubled(self):
        r = score_team(team(cap=10, vice=6), played(p10=(0, 0), p6=(0, 0)))
        self.assertIsNone(r["captain"])
        self.assertEqual(r["total"], 11 * 2)              # 9 starters + 2 subs (13 and 14), nobody doubled

    def test_captain_with_minutes_keeps_it(self):
        self.assertEqual(score_team(team(), played(p10=(1, 1)))["captain"], 10)


class Chips(unittest.TestCase):
    def test_triple_captain(self):
        self.assertEqual(score_team(team(), played(p10=(90, 8)), "3xc")["total"], 10 * 2 + 8 * 3)

    def test_triple_captain_passes_to_vice(self):
        r = score_team(team(), played(p10=(0, 0), p6=(90, 5)), "3xc")
        self.assertEqual(r["multipliers"][6], 3)

    def test_bench_boost_counts_all_15_without_subs(self):
        r = score_team(team(), played(p7=(0, 0), p13=(90, 6)), "bboost")
        self.assertEqual(r["subs"], [])
        self.assertEqual(r["total"], 13 * 2 + 0 + 6 + 2)  # the other 13 on 2, player 7 on 0, 13 on 6, captain doubled

    def test_wildcard_and_free_hit_score_normally(self):
        for chip in ("wildcard", "freehit"):
            self.assertEqual(score_team(team(), played(), chip)["total"], 11 * 2 + 2)


class DoubleGameweek(unittest.TestCase):
    def test_points_and_minutes_are_already_summed(self):
        # a double: 2 matches, 150 minutes and 11 points in all; the captain doubles the lot
        self.assertEqual(score_team(team(), played(p10=(150, 11)))["total"], 10 * 2 + 22)


class RealGameweeks(unittest.TestCase):
    """Your GW8 and GW9 (team 8122679), as submitted, must score exactly what FPL gave, with the same auto-subs."""
    def test_matches_fpl(self):
        with open(os.path.join(HERE, "fpl_score_real.json")) as f:
            data = json.load(f)
        for g, d in data.items():
            pos = {int(k): v for k, v in d["pos"].items()}
            pl = {int(k): tuple(v) for k, v in d["played"].items()}
            r = score_team(as_submitted(d["picks"], pos), pl, d["picks"]["active_chip"])
            self.assertEqual(r["total"], d["fpl_points"], f"GW{g}")
            self.assertEqual(r["subs"], [(s["element_out"], s["element_in"]) for s in d["picks"]["automatic_subs"]], f"GW{g}")


if __name__ == "__main__":
    unittest.main()


from fpl_score import supercomputer_pick


class Supercomputer(unittest.TestCase):
    SQUAD = XI + BENCH

    def xp(self, **over):
        out = {i: 1.0 for i in self.SQUAD}
        out.update({int(k[1:]): v for k, v in over.items()})
        return out

    def test_no_saved_forecast_no_pick(self):
        self.assertIsNone(supercomputer_pick(self.SQUAD, POS, None))

    def test_best_legal_xi_captain_vice(self):
        t = supercomputer_pick(self.SQUAD, POS, self.xp(p13=5, p14=4, p15=6, p12=0.5, p10=7))
        self.assertEqual(len(t["xi"]), 11)
        self.assertIn(15, t["xi"]); self.assertIn(13, t["xi"]); self.assertIn(14, t["xi"])
        self.assertEqual((t["captain"], t["vice"]), (10, 15))
        self.assertEqual(t["bench"][0], 12)               # spare keeper first

    def test_formation_limits_hold(self):
        # every defender projects highest: still only 5 of them, and at least 2 midfielders and 1 forward
        pos = {**POS, 6: "DEF", 7: "DEF"}                 # 7 defenders in the squad
        xp = self.xp(**{f"p{i}": 9 for i in (2, 3, 4, 5, 6, 7, 13)})
        t = supercomputer_pick(self.SQUAD, pos, xp)
        n = {k: sum(pos[i] == k for i in t["xi"]) for k in ("GKP", "DEF", "MID", "FWD")}
        self.assertEqual(n["GKP"], 1); self.assertEqual(n["DEF"], 5)
        self.assertGreaterEqual(n["MID"], 2); self.assertGreaterEqual(n["FWD"], 1)

    def test_missing_player_counts_as_zero_and_bench_by_xp(self):
        xp = self.xp(p13=3, p14=2, p15=5); del xp[9]       # 9 missing from the saved forecast
        t = supercomputer_pick(self.SQUAD, POS, xp)
        self.assertNotIn(9, t["xi"])
        self.assertEqual(t["bench"][0], 12)
        self.assertEqual(t["bench"][1:], sorted(t["bench"][1:], key=lambda i: -xp.get(i, 0)))

    def test_ties_follow_your_order(self):
        a = supercomputer_pick(self.SQUAD, POS, self.xp())
        self.assertEqual(a["xi"], XI)                     # all equal: your XI, your captain order
        self.assertEqual(a, supercomputer_pick(self.SQUAD, POS, self.xp()))

    def test_real_gw8_and_gw9(self):
        """Your 15 with the forecasts saved before GW8 and GW9: both weeks finish level."""
        with open(os.path.join(HERE, "fpl_score_real.json")) as f:
            data = json.load(f)
        want = {"8": (52, 52, 411), "9": (70, 70, 411)}   # you, Supercomputer, its captain (Haaland)
        for g, d in data.items():
            pos = {int(k): v for k, v in d["pos"].items()}
            pl = {int(k): tuple(v) for k, v in d["played"].items()}
            you = as_submitted(d["picks"], pos)
            sc = supercomputer_pick(you["xi"] + you["bench"], pos, {int(k): v for k, v in d["xp_saved"].items()})
            got = (score_team(you, pl)["total"], score_team(sc, pl)["total"], sc["captain"])
            self.assertEqual(got, want[g], f"GW{g}")


from fpl_score import streak, result, expected, target


class Streak(unittest.TestCase):
    def test_result(self):
        self.assertEqual([result(5, 3), result(3, 3), result(2, 3)], ["W", "D", "L"])

    def test_expected_and_target(self):
        xp = {i: 1.0 for i in POS}; xp[10] = 6.0
        self.assertAlmostEqual(expected(team(), xp), 10 * 1 + 6 * 2)
        self.assertAlmostEqual(expected(team(), xp, "3xc"), 10 * 1 + 6 * 3)
        self.assertAlmostEqual(expected(team(), xp, "bboost"), 14 * 1 + 6 * 2)
        del xp[3]
        self.assertAlmostEqual(expected(team(), xp), 9 * 1 + 6 * 2)      # missing from the forecast counts as 0
        self.assertEqual([target(48.8), target(48.5), target(48.49), target(-1.5)], [49, 49, 48, -2])

    def test_best_suggestion_is_highest_after_hits(self):
        from fpl_score import best_suggestion
        wk = lambda xp, hits=0: {"weeks": [{"gw": 10, "out": [], "in": [], "hits": hits, "captain": 1, "xi": [1], "xp": xp},
                                           {"gw": 11, "xp": 99, "hits": 0}]}
        plans = {"roll": wk(47.3), "two": wk(49.5), "chase_hit": wk(52.0, hits=1), "tie": wk(49.5)}
        b = best_suggestion(plans, 10)
        self.assertEqual((b["plan"], b["exp"]), ("two", 49.5))      # 52 - 4 = 48 after the hit; ties keep the first
        self.assertIsNone(best_suggestion({}, 10))
        self.assertIsNone(best_suggestion(plans, 12))                 # no plan has a week for GW12
        self.assertIsNone(best_suggestion(None, 10))

    def test_real_gw10_suggestions(self):
        """The plans saved before the GW10 deadline: the best is two transfers (Rogers and De Cuyper out, Gabriel and Rudoni in), 49.5 -> 50."""
        from fpl_score import best_suggestion
        with open(os.path.join(HERE, "..", "history", "deadline_gw10.json")) as f:
            b = best_suggestion(json.load(f)["plans"], 10)
        self.assertEqual((b["exp"], target(b["exp"]), b["hits"]), (49.5, 50, 0))

    def test_real_gw8_and_gw9_against_expected(self):
        """Your actual points against what the model expected its pick from your 15 to score: two wins."""
        with open(os.path.join(HERE, "fpl_score_real.json")) as f:
            data = json.load(f)
        want = {"8": (52, 49, "W"), "9": (70, 47, "W")}
        for g, d in data.items():
            pos = {int(k): v for k, v in d["pos"].items()}
            pl = {int(k): tuple(v) for k, v in d["played"].items()}
            xp = {int(k): v for k, v in d["xp_saved"].items()}
            you = as_submitted(d["picks"], pos)
            m = supercomputer_pick(you["xi"] + you["bench"], pos, xp)
            a, par = score_team(you, pl)["total"], target(expected(m, xp))
            self.assertEqual((a, par, result(a, par)), want[g], f"GW{g}")

    def test_wins_build_the_run_draw_ends_it(self):
        s = streak(list("WWD"))
        self.assertEqual((s["run"], s["best"], s["record"]), (0, 2, {"W": 2, "D": 1, "L": 0}))

    def test_hat_trick_earns_a_wildcard_that_saves_a_defeat(self):
        s = streak(list("WWWL"))
        self.assertEqual((s["run"], s["held"], s["used"], s["earned"]), (3, 0, 1, 1))
        s = streak(list("WWWLW"))
        self.assertEqual(s["run"], 4)                     # the saved defeat adds nothing; the next win carries on

    def test_defeat_without_wildcard_ends_run(self):
        self.assertEqual(streak(list("WWL"))["run"], 0)

    def test_draw_is_never_saved(self):
        s = streak(list("WWWD"))
        self.assertEqual((s["run"], s["held"], s["used"]), (0, 1, 0))   # wildcard kept for later

    def test_defeat_with_no_run_costs_nothing(self):
        s = streak(list("WWWDL"))
        self.assertEqual((s["run"], s["held"], s["used"]), (0, 1, 0))

    def test_hold_at_most_two(self):
        s = streak(["W"] * 19)                            # milestones at 3, 6, 10, 19
        self.assertEqual((s["earned"], s["held"], s["lost"]), (4, 2, 2))

    def test_milestones_reset_with_a_new_run(self):
        s = streak(list("WWWD") + list("WWW"))
        self.assertEqual((s["earned"], s["held"]), (2, 2))

    def test_invincibles_locked_this_season(self):
        inv = streak(["W"] * 31)["milestones"][-1]
        self.assertEqual((inv["name"], inv["locked"]), ("Invincibles", True))
        self.assertTrue(streak(["W"] * 38, season_from_gw1=True)["invincible"])
        self.assertFalse(streak(["W"] * 37 + ["D"], season_from_gw1=True)["invincible"])
