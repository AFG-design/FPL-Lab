"""FL-113: priors from the last two calendar seasons only, and no silent shrinking of priors.json.

make_priors.py took a player's last two Premier League seasons however old (2015/16 for one player on 9 Nov 2026;
FPL xG is 0 before 2022/23), unlike archive.py, which the backtests use. Failed downloads shrank the file silently.
"""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import make_priors as mp
import validate


def season(name, minutes, xg=1.0):
    return {"season_name": name, "minutes": minutes, "expected_goals": str(xg), "expected_assists": "0.5", "bonus": 3,
            "saves": 0, "defensive_contribution": 10, "yellow_cards": 1, "total_points": 50, "starts": minutes // 90,
            "expected_goal_involvements": str(xg + 0.5)}


class Seasons(unittest.TestCase):
    def test_only_the_two_seasons_before_this_one(self):
        self.assertEqual(mp.window(2026), [2024, 2025])
        p = mp.summarise([season("2015/16", 3000, 0), season("2025/26", 900, 3.0)], 2026)
        self.assertEqual(p["season"], "2025/26")
        self.assertAlmostEqual(p["xg90"], 0.3)                  # 2015/16 (0 xG) no longer dilutes it
        self.assertIsNone(mp.summarise([season("2016/17", 340), season("2015/16", 75)], 2026))   # McNair-like: none
        p = mp.summarise([season("2024/25", 900, 1.0), season("2025/26", 1800, 4.0)], 2026)
        self.assertAlmostEqual(p["xg90"], (1.0 + 2 * 4.0) / (900 + 2 * 1800) * 90)            # 1:2 weights kept

    def test_zero_minute_season_and_unreadable_names_are_left_out(self):
        p = mp.summarise([season("2024/25", 2700), season("2025/26", 0)], 2026)
        self.assertEqual((p["season"], p["mins"]), ("2024/25", 2700))     # was 900: the empty season diluted it
        self.assertIsNone(mp.summarise([season("??", 900)], 2026))

    def test_no_xg_season_before_2022_23_even_with_an_early_window(self):
        self.assertEqual(mp.window(2022), [])
        self.assertEqual(mp.window(2023), [2022])


class Counts(unittest.TestCase):
    def test_sharp_drop_or_failed_downloads_stop_the_write(self):
        mp.check_counts(459, 481, 0, 672)                       # 12 Nov 2026: 95% kept, fine
        with self.assertRaises(SystemExit):
            mp.check_counts(300, 481, 0, 672)
        with self.assertRaises(SystemExit):
            mp.check_counts(470, 481, 40, 672)

    def test_main_keeps_the_previous_file_when_downloads_fail(self):
        boot = {"events": [{"deadline_time": "2026-08-15T10:00:00Z"}], "elements": [{"id": i} for i in range(1, 101)]}
        def get(path):
            if path == "/bootstrap-static/":
                return boot
            return None if int(path.split("/")[2]) > 50 else {"history_past": [season("2025/26", 900)]}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "priors.json"
            out.write_text(json.dumps({"built": "old", "players": {str(i): {} for i in range(1, 101)}}))
            with patch.object(mp, "get", get), self.assertRaises(SystemExit):
                mp.main(str(out))
            self.assertEqual(json.loads(out.read_text())["built"], "old")


class ValidatePriorSeasons(unittest.TestCase):
    def errors(self, priors):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "history").mkdir()
            (root / "odds").mkdir()
            (root / "priors.json").write_text(json.dumps(priors))
            D = {"meta": {"built": "2026-11-12T12:00:00+00:00", "next_gw": 11, "cur_gw": 10, "team_id": 1},
                 "manager": {"free_transfers": 1, "bank": 0.0}, "squad": [], "players": [], "history": []}
            (root / "data.json").write_text(json.dumps(D))
            with patch.object(validate, "HERE", str(root)), contextlib.redirect_stdout(io.StringIO()):
                validate.main(root / "data.json")
            return [e for e in json.loads((root / "data.json").read_text())["health"]["errors"] if "priors.json" in e]

    def test_old_season_prior_stops_the_publish(self):
        ok = {"seasons": [2024, 2025], "players": {"1": {"season": "2025/26"}, "2": {"season": "2024/25"}}}
        self.assertEqual(self.errors(ok), [])
        self.assertEqual(len(self.errors(dict(ok, players={"3": {"season": "2015/16"}}))), 1)
        self.assertEqual(self.errors({"players": {"3": {"season": "2015/16"}}}), [])   # older file: not checked


if __name__ == "__main__":
    unittest.main()
