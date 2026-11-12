"""FL-110: "no moves for the sake of it" is measured against rolling this week, not against never transferring.

Before, a plan's moves only had to beat keeping the squad for all 5 GWs by MIN_PROFIT. A Roll plan that moves later
already beats that easily, so the rule hardly ever bound (live 12 Nov: Balanced 3 moves for +0.32 against rolling).
Run: python3 -m unittest discover tests
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import optimise  # noqa: E402

V0 = 100.0


def stub(roll_gain=4.0, gain={1: 4.32, 2: 4.32, 3: 4.32}, best_moves=3):
    """Keep-squad: V0. Roll: no move now, one later, V0 + roll_gain. n moves now: V0 + gain[n]. Free week 1: best_moves."""
    def solve(players, squad, sell, bank, ft0, gws, **a):
        n = a.get("week1_moves")
        if a.get("freeze_after") == 0:
            wk, v = [{"in": [], "out": [], "hits": 0}, {"in": [], "out": [], "hits": 0}], V0
        elif n == 0:
            wk, v = [{"in": [], "out": [], "hits": 0}, {"in": [7], "out": [8], "hits": 0}], V0 + roll_gain
        else:
            n = best_moves if n is None else n
            wk, v = [{"in": list(range(n)), "out": list(range(50, 50 + n)), "hits": 0}, {"in": [], "out": [], "hits": 0}], V0 + gain[n]
        if a.get("floor") is not None and v < a["floor"] - 1e-9:
            return None
        return {"weeks": wk, "value": v, "xp_total": v, "ft_left": 1, "optimal": True}
    return solve


OPTS = [("best", None), ("roll", 0), ("one", 1), ("two", 2), ("three", 3)]


def run(solve, opts=OPTS):
    with mock.patch.object(optimise, "solve", solve):
        return optimise.strategy_plans({}, [], {}, 0.0, 3, [11, 12], opts, eo={1: 0.5})


class ProfitVsRoll(unittest.TestCase):
    def test_small_gain_over_rolling_is_dropped(self):
        # the live case: three moves now worth +0.32 against rolling (+4.32 against never transferring)
        plans, notes = run(stub())
        self.assertEqual(sorted(k for k in plans if not k.startswith(("safe", "chase"))), ["roll"])
        self.assertTrue(any(n.startswith("three:") and "vs rolling this week" in n for n in notes), notes)
        for p in plans.values():
            self.assertFalse(p["weeks"][0]["in"])

    def test_clear_gain_over_rolling_is_kept(self):
        plans, _ = run(stub(gain={1: 5.5, 2: 4.3, 3: 4.3}, best_moves=1))
        self.assertIn("one", plans)
        self.assertNotIn("two", plans)
        self.assertGreaterEqual(plans["one"]["value"] - plans["roll"]["value"], optimise.MIN_PROFIT)

    def test_without_a_roll_option_balanced_roll_is_the_yardstick(self):
        # strategy_replay's default asks only for "best": the rule still holds, against Balanced's Roll plan
        plans, notes = run(stub(), opts=[("best", None)])
        self.assertNotIn("best", plans)
        plans, _ = run(stub(gain={1: 6, 2: 6, 3: 6}), opts=[("best", None)])
        self.assertIn("best", plans)

    def test_every_plan_moving_now_beats_rolling(self):
        for g in (4.2, 4.9, 5.0, 5.1, 7.0):
            plans, _ = run(stub(gain={1: g, 2: g - 0.3, 3: g + 0.2}, best_moves=3))
            for k, p in plans.items():
                if p["weeks"][0]["in"]:
                    mode = k.split("_")[0] + "_" if "_" in k else ""
                    self.assertGreaterEqual(p["value"] - plans[mode + "roll"]["value"], optimise.MIN_PROFIT - 1e-9, (g, k))


if __name__ == "__main__":
    unittest.main()
