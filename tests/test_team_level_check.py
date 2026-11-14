"""FL-114: tools/team_level_check.py reads each side's goals the right way round and reports real/projected."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import team_level_check as tl


class FakeProject:
    """project() stand-in: one match, club 1 at home to club 2, expected goals 2.0 v 0.5."""
    def __call__(self, ctx, k, h, params):
        return {"upcoming": {1: {k: [(2, True, 2.0, 0.5, 2)]}, 2: {k: [(1, False, 0.5, 2.0, 5)]}}}


class Rows(unittest.TestCase):
    def test_home_and_away_sides(self):
        tl.project = FakeProject()
        ctx = {"fixtures": [{"event": 5, "team_h": 1, "team_a": 2, "team_h_score": 3, "team_a_score": 0}]}
        rows = sorted(tl.season(ctx, [5], {"cs_k": 1.0}), key=lambda r: r[1])
        self.assertEqual([(r[1], r[2], r[3], r[5]) for r in rows], [(2, 2.0, 3, 1), (5, 0.5, 0, 0)])   # home kept a CS
        self.assertIn("goals proj 1.25 v real 1.50", tl.summary(rows))

    def test_unplayed_match_skipped(self):
        tl.project = FakeProject()
        ctx = {"fixtures": [{"event": 5, "team_h": 1, "team_a": 2, "team_h_score": None, "team_a_score": None}]}
        self.assertEqual(tl.season(ctx, [5], {}), [])


if __name__ == "__main__":
    unittest.main()
