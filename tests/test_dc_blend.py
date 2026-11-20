"""FL-224: unit tests for dc_blend validation and n=0, dc_blend=0 fallback."""
import unittest

import fplmodel
from tests.test_def_bonus_mult import _mini_ctx


class TestDcBlend(unittest.TestCase):
    def test_default_is_fifteen(self):
        self.assertEqual(fplmodel.DEFAULTS["dc_blend"], 15.0)

    def test_invalid_values_raise(self):
        ctx = _mini_ctx()
        for bad in (-0.1, -4, None, True, False, "15", float("nan"), float("inf"), float("-inf")):
            with self.assertRaises(ValueError, msg=f"expected ValueError for {bad!r}"):
                fplmodel.project(ctx, 4, 1, {"dc_blend": bad})

    def test_zero_dc_blend_with_no_starts_falls_back_to_model(self):
        ctx = _mini_ctx()
        # Player 2 (DEF) has 0 prior starts/minutes -> n = 0; dc_blend = 0 must not divide by zero
        ctx["pstats"][2] = {}
        ctx["dc_fx"] = {}
        for dc_fix in (False, True):
            r0 = fplmodel.project(ctx, 4, 1, {"dc_blend": 0.0, "dc_fixture": dc_fix})["players"][2]
            rm = fplmodel.project(ctx, 4, 1, {"dc_blend": 1e6, "dc_fixture": dc_fix})["players"][2]
            self.assertAlmostEqual(r0["detail"][4]["dc"], rm["detail"][4]["dc"], places=6)


if __name__ == "__main__":
    unittest.main()
