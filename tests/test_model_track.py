"""FL-145: the Model page's track record, from saved pre-deadline files only (model_track.py)."""
import json
import os
import tempfile
import unittest

import model_track as mt

FX = [dict(event=10, team_h=1, team_a=2), dict(event=10, team_h=3, team_a=1)]   # club 1 has a double in GW10
LIVE = {10: {"elements": [{"id": 5, "stats": {"starts": 1, "minutes": 90, "total_points": 9}},
                          {"id": 6, "stats": {"starts": 0, "minutes": 0, "total_points": 0}},
                          {"id": 7, "stats": {"starts": 1, "minutes": 180, "total_points": 4}}]}}
LOG = """# log
## 12 Nov 2026 — FL-113: priors (Adopt as Marginal)
## 13 Nov 2026 — FL-031: rules tested (no change; Don't adopt)
## 13 Nov 2026 — FL-131: shadow re-landed (shadow only; no live change)
## 8 Nov 2026 — FL-062: team ratings skip unfinished matches
## 6 Nov 2026 — FL-999: logged on the GW10 deadline day (Adopt)
## 1 Nov 2026 — backtest hindsight removed (PR #39)
"""


class Track(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        h = self.h = self.tmp.name
        json.dump({"mins": {"5": [0.8, 0.1, 70], "6": [0.4, 0.2, 40], "7": [0.9, 0.0, 80], "8": [None, None, 0]}},
                  open(os.path.join(h, "deadline_gw10.json"), "w"))
        json.dump({"players": {"5": [3.0], "6": [2.0], "7": [5.0]}}, open(os.path.join(h, "proj_gw10.json"), "w"))
        json.dump({"players": {}}, open(os.path.join(h, "proj_gw9.json"), "w"))

    def test_start_brier_singles_only(self):
        r = mt.start_brier(self.h, [9, 10], LIVE, FX, {5: 2, 6: 3, 7: 1})
        # player 7's club played twice: left out; 5 started (0.8), 6 didn't (0.4): ((0.2)^2 + (0.4)^2) / 2
        self.assertEqual(r, [{"gw": 10, "n": 2, "brier": 0.1, "chance": 0.6, "started": 0.5}])

    def test_misses(self):
        r = mt.misses(self.h, [10], LIVE)
        self.assertEqual(r, [{"gw": 10, "n": 3, "big": 1, "mae": round((6 + 2 + 1) / 3, 3)}])

    def test_downloads(self):
        d = mt.downloads(self.h)
        self.assertEqual([x["gw"] for x in d], [9, 10])
        self.assertIsNone(d[0]["deadline"])
        self.assertTrue(d[1]["deadline"].endswith("/history/deadline_gw10.json"))

    def test_versions_only_live_changes_and_deadline_day_assumed(self):
        labels = [t for _, t in mt.adopted(LOG)]
        self.assertEqual(labels, ["FL-999: logged on the GW10 deadline day", "FL-062: team ratings skip unfinished matches",
                                  "FL-113: priors"])
        v = mt.versions(LOG, [(10, "2026-11-06T18:30:00Z"), (11, "2026-11-21T11:00:00Z")])
        self.assertEqual(v[0]["changes"], [])
        self.assertEqual(v[1]["changes"], labels)
        self.assertTrue(v[1]["assumed"])


if __name__ == "__main__":
    unittest.main()
