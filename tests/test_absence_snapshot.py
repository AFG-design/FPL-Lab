import datetime as dt
import os
import tempfile
import unittest
from deadline_snapshot import absence_snapshot_due

UTC = dt.timezone.utc
DEADLINE = '2026-10-23T17:30:00Z'   # GW8's real deadline; absence_gw8.json was built at 19:43, after it


class AbsenceSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, 'absence_gw8.json')
        self.next_ev = {'id': 8, 'deadline_time': DEADLINE}

    def tearDown(self):
        self.dir.cleanup()

    def due(self, gw=8, next_ev=None, now=dt.datetime(2026, 10, 23, 16, 0, tzinfo=UTC)):
        return absence_snapshot_due(self.path, gw, self.next_ev if next_ev is None else next_ev, now)

    def test_next_gw_before_deadline_writes(self):
        self.assertEqual(self.due(), (True, ''))
        self.assertTrue(self.due(now=dt.datetime(2026, 10, 23, 17, 29, 59, tzinfo=UTC))[0])

    def test_after_deadline_does_not_write(self):
        for now in [dt.datetime(2026, 10, 23, 17, 30, tzinfo=UTC),      # at the deadline
                    dt.datetime(2026, 10, 23, 19, 43, 12, tzinfo=UTC)]:  # when the real gw8 file was built
            with self.subTest(now=now):
                due, why = self.due(now=now)
                self.assertFalse(due)
                self.assertIn('deadline has passed', why)

    def test_current_gw_does_not_write(self):
        # the old guard allowed cur_gw: GW8 under way, GW9 next, so GW8's deadline has gone
        due, why = self.due(gw=8, next_ev={'id': 9, 'deadline_time': '2026-10-31T11:00:00Z'},
                            now=dt.datetime(2026, 10, 24, 12, 0, tzinfo=UTC))
        self.assertFalse(due)
        self.assertIn('not the next gameweek', why)

    def test_later_gw_and_season_over_do_not_write(self):
        self.assertFalse(self.due(gw=9)[0])            # written once GW9 is next, not now
        self.assertFalse(absence_snapshot_due(self.path, 8, None)[0])

    def test_existing_file_is_not_overwritten(self):
        with open(self.path, 'w') as f:
            f.write('{"gw": 8}')
        self.assertEqual(self.due(), (False, 'already written'))
        with open(self.path) as f:
            self.assertEqual(f.read(), '{"gw": 8}')

    def test_missing_deadline_fails_loudly(self):
        with self.assertRaisesRegex(ValueError, 'no deadline_time'):
            self.due(next_ev={'id': 8})


if __name__ == '__main__':
    unittest.main()
