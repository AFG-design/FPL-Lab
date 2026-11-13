"""FL-080: defensive contributions per fixture, with no 60-minute gate (FPL's rules have none).

Old: the DC chance was learned from gameweeks where he played 60+ (a double summed into one "week") and only applied
to 60+ minute appearances, so subs and early withdrawals got no DC points and a double counted as one chance.
New (dc_fixture): the chance per START comes from his own starts fixture by fixture, any length; per SUB appearance from
the rate model at his minutes off the bench; every fixture in a double is its own chance.
Missing: a fixture with no minutes row counts as 0 minutes; starts per fixture aren't in FPL's data, so in a double the
`starts` fixtures with the most minutes are the starts.
"""
import gzip
import json
from pathlib import Path
import unittest

from fplmodel import DEFAULTS, prepare, project

ROOT = Path(__file__).resolve().parent.parent
API = json.load(gzip.open(ROOT / "tests" / "fixtures" / "season_end_api.json.gz"))


def dc_row(pid, fxs, starts):
    return {"id": pid, "stats": dict(minutes=sum(m for _, m, _ in fxs), starts=starts, total_points=2, expected_goals="0",
                                      expected_assists="0", bonus=0, saves=0, yellow_cards=0, defensive_contribution=0),
            "explain": [{"fixture": f, "stats": [{"identifier": "minutes", "points": 0, "value": m}] +
                         ([{"identifier": "defensive_contribution", "points": 2, "value": 11}] if hit else [])}
                        for f, m, hit in fxs]}


class PerFixture(unittest.TestCase):
    def test_default_on(self):
        self.assertTrue(DEFAULTS["dc_fixture"])

    def test_double_recorded_per_fixture(self):
        boot = {"elements": [dict(id=7, team=1, element_type=2, status="a")], "teams": [{"id": 1}, {"id": 2}, {"id": 3}],
                "events": [], "game_config": {"scoring": {}}}
        fixtures = [dict(id=1, event=1, team_h=1, team_a=2, finished=True), dict(id=2, event=1, team_h=3, team_a=1, finished=True)]
        ctx = prepare(boot, fixtures, {1: {"elements": [dc_row(7, [(1, 90, True), (2, 30, False)], starts=1)]}})
        self.assertEqual(ctx["dc_fx"][7][1], [[90, True, True], [30, False, False]])   # two chances, one started

    def test_subs_and_short_starts_now_count(self):
        boot = API["/bootstrap-static/"]
        live = {g: API[f"/event/{g}/live/"] for g in range(1, 11)}
        ctx = prepare(boot, API["/fixtures/"], live, json.load(open(ROOT / "priors.json")))
        nxt = next(e["id"] for e in boot["events"] if e["is_next"])
        new = project(ctx, nxt, 1, {"sim": 0})["players"]
        old = project(ctx, nxt, 1, {"sim": 0, "dc_fixture": False})["players"]
        # a defender who is mostly a sub: the old rule gave him no DC points off the bench
        subs = [p for p, r in new.items() if r["p_sub"] > 0.4 and r["p_start"] < 0.2 and r["dc90"] > 8
                and nxt in r["detail"]]
        self.assertTrue(subs)
        self.assertTrue(all(new[p]["detail"][nxt]["dc"] > old[p]["detail"][nxt]["dc"] for p in subs))


if __name__ == "__main__":
    unittest.main()
