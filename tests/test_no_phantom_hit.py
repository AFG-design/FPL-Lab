"""A hit is only ever the moves beyond your free transfers (FPL's rule), never a -4 booked to bank an extra transfer.

Found by the property tests (tests/test_plan_properties.py, seeds 102 and 103, Chase rank): optimise.solve could take
a hit in a week with no moves, which raised the next week's free transfers by one (the FT rule was
ft[w+1] <= ft[w] - moves + hits + 1). With max_hits=1 (Chase rank's one -4 a week) that let a plan roll in GW11 with a
"hit" and make 4 moves on 3 free transfers in GW12: FPL would give 2 free transfers there and charge -8, two hits in one
week. The plan's total was the same, but its weeks were wrong and it broke the one-hit-a-week cap. Same case for the
browser solver in tests/no-phantom-hit.mjs.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import optimise  # noqa: E402

POS = ["GKP"] * 2 + ["DEF"] * 5 + ["MID"] * 5 + ["FWD"] * 3
GWS = [11, 12]


def case():
    """15 owned players on 0.5 xP, five far better ones (12 xP in GW12) at the same price, each from his own club."""
    players = {k: {"pos": p, "team": k, "price": 5.0, "ok": True, "xp": {g: 0.5 for g in GWS}} for k, p in enumerate(POS, 1)}
    for k, p in enumerate(["DEF", "MID", "MID", "FWD", "DEF"], 16):
        players[k] = {"pos": p, "team": k, "price": 5.0, "ok": True, "xp": {11: 0.5, 12: 12.0}}
    return players, list(range(1, 16))


class NoPhantomHit(unittest.TestCase):
    def test_roll_then_one_hit_at_most(self):
        players, squad = case()
        r = optimise.solve(players, squad, {}, 0.0, 1, GWS, max_hits=1, week1_moves=0, time_limit=20)
        self.assertIsNotNone(r, optimise.LAST_FAIL[0])
        ft = 1
        for wk in r["weeks"]:
            n = len(wk["in"])
            self.assertEqual(wk["ft"], ft, f"GW{wk['gw']}: free transfers")
            self.assertEqual(wk["hits"], max(0, n - ft), f"GW{wk['gw']}: {wk['hits']} hits for {n} moves on {ft} FT")
            ft = 1 if n > ft else min(5, ft - n + 1)
        # before the fix: GW11 1 hit and no moves, GW12 4 moves on 3 FT
        self.assertEqual(r["weeks"][0]["hits"], 0)
        self.assertLessEqual(len(r["weeks"][1]["in"]), 3)   # 2 free transfers + Chase rank's one hit

    def test_no_hit_without_moves_beyond_free_transfers(self):
        players, squad = case()
        for ft0 in (1, 2, 3):
            r = optimise.solve(players, squad, {}, 0.0, ft0, GWS, max_hits=2, time_limit=20)
            for wk in r["weeks"]:
                self.assertEqual(wk["hits"], max(0, len(wk["in"]) - wk["ft"]), f"ft0 {ft0} GW{wk['gw']}")


if __name__ == "__main__":
    unittest.main()
