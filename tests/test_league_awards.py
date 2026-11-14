"""Weekly honours (league_awards.py): medal ties, each award's rule and what happens when inputs are missing.
Sample values only; the site shows real FPL data."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import league_awards as la  # noqa: E402

# 16 players: 1-2 keepers, 3-8 defenders, 9-13 midfielders, 14-16 forwards; clubs 1-8, two players each
POS = {i: "GKP" if i <= 2 else "DEF" if i <= 8 else "MID" if i <= 13 else "FWD" for i in range(1, 17)}
TEAM = {i: (i + 1) // 2 for i in range(1, 17)}
XI = [1, 3, 4, 5, 9, 10, 11, 12, 14, 15, 13]
BENCH = [2, 6, 7, 16]


def picks(xi=XI, bench=BENCH, chip=None, subs=()):
    rows = [{"element": e, "position": k + 1, "multiplier": 1} for k, e in enumerate(list(xi) + list(bench))]
    return {"picks": rows, "active_chip": chip, "automatic_subs": [{"element_out": o, "element_in": i} for o, i in subs]}


def hist(cost=0, tx=0):
    return {"event_transfers_cost": cost, "event_transfers": tx, "total_points": 500, "points": 50}


def run(inputs, pts=None, ranks=None, size=None):
    members = [{"entry": e, "player": f"M{e}"} for e in inputs]
    info = {"pts": pts or {i: 2 for i in POS}, "pos": POS, "team": TEAM, "name": {i: f"P{i}" for i in POS}}
    return la.league_awards(members, 10, inputs, info, ranks=ranks, size=size)["awards"]


def vals(a):
    return [(p["entry"], p["value"], p["medal"]) for p in a["places"]]


class Podium(unittest.TestCase):
    def test_shared_bronze(self):
        p = la.podium([{"entry": e, "value": v} for e, v in [(1, 9), (2, 7), (3, 5), (4, 5), (5, 1)]])
        self.assertEqual([(r["entry"], r["rank"], r["medal"]) for r in p], [(1, 1, "gold"), (2, 2, "silver"), (3, 3, "bronze"), (4, 3, "bronze")])

    def test_shared_gold_skips_silver(self):
        p = la.podium([{"entry": e, "value": v} for e, v in [(1, 9), (2, 9), (3, 5), (4, 4)]])
        self.assertEqual([(r["entry"], r["medal"]) for r in p], [(1, "gold"), (2, "gold"), (3, "bronze")])

    def test_fewer_qualifiers_fewer_places(self):
        self.assertEqual(len(la.podium([{"entry": 1, "value": 3}])), 1)
        self.assertEqual(la.podium([]), [])


class Awards(unittest.TestCase):
    def test_transfer_of_the_week_nets_chains_and_takes_off_the_hit(self):
        # A: 14 -> 16 and 16 -> 2? (outfield chain 15 -> 16 -> 6): net 15 out, 6 in; hit 4
        tx = [{"element_out": 15, "element_in": 16}, {"element_out": 16, "element_in": 6}]
        pts = {i: 1 for i in POS} | {6: 10, 15: 3}
        a = run({1: {"hist": hist(4), "picks": picks(), "transfers": tx}}, pts)["totw"]
        p = a["places"][0]
        self.assertEqual((p["pin"], p["pout"], p["hit"], p["value"]), (10, 3, 4, 3))
        self.assertEqual(p["ins"], [["P6", 10]])

    def test_free_hit_is_not_a_transfer_but_counts_for_the_shuffler(self):
        tx = [{"element_out": o, "element_in": o + 1} for o in (3, 9)]
        aw = run({1: {"hist": hist(), "picks": picks(chip="freehit"), "transfers": tx}})
        self.assertEqual(aw["totw"]["status"], "none")
        self.assertEqual(aw["shuffler"]["places"][0]["chip"], "freehit")
        self.assertEqual(aw["shuffler"]["places"][0]["value"], 2)

    def test_wall_uses_final_xi_with_fpl_subs_and_no_captaincy(self):
        pts = {i: 0 for i in POS} | {1: 6, 3: 2, 4: 2, 5: 2, 6: 5}
        a = run({1: {"hist": hist(), "picks": picks(subs=[(5, 6)]), "transfers": []}}, pts)["wall"]
        self.assertEqual((a["places"][0]["gk"], a["places"][0]["df"]), (6, 9))

    def test_bench_boost_bench_is_not_in_the_wall_or_bench_rescue(self):
        pts = {i: 0 for i in POS} | {2: 10, 6: 8}
        aw = run({1: {"hist": hist(), "picks": picks(chip="bboost"), "transfers": []}}, pts)
        self.assertEqual(aw["wall"]["places"][0]["value"], 0)
        self.assertEqual(aw["bench"]["status"], "none")

    def test_bench_rescue_best_single_sub_that_scored(self):
        pts = {i: 0 for i in POS} | {6: 3, 16: 7}
        aw = run({1: {"hist": hist(), "picks": picks(subs=[(5, 6), (14, 16)]), "transfers": []},
                  2: {"hist": hist(), "picks": picks(subs=[(5, 7)]), "transfers": []}}, pts)["bench"]
        self.assertEqual(vals(aw), [(1, 7, "gold")])   # manager 2's sub scored 0: doesn't qualify

    def test_climber_rises_only_and_unavailable_without_ranks(self):
        ins = {e: {"hist": hist(), "picks": picks(), "transfers": []} for e in (1, 2, 3)}
        aw = run(ins, ranks={1: (1, 3), 2: (2, 1), 3: (3, 2)})["climber"]
        self.assertEqual(vals(aw), [(1, 2, "gold")])
        self.assertEqual(run(ins)["climber"]["status"], "unavailable")

    def test_blueprint_reference_xi_is_legal_and_deterministic(self):
        ref, _ = la.reference_xi([XI, XI, [2, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16]], POS, TEAM)
        self.assertEqual(len(ref), 11)
        self.assertEqual(sum(POS[i] == "GKP" for i in ref), 1)
        self.assertTrue(all(sum(TEAM[i] == t for i in ref) <= 3 for t in set(TEAM.values())))
        self.assertEqual(ref, la.reference_xi([XI, XI, [2, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16]], POS, TEAM)[0])

    def test_blueprint_and_grain_need_three_xis(self):
        aw = run({1: {"hist": hist(), "picks": picks(), "transfers": []}})
        self.assertEqual(aw["blueprint"]["status"], "unavailable")
        self.assertEqual(aw["grain"]["status"], "unavailable")

    def test_grain_is_strictly_under_20_percent_of_covered_xis(self):
        # 5 XIs: a player in exactly 1 (20%) is not rare; 10 XIs: a player in 1 (10%) is
        other = [2, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16]
        five = {e: {"hist": hist(), "picks": picks(xi=other if e == 1 else XI), "transfers": []} for e in range(1, 6)}
        self.assertEqual(run(five)["grain"]["status"], "none")
        ten = {e: {"hist": hist(), "picks": picks(xi=other if e == 1 else XI), "transfers": []} for e in range(1, 11)}
        g = run(ten)["grain"]
        self.assertEqual(g["places"][0]["entry"], 1)
        self.assertEqual(g["base"], 10)

    def test_hit_parade_only_hit_takers_and_says_if_it_paid(self):
        tx = [{"element_out": 15, "element_in": 16}]
        pts = {i: 0 for i in POS} | {16: 9, 15: 1}
        aw = run({1: {"hist": hist(4), "picks": picks(), "transfers": tx}, 2: {"hist": hist(0), "picks": picks(), "transfers": []}}, pts)["hits"]
        self.assertEqual(vals(aw), [(1, 4, "gold")])
        self.assertTrue(aw["places"][0]["covered_cost"])

    def test_missing_inputs_are_left_out_and_counted(self):
        aw = run({1: {"hist": hist(), "picks": picks(), "transfers": None}, 2: {"hist": None, "picks": None, "transfers": None},
                  3: {"hist": hist(), "picks": picks(), "transfers": []}})
        self.assertEqual(aw["totw"]["covered"], 1)
        self.assertEqual(aw["wall"]["covered"], 2)
        self.assertEqual(aw["shuffler"]["covered"], 1)

    def test_zero_qualifiers(self):
        aw = run({e: {"hist": hist(), "picks": picks(), "transfers": []} for e in (1, 2, 3)})
        for k in ("totw", "bench", "hits", "shuffler"):
            self.assertEqual((aw[k]["status"], aw[k]["places"]), ("none", []), k)


if __name__ == "__main__":
    unittest.main()
