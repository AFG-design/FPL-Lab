"""Live scores must never be interpreted as a complete match's xG."""
import copy
import unittest

from fplmodel import DEFAULTS, prepare, team_ratings


def fixture(gw, home, away, hs=2, aas=1, finished=True):
    return dict(id=gw * 100 + home * 10 + away, event=gw, team_h=home, team_a=away,
                team_h_score=hs, team_a_score=aas, finished=finished)


class LiveRatings(unittest.TestCase):
    def setUp(self):
        self.boot = {'teams': [{'id': t} for t in range(1, 5)], 'events': [],
                     'elements': [dict(id=t, team=t, element_type=3, status='a') for t in range(1, 5)],
                     'game_config': {'scoring': {}}}
        self.past = [fixture(1, 1, 2, 3, 0), fixture(1, 3, 4, 1, 2)]
        self.live = {g: {'elements': [dict(id=t, stats=dict(expected_goals=str(t / 3), total_points=t), explain=[])
                                     for t in range(1, 5)]} for g in (1, 2)}
        self.params = dict(DEFAULTS, mkt_w=0)

    def ctx(self, fixtures, live=None):
        return prepare(self.boot, fixtures, self.live if live is None else live)

    def ratings(self, fixtures, live=None):
        return team_ratings(self.ctx(fixtures, live), 3, self.params)

    def test_score_at_kickoff_is_exactly_neutral(self):
        upcoming = fixture(2, 1, 2, None, None, False)
        before = self.ratings(self.past + [upcoming])
        for score in ((0, 0), (1, 0), (2, 3)):
            with self.subTest(score=score):
                active = dict(upcoming, team_h_score=score[0], team_a_score=score[1])
                self.assertEqual(self.ratings(self.past + [active]), before)
        self.assertEqual(before, self.ratings(self.past, {1: self.live[1]}))

    def test_partial_double_omits_whole_week_for_pending_team(self):
        first = fixture(2, 1, 2, 4, 1)
        second = fixture(2, 1, 3, None, None, False)
        ctx = self.ctx(self.past + [first, second])
        self.assertNotIn(2, ctx['pstats'][1])
        self.assertNotIn(2, ctx['team_gw_xg'][1])
        self.assertNotIn((1, 2), ctx['opp_of'])
        # Neither the unfinished match nor the completed match with unavailable opponent xG affects ratings.
        self.assertEqual(team_ratings(ctx, 3, self.params), self.ratings(self.past, {1: self.live[1]}))
        # A team with no remaining fixture still has its complete GW stats and opponent adjustment.
        self.assertIn(2, ctx['pstats'][2])
        self.assertEqual(ctx['opp_of'][(2, 2)], [1])
        self.assertEqual(self.ratings(self.past + [first, dict(second, team_h_score=0, team_a_score=0)]),
                         team_ratings(ctx, 3, self.params))

    def test_completed_teams_in_a_live_gameweek_still_count(self):
        complete = fixture(2, 3, 4, 5, 0)
        active = fixture(2, 1, 2, 0, 0, False)
        ctx = self.ctx(self.past + [complete, active])
        self.assertIn(2, ctx['team_gw_xg'][3])
        self.assertEqual(ctx['opp_of'][(3, 2)], [4])
        self.assertEqual(team_ratings(ctx, 3, self.params), self.ratings(self.past + [complete]))
        self.assertNotEqual(team_ratings(ctx, 3, self.params), self.ratings(self.past, {1: self.live[1]}))

    def test_complete_double_counts_both_matches_and_all_xg(self):
        games = self.past + [fixture(2, 1, 2, 4, 1), fixture(2, 1, 3, 3, 0)]
        ctx = self.ctx(games)
        self.assertEqual(ctx['opp_of'][(1, 2)], [2, 3])
        self.assertAlmostEqual(ctx['team_gw_xg'][1][2], 1 / 3)
        self.assertIn(2, ctx['pstats'][1])
        self.assertNotEqual(team_ratings(ctx, 3, self.params), self.ratings(self.past, {1: self.live[1]}))

    def test_missing_or_provisional_finished_flag_is_not_completion(self):
        active = fixture(2, 1, 2, 1, 1, False)
        for missing in (False, True):
            f = dict(active, finished_provisional=True)
            if missing:
                del f['finished']
            ctx = self.ctx(self.past + [f])
            self.assertNotIn(2, ctx['team_gw_xg'][1])
            self.assertNotIn((1, 2), ctx['opp_of'])
            self.assertEqual(team_ratings(ctx, 3, self.params), self.ratings(self.past, {1: self.live[1]}))

    def test_already_filtered_live_rows_give_identical_ratings(self):
        fixtures = self.past + [fixture(2, 1, 2, 0, 0, False)]
        filtered = copy.deepcopy(self.live)
        filtered[2]['elements'] = [p for p in filtered[2]['elements'] if p['id'] not in (1, 2)]
        self.assertEqual(self.ratings(fixtures), self.ratings(fixtures, filtered))


if __name__ == '__main__':
    unittest.main()
