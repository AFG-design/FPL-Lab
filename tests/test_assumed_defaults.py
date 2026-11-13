"""FL-082: the remaining silent defaults are written down or marked assumed.

  - make_priors.py summed starts and dropped them, so fplmodel guessed a start rate from minutes; it now writes
    start_rate (share of the club's 38 games started). A season with no starts field: no start_rate (never guessed
    here), and validate.py warns how many priors lack it.
  - crowd.py centred the rank band on 100,000 when FPL gave no overall rank, and wrote "complete": true whatever
    failed. It now marks rank_assumed and counts failed requests; validate.py warns on Health, the Rivals label says
    the rank was assumed.
The new-signing minutes defaults (fplmodel) are left to FL-030, which replaces them.
"""
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import make_priors as mp
import validate

ROOT = Path(__file__).resolve().parent.parent


def season(name, minutes, starts=None):
    s = {"season_name": name, "minutes": minutes, "expected_goals": "1.0", "expected_assists": "1.0", "bonus": 5,
         "saves": 0, "yellow_cards": 1, "total_points": 80, "expected_goal_involvements": "2.0"}
    if starts is not None:
        s["starts"] = starts
    return s


class StartRate(unittest.TestCase):
    def test_written_from_starts(self):
        p = mp.summarise([season("2024/25", 1900, 19), season("2025/26", 3420, 38)], 2026)
        self.assertAlmostEqual(p["start_rate"], (19 + 2 * 38) / (38 * 3), 6)

    def test_missing_starts_is_not_guessed(self):
        p = mp.summarise([season("2024/25", 1900, 19), season("2025/26", 3420)], 2026)
        self.assertNotIn("start_rate", p)

    def test_committed_priors_have_it(self):
        pp = json.load(open(ROOT / "priors.json"))["players"]
        self.assertTrue(pp and all(0 <= v["start_rate"] <= 1 for v in pp.values()))


class CrowdFlags(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "priors.json").write_text(json.dumps({"built": "2026-11-09T12:58:32Z", "players": {}}))
        self.D = {"meta": {"built": "2026-11-10T19:39:57+00:00", "cur_gw": 10, "priors_season": "2025/26",
                           "odds": {"built": "2026-11-10T19:38:46Z", "matches": 110, "upcoming": 0}},
                  "crowd": {"gw": 10, "complete": True, "failed": 0, "rank_assumed": False}}

    def run_check(self):
        w = []
        with patch.object(validate, "HERE", str(self.root)):
            validate.check_sources(self.D, w)
        return w

    def test_quiet_when_complete(self):
        self.assertEqual(self.run_check(), [])
        self.D["crowd"] = {"gw": 10}                       # a sample from before FL-082: not known, not warned
        self.assertEqual(self.run_check(), [])

    def test_failed_requests_and_assumed_rank_warn(self):
        self.D["crowd"].update(complete=False, failed=7, rank_assumed=True)
        w = " | ".join(self.run_check())
        self.assertIn("7 FPL requests failed", w)
        self.assertIn("assumed 100,000", w)

    def test_crowd_script_marks_them(self):
        src = (ROOT / "crowd.py").read_text()
        self.assertNotIn('"complete": True', src)
        self.assertIn('rank_assumed=rank_assumed', src)
        self.assertTrue(re.search(r'"complete": not FAILED', src))

    def test_rivals_label_says_assumed(self):
        self.assertIn("rank_assumed", (ROOT / "site" / "js" / "views" / "rivals.js").read_text())


if __name__ == "__main__":
    unittest.main()
