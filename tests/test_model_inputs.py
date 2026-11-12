"""FL-072: whether the status log and europe.json loaded is recorded in meta and checked by validate.py.

Before, build.py ran on without either and nothing said so: a missing history/status.json left the model without any
injury history (it can't tell injured from dropped), and a missing or broken europe.json removed the rotation allowance
for European midweeks, with no sign on Data health.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_harness import ROOT, offline_build  # noqa: E402


class StatusLogMissing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, cls.D, cls.rc, _ = offline_build(cls, lambda repo: (repo / "history" / "status.json").unlink())

    def test_recorded_and_stops_the_publish(self):
        self.assertEqual(self.D["meta"]["status_log"]["state"], "missing")
        self.assertEqual(self.rc, 1)
        self.assertTrue(any(e.startswith("Status log (history/status.json) missing") for e in self.D["health"]["errors"]),
                        self.D["health"]["errors"])


class Unreadable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def prepare(repo):
            (repo / "history" / "status.json").write_text('{"gws": {"9": ')
            (repo / "europe.json").write_text('{"competitions": {"UCL": {"teams": ["ARS"], "dates": ["not a date"]}}}')
        cls.repo, cls.D, cls.rc, _ = offline_build(cls, prepare)

    def test_status_log_unreadable_is_an_error_and_left_alone(self):
        sl = self.D["meta"]["status_log"]
        self.assertEqual(sl["state"], "unreadable")
        self.assertTrue(sl["error"])
        self.assertEqual((self.repo / "history" / "status.json").read_text(), '{"gws": {"9": ')
        self.assertTrue(any(e.startswith("Status log (history/status.json) unreadable") for e in self.D["health"]["errors"]))

    def test_europe_unreadable_is_a_warning(self):
        eu = self.D["meta"]["europe"]
        self.assertEqual(eu["state"], "unreadable")
        self.assertIn("ValueError", eu["error"])
        self.assertTrue(any(w.startswith("europe.json didn't load (ValueError") for w in self.D["health"]["warnings"]))


class AllLoaded(unittest.TestCase):
    """The repo's own files: both load; the unconfirmed competition in europe.json is listed."""

    @classmethod
    def setUpClass(cls):
        cls.repo, cls.D, cls.rc, _ = offline_build(cls)

    def test_ok(self):
        m = self.D["meta"]
        self.assertEqual(m["status_log"]["state"], "ok")
        self.assertGreater(m["status_log"]["gws"], 0)
        self.assertEqual(m["europe"]["state"], "ok")
        self.assertFalse(any(e.startswith("Status log") for e in self.D["health"]["errors"]))
        self.assertEqual(self.rc, 0, self.D["health"]["errors"])


class Check(unittest.TestCase):
    def check(self, **meta):
        sys.path.insert(0, str(ROOT))
        try:
            from validate import check_model_inputs
        finally:
            sys.path.remove(str(ROOT))
        errors, warnings = [], []
        check_model_inputs(meta, errors, warnings)
        return errors, warnings

    OK_EU = {"state": "ok", "competitions": 2, "unconfirmed": [], "error": None}

    def test_all_fine(self):
        self.assertEqual(self.check(cur_gw=11, status_log={"state": "ok", "gws": 9}, europe=self.OK_EU), ([], []))

    def test_missing_log_before_the_first_deadline_is_normal(self):
        self.assertEqual(self.check(cur_gw=0, status_log={"state": "missing", "gws": 0}, europe=self.OK_EU), ([], []))

    def test_missing_log_in_season_is_an_error(self):
        errors, _ = self.check(cur_gw=5, status_log={"state": "missing", "gws": 0}, europe=self.OK_EU)
        self.assertEqual(len(errors), 1)

    def test_empty_log_in_season_warns(self):
        errors, warnings = self.check(cur_gw=5, status_log={"state": "ok", "gws": 0}, europe=self.OK_EU)
        self.assertEqual((errors, len(warnings)), ([], 1))

    def test_europe_missing_and_unconfirmed_warn(self):
        _, warnings = self.check(cur_gw=5, europe={"state": "missing", "competitions": 0, "unconfirmed": [], "error": None})
        self.assertTrue(warnings[0].startswith("europe.json is missing"))
        _, warnings = self.check(cur_gw=5, europe=dict(self.OK_EU, unconfirmed=["UECL"]))
        self.assertTrue(warnings[0].startswith("europe.json: UECL skipped"))

    def test_older_data_not_checked(self):
        self.assertEqual(self.check(cur_gw=11), ([], []))


if __name__ == "__main__":
    unittest.main()
