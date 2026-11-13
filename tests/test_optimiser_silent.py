"""FL-140: optimiser outcomes that used to pass silently are now said (plan_notes -> Health warnings, and the Planner).

The 23 Oct stress test listed five issues. Three were fixed by later PRs (checked in this PR): browser HiGHS aborts
(plan-solver.js retries with a fresh module and other settings), locks outside the shortlist (honoured in both
solvers), the 0.6 captain swap (one captain rule, model.js capPick) and the best XI ignoring Safe / Chase (adjXI).
Left, and fixed here:
  - a plan from a solve stopped at its time limit (CBC "Not Solved" with a plan) was used with only a build-log line;
  - Play safe / Chase rank finding no plan of their own fell back to Balanced's plan without a word;
  - any failed Balanced solve was reported as "needs a hit", even when the solver simply found nothing.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import optimise  # noqa: E402

OPTS = [("roll", 0), ("one", 1)]
ARGS = ({}, [], {}, 0.0, 1, [11, 12])


def stub(fail=lambda a: None, optimal=True):
    """fail(a) -> None (solve normally) or the LAST_FAIL reason to fail with."""
    def solve(players, squad, sell, bank, ft0, gws, **a):
        why = fail(a)
        if why:
            optimise.LAST_FAIL[0] = why
            return None
        optimise.LAST_FAIL[0] = None
        n = a.get("week1_moves") or 0
        frozen = a.get("freeze_after") == 0
        value = 100.0 if frozen else 105.0 + n - (0.5 if a.get("lam") else 0)
        return {"weeks": [{"in": list(range(n)), "out": list(range(10, 10 + n)), "hits": 0}], "value": value,
                "xp_total": value, "ft_left": 1, "optimal": optimal}
    return solve


def run(solve):
    with mock.patch.object(optimise, "solve", solve):
        return optimise.strategy_plans(*ARGS, OPTS, eo={1: 0.5})


class Silent(unittest.TestCase):
    def test_strategy_falling_back_to_balanced_is_said(self):
        plans, notes = run(stub(lambda a: "solver found no plan (Not Solved)" if a.get("lam", 0) > 0 else None))
        self.assertEqual(plans["safe_one"]["fallback"], "balanced")
        self.assertNotIn("fallback", plans["chase_one"])
        self.assertTrue(any(n.startswith("safe one: solver found no plan") and "Balanced's plan shown instead" in n
                            for n in notes))

    def test_balanced_failure_is_not_called_a_hit(self):
        _, notes = run(stub(lambda a: "solver found no plan (Not Solved)" if a.get("week1_moves") == 1 and not a.get("lam") else None))
        self.assertIn("balanced one: solver found no plan (Not Solved); option left out", notes)
        _, notes = run(stub(lambda a: "infeasible" if a.get("week1_moves") == 1 and not a.get("lam") else None))
        self.assertIn("balanced one: needs a hit, and Balanced never takes one: dropped", notes)

    def test_time_limit_plan_is_said(self):
        plans, notes = run(stub(optimal=False))
        self.assertTrue(plans)
        self.assertTrue(all(any(n.startswith(f"{k}: the solver stopped at its time limit") for n in notes) for k in plans))

    def test_planner_says_it(self):
        src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "site", "js", "views", "planner-views.js")).read()
        self.assertIn('pl.fallback === "balanced"', src)
        self.assertIn("pl.optimal === false", src)


if __name__ == "__main__":
    unittest.main()
