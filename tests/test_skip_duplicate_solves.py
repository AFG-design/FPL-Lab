"""FL-118: strategy_plans skips a solver run that would repeat a plan already found, and only then."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import optimise  # noqa: E402


def stub(best_moves=2, optimal=True):
    """A fake solver: week 1 left free makes best_moves moves; a fixed count n makes n. Records every call."""
    calls = []

    def solve(players, squad, sell, bank, ft0, gws, **a):
        calls.append(a)
        n = a.get("week1_moves")
        free = n is None
        n = best_moves if free else n
        frozen = a.get("freeze_after") == 0
        value = 100.0 if frozen else 110.0 - abs(n - best_moves) - (0.5 if a.get("lam") else 0)
        return {"weeks": [{"in": list(range(n)), "out": list(range(10, 10 + n)), "hits": 0}], "value": value,
                "xp_total": value, "ft_left": 1, "optimal": optimal if free else True,
                "tag": (n, a.get("lam"), a.get("floor"), a.get("max_hits"))}
    return solve, calls


OPTS = [("best", None), ("roll", 0), ("one", 1), ("two", 2), ("three", 3)]
ARGS = ({}, [], {}, 0.0, 3, [11, 12])


def run(solve):
    with mock.patch.object(optimise, "solve", solve):
        return optimise.strategy_plans(*ARGS, OPTS, eo={1: 0.5})


class SkipDuplicateSolves(unittest.TestCase):
    def test_skips_only_the_repeat_and_plans_match(self):
        solve, calls = stub(best_moves=2)
        plans, _ = run(solve)
        # 1 no-transfer run + 5 options x 3 strategies = 16; "two" repeats "best" for all three strategies
        self.assertEqual(len(calls), 13)
        self.assertNotIn(2, [c.get("week1_moves") for c in calls])
        for p in ("", "safe_", "chase_"):
            self.assertEqual(plans[p + "two"], plans[p + "best"])
            self.assertIsNot(plans[p + "two"]["weeks"], plans[p + "best"]["weeks"])   # a copy, not shared

    def test_reused_plan_equals_a_fresh_run(self):
        solve, _ = stub(best_moves=1)
        plans, _ = run(solve)
        fresh, _ = stub(best_moves=1)
        ref = fresh(*ARGS, week1_moves=1, max_hits=0)   # what the skipped Balanced run would have returned
        self.assertEqual(plans["one"]["weeks"], ref["weeks"])
        self.assertEqual(plans["one"]["value"], ref["value"])

    def test_no_skip_when_the_free_plan_was_not_proven_optimal(self):
        solve, calls = stub(best_moves=2, optimal=False)
        run(solve)
        self.assertEqual(len(calls), 16)

    def test_no_skip_when_no_option_matches(self):
        solve, calls = stub(best_moves=4)   # no option fixes week 1 at 4
        run(solve)
        self.assertEqual(len(calls), 16)


if __name__ == "__main__":
    unittest.main()
