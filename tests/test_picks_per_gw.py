"""FL-070: each finished gameweek's picks are fetched on their own.

Before, the picks for every finished gameweek were fetched in one expression inside one try: a single failed request
emptied them all, and Review, You vs the model, the template tracker and the journal came out empty with no message.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_harness import ROOT, TEAM_ID, offline_build  # noqa: E402

LOST = 5   # a gameweek whose picks request fails (the current gameweek's picks are fetched separately, earlier)


def drop(*gws):
    def change(api):
        for g in gws:
            del api[f"/entry/{TEAM_ID}/event/{g}/picks/"]
    return change


class OneWeekFails(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, cls.D, cls.rc, cls.cur = offline_build(cls, api_change=drop(LOST))

    def test_only_that_week_is_left_out(self):
        weeks = [w["gw"] for w in self.D["review"]["weeks"]]
        self.assertNotIn(LOST, weeks)
        self.assertEqual(weeks, [g for g in range(1, self.cur) if g != LOST])   # the current week is still in play
        self.assertEqual(self.D["review"]["skipped"], [LOST])

    def test_reported_on_data_health(self):
        self.assertEqual(self.rc, 0, self.D["health"]["errors"])
        self.assertTrue(any(w.startswith(f"Review: GW{LOST} left out") for w in self.D["health"]["warnings"]),
                        self.D["health"]["warnings"])


class EveryPastWeekFails(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def change(api):
            cur = next(e["id"] for e in api["/bootstrap-static/"]["events"] if e["is_current"])
            drop(*range(1, cur))(api)
        cls.repo, cls.D, cls.rc, cls.cur = offline_build(cls, api_change=change)

    def test_each_week_is_listed_and_data_health_says_review_is_empty(self):
        self.assertEqual(self.D["review"]["skipped"], list(range(1, self.cur)))
        self.assertEqual(self.D["review"]["weeks"], [])
        self.assertEqual(self.rc, 0, self.D["health"]["errors"])
        self.assertIn(f"Review is empty although {self.cur - 1} finished gameweek(s) have your points: picks not fetched?",
                      self.D["health"]["warnings"])


class Check(unittest.TestCase):
    def check(self, D, saved=()):
        sys.path.insert(0, str(ROOT))
        try:
            import validate
        finally:
            sys.path.remove(str(ROOT))
        warnings = []
        exists = validate.os.path.exists
        validate.os.path.exists = lambda p: Path(p).name in {f"proj_gw{g}.json" for g in saved} or (
            exists(p) and not Path(p).name.startswith("proj_gw"))
        try:
            validate.check_picks_sections(D, warnings)
        finally:
            validate.os.path.exists = exists
        return warnings

    def data(self, review=None, vs_model=None, fin=(1, 2)):
        return {"meta": {"finished_gws": list(fin)}, "history": [{"gw": g} for g in fin],
                "review": review, "vs_model": vs_model}

    def test_all_fine(self):
        D = self.data({"weeks": [{"gw": 1}, {"gw": 2}], "skipped": []}, {"weeks": [{"gw": 2}], "skipped": []})
        self.assertEqual(self.check(D, saved=[2]), [])

    def test_skipped_weeks_warn(self):
        w = self.check(self.data({"weeks": [{"gw": 1}], "skipped": [2]}, {"weeks": [], "skipped": [2]}), saved=[2])
        self.assertTrue(any(x.startswith("Review: GW2 left out") for x in w), w)
        self.assertTrue(any(x.startswith("You vs the model: GW2 left out") for x in w), w)
        self.assertTrue(any(x.startswith("You vs the model is empty although GW2") for x in w), w)

    def test_empty_review_warns_even_in_older_data(self):
        w = self.check(self.data({"weeks": []}, None))
        self.assertEqual(w, ["Review is empty although 2 finished gameweek(s) have your points: picks not fetched?"])

    def test_no_saved_forecast_means_no_head_to_head_expected(self):
        self.assertEqual(self.check(self.data({"weeks": [{"gw": 1}, {"gw": 2}]}, None)), [])

    def test_pre_season_not_checked(self):
        self.assertEqual(self.check(self.data(None, None, fin=())), [])


if __name__ == "__main__":
    unittest.main()
