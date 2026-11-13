"""FL-065: a player's past xG counts for the club he played for that week, and his past opponents are that club's,
in the live model (FL-068 did it for backtests only). A summer mover's GW1-2 xG used to inflate his new club's attack
rating, and his GW1-2 form was judged against his new club's opponents.
Ambiguous (one game at a club he has since left): his xG goes to no club and his opponent adjustment is off that
week; build.py lists those player-weeks in meta.club_ambiguous and validate.py warns.
"""
import unittest

from fplmodel import DEFAULTS, clubs_then, prepare, team_ratings
import validate
from tests.test_honest_backtest import fx, row


def ctx_mover():
    # player 7: at club 3 for GW1-2 (v 4, v 5), at club 1 since (GW3 v 2). Player 8 stays at club 2 throughout.
    els = [dict(id=7, team=1, element_type=4, status="a", chance_of_playing_next_round=None, news_added=None, news=""),
           dict(id=8, team=2, element_type=4, status="a", chance_of_playing_next_round=None, news_added=None, news="")]
    boot = {"elements": els, "teams": [{"id": t} for t in range(1, 6)],
            "events": [dict(id=g, finished=True) for g in (1, 2, 3)], "game_config": {"scoring": {}}}
    fixtures = [fx(1, 1, 3, 4, 1), fx(2, 2, 5, 3, 8), fx(3, 3, 1, 2, 15)]
    live = {1: {"elements": [row(7, 1, xg="0.90")]}, 2: {"elements": [row(7, 2, xg="0.60")]},
            3: {"elements": [row(7, 3, xg="0.30"), row(8, 3, xg="0.10")]}}
    return prepare(boot, fixtures, live)


class ClubThen(unittest.TestCase):
    def test_default_on(self):
        self.assertTrue(DEFAULTS["xg_club_then"])

    def test_clubs_map(self):
        ctx = ctx_mover()
        self.assertEqual((ctx["club_then"][(7, 1)], ctx["club_then"][(7, 2)], ctx["club_then"][(7, 3)]), (3, 3, 1))

    def test_live_team_xg_goes_to_the_club_then(self):
        ctx = ctx_mover()
        P = dict(DEFAULTS)
        orig = ctx["team_gw_xg_then"]
        self.assertAlmostEqual(orig[3][1] + orig[3][2], 1.5)
        self.assertAlmostEqual(orig[1][1] + orig[1][2], 0.0)
        self.assertAlmostEqual(ctx["team_gw_xg"][1][1] + ctx["team_gw_xg"][1][2], 1.5)   # the old, today's-club view
        r_new, _ = team_ratings(ctx, 4, P)
        r_old, _ = team_ratings(ctx, 4, dict(P, xg_club_then=False))
        self.assertLess(r_new[1]["att"], r_old[1]["att"])     # club 1 no longer gets his GW1-2 xG
        self.assertGreater(r_new[3]["att"], r_old[3]["att"])

    def test_ambiguous_week_warns(self):
        w = []
        validate.check_club_then({"club_ambiguous": [[7, 1]]}, w)
        self.assertIn("player 7 GW1", w[0])
        w = []
        validate.check_club_then({}, w)
        self.assertEqual(w, [])


if __name__ == "__main__":
    unittest.main()
