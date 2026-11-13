"""FL-147: FPL School team review (tools/fpl_school.py): any team ID in, a rating and one suggested move out, read-only.

Covers the review maths with a fake FPL (no network), every "can't show it" reason, and that nothing is written.
"""
import io
import os
import sys
import tempfile
import unittest
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import fpl_school  # noqa: E402

GWS = [11, 12]


def player(i, pos, team, price, xp):
    return {"id": i, "name": f"P{i}", "pos": pos, "team": team, "price": price, "xp": {str(g): xp for g in GWS}}


# 15: 2 GKP, 5 DEF, 5 MID, 3 FWD on 8 clubs; one weak midfielder (P9, 1.0 xP) and a better one to buy (P99)
SQUAD = ([player(1, "GKP", 1, 4.5, 3.0), player(2, "GKP", 2, 4.0, 1.0)]
         + [player(i, "DEF", i, 4.5, 3.5) for i in range(3, 8)]
         + [player(i, "MID", i, 6.0, 4.0) for i in range(8, 12)] + [player(12, "MID", 1, 5.0, 1.0)]
         + [player(i, "FWD", i - 10, 7.0, 5.0) for i in range(13, 16)])
D = {"players": SQUAD + [player(99, "MID", 6, 5.5, 6.0)], "rating": {"gws": GWS, "field": [60.0, 60.0]},
     "meta": {"built": "2026-11-13T10:00:00Z"}}


def fake_get(entry=None, picks=True, fail=None):
    def get(url):
        if fail == "404":
            raise urllib.error.HTTPError(url, 404, "Not Found", None, io.BytesIO())
        if fail == "down":
            raise urllib.error.URLError("timed out")
        if url.endswith("/entry/123/"):
            return entry or {"name": "Test XI", "player_first_name": "A", "player_last_name": "B", "current_event": 10}
        if "/picks/" in url and picks:
            return {"picks": [{"element": p["id"]} for p in SQUAD], "entry_history": {"event": 10, "bank": 5}}
        raise AssertionError(url)
    return get


class Review(unittest.TestCase):
    def test_rating_and_one_move(self):
        r = fpl_school.review(123, D, get=fake_get(), solve=False)
        self.assertEqual((r["team"], r["gw"], r["gws"]), ("Test XI", 10, GWS))
        # P99 (6.0 xP) replaces a 4.0 midfielder in the best XI (+2.0 a week) and becomes the best captain (+1.0 a week
        # over the 5.0 forwards): +3.0 a week over 2 weeks. Selling the bench one (P12) or a starter gains the same; the
        # first found is kept, as the site's "weakest links"
        self.assertEqual(r["move"]["in"], "P99")
        self.assertAlmostEqual(r["move"]["gain"], 6.0)
        self.assertEqual(r["best"], None)
        self.assertTrue(0 <= r["score"] <= 100)
        self.assertEqual(r["budget"], round(0.5 + sum(p["price"] for p in SQUAD), 1))   # current prices, assumed

    def test_cannot_show_reasons(self):
        for kw, msg in ((dict(fail="404"), "FPL has no team 123"), (dict(fail="down"), "FPL didn't answer"),
                        (dict(entry={"name": "X", "current_event": None}), "hasn't picked a team")):
            with self.subTest(msg):
                with self.assertRaisesRegex(fpl_school.ReviewError, msg):
                    fpl_school.review(123, D, get=fake_get(**kw), solve=False)
        with self.assertRaisesRegex(fpl_school.ReviewError, "no rating gameweeks"):
            fpl_school.review(123, dict(D, rating={}), get=fake_get(), solve=False)

    def test_page_says_assumed_and_writes_nothing(self):
        before = set(os.listdir(tempfile.gettempdir()))
        r = fpl_school.review(123, D, get=fake_get(), solve=False)
        page = fpl_school.as_html(r, tid="123", built="x")
        self.assertIn("assumed", page)
        self.assertIn("Read-only: nothing is saved", page)
        self.assertIn("→ P99 (£5.5m)", page)
        self.assertIn("A team ID is a number", fpl_school.as_html(err="A team ID is a number."))
        self.assertEqual(set(os.listdir(tempfile.gettempdir())) - before, set())


if __name__ == "__main__":
    unittest.main()
