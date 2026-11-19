"""FL-115: the European window rule shared by build.py, backtest.py and bench.py, the europe.json / europe_hist.json
readers, and the openfootball parser (tools/europe_hist.py)."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import fplmodel as fm
import europe_hist

D = dt.date


class Window(unittest.TestCase):
    def test_two_days_before_to_three_after_not_the_same_day(self):
        eu = [D(2026, 11, 4)]   # a Wednesday
        got = {d: bool(fm.euro_window(D(2026, 11, d), eu)) for d in range(1, 9)}
        self.assertEqual(got, {1: False, 2: True, 3: True, 4: False, 5: True, 6: True, 7: True, 8: False})

    def test_weeks_from_fixtures(self):
        fx = [{"event": 11, "team_h": 1, "team_a": 2, "kickoff_time": "2026-11-07T15:00:00Z"},
              {"event": 12, "team_h": 1, "team_a": 3, "kickoff_time": "2026-11-21T15:00:00Z"},
              {"event": None, "team_h": 1, "team_a": 4, "kickoff_time": None}]   # unscheduled: skipped
        self.assertEqual(fm.euro_weeks(fx, {1: [D(2026, 11, 5)]}), {(1, 11)})
        self.assertEqual(fm.euro_weeks(fx, {}), set())


class Readers(unittest.TestCase):
    def test_europe_json_skips_unconfirmed_and_unknown_clubs(self):
        teams = [{"id": 1, "short_name": "ARS"}, {"id": 2, "short_name": "BHA"}]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"competitions": {"UCL": {"teams": ["ARS", "XXX"], "dates": ["2026-11-04"]},
                                        "UECL": {"teams": ["BHA"], "confirmed": False, "dates": ["2026-11-05"]}}}, f)
        try:
            self.assertEqual(fm.europe_dates(f.name, teams), {1: [D(2026, 11, 4)]})
        finally:
            os.unlink(f.name)
        self.assertEqual(fm.europe_dates("/no/such/file.json", teams), {})

    def test_history_by_season(self):
        teams = [{"id": 7, "short_name": "AVL"}, {"id": 14, "short_name": "MUN"}]
        got25 = fm.europe_dates(str(ROOT / "europe_hist.json"), teams, "2024-25")
        self.assertIn(D(2025, 4, 15), got25[7])         # Villa's Champions League quarter-final second leg
        got26 = fm.europe_dates(str(ROOT / "europe_hist.json"), teams, "2025-26")
        self.assertIn(D(2026, 5, 20), got26[7])         # Villa's 2025/26 Europa League final (from manual supplement)
        self.assertNotIn(14, got26)                     # Man Utd: not in Europe in 2025/26


class Parser(unittest.TestCase):
    TEXT = """= UEFA Champions League 2024/25

▪ League, Matchday 1
  Tue Sep 17 2024
    18:45  BSC Young Boys (SUI)    v Aston Villa FC (ENG)     0-3 (0-2)
  Wed Sep 18
    21:00  Manchester City FC (ENG) v FC Internazionale Milano (ITA)  0-0
▪ Playoffs
  Tue Feb 11
    21:00  Manchester City FC (ENG) v Real Madrid CF (ESP)  2-3
"""

    def test_dates_and_years(self):
        self.assertEqual(europe_hist.parse(self.TEXT, "2024-25"),
                         {"AVL": ["2024-09-17"], "MCI": ["2024-09-18", "2025-02-11"]})

    def test_unknown_english_club_fails_loudly(self):
        with self.assertRaises(SystemExit):
            europe_hist.parse("  Tue Sep 17 2024\n    18:45  Mystery Town FC (ENG) v X (ITA) 1-0\n", "2024-25")


class ManualSupplement(unittest.TestCase):
    def test_merges_and_updates_missing(self):
        res = {"seasons": {"2025-26": {"ARS": {"UCL": ["2025-09-16"]}}},
               "missing": ["2025-26 UEL", "2025-26 UECL"]}
        manual = {
            "source": ["https://www.uefa.com/uefaeuropaleague/history/seasons/2026/matches/"],
            "seasons": {
                "2025-26": {
                    "UEL": {"AVL": ["2026-05-20", "2025-09-25"], "NFO": ["2025-09-24"]},
                    "UECL": {"CRY": ["2025-08-21"]},
                }
            },
        }
        skipped = europe_hist.merge_manual(res, manual)
        self.assertEqual(skipped, [])
        self.assertEqual(res["missing"], [])
        self.assertEqual(res["seasons"]["2025-26"]["AVL"], {"UEL": ["2025-09-25", "2026-05-20"]})
        self.assertEqual(res["seasons"]["2025-26"]["NFO"], {"UEL": ["2025-09-24"]})
        self.assertEqual(res["seasons"]["2025-26"]["CRY"], {"UECL": ["2025-08-21"]})
        self.assertEqual(res["seasons"]["2025-26"]["ARS"], {"UCL": ["2025-09-16"]})
        self.assertEqual(res["supplement_source"], manual["source"])

    def test_openfootball_wins_when_not_missing(self):
        res = {"seasons": {"2025-26": {"AVL": {"UEL": ["2025-09-25"]}}}, "missing": []}
        manual = {"seasons": {"2025-26": {"UEL": {"AVL": ["2025-10-02"]}}}}
        skipped = europe_hist.merge_manual(res, manual)
        self.assertEqual(skipped, ["2025-26 UEL"])
        self.assertEqual(res["seasons"]["2025-26"]["AVL"]["UEL"], ["2025-09-25"])

    def test_bad_club_name_fails_loudly(self):
        res = {"seasons": {"2025-26": {}}, "missing": ["2025-26 UEL"]}
        manual = {"seasons": {"2025-26": {"UEL": {"XXX": ["2025-09-25"]}}}}
        with self.assertRaises(SystemExit):
            europe_hist.merge_manual(res, manual)

    def test_date_outside_season_fails_loudly(self):
        res = {"seasons": {"2025-26": {}}, "missing": ["2025-26 UEL"]}
        for bad_date in ("2025-06-30", "2026-07-01", "not-a-date"):
            manual = {"seasons": {"2025-26": {"UEL": {"AVL": [bad_date]}}}}
            with self.assertRaises(SystemExit):
                europe_hist.merge_manual(res, manual)

    def test_committed_europe_hist_has_no_missing(self):
        with open(ROOT / "europe_hist.json") as f:
            hist = json.load(f)
        self.assertEqual(hist["missing"], [])
        self.assertIn("UEL", hist["seasons"]["2025-26"]["AVL"])
        self.assertIn("UEL", hist["seasons"]["2025-26"]["NFO"])
        self.assertIn("UECL", hist["seasons"]["2025-26"]["CRY"])


if __name__ == "__main__":
    unittest.main()
