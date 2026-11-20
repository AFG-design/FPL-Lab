"""FL-229: Understat cache v3 (last action on each shot), teams.json (pressing and deep completions), the past-season
backfill and their Data health warnings. Understat itself is never called: fetch and the FPL API are faked."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import understat
import validate

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import understat_backfill  # noqa: E402


def shot(pid=1, name="A Striker", x=0.9, y=0.5, xg=0.2, sit="OpenPlay", stype="Head", la="Cross", assisted="B Winger"):
    s = {"player_id": str(pid), "player": name, "X": str(x), "Y": str(y), "xG": str(xg), "result": "SavedShot",
         "situation": sit, "shotType": stype, "player_assisted": assisted}
    if la is not None:
        s["lastAction"] = la
    return s


def hist(date, h_a="h", **kw):
    row = {"date": date + " 15:00:00", "h_a": h_a, "ppda": {"att": 300, "def": 30}, "ppda_allowed": {"att": 200, "def": 25},
           "deep": 8, "deep_allowed": 5, "xG": 1.5, "xGA": 0.8, "npxG": 1.5, "npxGA": 0.8}
    row.update(kw)
    return row


def date_entry(mid, h=("Arsenal", "ARS"), a=("Chelsea", "CHE"), day="2026-08-21", result=True):
    return {"id": mid, "isResult": result, "datetime": day + " 20:00:00",
            "h": {"title": h[0], "short_title": h[1]}, "a": {"title": a[0], "short_title": a[1]}}


V2_ROW = [1, "A Striker", 0.9, 0.5, 0.2, "Goal", "OpenPlay", "", "h", "RightFoot"]


class ShotRow(unittest.TestCase):
    def test_last_action_kept_as_sent(self):
        self.assertEqual(understat.shot_row(shot(la="Throughball"), "a")[10], "Throughball")
        self.assertEqual(understat.shot_row(shot(la="None"), "a")[10], "None")   # Understat's own "no action"

    def test_missing_last_action_is_blank_not_guessed(self):
        r = understat.shot_row(shot(la=None), "h")
        self.assertEqual(len(r), 11)
        self.assertEqual(r[10], "")
        self.assertEqual(r[:10], [1, "A Striker", 0.9, 0.5, 0.2, "SavedShot", "OpenPlay", "B Winger", "h", "Head"])


class Cache(unittest.TestCase):
    def write(self, d, obj):
        p = os.path.join(d, "shots.json")
        with open(p, "w") as f:
            f.write(obj if isinstance(obj, str) else json.dumps(obj))
        return p

    def test_v2_upgraded_in_place_and_queued(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.write(d, {"season": "2026", "v": 2, "matches": {
                "2": {"date": "2026-08-30", "h": "ARS", "a": "CHE", "shots": [V2_ROW]},
                "1": {"date": "2026-08-21", "h": "CHE", "a": "ARS", "shots": [V2_ROW, V2_ROW]}}})
            c = understat.load_cache(p, "2026")
        self.assertEqual(c["v"], 3)
        self.assertEqual(len(c["matches"]), 2)   # nothing lost
        self.assertEqual(c["matches"]["1"]["shots"][0], V2_ROW + [""])
        self.assertEqual(understat.refetch_ids(c), ["1", "2"])   # oldest first
        self.assertEqual(understat.refetch_ids(c, limit=1), ["1"])
        self.assertEqual(understat.last_action_stats(c), (0, 2, None))

    def test_v3_kept_and_not_refetched(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.write(d, {"season": "2026", "v": 3, "matches": {
                "1": {"date": "2026-08-21", "h": "ARS", "a": "CHE", "la": True,
                      "shots": [V2_ROW + ["Cross"], V2_ROW + [""], V2_ROW + ["Pass"], V2_ROW + ["None"]]}}})
            c = understat.load_cache(p, "2026")
        self.assertEqual(understat.refetch_ids(c), [])
        self.assertEqual(understat.last_action_stats(c), (1, 0, 0.75))

    def test_other_season_version_or_unreadable_starts_empty(self):
        with tempfile.TemporaryDirectory() as d:
            for obj in ({"season": "2025", "v": 2, "matches": {"1": {}}}, {"season": "2026", "v": 1, "matches": {"1": {}}},
                        "not json"):
                with self.subTest(obj=obj):
                    c = understat.load_cache(self.write(d, obj), "2026")
                    self.assertEqual(c, {"season": "2026", "v": 3, "matches": {}})
            self.assertEqual(understat.load_cache(os.path.join(d, "none.json"), "2026")["matches"], {})

    def test_failed_download_keeps_the_old_row(self):
        c = {"season": "2026", "v": 3, "matches": {"1": {"date": "2026-08-21", "h": "ARS", "a": "CHE", "shots": [V2_ROW + [""]]}}}
        info = {"1": date_entry("1"), "2": date_entry("2", day="2026-08-30")}
        with mock.patch.object(understat, "fetch", return_value=None), mock.patch.object(understat.time, "sleep"):
            self.assertEqual(understat.download_matches(c, ["1", "2"], info), ["1", "2"])
        self.assertEqual(list(c["matches"]), ["1"])
        self.assertNotIn("la", c["matches"]["1"])


class TeamHistory(unittest.TestCase):
    def test_raw_counts_by_short_code(self):
        league = {"dates": [date_entry("1")], "teams": {
            "83": {"title": "Arsenal", "history": [hist("2026-08-30", "a", deep=3), hist("2026-08-21")]},
            "80": {"title": "Chelsea", "history": [hist("2026-08-21", "a")]}}}
        out, unmapped, bad = understat.team_history(league)
        self.assertEqual((sorted(out), unmapped, bad), (["ARS", "CHE"], [], 0))
        ars = out["ARS"]
        self.assertEqual((ars["title"], ars["us_id"]), ("Arsenal", "83"))
        self.assertEqual([m["date"] for m in ars["matches"]], ["2026-08-21", "2026-08-30"])   # sorted by date
        self.assertEqual(ars["matches"][0]["ppda"], [300, 30])   # counts, not the ratio
        self.assertEqual(ars["matches"][0]["ppda_allowed"], [200, 25])
        self.assertEqual(ars["matches"][1]["deep"], 3)

    def test_unmapped_club_and_bad_rows_counted_not_dropped_silently(self):
        broken = hist("2026-08-28")
        del broken["ppda"]
        league = {"dates": [date_entry("1")], "teams": {
            "83": {"title": "Arsenal", "history": [hist("2026-08-21"), broken]},
            "99": {"title": "Nowhere Town", "history": [hist("2026-08-21")]}}}
        out, unmapped, bad = understat.team_history(league)
        self.assertEqual(list(out), ["ARS"])
        self.assertEqual(unmapped, ["Nowhere Town"])
        self.assertEqual(bad, 1)
        self.assertEqual(len(out["ARS"]["matches"]), 1)

    def test_no_teams_key_gives_nothing(self):
        self.assertEqual(understat.team_history({"dates": []}), ({}, [], 0))


class MainEndToEnd(unittest.TestCase):
    """understat.main() with a v2 cache: the old match is downloaded again with last action, the new one added,
    teams.json written and the FL-229 health figures in the meta. The tally (still 10 fields) runs unchanged."""

    def test_run(self):
        boot = {"events": [{"id": 1, "deadline_time": "2026-08-15T10:00:00Z", "finished": True}],
                "teams": [{"id": 1, "short_name": "ARS"}, {"id": 2, "short_name": "CHE"}],
                "elements": [{"id": 10, "team": 1, "first_name": "A", "second_name": "Striker", "web_name": "Striker",
                              "known_name": "", "minutes": 180}]}
        fixtures = [{"event": 1, "kickoff_time": "2026-08-21T19:00:00Z", "team_h": 1, "team_a": 2},
                    {"event": 1, "kickoff_time": "2026-08-30T14:00:00Z", "team_h": 2, "team_a": 1}]
        league = {"dates": [date_entry("1"), date_entry("2", h=("Chelsea", "CHE"), a=("Arsenal", "ARS"), day="2026-08-30"),
                            date_entry("3", day="2026-09-30", result=False)],
                  "players": [{"id": "1", "player_name": "A Striker", "team_title": "Arsenal", "time": "180",
                               "games": "2", "shots": "3", "key_passes": "0", "npxG": "0.6", "xGChain": "0.7",
                               "xGBuildup": "0.1", "position": "F"}],
                  "teams": {"83": {"title": "Arsenal", "history": [hist("2026-08-21")]},
                            "80": {"title": "Chelsea", "history": [hist("2026-08-21", "a")]}}}
        match = {"shots": {"h": [shot(la="Cross"), shot(la=None)], "a": []}}

        def fetch(url, referer):
            return league if "getLeagueData" in url else match

        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "shots.json"), "w") as f:
                json.dump({"season": "2026", "v": 2, "matches": {
                    "1": {"date": "2026-08-21", "h": "ARS", "a": "CHE", "shots": [V2_ROW]}}}, f)
            fpl = {"/bootstrap-static/": boot, "/fixtures/": fixtures}
            with mock.patch.object(understat, "OUTDIR", d), mock.patch.object(understat, "SEASON", "2026"), \
                    mock.patch.object(understat, "fetch", side_effect=fetch), \
                    mock.patch.object(understat, "fpl", side_effect=lambda p: fpl[p]), \
                    mock.patch.object(understat.time, "sleep"), mock.patch("builtins.print"):
                understat.main()
            cache = json.load(open(os.path.join(d, "shots.json")))
            teams = json.load(open(os.path.join(d, "teams.json")))
            meta = json.load(open(os.path.join(d, "fpl_players.json")))["meta"]
        self.assertEqual(cache["v"], 3)
        self.assertEqual(sorted(cache["matches"]), ["1", "2"])   # the unplayed match 3 isn't fetched
        self.assertTrue(all(m["la"] for m in cache["matches"].values()))
        self.assertEqual([r[10] for r in cache["matches"]["1"]["shots"]], ["Cross", ""])
        self.assertEqual(sorted(teams["teams"]), ["ARS", "CHE"])
        self.assertEqual({k: meta[k] for k in ("v", "la_matches", "la_pending", "la_share", "failed", "teams",
                                               "teams_unmapped", "teams_bad_rows", "new_matches")},
                         {"v": 3, "la_matches": 2, "la_pending": 0, "la_share": 0.5, "failed": 0, "teams": 2,
                          "teams_unmapped": 0, "teams_bad_rows": 0, "new_matches": 1})


class Backfill(unittest.TestCase):
    def league(self, n=2):
        teams = {str(i): {"title": f"Club {i}", "history": [hist("2024-08-17")]} for i in range(20)}
        dates = [date_entry(str(i), h=(f"Club {i % 20}", f"C{i % 20:02d}"), a=(f"Club {(i + 1) % 20}", f"C{(i + 1) % 20:02d}"))
                 for i in range(n)]
        dates += [date_entry(f"x{i}", h=(f"Club {i}", f"C{i:02d}"), a=(f"Club {(i + 1) % 20}", f"C{(i + 1) % 20:02d}"),
                             result=False) for i in range(20)]   # short codes for every club
        return {"dates": dates, "teams": teams}

    def test_season_name(self):
        self.assertEqual(understat_backfill.season_name(2024), "2024-25")
        self.assertEqual(understat_backfill.season_name("2099"), "2099-00")

    def test_partial_then_resumed(self):
        lg = self.league()
        calls = []

        def flaky(url, referer):
            if "getLeagueData" in url:
                return lg
            calls.append(url)
            return None if url.endswith("/1") and len(calls) == 2 else {"shots": {"h": [shot()], "a": []}}

        with tempfile.TemporaryDirectory() as d, mock.patch.object(understat.time, "sleep"), \
                mock.patch("builtins.print"):
            path, complete = understat_backfill.backfill(2024, d, fetch=flaky)
            first = json.load(open(path))
            self.assertFalse(complete)
            self.assertEqual((first["missing"], first["complete"], first["season"]), (["1"], False, "2024-25"))
            self.assertEqual(sorted(first["matches"]), ["0"])
            path, complete = understat_backfill.backfill(2024, d, fetch=flaky)
            second = json.load(open(path))
        self.assertTrue(complete)
        self.assertEqual(calls[2:], ["https://understat.com/getMatchData/1"])   # match 0 not downloaded again
        self.assertEqual((second["missing"], second["expected"], len(second["teams"])), ([], 2, 20))

    def test_feed_down_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError):
                understat_backfill.backfill(2024, d, fetch=lambda u, r: None)
            self.assertEqual(os.listdir(d), [])

    def test_unmapped_club_is_not_complete(self):
        lg = self.league()
        lg["teams"]["99"] = {"title": "Extra FC", "history": []}
        with tempfile.TemporaryDirectory() as d, mock.patch.object(understat.time, "sleep"), \
                mock.patch("builtins.print"):
            _, complete = understat_backfill.backfill(
                2024, d, fetch=lambda u, r: lg if "League" in u else {"shots": {"h": [], "a": []}})
        self.assertFalse(complete)


class Health(unittest.TestCase):
    def run_(self, **meta):
        w = []
        validate.check_understat_style(meta, w)
        return w

    def test_old_meta_not_checked(self):
        self.assertEqual(self.run_(teams=3, la_share=0.1, la_matches=50), [])

    def test_good_meta_is_quiet(self):
        self.assertEqual(self.run_(v=3, la_matches=100, la_pending=0, la_share=0.97, failed=0, teams=20,
                                   teams_unmapped=0, teams_bad_rows=0), [])

    def test_low_last_action_share_warns_once_enough_matches(self):
        self.assertIn("only 40% of shots", self.run_(v=3, la_matches=10, la_share=0.4, teams=20)[0])
        self.assertEqual(self.run_(v=3, la_matches=9, la_share=0.4, teams=20), [])   # too few to judge
        self.assertEqual(self.run_(v=3, la_matches=0, la_share=None, teams=20), [])

    def test_each_problem_warns(self):
        w = self.run_(v=3, la_matches=50, la_share=0.95, la_pending=12, failed=2, teams=19, teams_unmapped=1,
                      teams_bad_rows=3)
        self.assertEqual(len(w), 5)
        for part in ("12 matches cached before", "2 match downloads failed", "19 clubs, not 20",
                     "1 clubs in the league feed", "3 team match rows"):
            self.assertTrue(any(part in x for x in w), part)


if __name__ == "__main__":
    unittest.main()
