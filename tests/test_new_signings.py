"""FL-030: new signings.

- A player new to the Premier League (no prior: no PL minutes in the last two seasons) gets a start chance from his
  price band (ARRIVAL_START, fitted on 2022/23-2023/24 arrivals) that fades out over his first 5 registered club games, and only until he first plays.
  With no history the minutes model gave every arrival about 30%, while cheap ones start 7% of their first 5 games.
  The guess is marked assumed for the site (arrival, start_assumed); validate.py checks it.
- A player who moved within the Premier League keeps his minutes from his old club (weeks his old club played count,
  with its fixture count), via fplmodel's ctx["moved"] from clubs_then.
Missing: no price (now_cost) -> no guess (the minutes model alone); a mover's ambiguous week isn't in ctx["moved"].
"""
import gzip
import json
from pathlib import Path
import unittest

import fplmodel
from fplmodel import ARRIVAL_START, prepare, project
import validate

ROOT = Path(__file__).resolve().parent.parent
API = json.load(gzip.open(ROOT / "tests" / "fixtures" / "season_end_api.json.gz"))


def ctx_with_arrival(cost):
    boot = json.loads(json.dumps(API["/bootstrap-static/"]))
    live = {g: API[f"/event/{g}/live/"] for g in range(1, 11)}
    pri = json.load(open(ROOT / "priors.json"))
    # an established forward with a prior, re-cast as an arrival: drop his prior, give him a new price
    e = next(x for x in boot["elements"] if x["element_type"] == 4 and str(x["id"]) in pri["players"] and x["status"] == "a")
    e["now_cost"] = cost
    pri = dict(pri, players={k: v for k, v in pri["players"].items() if k != str(e["id"])})
    # registered only from GW9 and not played yet: blank his earlier rows, zero his GW9-10 minutes
    for g in range(1, 9):
        live[g] = dict(live[g], elements=[x for x in live[g]["elements"] if x["id"] != e["id"]])
    for g in (9, 10):
        live[g] = dict(live[g], elements=[dict(x, stats=dict(x["stats"], minutes=0, starts=0)) if x["id"] == e["id"] else x
                                          for x in live[g]["elements"]])
    nxt = next(ev["id"] for ev in boot["events"] if ev["is_next"])
    return prepare(boot, API["/fixtures/"], live, pri), e["id"], nxt


class Arrival(unittest.TestCase):
    def test_price_bands_fitted(self):
        self.assertEqual([v for _, v in ARRIVAL_START], [0.07, 0.23, 0.21, 0.30])

    def test_cheap_arrival_pulled_down_and_fading(self):
        ctx, pid, nxt = ctx_with_arrival(40)
        new = project(ctx, nxt, 1, {"sim": 0})["players"][pid]
        old = project(ctx, nxt, 1, {"sim": 0, "new_signings": False})["players"][pid]
        # registered for GW9-10: 2 games, so the guess weighs 3/5
        self.assertAlmostEqual(new["start_guess"], 0.6, 6)
        self.assertAlmostEqual(new["p_start"], 0.6 * 0.07 + 0.4 * old["p_start"], 6)
        self.assertEqual(old["start_guess"], 0.0)

    def test_no_guess_once_he_has_played(self):
        ctx, pid, nxt = ctx_with_arrival(40)
        ctx["pstats"][pid][10] = dict(ctx["pstats"][pid][10], minutes=90, starts=1)
        self.assertEqual(project(ctx, nxt, 1, {"sim": 0})["players"][pid]["start_guess"], 0.0)

    def test_player_with_a_prior_is_untouched(self):
        boot = API["/bootstrap-static/"]
        live = {g: API[f"/event/{g}/live/"] for g in range(1, 11)}
        ctx = prepare(boot, API["/fixtures/"], live, json.load(open(ROOT / "priors.json")))
        nxt = next(ev["id"] for ev in boot["events"] if ev["is_next"])
        new = project(ctx, nxt, 1, {"sim": 0})["players"]
        pri = json.load(open(ROOT / "priors.json"))["players"]
        self.assertTrue(all(r["start_guess"] == 0 for p, r in new.items() if str(p) in pri))


class Moved(unittest.TestCase):
    def test_moved_weeks_from_clubs_then(self):
        from tests.test_xg_club_then import ctx_mover
        ctx = ctx_mover()
        self.assertEqual(ctx["moved"][7], {1: 3, 2: 3})
        self.assertNotIn(8, ctx["moved"])


class Validate(unittest.TestCase):
    def test_arrival_checked(self):
        import os
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "priors.json"), "w") as f:
                json.dump({"players": {"5": {}}}, f)
            errs = []
            D = {"players": [{"id": 5, "name": "A", "arrival": 0.4, "start_assumed": True},    # has a prior
                             {"id": 6, "name": "B", "arrival": 1.4, "start_assumed": True},    # weight out of range
                             {"id": 8, "name": "D", "arrival": 0.6},                           # not marked assumed
                             {"id": 7, "name": "C", "arrival": 1.0, "start_assumed": True}]}
            with patch.object(validate, "HERE", tmp):
                validate.check_arrivals(D, errs)
        self.assertEqual([e.split(" (")[0] for e in errs], ["A", "B", "D"])


if __name__ == "__main__":
    unittest.main()
