"""FL-092: upcoming fixture odds from The Odds API feed odds/odds.json before each deadline.

odds.json had no upcoming matches (football-data's fixtures file lists them only a few days ahead), so the
fixture-odds blend (direct_w 0.85) never ran for the next gameweek.
"""
import contextlib
import datetime as dt
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import odds
import odds_players
import validate
import scripts.refresh as refresh

UTC = dt.timezone.utc
DEADLINE = dt.datetime(2026, 11, 21, 11, 0, tzinfo=UTC)
BOOT = {"events": [{"id": 12, "is_next": True, "deadline_time": "2026-11-21T11:00:00Z"}],
        "teams": [{"id": 1, "name": "Arsenal", "short_name": "ARS"}, {"id": 2, "name": "Chelsea", "short_name": "CHE"},
                  {"id": 3, "name": "Brighton", "short_name": "BHA"}, {"id": 4, "name": "Spurs", "short_name": "TOT"}]}
FIXTURES = [{"id": 120, "event": 12, "team_h": 1, "team_a": 2, "kickoff_time": "2026-11-21T15:00:00Z", "finished": False},
            {"id": 121, "event": 12, "team_h": 3, "team_a": 4, "kickoff_time": "2026-11-22T16:30:00Z", "finished": False}]


def book(key, h, d, a, over=None, under=None, home="Arsenal", away="Chelsea"):
    mk = [{"key": "h2h", "outcomes": [{"name": home, "price": h}, {"name": "Draw", "price": d}, {"name": away, "price": a}]}]
    if over:
        mk.append({"key": "totals", "outcomes": [{"name": "Over", "price": over, "point": 2.5},
                                                  {"name": "Under", "price": under, "point": 2.5}]})
    return {"key": key, "markets": mk}


EVENTS = [{"home_team": "Arsenal", "away_team": "Chelsea", "commence_time": "2026-11-21T15:00:00Z",
           "bookmakers": [book("a", 1.8, 3.8, 4.4, 1.75, 2.1), book("b", 1.85, 3.7, 4.2, 1.8, 2.05)]},
          {"home_team": "Brighton and Hove Albion", "away_team": "Tottenham Hotspur", "commence_time": "2026-11-22T16:30:00Z",
           "bookmakers": [book("a", 2.6, 3.4, 2.7, home="Brighton and Hove Albion", away="Tottenham Hotspur")]},
          {"home_team": "Atletico Somewhere", "away_team": "Chelsea", "commence_time": "2026-11-23T20:00:00Z", "bookmakers": []}]


class Api:
    def __init__(self, events=EVENTS, left=300, fail=None):
        self.calls, self.events, self.left, self.fail = [], events, left, fail

    def __call__(self, path, **params):
        self.calls.append((path, params))
        if self.fail:
            raise self.fail
        return self.events, self.left, "2"


class Tmp:
    def __enter__(self):
        self.d = tempfile.TemporaryDirectory()
        root = Path(self.d.name)
        (root / "history").mkdir()
        (root / "odds").mkdir()
        self.root = root
        self.p = [patch.object(odds, "UPCOMING", str(root / "odds" / "upcoming.json")),
                  patch.object(odds, "HIST", str(root / "history")),
                  patch.object(odds_players, "OUT", str(root / "odds" / "players.json"))]
        for x in self.p:
            x.start()
        return self

    def __exit__(self, *a):
        for x in self.p:
            x.stop()
        self.d.cleanup()

    def run(self, now, key="k", api=None):
        with contextlib.redirect_stdout(io.StringIO()):
            return odds.fetch_upcoming(BOOT, FIXTURES, now=now, key=key, get=api or Api())


class Convert(unittest.TestCase):
    def test_margin_removed_per_bookmaker_then_median(self):
        p_h, p_d, p_a, p_over, books = odds.api_probs(EVENTS[0])
        self.assertAlmostEqual(p_h + p_d + p_a, 1, places=3)
        a = odds.implied([1.8, 3.8, 4.4])[0]; b = odds.implied([1.85, 3.7, 4.2])[0]
        self.assertAlmostEqual(p_h, (a + b) / 2, places=3)
        self.assertEqual(books, 2)
        self.assertAlmostEqual(p_over, (odds.implied([1.75, 2.1])[0] + odds.implied([1.8, 2.05])[0]) / 2, places=4)

    def test_no_totals_means_no_over_chance_and_no_result_prices_means_no_row(self):
        self.assertIsNone(odds.api_probs(EVENTS[1])[3])
        self.assertIsNone(odds.api_probs({"home_team": "A", "away_team": "B", "bookmakers": [
            {"key": "x", "markets": [{"key": "h2h", "outcomes": [{"name": "A", "price": 2.0}]}]}]}))

    def test_rows_join_fpl_fixtures_and_report_what_they_cannot(self):
        rows, unmatched, no_fx = odds.api_rows(EVENTS, BOOT, FIXTURES)
        self.assertEqual([r["fixture"] for r in rows], [120, 121])
        self.assertTrue(all(r["src"] == "odds_api" and not r["played"] for r in rows))
        self.assertGreater(rows[0]["lam_h"], rows[0]["lam_a"])   # Arsenal favourites
        self.assertEqual(unmatched, ["Atletico Somewhere"])
        far = [dict(EVENTS[0], commence_time="2026-11-25T15:00:00Z")]
        self.assertEqual(odds.api_rows(far, BOOT, FIXTURES)[0], [])   # kick-off 4 days off: no fixture, not a guess


class Fetch(unittest.TestCase):
    def test_due_checkpoint_saves_one_bulk_snapshot(self):
        with Tmp() as t:
            api = Api()
            rows, st = t.run(DEADLINE - dt.timedelta(hours=70), api=api)
            self.assertEqual(len(api.calls), 1)
            path, params = api.calls[0]
            self.assertEqual(path, "/sports/soccer_epl/odds")
            self.assertEqual((params["markets"], params["regions"]), ("h2h,totals", "uk"))   # 2 credits
            self.assertEqual(len(rows), 2)
            hist = json.loads((t.root / "history" / "fixture_odds_gw12.json").read_text())
            self.assertEqual(list(hist["snapshots"]), ["72"])
            self.assertEqual(st["credits_left"], 300)
            # same checkpoint again: no new call, same rows
            api2 = Api()
            rows2, _ = t.run(DEADLINE - dt.timedelta(hours=69), api=api2)
            self.assertEqual((api2.calls, len(rows2)), ([], 2))
            # next checkpoint: a second snapshot
            t.run(DEADLINE - dt.timedelta(hours=23), api=api2)
            self.assertEqual(len(api2.calls), 1)
            self.assertEqual(sorted(json.loads((t.root / "history" / "fixture_odds_gw12.json").read_text())["snapshots"]), ["24", "72"])

    def test_no_key_low_credits_or_not_due_spend_nothing(self):
        with Tmp() as t:
            api = Api()
            _, st = t.run(DEADLINE - dt.timedelta(hours=70), key="", api=api)
            self.assertEqual((api.calls, st["skipped"]), ([], "no ODDS_API_KEY"))
            _, st = t.run(DEADLINE - dt.timedelta(hours=100), api=api)
            self.assertEqual((api.calls, st["skipped"]), ([], "no checkpoint due"))
            month = (DEADLINE - dt.timedelta(hours=70)).isoformat()
            (t.root / "odds" / "players.json").write_text(json.dumps({"credits_left": 41, "built": dt.datetime.now(UTC).isoformat()}))
            _, st = t.run(DEADLINE - dt.timedelta(hours=70), api=api)
            self.assertEqual(api.calls, [])
            self.assertIn("only 41 credits left", st["skipped"])

    def test_failed_request_keeps_the_last_snapshot_and_says_so(self):
        with Tmp() as t:
            t.run(DEADLINE - dt.timedelta(hours=70))
            err = urllib.error.HTTPError("u", 429, "Too many", {}, None)
            rows, st = t.run(DEADLINE - dt.timedelta(hours=23), api=Api(fail=err))
            self.assertEqual(len(rows), 2)
            self.assertIn("429", st["last_error"]["message"])

    def test_kicked_off_fixture_leaves_the_live_rows(self):
        with Tmp() as t:
            t.run(DEADLINE - dt.timedelta(hours=70))
            rows, _ = t.run(dt.datetime(2026, 11, 21, 16, 0, tzinfo=UTC))   # Arsenal v Chelsea under way
            self.assertEqual([r["fixture"] for r in rows], [121])


class Merge(unittest.TestCase):
    def test_api_rows_replace_football_data_upcoming_never_played(self):
        fd = [{"fixture": 120, "played": False, "src": "football-data", "lam_h": 9},
              {"fixture": 100, "played": True, "src": "football-data"}, {"fixture": 130, "played": False}]
        out = odds.merge_upcoming(fd, [{"fixture": 120, "played": False, "src": "odds_api"}])
        self.assertEqual([(m["fixture"], m.get("src")) for m in out], [(100, "football-data"), (130, None), (120, "odds_api")])

    def test_refresh_passes_the_key_to_odds_py(self):
        envs = {}
        def call(cmd, env=None):
            envs[cmd[1]] = (env or {}).get("ODDS_API_KEY")
            return 0
        with patch.object(refresh.subprocess, "call", side_effect=call), patch.object(refresh.subprocess, "run"):
            refresh.build("secret")
        self.assertEqual((envs["odds.py"], envs["odds_players.py"]), ("secret", "secret"))


class Validate(unittest.TestCase):
    def health(self, matches, upcoming=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "history").mkdir()
            (root / "odds").mkdir()
            (root / "odds" / "odds.json").write_text(json.dumps({"matches": matches}))
            if upcoming is not None:
                (root / "odds" / "upcoming.json").write_text(json.dumps(upcoming))
            D = {"meta": {"built": "2026-11-18T12:00:00+00:00", "next_gw": 12, "cur_gw": 11, "team_id": 1},
                 "manager": {"free_transfers": 1, "bank": 0.0}, "squad": [], "players": [], "history": []}
            (root / "data.json").write_text(json.dumps(D))
            with patch.object(validate, "HERE", str(root)), contextlib.redirect_stdout(io.StringIO()):
                validate.main(root / "data.json")
            h = json.loads((root / "data.json").read_text())["health"]
            return [e for e in h["errors"] if "Odds API" in e], [w for w in h["warnings"] if "Odds API" in w or "Upcoming" in w]

    def test_bad_rows_stop_the_publish(self):
        good = {"fixture": 120, "gw": 12, "played": False, "src": "odds_api", "p_h": .5, "p_d": .25, "p_a": .25,
                "p_over": .55, "lam_h": 1.7, "lam_a": 1.0}
        self.assertEqual(self.health([good])[0], [])
        self.assertEqual(len(self.health([dict(good, p_h=.7)])[0]), 1)
        self.assertEqual(len(self.health([dict(good, lam_a=0.0)])[0]), 1)

    def test_failed_fetch_and_unused_snapshot_warn(self):
        up = {"latest": {"built": "2026-11-18T08:00:00+00:00", "rows": [{"fixture": 120, "gw": 12}]},
              "last_error": {"at": "2026-11-18T10:00:00+00:00", "message": "HTTP 401"}}
        _, w = self.health([], up)
        self.assertEqual(len(w), 2)
        self.assertTrue(any("HTTP 401" in x for x in w) and any("doesn't use" in x for x in w))


if __name__ == "__main__":
    unittest.main()
