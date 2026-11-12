"""FL-060: the refresh must still build and validate after GW38's deadline, when FPL lists no next gameweek.

Runs the real build.py offline on recorded FPL responses turned into a season end the way FPL reports one: the current
gameweek is the last one, its matches are still being played and no event is marked is_next (tests/build_harness.py).
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_harness import ROOT, offline_build  # noqa: E402


class SeasonEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, cls.D, cls.rc, cls.cur = offline_build(cls)

    def test_builds_without_a_next_gameweek(self):
        m = self.D["meta"]
        self.assertIsNone(m["next_gw"])
        self.assertTrue(m["season_over"])
        self.assertEqual((m["cur_gw"], m["last_gw"]), (self.cur, self.cur))
        self.assertEqual(m["proj_gws"], [])
        self.assertEqual(self.D["plans"], {})

    def test_keeps_players_and_team_ratings(self):
        # live scores, Review and season stats need every player's row even with nothing left to forecast
        self.assertGreater(len(self.D["players"]), 300)
        self.assertTrue(all(p["xp"] == {} for p in self.D["players"]))
        teams = self.D["teams"].values() if isinstance(self.D["teams"], dict) else self.D["teams"]
        self.assertTrue(all(t["att"] > 0 and t["def"] > 0 for t in teams))

    def test_validates_and_says_why(self):
        self.assertEqual(self.rc, 0, self.D["health"]["errors"])
        w = self.D["health"]["warnings"]
        self.assertTrue(any(x.startswith("Season over:") for x in w), w)
        self.assertFalse(any(x.startswith("No optimiser plans") for x in w), w)


class SeasonEndCheck(unittest.TestCase):
    """validate.check_season_end on its own: a missing next gameweek mid-season must stop the publish."""

    def check(self, **meta):
        sys.path.insert(0, str(ROOT))
        try:
            from validate import check_season_end
        finally:
            sys.path.remove(str(ROOT))
        errors, warnings = [], []
        check_season_end(meta, errors, warnings)
        return errors, warnings

    def test_in_season(self):
        self.assertEqual(self.check(next_gw=12, cur_gw=11, last_gw=38, proj_gws=[12]), ([], []))

    def test_older_data_without_the_flag(self):
        self.assertEqual(self.check(next_gw=12, cur_gw=11), ([], []))

    def test_no_next_gameweek_mid_season_is_an_error(self):
        errors, _ = self.check(next_gw=None, season_over=True, cur_gw=20, last_gw=38, proj_gws=[])
        self.assertEqual(len(errors), 1)
        self.assertIn("not the last", errors[0])

    def test_flag_disagrees_with_next_gw(self):
        errors, _ = self.check(next_gw=None, season_over=False, cur_gw=38, last_gw=38)
        self.assertIn("season_over is False", errors[0])
        errors, _ = self.check(next_gw=39, season_over=True, cur_gw=38, last_gw=38)
        self.assertIn("season_over is True", errors[0])

    def test_older_data_with_no_next_gameweek_is_not_checked(self):
        self.assertEqual(self.check(next_gw=None, cur_gw=38), ([], []))

    def test_season_end_without_last_gw(self):
        errors, _ = self.check(next_gw=None, season_over=True, cur_gw=38, proj_gws=[])
        self.assertEqual(len(errors), 1)

    def test_season_end(self):
        errors, warnings = self.check(next_gw=None, season_over=True, cur_gw=38, last_gw=38, proj_gws=[], plan_gws=[])
        self.assertEqual(errors, [])
        self.assertTrue(warnings[0].startswith("Season over: GW38"))


if __name__ == "__main__":
    unittest.main()
