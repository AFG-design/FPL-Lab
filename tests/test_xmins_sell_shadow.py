"""FL-131: the late-selling xMins model (xmins_sell) runs as a shadow; the live projections don't change.

PR #29 was never merged, so no shadow data was saved before any deadline. This re-lands it on current main. The
shadow is computed beside the live numbers and saved in history/proj_gw{g}.json ("xmins_sell") for
tools/score_shadow.py; the switch stays off until that test passes (around GW15).
Missing data: no selling table -> project() with xmins_sell on raises (never guesses); build.py then saves
{"error": ...} instead of a shadow and validate.py warns.
"""
import gzip
import json
import math
from pathlib import Path
import unittest

from fplmodel import DEFAULTS, prepare, project
import selling

ROOT = Path(__file__).resolve().parent.parent
API = json.load(gzip.open(ROOT / "tests" / "fixtures" / "season_end_api.json.gz"))


def ctx_and_gw():
    boot, fixtures = API["/bootstrap-static/"], API["/fixtures/"]
    live = {g: API[f"/event/{g}/live/"] for g in range(1, 11)}
    nxt = next(e["id"] for e in boot["events"] if e["is_next"])
    return prepare(boot, fixtures, live, json.load(open(ROOT / "priors.json"))), nxt


class Shadow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx, cls.gw = ctx_and_gw()
        cls.base = project(cls.ctx, cls.gw, 3, {"sim": 0})["players"]
        sell = selling.from_rounds(json.load(open(ROOT / "history" / "sell_hist.json"))["rounds"])
        cls.ctx_s = dict(cls.ctx, sell=sell)

    def test_off_by_default(self):
        self.assertIs(DEFAULTS["xmins_sell"], False)

    def test_live_projection_ignores_the_selling_table(self):
        with_sell = project(self.ctx_s, self.gw, 3, {"sim": 0})["players"]
        for pid, r in self.base.items():
            self.assertEqual(r["xp"], with_sell[pid]["xp"], pid)
            self.assertIsNone(with_sell[pid]["min_src_next"])

    def test_shadow_without_selling_data_raises(self):
        with self.assertRaises(ValueError):
            project(self.ctx, self.gw, 1, {"xmins_sell": True, "sim": 0})

    def test_shadow_changes_next_gw_only(self):
        sh = project(self.ctx_s, self.gw, 3, {"xmins_sell": True, "sim": 0})["players"]
        used = [p for p, r in sh.items() if r["min_src_next"] == "xmins_sell"]
        self.assertGreater(len(used), 200)
        later = [g for g in next(iter(self.base.values()))["xp"] if g != self.gw]
        moved = 0
        for p in used:
            for g in later:
                self.assertAlmostEqual(sh[p]["xp"].get(g, 0), self.base[p]["xp"].get(g, 0), 9)
            moved += abs(sh[p]["xp"].get(self.gw, 0) - self.base[p]["xp"].get(self.gw, 0)) > 1e-6
            self.assertTrue(0 <= sh[p]["ps_next"] <= 1 + 1e-9 and not math.isnan(sh[p]["ps_next"]))
            self.assertEqual(sh[p]["p_start"], self.base[p]["p_start"])   # reported start chance stays the live one
        self.assertGreater(moved, 0)


if __name__ == "__main__":
    unittest.main()
