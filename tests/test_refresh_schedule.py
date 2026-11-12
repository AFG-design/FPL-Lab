"""FL-111: the refresh runs hourly outside match windows and every 10 minutes during matches, and every place that
states the cadence (README, validate.py's gap warning, the Data health page, CLAUDE.md) says the same."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
read = lambda p: (ROOT / p).read_text()


class RefreshSchedule(unittest.TestCase):
    def test_workflow_is_hourly_plus_live(self):
        wf = read(".github/workflows/refresh.yml")
        crons = re.findall(r'cron: "([^"]+)"', wf)
        self.assertEqual(crons, ["7 * * * *", "*/10 * * * *"])
        self.assertIn("live = live or now.minute < 10", wf)       # off-match fallback: the first run of each hour
        self.assertNotIn("% 30", wf)

    def test_gap_warning_allows_for_hourly(self):
        import validate
        self.assertEqual(validate.GAP_MAX_MIN, 75)
        self.assertIn("scheduled hourly", read("validate.py"))

    def test_text_matches_the_schedule(self):
        for f in ("README.md", "validate.py", "CLAUDE.md", "site/js/views/health.js", "site/js/views/model.js",
                  "site/js/views/home.js", ".github/workflows/refresh.yml"):
            with self.subTest(f=f):
                t = read(f)
                self.assertNotRegex(t, r"(?i)every 30 minutes|twice an hour|every half hour|otherwise every 30")
        self.assertIn("maxGap > 75", read("site/js/views/health.js"))
        self.assertIn("otherwise hourly", read("site/js/views/health.js"))
        self.assertIn("scheduled hourly (at 7 minutes past)", read("README.md"))
        self.assertIn("more than 75 minutes earlier", read("README.md"))


if __name__ == "__main__":
    unittest.main()
