"""FL-111: the refresh runs hourly, every 30 minutes in the 6 hours before a deadline and every 10 minutes during
matches (scripts/refresh_due.py), and every place that states the cadence says the same."""
import datetime as dt
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import refresh_due  # noqa: E402

read = lambda p: (ROOT / p).read_text()
T = lambda s: dt.datetime.fromisoformat(s)
EVENTS = [{"id": 11, "is_next": True, "deadline_time": "2026-11-21T11:00:00Z"}]
FIX = [{"kickoff_time": "2026-11-21T12:30:00Z"}]


def due(now, fixtures=FIX, events=EVENTS):
    return refresh_due.due(T(now), fixtures, events)[0]


class Due(unittest.TestCase):
    def test_hourly_far_from_a_deadline(self):
        self.assertTrue(due("2026-11-20T09:05:00+00:00"))
        self.assertFalse(due("2026-11-20T09:35:00+00:00"))

    def test_every_30_minutes_in_the_6_hours_before_the_deadline(self):
        for now, want in (("2026-11-21T05:05:00+00:00", True), ("2026-11-21T05:35:00+00:00", True),
                          ("2026-11-21T05:15:00+00:00", False), ("2026-11-21T10:35:00+00:00", True),
                          ("2026-11-21T04:55:00+00:00", False),   # 6 h 5 min before: not yet in the window
                          ("2026-11-21T04:35:00+00:00", False)):
            with self.subTest(now=now):
                self.assertEqual(due(now), want)

    def test_every_run_while_a_match_is_on(self):
        self.assertTrue(due("2026-11-21T13:15:00+00:00"))
        self.assertTrue(due("2026-11-21T12:25:00+00:00"))    # kicks off within 10 minutes
        self.assertFalse(due("2026-11-21T15:15:00+00:00"))   # 2 h 45 after kick-off, deadline passed: hourly

    def test_fpl_unreachable_or_season_over(self):
        self.assertTrue(due("2026-11-20T09:35:00+00:00", fixtures=None, events=None))    # deadline unknown: half hour
        self.assertFalse(due("2026-11-20T09:15:00+00:00", fixtures=None, events=None))
        self.assertFalse(due("2026-11-20T09:35:00+00:00", events=[]))                     # no next deadline: hourly
        self.assertEqual(refresh_due.DEADLINE_WINDOW_H, __import__("validate").GAP_WINDOW_H)


class Text(unittest.TestCase):
    def test_workflow(self):
        wf = read(".github/workflows/refresh.yml")
        self.assertEqual(re.findall(r'cron: "([^"]+)"', wf), ["7 * * * *", "*/10 * * * *"])
        self.assertIn("python3 scripts/refresh_due.py", wf)
        self.assertIn("sparse-checkout: scripts/refresh_due.py", wf)

    def test_gap_warning_matches_the_deadline_cadence(self):
        import validate
        self.assertEqual(validate.GAP_MAX_MIN, 45)

    def test_text_matches_the_schedule(self):
        for f in ("README.md", "validate.py", "CLAUDE.md", "site/js/views/health.js", "site/js/views/model.js",
                  "site/js/views/home.js", ".github/workflows/refresh.yml"):
            with self.subTest(f=f):
                self.assertNotRegex(read(f), r"(?i)twice an hour|every half hour|otherwise every 30|every 30 minutes \(")
        self.assertIn("every 30 minutes in the 6 hours before a deadline", read("site/js/views/health.js"))
        self.assertIn("every 30 minutes in the 6 hours before a deadline", read("README.md"))
        self.assertIn("more than 45 minutes earlier", read("README.md"))
        self.assertIn("every 30 minutes in the 6 hours before a deadline", read("CLAUDE.md"))


if __name__ == "__main__":
    unittest.main()
