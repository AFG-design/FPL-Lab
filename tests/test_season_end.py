"""FL-060: the refresh must still build and validate after GW38's deadline, when FPL lists no next gameweek.

Runs the real build.py in a temporary copy of the repo against recorded FPL API responses
(tests/fixtures/season_end_api.json.gz: bootstrap, fixtures, live and one entry, no rival or league data; the manager's
name is replaced). The responses are turned into a season end the way FPL reports one: the current gameweek is the last
one, its matches are still being played and no event is marked is_next. Any fetch outside the fixture (rivals, the
overall leader, the previous deploy) fails, as a flaky network would, and the build must carry on without it.
"""
import gzip
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import sys
import tempfile
import unittest
from unittest import mock
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "season_end_api.json.gz"
API = "https://fantasy.premierleague.com/api"
TEAM_ID = "8122679"


def season_end(api):
    """The recorded mid-season responses as FPL serves them just after the last deadline."""
    boot = api["/bootstrap-static/"]
    cur = next(e["id"] for e in boot["events"] if e["is_current"])
    boot["events"] = [e for e in boot["events"] if e["id"] <= cur]
    for e in boot["events"]:
        e["is_next"] = False
        if e["id"] == cur:
            e["finished"] = e["data_checked"] = False   # live: the last gameweek is still being played
    api["/fixtures/"] = [f for f in api["/fixtures/"] if f["event"] and f["event"] <= cur]
    return api, cur


class SeasonEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        cls.repo = Path(tmp.name) / "repo"
        # build.py reads and writes history/, odds/ and friends next to itself: work on a copy, never the real repo
        shutil.copytree(ROOT, cls.repo, ignore=shutil.ignore_patterns(".git", "node_modules", "site", "tests"))
        (cls.repo / "site").mkdir()
        with gzip.open(FIXTURE, "rt") as f:
            api, cls.cur = season_end(json.load(f))

        def urlopen(req, *a, **k):
            url = req.full_url if hasattr(req, "full_url") else req
            path = url[len(API):] if url.startswith(API) else None
            if path not in api:
                raise OSError(f"offline in test: {url}")
            return io.BytesIO(json.dumps(api[path]).encode())

        cls.out = cls.repo / "site" / "data.json"
        cwd, argv, path = os.getcwd(), sys.argv, list(sys.path)
        try:
            os.chdir(cls.repo)
            sys.argv = ["build.py", TEAM_ID, str(cls.out)]
            sys.path.insert(0, str(cls.repo))
            for name in [m for m in sys.modules if (cls.repo / f"{m}.py").exists()]:
                del sys.modules[name]   # import the copy's modules, not ones another test loaded from the repo
            with mock.patch.object(urllib.request, "urlopen", urlopen), mock.patch("time.sleep"):
                runpy.run_path(str(cls.repo / "build.py"), run_name="__main__")
            validate = runpy.run_path(str(cls.repo / "validate.py"))
            cls.rc = validate["main"](str(cls.out))
        finally:
            os.chdir(cwd)
            sys.argv, sys.path[:] = argv, path
        cls.D = json.loads(cls.out.read_text())

    def test_builds_without_a_next_gameweek(self):
        m = self.D["meta"]
        self.assertIsNone(m["next_gw"])
        self.assertTrue(m["season_over"])
        self.assertEqual((m["cur_gw"], m["last_gw"]), (self.cur, self.cur))
        self.assertEqual(m["proj_gws"], [])
        self.assertEqual(self.D["plans"], {})

    def test_keeps_players_and_team_ratings(self):
        # live scores, Review and season stats need every player's row even with nothing left to forecast
        self.assertGreater(len(self.D["players"]), 300)
        self.assertTrue(all(p["xp"] == {} for p in self.D["players"]))
        teams = self.D["teams"].values() if isinstance(self.D["teams"], dict) else self.D["teams"]
        self.assertTrue(all(t["att"] > 0 and t["def"] > 0 for t in teams))

    def test_validates_and_says_why(self):
        self.assertEqual(self.rc, 0, self.D["health"]["errors"])
        w = self.D["health"]["warnings"]
        self.assertTrue(any(x.startswith("Season over:") for x in w), w)
        self.assertFalse(any(x.startswith("No optimiser plans") for x in w), w)


class SeasonEndCheck(unittest.TestCase):
    """validate.check_season_end on its own: a missing next gameweek mid-season must stop the publish."""

    def check(self, **meta):
        sys.path.insert(0, str(ROOT))
        try:
            from validate import check_season_end
        finally:
            sys.path.remove(str(ROOT))
        errors, warnings = [], []
        check_season_end(meta, errors, warnings)
        return errors, warnings

    def test_in_season(self):
        self.assertEqual(self.check(next_gw=12, cur_gw=11, last_gw=38, proj_gws=[12]), ([], []))

    def test_older_data_without_the_flag(self):
        self.assertEqual(self.check(next_gw=12, cur_gw=11), ([], []))

    def test_no_next_gameweek_mid_season_is_an_error(self):
        errors, _ = self.check(next_gw=None, season_over=True, cur_gw=20, last_gw=38, proj_gws=[])
        self.assertEqual(len(errors), 1)
        self.assertIn("not the last", errors[0])

    def test_flag_disagrees_with_next_gw(self):
        errors, _ = self.check(next_gw=None, season_over=False, cur_gw=38, last_gw=38)
        self.assertIn("season_over is False", errors[0])
        errors, _ = self.check(next_gw=39, season_over=True, cur_gw=38, last_gw=38)
        self.assertIn("season_over is True", errors[0])

    def test_older_data_with_no_next_gameweek_is_not_checked(self):
        self.assertEqual(self.check(next_gw=None, cur_gw=38), ([], []))

    def test_season_end_without_last_gw(self):
        errors, _ = self.check(next_gw=None, season_over=True, cur_gw=38, proj_gws=[])
        self.assertEqual(len(errors), 1)

    def test_season_end(self):
        errors, warnings = self.check(next_gw=None, season_over=True, cur_gw=38, last_gw=38, proj_gws=[], plan_gws=[])
        self.assertEqual(errors, [])
        self.assertTrue(warnings[0].startswith("Season over: GW38"))


if __name__ == "__main__":
    unittest.main()
