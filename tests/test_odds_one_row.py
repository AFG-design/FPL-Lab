"""FL-112: odds/odds.json holds one row per FPL fixture.

football-data.co.uk's fixtures.csv kept listing GW10 after it was played, so each GW10 match came back twice
(played from the results file, upcoming from the fixtures file): 110 rows, 10 ids duplicated, GW10 counted twice in
the market team ratings and Health showed 10 upcoming odds for a finished gameweek.
"""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import odds
import validate

HEAD = "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,AvgH,AvgD,AvgA,Avg>2.5,Avg<2.5\n"
# the same match in both files, as on 12 Nov 2026 for GW10
PAST = HEAD + "E0,07/11/2026,Arsenal,Chelsea,2,1,1.80,3.80,4.40,1.75,2.10\n"
UPCOMING = HEAD + ("E0,07/11/2026,Arsenal,Chelsea,,,1.80,3.80,4.40,1.75,2.10\n"
                   "E0,22/11/2026,Chelsea,Arsenal,,,2.60,3.40,2.70,1.80,2.00\n")
BOOT = {"events": [{"id": 1, "deadline_time": "2026-08-15T10:00:00Z"}],
        "teams": [{"id": 1, "short_name": "ARS"}, {"id": 2, "short_name": "CHE"}]}
FIXTURES = [{"id": 100, "event": 10, "team_h": 1, "team_a": 2, "kickoff_time": "2026-11-07T15:00:00Z", "finished": True},
            {"id": 120, "event": 12, "team_h": 2, "team_a": 1, "kickoff_time": "2026-11-22T15:00:00Z", "finished": False}]


def run_odds(tmp, past=PAST, upcoming=UPCOMING, fixtures=FIXTURES, previous=None):
    out = Path(tmp) / "odds.json"
    if previous is not None:
        out.write_text(json.dumps(previous))
    pages = {"/bootstrap-static/": BOOT, "/fixtures/": fixtures}
    fetch = lambda url: past if url.endswith("E0.csv") else upcoming
    with patch.object(odds, "OUT", str(out)), patch.object(odds, "fpl", pages.get), patch.object(odds, "fetch", fetch), \
            contextlib.redirect_stdout(io.StringIO()):
        try:
            odds.main()
        except SystemExit:
            pass
    return json.loads(out.read_text())


class OneRowPerFixture(unittest.TestCase):
    def test_finished_fixture_keeps_only_its_played_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = run_odds(tmp)
        ids = [m["fixture"] for m in d["matches"]]
        self.assertEqual(sorted(ids), [100, 120])   # failed before FL-112: [100, 100, 120]
        self.assertTrue(next(m for m in d["matches"] if m["fixture"] == 100)["played"])
        self.assertFalse(next(m for m in d["matches"] if m["fixture"] == 120)["played"])
        self.assertEqual((d["status"]["dropped_finished"], d["status"]["dropped_duplicate"]), (1, 0))

    def test_unconfirmed_result_keeps_the_upcoming_row(self):
        # FPL hasn't marked it finished (or the field is missing): keep the upcoming row, never guess
        fx = [dict(FIXTURES[0], finished=False), FIXTURES[1]]
        fx2 = [{k: v for k, v in FIXTURES[0].items() if k != "finished"}, FIXTURES[1]]
        for fixtures in (fx, fx2):
            with self.subTest(fixtures=fixtures[0]), tempfile.TemporaryDirectory() as tmp:
                d = run_odds(tmp, past=HEAD, fixtures=fixtures)
                self.assertEqual([(m["fixture"], m["played"]) for m in d["matches"]], [(100, False), (120, False)])

    def test_duplicates_left_after_the_finished_rule(self):
        row = lambda fx, played, lam=1.0: {"fixture": fx, "played": played, "lam_h": lam}
        out, df, dd = odds.one_row_per_fixture(
            [row(1, True, 1.1), row(1, False), row(2, False, 1.0), row(2, False, 2.0), row(3, True, 1.0), row(3, True, 3.0)], [])
        self.assertEqual([(m["fixture"], m["played"], m["lam_h"]) for m in out], [(1, True, 1.1), (2, False, 2.0), (3, True, 3.0)])
        self.assertEqual((df, dd), (0, 3))

    def test_source_down_still_cleans_an_old_file(self):
        prev = {"season": "2627", "built": "x", "matches": [
            {"fixture": 100, "gw": 10, "played": True, "lam_h": 1.5}, {"fixture": 100, "gw": 10, "played": False, "lam_h": 1.5}]}
        with tempfile.TemporaryDirectory() as tmp:
            d = run_odds(tmp, past=None, upcoming=None, previous=prev)
        self.assertEqual([(m["fixture"], m["played"]) for m in d["matches"]], [(100, True)])


class ValidateDuplicates(unittest.TestCase):
    def errors(self, matches):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "history").mkdir()
            (root / "odds").mkdir()
            (root / "odds" / "odds.json").write_text(json.dumps({"matches": matches}))
            D = {"meta": {"built": "2026-11-08T12:00:00+00:00", "next_gw": 11, "cur_gw": 10, "team_id": 1},
                 "manager": {"free_transfers": 1, "bank": 0.0}, "squad": [], "players": [], "history": []}
            (root / "data.json").write_text(json.dumps(D))
            with patch.object(validate, "HERE", str(root)), contextlib.redirect_stdout(io.StringIO()):
                validate.main(root / "data.json")
            return [e for e in json.loads((root / "data.json").read_text())["health"]["errors"] if e.startswith("Match odds")]

    def test_duplicate_fixture_id_stops_the_publish(self):
        e = self.errors([{"fixture": 100, "gw": 10, "played": True}, {"fixture": 100, "gw": 10, "played": False}])
        self.assertEqual(len(e), 1)
        self.assertIn("1 fixture id(s) appear more than once", e[0])
        self.assertEqual(self.errors([{"fixture": 100, "gw": 10, "played": True}]), [])


if __name__ == "__main__":
    unittest.main()
