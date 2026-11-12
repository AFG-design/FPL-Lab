"""FL-073: a Roll plan with moves that miss the profit rule falls back to the keep-squad plan.

Before, Roll was exempt from "no moves for the sake of it" (optimise.strategy_plans skipped the check for key "roll"),
so a Roll plan could recommend a transfer later in the plan worth less than MIN_PROFIT, even less than doing nothing
(reproduced: Chase rank -0.8). Run: python3 -m unittest discover tests
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import optimise  # noqa: E402

V0 = 100.0


def stub(roll_gain, chase_roll_gain=None, roll_moves_later=1):
    """Fake solver. Keep-squad (freeze_after=0): V0, no moves. Roll (week1_moves 0): no move in week 1 and
    roll_moves_later moves in week 2, worth V0 + roll_gain (chase_roll_gain for Chase rank, lam < 0). Other move
    counts: n moves in week 1, worth V0 + 3."""
    def solve(players, squad, sell, bank, ft0, gws, **a):
        n = a.get("week1_moves")
        if a.get("freeze_after") == 0:
            weeks, value = [{"in": [], "out": [], "hits": 0}, {"in": [], "out": [], "hits": 0}], V0
        elif n == 0:
            g = chase_roll_gain if (a.get("lam") or 0) < 0 and chase_roll_gain is not None else roll_gain
            later = list(range(roll_moves_later))
            weeks, value = [{"in": [], "out": [], "hits": 0}, {"in": later, "out": [x + 50 for x in later], "hits": 0}], V0 + g
        else:
            n = 1 if n is None else n
            weeks, value = [{"in": list(range(n)), "out": list(range(50, 50 + n)), "hits": 0},
                            {"in": [], "out": [], "hits": 0}], V0 + 3
        if a.get("floor") is not None and value < a["floor"] - 1e-9:
            return None
        return {"weeks": weeks, "value": value, "xp_total": value, "ft_left": 1, "optimal": True}
    return solve


def run(solve):
    with mock.patch.object(optimise, "solve", solve):
        return optimise.strategy_plans({}, [], {}, 0.0, 1, [11, 12], [("roll", 0), ("one", 1)], eo={1: 0.5})


def moves(p):
    return sum(len(w["in"]) for w in p["weeks"])


class RollProfitRule(unittest.TestCase):
    def test_roll_with_a_small_later_gain_keeps_the_squad(self):
        plans, notes = run(stub(roll_gain=0.4))
        self.assertEqual(moves(plans["roll"]), 0)
        self.assertEqual((plans["roll"]["value"], plans["roll"]["vs_none"]), (V0, 0.0))
        self.assertTrue(any(n.startswith("balanced roll:") and "keep-squad plan used" in n for n in notes), notes)

    def test_chase_roll_below_doing_nothing_keeps_the_squad(self):
        # the reproduced case: Chase rank's Roll plan worth -0.8 against doing nothing
        plans, notes = run(stub(roll_gain=0.4, chase_roll_gain=-0.8))
        self.assertEqual(moves(plans["chase_roll"]), 0)
        self.assertGreaterEqual(plans["chase_roll"]["vs_none"], 0)
        self.assertGreaterEqual(plans["chase_roll"]["vs_balanced"], -optimise.CHASE_BUDGET)

    def test_roll_that_clears_the_rule_is_kept(self):
        plans, notes = run(stub(roll_gain=1.5))
        self.assertEqual(moves(plans["roll"]), 1)
        self.assertEqual(plans["roll"]["vs_none"], 1.5)
        self.assertFalse(any("keep-squad plan used" in n for n in notes), notes)

    def test_every_roll_plan_obeys_the_rule(self):
        for g in (-0.8, 0.0, 0.4, 0.99, 1.0, 2.5):
            plans, _ = run(stub(roll_gain=g, chase_roll_gain=g - 0.5))
            for k, p in plans.items():
                if moves(p):
                    self.assertGreaterEqual(p["vs_none"], optimise.MIN_PROFIT, (g, k))


if __name__ == "__main__":
    unittest.main()
