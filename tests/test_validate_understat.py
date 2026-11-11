"""validate.check_understat: a missing or stale Understat file is surfaced on the Health page."""
import unittest

import validate

BUILT = "2026-11-10T19:39:57+00:00"


def run(understat="absent", finished=100):
    meta = {"built": BUILT}
    if finished is not None:
        meta["finished_fixtures"] = finished
    if understat != "absent":
        meta["understat"] = understat
    warnings = []
    validate.check_understat(meta, warnings)
    return warnings


class Understat(unittest.TestCase):
    def test_complete_is_quiet(self):
        self.assertEqual(run({"matches": 100, "built": "2026-11-01T00:00:00Z"}), [])   # old stamp, nothing missing
        self.assertEqual(run({"matches": 101, "built": "2026-11-10T19:00:00Z"}), [])

    def test_recently_updated_and_slightly_behind_is_quiet(self):
        self.assertEqual(run({"matches": 96, "built": "2026-11-10T07:00:00Z"}), [])
        self.assertEqual(run({"matches": 96, "built": "2026-11-09T07:39:57Z"}), [])   # exactly 36 hours

    def test_stale_and_behind_warns(self):
        w = run({"matches": 89, "built": "2026-11-01T20:46:53Z"})
        self.assertEqual(len(w), 1)
        self.assertIn("89 of 100 finished matches", w[0])
        self.assertIn("9 days ago", w[0])

    def test_unreadable_stamp_counts_as_stale(self):
        for stamp in (None, "soon", 7):
            with self.subTest(stamp=stamp):
                w = run({"matches": 89, "built": stamp})
                self.assertIn("last update time unknown", w[0])
        self.assertIn("last update time unknown", run({"matches": 89})[0])

    def test_missing_data_warns(self):
        for us in ("absent", None, {}, {"built": BUILT}, {"matches": "89"}):
            with self.subTest(us=us):
                self.assertIn("No Understat data", run(us)[0])

    def test_older_builds_are_not_checked(self):
        self.assertEqual(run(None, finished=None), [])

    def test_before_the_season_nothing_is_behind(self):
        self.assertEqual(run({"matches": 0, "built": "2026-08-01T00:00:00Z"}, finished=0), [])


if __name__ == "__main__":
    unittest.main()
