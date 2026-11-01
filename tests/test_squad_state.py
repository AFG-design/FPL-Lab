"""Free Hit restore: the squad and bank the plans start from. Run: python3 -m unittest discover tests"""
import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from squad_state import owned_picks, team_value


def pk(ids, bank, value, chip=None):
    return {"picks": [{"element": i, "position": n + 1} for n, i in enumerate(ids)], "active_chip": chip,
            "entry_history": {"bank": bank, "value": value}}


PERM = pk(range(1, 16), 15, 1000)                      # your real squad, GW9: £1.5m in the bank
FH = pk(range(101, 116), 3, 1012, chip="freehit")     # the Free Hit squad, GW10


class FreeHit(unittest.TestCase):
    def test_free_hit_week_plans_from_the_week_before(self):
        asked = []
        own, gw, active = owned_picks(FH, 10, 11, lambda g: asked.append(g) or PERM)
        self.assertEqual((own, gw, active, asked), (PERM, 9, True, [9]))

    def test_normal_week_uses_this_weeks_picks(self):
        own, gw, active = owned_picks(PERM, 9, 10, lambda g: self.fail("nothing to fetch"))
        self.assertEqual((own, gw, active), (PERM, 9, False))

    def test_other_chips_dont_restore(self):
        for chip in ("wildcard", "bboost", "3xc"):
            wk = dict(PERM, active_chip=chip)
            self.assertIs(owned_picks(wk, 9, 10, lambda g: self.fail("nothing to fetch"))[0], wk)

    def test_free_hit_in_gw38_has_nothing_to_plan(self):
        self.assertEqual(owned_picks(FH, 38, None, lambda g: self.fail("nothing to fetch")), (FH, 38, False))

    def test_failed_fetch_fails_loudly(self):
        def boom(g):
            raise OSError("FPL API down")
        with self.assertRaises(OSError):
            owned_picks(FH, 10, 11, boom)

    def test_free_hit_in_gw1_is_impossible(self):
        with self.assertRaises(RuntimeError):
            owned_picks(dict(FH), 1, 2, lambda g: PERM)

    def test_no_season_yet(self):
        self.assertEqual(owned_picks(None, 0, 1, lambda g: self.fail("nothing to fetch")), (None, 0, False))


class Value(unittest.TestCase):
    def test_value_after_free_hit_uses_todays_prices(self):
        now = {i: 70 for i in range(1, 16)}                         # every restored player now £7.0m
        self.assertEqual(team_value(PERM, 1.5, now, True), 106.5)   # 1.5 + 15 x 7.0

    def test_value_otherwise_is_fpls_figure(self):
        self.assertEqual(team_value(PERM, 1.5, {}, False), 100.0)


if __name__ == "__main__":
    unittest.main()
