"""odds.carry_played: a failed or short results download never drops played matches from odds.json."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import odds
import validate


def row(fx, played=True, gw=1):
    return {"fixture": fx, "gw": gw, "h": 1, "a": 2, "lam_h": 1.5, "lam_a": 1.1, "played": played}


PREV = {"season": "2627", "matches": [row(i) for i in range(1, 31)] + [row(40, False, 4)]}


class CarryPlayed(unittest.TestCase):
    def test_normal_run_carries_nothing(self):
        new = [row(i) for i in range(1, 41)] + [row(50, False, 5)]
        out, st = odds.carry_played(new, PREV, "2627", True)
        self.assertEqual(out, new)
        self.assertEqual(st, {"past_ok": True, "kept_played": 0})

    def test_results_file_failed_keeps_previous_played_rows(self):
        new = [row(50, False, 5)]
        out, st = odds.carry_played(new, PREV, "2627", False)
        self.assertEqual(sum(1 for m in out if m["played"]), 30)
        self.assertEqual([m["fixture"] for m in out if not m["played"]], [50])   # the stale upcoming row is not kept
        self.assertFalse(st["past_ok"])
        self.assertEqual(st["kept_played"], 30)
        self.assertIn("past_failed_since", st)

    def test_short_results_file_is_topped_up_and_new_rows_win(self):
        fresh = dict(row(3), lam_h=9.9)
        out, st = odds.carry_played([fresh, row(31)], PREV, "2627", True)
        self.assertEqual(sum(1 for m in out if m["played"]), 31)
        self.assertEqual([m["lam_h"] for m in out if m["fixture"] == 3], [9.9])
        self.assertEqual(st["kept_played"], 29)
        self.assertTrue(st["past_ok"])

    def test_failure_time_is_remembered_until_it_recovers(self):
        prev = dict(PREV, status={"past_ok": False, "kept_played": 30, "past_failed_since": "2026-11-01T00:00:00Z"})
        _, st = odds.carry_played([], prev, "2627", False)
        self.assertEqual(st["past_failed_since"], "2026-11-01T00:00:00Z")
        _, st = odds.carry_played([row(i) for i in range(1, 31)], prev, "2627", True)
        self.assertNotIn("past_failed_since", st)

    def test_nothing_to_carry_is_reported_not_invented(self):
        for previous in (None, [], "x", {"season": "2526", "matches": [row(1)]}, {"season": "2627"}):
            with self.subTest(previous=previous):
                out, st = odds.carry_played([row(50, False)], previous, "2627", False)
                self.assertEqual(out, [row(50, False)])
                self.assertEqual((st["past_ok"], st["kept_played"]), (False, 0))


class ValidateWarning(unittest.TestCase):
    def warnings(self, odds_file):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "history").mkdir()
            (root / "odds").mkdir()
            if odds_file is not None:
                (root / "odds" / "odds.json").write_text(json.dumps(odds_file))
            D = {"meta": {"built": "2026-11-08T12:00:00+00:00", "next_gw": 11, "cur_gw": 10, "team_id": 1},
                 "manager": {"free_transfers": 1, "bank": 0.0}, "squad": [], "players": [], "history": []}
            (root / "data.json").write_text(json.dumps(D))
            with patch.object(validate, "HERE", str(root)), contextlib.redirect_stdout(io.StringIO()):
                validate.main(root / "data.json")
            return [w for w in json.loads((root / "data.json").read_text())["health"]["warnings"] if w.startswith("Match odds")]

    def test_healthy_or_older_file_is_quiet(self):
        self.assertEqual(self.warnings({"matches": [row(1)], "status": {"past_ok": True, "kept_played": 0}}), [])
        self.assertEqual(self.warnings({"matches": [row(1)]}), [])
        self.assertEqual(self.warnings(None), [])

    def test_carried_rows_warn(self):
        w = self.warnings({"matches": [row(i) for i in range(1, 31)],
                           "status": {"past_ok": False, "kept_played": 30, "past_failed_since": "2026-11-01T00:00:00Z"}})
        self.assertEqual(len(w), 1)
        self.assertIn("did not load (since 2026-11-01T00:00:00Z); 30 of 30 played", w[0])
        self.assertNotIn("fewer than 20", w[0])

    def test_no_rows_to_carry_says_the_ratings_are_off(self):
        w = self.warnings({"matches": [row(50, False)], "status": {"past_ok": False, "kept_played": 0, "past_failed_since": "x"}})
        self.assertIn("fewer than 20, so the betting-market team ratings are off", w[0])

    def test_short_file_wording(self):
        w = self.warnings({"matches": [row(i) for i in range(1, 31)], "status": {"past_ok": True, "kept_played": 4, "past_failed_since": "x"}})
        self.assertIn("came back short", w[0])


if __name__ == "__main__":
    unittest.main()
