"""FL-078: rivals' live points are on the same basis as yours and as FPL's standings.

Before, a rival's live total was confirmed points only (no provisional bonus) and had the hit taken off, while your own
row (live.js liveState) had provisional bonus. During matches your row could sit 3+ points apart from the same score on
Home, and a rival's hit appeared during matches and vanished once the table fell back to FPL's event_total (which is
before hits). Now every live total is before hits, with provisional bonus while it's unconfirmed.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_harness import offline_build  # noqa: E402


def unconfirm_bonus(api):
    """The current gameweek as FPL serves it before bonus is processed: no bonus in the fixtures' stats, and players'
    live total_points without it. build.py then works the provisional bonus out from BPS."""
    boot = api["/bootstrap-static/"]
    cur = next(e["id"] for e in boot["events"] if e["is_current"])
    removed = {}
    confirmed = {el["id"]: el["stats"]["total_points"] for el in api[f"/event/{cur}/live/"]["elements"]}
    for f in api["/fixtures/"]:
        if f["event"] != cur:
            continue
        for st in f["stats"]:
            if st["identifier"] == "bonus":
                for side in ("h", "a"):
                    for x in st[side]:
                        removed[x["element"]] = removed.get(x["element"], 0) + x["value"]
                st["h"], st["a"] = [], []
    for el in api[f"/event/{cur}/live/"]["elements"]:
        b = removed.get(el["id"], 0)
        el["stats"]["total_points"] -= b
        el["stats"]["bonus"] -= b
    return removed, confirmed


class RivalLiveBasis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        got = {}

        def change(api):
            got["removed"], got["confirmed"] = unconfirm_bonus(api)
        cls.repo, cls.D, cls.rc, cls.cur = offline_build(cls, api_change=change)
        cls.removed, cls.confirmed = got["removed"], got["confirmed"]
        cls.rows = [r for lg in cls.D["crowd"]["leagues"] for r in lg["rows"] if r.get("picks") and not r["me"]]

    def test_setup_is_meaningful(self):
        self.assertEqual(self.D["crowd"]["gw"], self.D["live"]["gw"])
        self.assertTrue(self.removed, "no bonus to unconfirm")
        self.assertTrue(any(r["hits"] for r in self.rows), "no rival with a hit")
        pts = self.D["live"]["pts_all"]
        self.assertTrue(any(el in self.removed and m for r in self.rows for el, m in r["picks"]),
                        "no rival owns a player with provisional bonus")
        self.assertTrue(pts)

    def test_rival_live_is_before_hits_with_provisional_bonus(self):
        pts = self.D["live"]["pts_all"]
        for r in self.rows:
            self.assertEqual(r["live"], sum(pts.get(str(el), 0) * m for el, m in r["picks"]), r["entry"])

    def test_equals_the_score_fpl_later_confirmed(self):
        # provisional bonus (top 3 BPS) gives back what FPL confirmed for this week, so each rival's live total is
        # their real gross score: the same number FPL's standings show (event_total, before hits) once bonus is in.
        # On main it was confirmed points only, minus the hit.
        for r in self.rows:
            self.assertEqual(r["live"], sum(self.confirmed.get(el, 0) * m for el, m in r["picks"]), r["entry"])


if __name__ == "__main__":
    unittest.main()
