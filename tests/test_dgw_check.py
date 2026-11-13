"""FL-053: tools/dgw_check.py finds each club's double weeks and its single-match weeks around them."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import dgw_check  # noqa: E402


class Kinds(unittest.TestCase):
    def test_double_and_nearby_singles(self):
        fx = [dict(event=g, team_h=1, team_a=2) for g in range(1, 12)] + [dict(event=6, team_h=3, team_a=1)]
        kinds = dgw_check.week_kinds(dgw_check.fixture_counts(fx), window=2)
        self.assertEqual(kinds[(1, 6)], "double")
        self.assertEqual([g for g in range(1, 12) if kinds.get((1, g)) == "near single"], [4, 5, 7, 8])
        self.assertIsNone(kinds.get((2, 6)))   # club 2 has no double, so none of its weeks count

    def test_bootstrap_interval_contains_the_mean(self):
        lo, hi = dgw_check.boot([(1, 0.1), (1, 0.3), (2, -0.2), (3, 0.5)])
        self.assertLessEqual(lo, 0.175)
        self.assertGreaterEqual(hi, 0.175)


if __name__ == "__main__":
    unittest.main()
