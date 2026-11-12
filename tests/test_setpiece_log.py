"""FL-069: the set-piece change list is kept in history/setpieces.json, not re-read from the deployed site each build.

Before, every build fetched the live data.json for the old list: one failed fetch published an empty list, and the next
build copied that empty list forward, so the history was lost for good.
"""
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_harness import ROOT, offline_build  # noqa: E402

sys.path.insert(0, str(ROOT))

NOW = dt.datetime(2026, 11, 12, 9, 0, tzinfo=dt.timezone.utc)
OLD = {"date": "2026-10-01", "season": "2026-27", "team": 1, "type": "pen", "old": 10, "new": 11}


def offline():
    raise OSError("deployed site unreachable")


class BuildKeepsTheList(unittest.TestCase):
    """The whole build, with the deployed site unreachable (as every offline_build is)."""

    @classmethod
    def setUpClass(cls):
        def prepare(repo):
            # a saved change list and no taker rows yet: the build adds today's rows and must keep the list
            (repo / "history" / "setpieces.json").write_text(json.dumps({"now": {}, "changes": [OLD], "season": "2026-27"}))
        cls.repo, cls.D, cls.rc, _ = offline_build(cls, prepare)

    def test_list_survives_a_failed_fetch(self):
        self.assertIn(OLD, self.D["setpieces"]["changes"])
        self.assertEqual(self.D["setpieces"]["status"], "ok")
        self.assertEqual(self.rc, 0, self.D["health"]["errors"])

    def test_log_is_written_to_history(self):
        log = json.loads((self.repo / "history" / "setpieces.json").read_text())
        self.assertEqual(log["changes"][-1], OLD)
        self.assertEqual(len(log["now"]), 20)   # every team now has a row to compare against next build


class Log(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = str(Path(tmp.name) / "history" / "setpieces.json")
        import setpiece_log
        self.log = setpiece_log

    def write(self, log):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.path).write_text(json.dumps(log))

    def read(self):
        return json.loads(Path(self.path).read_text())

    def update(self, now_rows, fetch=offline, season="2026-27"):
        return self.log.update(self.path, now_rows, NOW, season, fetch)

    def test_change_is_logged_newest_first(self):
        self.write({"now": {"1": {"pen": [11], "cor": [5], "fk": []}}, "changes": [OLD], "season": "2026-27"})
        out = self.update({"1": {"pen": [12, 11], "cor": [5], "fk": []}})
        new = {"date": "2026-11-12", "season": "2026-27", "team": 1, "type": "pen", "old": 11, "new": 12}
        self.assertEqual(out["changes"], [new, OLD])
        self.assertEqual(self.read()["changes"], [new, OLD])
        self.assertEqual(self.read()["now"]["1"]["pen"], [12, 11])

    def test_quiet_refresh_writes_nothing(self):
        log = {"now": {"1": {"pen": [11], "cor": [5], "fk": []}}, "changes": [OLD], "season": "2026-27"}
        self.write(log)
        before = Path(self.path).read_text()
        out = self.update({"1": {"pen": [11, 9], "cor": [5], "fk": []}})   # only a back-up moved
        self.assertEqual(Path(self.path).read_text(), before)
        self.assertEqual((out["changes"], out["status"]), ([OLD], "ok"))

    def test_first_run_seeds_from_the_deployed_site(self):
        deployed = {"setpieces": {"now": {"1": {"pen": [11]}}, "changes": [{k: v for k, v in OLD.items() if k != "season"}]}}
        out = self.update({"1": {"pen": [12], "cor": [], "fk": []}}, fetch=lambda: deployed)
        self.assertEqual(out["status"], "seeded")
        self.assertEqual([c["new"] for c in out["changes"]], [12, 11])
        self.assertEqual(self.read()["changes"][1], OLD)   # tagged with this season

    def test_no_file_and_no_deployed_site_writes_nothing(self):
        out = self.update({"1": {"pen": [12], "cor": [], "fk": []}})
        self.assertEqual((out["status"], out["changes"]), ("seed_failed", []))
        self.assertFalse(Path(self.path).exists())   # the next build tries the seed again

    def test_unreadable_file_is_never_overwritten(self):
        Path(self.path).parent.mkdir(parents=True)
        Path(self.path).write_text("{not json")
        out = self.update({"1": {"pen": [12], "cor": [], "fk": []}}, fetch=lambda: {"setpieces": {"changes": [OLD]}})
        self.assertEqual((out["status"], out["changes"]), ("unreadable", [OLD]))
        self.assertEqual(Path(self.path).read_text(), "{not json")
        out = self.update({"1": {"pen": [12], "cor": [], "fk": []}})
        self.assertEqual((out["status"], out["changes"]), ("unreadable", []))

    def test_new_season_compares_nothing_and_hides_last_seasons_changes(self):
        self.write({"now": {"1": {"pen": [11], "cor": [5], "fk": [7]}}, "changes": [OLD], "season": "2026-27"})
        out = self.update({"1": {"pen": [300], "cor": [301], "fk": [302]}}, season="2027-28")
        self.assertEqual(out["changes"], [])
        log = self.read()
        self.assertEqual((log["season"], log["changes"], log["now"]["1"]["pen"]), ("2027-28", [OLD], [300]))

    def test_new_team_row_is_added_without_a_change(self):
        self.write({"now": {}, "changes": [], "season": "2026-27"})
        out = self.update({"1": {"pen": [12], "cor": [], "fk": []}})
        self.assertEqual(out["changes"], [])
        self.assertIn("1", self.read()["now"])


class Validate(unittest.TestCase):
    def check(self, sp):
        from validate import check_setpieces
        errors, warnings = [], []
        check_setpieces({"setpieces": sp, "teams": {"1": {}}}, errors, warnings)
        return errors, warnings

    def test_ok(self):
        self.assertEqual(self.check({"status": "ok", "changes": [OLD]}), ([], []))

    def test_failed_log_warns(self):
        for st in ("seed_failed", "unreadable"):
            errors, warnings = self.check({"status": st, "changes": []})
            self.assertEqual((errors, len(warnings)), ([], 1))
            self.assertIn("Set-piece history", warnings[0])

    def test_bad_rows_are_errors(self):
        for bad in ({"type": "throw"}, {"team": 99}, {"date": "12/11/2026"}):
            errors, _ = self.check({"status": "ok", "changes": [dict(OLD, **bad)]})
            self.assertEqual(len(errors), 1, bad)

    def test_out_of_order_warns(self):
        _, warnings = self.check({"status": "ok", "changes": [OLD, dict(OLD, date="2026-11-01")]})
        self.assertIn("out of order", warnings[0])

    def test_older_data_not_checked(self):
        self.assertEqual(self.check({"changes": []}), ([], []))


if __name__ == "__main__":
    unittest.main()
