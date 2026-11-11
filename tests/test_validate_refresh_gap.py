"""validate.check_refresh_gap: late refreshes close to a deadline are surfaced, everything else stays quiet."""
import unittest

import validate


def meta(built="2026-11-21T08:00:00+00:00", deadline="2026-11-21T11:00:00Z", **extra):
    return {"built": built, "deadline": deadline, "next_gw": 11, **extra}


def run(m):
    warnings = []
    validate.check_refresh_gap(m, warnings)
    return warnings


class RefreshGap(unittest.TestCase):
    def test_regular_refresh_is_quiet(self):
        self.assertEqual(run(meta(prev_built="2026-11-21T07:30:00+00:00")), [])
        self.assertEqual(run(meta(prev_built="2026-11-21T07:15:00+00:00")), [])   # exactly 45 minutes

    def test_long_gap_inside_the_window_warns(self):
        w = run(meta(prev_built="2026-11-21T00:06:00+00:00"))
        self.assertEqual(len(w), 1)
        self.assertIn("7.9 h since the previous refresh", w[0])
        self.assertIn("3.0 h before the GW11 deadline", w[0])

    def test_long_gap_outside_the_window_is_quiet(self):
        early = meta(built="2026-11-21T04:59:00+00:00", prev_built="2026-11-20T20:00:00+00:00")   # 6 h 1 min left
        self.assertEqual(run(early), [])
        passed = meta(built="2026-11-21T11:00:00+00:00", prev_built="2026-11-21T02:00:00+00:00")  # at the deadline
        self.assertEqual(run(passed), [])

    def test_unknown_previous_refresh_warns_inside_the_window(self):
        for prev in (None, "not a date", 5):
            with self.subTest(prev=prev):
                w = run(meta(prev_built=prev))
                self.assertEqual(len(w), 1)
                self.assertIn("Refresh gap unknown", w[0])
        self.assertEqual(run(meta(built="2026-11-20T08:00:00+00:00", prev_built=None)), [])   # far from the deadline

    def test_older_data_and_missing_deadline_are_not_checked(self):
        self.assertEqual(run(meta()), [])                                         # built before this field existed
        self.assertEqual(run(meta(deadline=None, prev_built=None)), [])           # season over: no deadline
        self.assertEqual(run(meta(built="garbage", prev_built=None)), [])

    def test_z_suffix_timestamps(self):
        w = run(meta(built="2026-11-21T08:00:00Z", prev_built="2026-11-21T06:00:00Z"))
        self.assertIn("2.0 h since the previous refresh", w[0])


if __name__ == "__main__":
    unittest.main()
