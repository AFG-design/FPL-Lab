"""FL-093: players close to a return stay in data.json's player list, with their start chance marked assumed.

The list kept only players with minutes this season, 3+ xP over 5 GWs or in your squad, so Saliba (FPL had him
available again on 4 Nov after a back injury), Mitoma ('Expected back 22 Nov') and Minteh were missing.
"""
import contextlib
import datetime as dt
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fplmodel import returning
import validate

TODAY = dt.date(2026, 11, 12)
WIN_END = dt.date(2026, 12, 20)


def el(status="a", chance=None, news="", minutes=0, added="2026-11-01T10:00:00Z", **k):
    return dict(id=1, status=status, chance_of_playing_next_round=chance, news=news, news_added=added, minutes=minutes, **k)


SALIBA_HIST = [["2026-07-23T12:01:23Z", "i", 0, "Back injury - Unknown return date"],
               ["2026-11-03T21:38:27Z", "d", 75, "Back injury - 75% chance of playing"],
               ["2026-11-04T21:49:55Z", "a", 100, ""]]


class Rule(unittest.TestCase):
    def test_reasons(self):
        self.assertEqual(returning(el(chance=100), SALIBA_HIST, TODAY, WIN_END), "back")
        self.assertEqual(returning(el("i", 0, "Hamstring injury - Expected back 22 Nov", added="2026-10-29T17:54:57Z"),
                                   [], TODAY, WIN_END), "date")
        self.assertEqual(returning(el("d", 25, "Hamstring injury - 25% chance of playing"), [], TODAY, WIN_END), "chance")
        self.assertEqual(returning(el("s", None, "Suspended until 15 Nov"), [], TODAY, WIN_END), "date")

    def test_not_close(self):
        cases = {
            "fit, never flagged (a squad player who just doesn't play)": el(chance=None),
            "unknown return date at 0%": el("i", 0, "Knee injury - Unknown return date"),
            "return date passed, still 0%": el("i", 0, "Thigh injury - Expected back 31 Oct", added="2026-10-01T10:00:00Z"),
            "return date after the 5-GW window": el("i", 0, "Knee injury - Expected back 10 Jan", added="2026-11-01T10:00:00Z"),
            "left the club": el("u", 0, "Has joined X on loan"),
        }
        for why, e in cases.items():
            with self.subTest(why):
                self.assertIsNone(returning(e, [], TODAY, WIN_END))
        self.assertIsNone(returning(el(chance=100, minutes=90), SALIBA_HIST, TODAY, WIN_END))   # already playing
        self.assertIsNone(returning(el("i", 0, "Hamstring injury - Expected back 22 Nov"), [], TODAY, None))   # no window


class ValidateReturning(unittest.TestCase):
    def errors(self, player):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "history").mkdir()
            (root / "odds").mkdir()
            base = {"id": 6, "name": "Saliba", "team": 1, "pos": "DEF", "xp": {}, "xp1": 0, "xp5": 0.3, "mins": 0,
                    "status": "a", "chance": 100, "news": "", "returning": "back", "start_assumed": True}
            D = {"meta": {"built": "2026-11-12T12:00:00+00:00", "next_gw": 11, "cur_gw": 10, "team_id": 1},
                 "manager": {"free_transfers": 1, "bank": 0.0}, "squad": [], "players": [dict(base, **player)], "history": []}
            (root / "data.json").write_text(json.dumps(D))
            with patch.object(validate, "HERE", str(root)), contextlib.redirect_stdout(io.StringIO()):
                validate.main(root / "data.json")
            return [e for e in json.loads((root / "data.json").read_text())["health"]["errors"] if "returning" in e]

    def test_reason_must_match_the_data(self):
        self.assertEqual(self.errors({}), [])
        self.assertEqual(len(self.errors({"mins": 45})), 1)                       # has played: not a returner
        self.assertEqual(len(self.errors({"start_assumed": False})), 1)           # must be marked assumed
        self.assertEqual(len(self.errors({"returning": "chance", "status": "d", "chance": 0})), 1)
        self.assertEqual(self.errors({"returning": "date", "status": "i", "chance": 0,
                                      "news": "Hamstring injury - Expected back 22 Nov"}), [])


if __name__ == "__main__":
    unittest.main()
