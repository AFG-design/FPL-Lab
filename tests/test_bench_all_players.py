"""FL-137: bench.py prints an "all players" line next to the pool, with the outside-pool group on its own."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bench  # noqa: E402


def ctx():
    # 1: regular (played GW4-6), 2: returner (no minutes GW4-6), 3: didn't play GW7, 4: played but no projection
    pstats = {1: {g: {"minutes": 90} for g in (4, 5, 6, 7)}, 2: {7: {"minutes": 70}},
              3: {g: {"minutes": 90} for g in (4, 5, 6)} | {7: {"minutes": 0}}, 4: {7: {"minutes": 20}}}
    pts = {1: {7: 6}, 2: {7: 2}, 3: {7: 0}, 4: {7: 1}}
    els = {i: {"element_type": 3} for i in (1, 2, 3, 4)}
    return {"elements": els, "pstats": pstats, "pts_gw": pts}


class AllPlayers(unittest.TestCase):
    def test_rows_are_pool_plus_outside_appearances(self):
        pred = {1: 5.0, 2: 0.3, 3: 4.0}
        rows = bench.all_rows(ctx(), 7, pred)
        self.assertEqual(sorted((r[0], r[2], r[3], r[4]) for r in rows),
                         [(1, 5.0, 6, True), (2, 0.3, 2, False), (3, 4.0, 0, True), (4, 0.0, 1, False)])
        # the in-pool rows are exactly the pool (the regular, and the one who didn't play GW7, scored 0)
        self.assertEqual(sorted(r[:4] for r in rows if r[4]), sorted(bench.pool_rows(ctx(), 7, pred)))

    def test_score_and_line(self):
        m = bench.score_all({7: bench.all_rows(ctx(), 7, {1: 5.0, 2: 0.3, 3: 4.0})})
        self.assertEqual(m["all"]["n"], 4)
        self.assertEqual(m["outside"]["n"], 2)
        self.assertAlmostEqual(m["outside"]["pred"], 0.15)
        self.assertAlmostEqual(m["outside"]["real"], 1.5)
        line = bench.fmt_all("current model", m)
        self.assertIn("all players", line)
        self.assertIn("outside pool n=2 (50.0%) projected 0.15 v real 1.50", line)

    def test_empty(self):
        m = bench.score_all({})
        self.assertEqual(m["all"]["n"], 0)
        self.assertTrue(math.isnan(m["outside"]["mae"]))
        self.assertIn("n=    0", bench.fmt_all("x", m))


if __name__ == "__main__":
    unittest.main()
