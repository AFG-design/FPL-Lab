"""FL-079: goalkeeper save points for a start and a sub appearance are worked out separately, then weighted by their
chances. One Poisson on his expected minutes understated them whenever his chance of playing was below 100%
(at 50% to start, about 3 saves a game: 0.20 v 0.33 points), because a save point needs 3 saves in the minutes he
actually plays. Missing input: no minutes as a sub (m_sub default 20) is the same default as before.
"""
import copy
import gzip
import json
from pathlib import Path
import unittest

from fplmodel import prepare, project, saves_pts

ROOT = Path(__file__).resolve().parent.parent
API = json.load(gzip.open(ROOT / "tests" / "fixtures" / "season_end_api.json.gz"))


class Saves(unittest.TestCase):
    def test_reproduced_numbers(self):
        self.assertAlmostEqual(0.5 * saves_pts(3.0), 0.332, 3)
        self.assertAlmostEqual(saves_pts(1.5), 0.196, 3)   # the old way: the same saves rate over half the minutes

    def test_half_the_chance_is_half_the_save_points(self):
        boot = API["/bootstrap-static/"]
        live = {g: API[f"/event/{g}/live/"] for g in range(1, 11)}
        nxt = next(e["id"] for e in boot["events"] if e["is_next"])
        mins = {x["id"]: x["stats"]["minutes"] for x in live[10]["elements"]}
        gk = next(e["id"] for e in boot["elements"] if e["element_type"] == 1 and mins.get(e["id"], 0) == 90
                  and e["status"] == "a")

        def saves(status, chance):
            b = copy.deepcopy(boot)
            e = next(x for x in b["elements"] if x["id"] == gk)
            e.update(status=status, chance_of_playing_next_round=chance, news="Knock - 50% chance of playing" if chance else "")
            ctx = prepare(b, API["/fixtures/"], live, json.load(open(ROOT / "priors.json")))
            return project(ctx, nxt, 1, {"sim": 0})["players"][gk]["detail"][nxt]["saves"]

        full, half = saves("a", None), saves("d", 50)
        self.assertGreater(full, 0)
        self.assertAlmostEqual(half, full / 2, 6)


if __name__ == "__main__":
    unittest.main()
