"""Collector integration tests with a fake clock and API: never spend real credits."""
import copy
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import odds_players as odds

UTC = dt.timezone.utc
DEADLINE = dt.datetime(2026, 11, 21, 11, tzinfo=UTC)


class Collector(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / 'odds/players.json'
        self.hist = Path(self.tmp.name) / 'history'
        self.path = self.hist / 'player_odds_gw11.json'
        self.left = 500
        self.names = ['Unknown A']
        self.boot = {'events': [{'id': 11, 'is_next': True, 'deadline_time': DEADLINE.isoformat()}],
                     'teams': [{'id': 1, 'name': 'Arsenal', 'short_name': 'ARS'},
                               {'id': 2, 'name': 'Chelsea', 'short_name': 'CHE'}],
                     'elements': [dict(id=i, team=1, element_type=pos, first_name=first,
                                       second_name=last, web_name=last)
                                  for i, pos, first, last in [(1, 3, 'Test', 'Player'), (2, 1, 'Test', 'Keeper'),
                                                            (3, 4, 'Other', 'Forward')]]}
        self.fixture = {'id': 100, 'event': 11, 'team_h': 1, 'team_a': 2, 'kickoff_time': DEADLINE.isoformat()}
        self.paid = []
        for name, value in [('OUT', str(self.out)), ('HIST', str(self.hist)), ('REGIONS', 'us')]:
            p = patch.object(odds, name, value); p.start(); self.addCleanup(p.stop)
        p = patch.dict('os.environ', {'ODDS_API_KEY': 'fake', 'ODDS_FORCE': ''}); p.start(); self.addCleanup(p.stop)
        p = patch.object(odds, 'fpl', side_effect=lambda path: self.boot if 'bootstrap' in path else [self.fixture])
        p.start(); self.addCleanup(p.stop)
        p = patch.object(odds, 'get', side_effect=self.api); p.start(); self.addCleanup(p.stop)

    def api(self, path, **params):
        if path.endswith('/events'):
            return [dict(id='event', home_team='Arsenal', away_team='Chelsea', commence_time=DEADLINE.isoformat())], self.left, 0
        self.paid.append(params)
        self.left -= 2
        goal = [dict(description=n, name='Yes', price=4) for n in ['Test Player', 'Test Keeper'] + self.names]
        assists = [dict(description='Test Player', name='Over', point=0.5, price=5),
                   dict(description='Test Player', name='Under', point=0.5, price=1.1),
                   dict(description='Other Forward', name='Over', point=0.5, price=4)]
        return {'bookmakers': [{'key': 'book', 'markets': [dict(key='player_goal_scorer_anytime', outcomes=goal),
                                                         dict(key='player_assists', outcomes=assists)]}]}, self.left, 2

    def run_at(self, hours, force=False):
        class Clock(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return DEADLINE - dt.timedelta(hours=hours)
        with patch.object(odds.dt, 'datetime', Clock), patch.dict('os.environ', {'ODDS_FORCE': '1' if force else ''}):
            odds.main()

    def test_three_checkpoints_are_kept_and_repeat_spends_nothing(self):
        saved = {}
        for h in (72, 24, 3):
            self.run_at(h)
            history = odds.load_json(self.path)
            for label, snapshot in saved.items():
                self.assertEqual(history['snapshots'][label], snapshot)
            saved[str(h)] = copy.deepcopy(history['snapshots'][str(h)])
        self.assertEqual(set(history['snapshots']), {'72', '24', '3'})
        self.assertEqual(history['fixtures'], saved['3']['fixtures'])  # Health/latest-reader compatibility
        before = self.path.read_bytes()
        self.run_at(2, force=True)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(len(self.paid), 3)
        self.assertEqual(sum(s['credits_used'] for s in saved.values()), 6)  # one fixture, two markets, three runs
        self.assertTrue(all(p['regions'] == 'us' and p['markets'] == odds.MARKETS for p in self.paid))

    def test_unmatched_names_accumulate_and_deduplicate(self):
        for h, names in [(72, ['Unknown A']), (24, ['Unknown A', 'Unknown B']), (3, ['Unknown B', 'Unknown C'])]:
            self.names = names
            self.run_at(h)
        expected = [f'Unknown {x} (ARS-CHE)' for x in 'ABC']
        self.assertEqual(odds.load_json(self.out)['unmatched_players'], expected)
        hist = odds.load_json(self.path)
        self.assertEqual(hist['unmatched_players'], expected)
        self.assertEqual(hist['snapshots']['72']['unmatched_players'], expected[:1])

    def test_raw_assist_fair_pair_goals_and_keeper(self):
        self.run_at(72)
        rows = odds.load_json(self.path)['fixtures']['100']['players']
        self.assertNotIn('2', rows)
        self.assertEqual(rows['1']['p_score'], .25)
        self.assertEqual(rows['1']['p_assist_raw'], .2)
        self.assertEqual(rows['1']['p_assist'], round(.2 / (.2 + 1 / 1.1), 4))
        self.assertEqual(rows['1']['assist_pairs'], 1)
        self.assertEqual(rows['3']['p_assist_raw'], .25)
        self.assertNotIn('p_assist', rows['3'])  # never pretend Over-only prices are fair

    def test_all_unmatched_names_survive_an_unsaved_checkpoint(self):
        self.boot['elements'] = []
        with self.assertRaisesRegex(ValueError, 'No outfield player odds'):
            self.run_at(72)
        self.assertIn('Unknown A (ARS-CHE)', odds.load_json(self.out)['unmatched_players'])
        self.assertFalse(self.path.exists())
        self.names = ['Unknown B']
        with self.assertRaisesRegex(ValueError, 'No outfield player odds'):
            self.run_at(24)
        names = odds.load_json(self.out)['unmatched_players']
        self.assertIn('Unknown A (ARS-CHE)', names)
        self.assertIn('Unknown B (ARS-CHE)', names)
        self.assertEqual(len(names), len(set(names)))

    def test_real_old_gw8_loads_as_one_snapshot_without_rewrite(self):
        path = Path(odds.HERE) / 'history/player_odds_gw8.json'
        before = path.read_bytes()
        data = odds.load_json(path)
        self.assertEqual(odds.snapshots(data), {'legacy': data})
        self.assertEqual(path.read_bytes(), before)
        self.assertNotIn('snapshots', data)

    def test_legacy_history_is_not_migrated_even_when_forced(self):
        self.hist.mkdir()
        self.path.write_text('{"gw":11,"built":"legacy","fixtures":{}}')
        before = self.path.read_bytes()
        self.run_at(3, force=True)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.paid, [])

    def test_corrupt_history_fails_without_replacing_it(self):
        self.hist.mkdir(); self.path.write_text('{broken')
        with self.assertRaises(json.JSONDecodeError):
            self.run_at(72)
        self.assertEqual(self.path.read_text(), '{broken')
        self.assertEqual(self.paid, [])

    def test_force_cannot_collect_after_deadline(self):
        self.run_at(-1, force=True)
        self.assertEqual(self.paid, [])
        self.assertFalse(self.path.exists())

    def test_missing_credit_header_refuses_paid_request(self):
        self.left = None
        with self.assertRaisesRegex(ValueError, 'remaining credits'):
            self.run_at(72)
        self.assertEqual(self.paid, [])

    def test_credit_reserve_is_not_spent(self):
        self.left = 41
        with self.assertRaisesRegex(ValueError, 'No outfield player odds'):
            self.run_at(72)
        self.assertEqual(self.paid, [])
        self.assertFalse(self.path.exists())

    def test_multiple_regions_rejected_before_paid_request(self):
        with patch.object(odds, 'REGIONS', 'us,uk'), self.assertRaisesRegex(ValueError, 'one region'):
            self.run_at(72)
        self.assertEqual(self.paid, [])

    def test_missing_file_has_no_snapshots(self):
        self.assertEqual(odds.snapshots(odds.load_json(self.path)), {})


if __name__ == '__main__':
    unittest.main()
