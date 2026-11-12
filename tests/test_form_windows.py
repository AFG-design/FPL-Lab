"""FL-083: form windows only count gameweeks where the player's club has finished its matches.

Mid-gameweek the model leaves out a club's week until all its matches are over (fplmodel.unfinished_team_weeks), so the
player stats have no row for it. The form windows still counted that week: an ever-present starter whose club plays on
Monday showed "4 starts from 5", and every "last 4" / "last 6" window (points, xGI, bonus, goals and assists, defensive
contributions) quietly covered a week less. Now the window skips the unfinished week and reaches one week further back.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_harness import offline_build  # noqa: E402


class ClubStillToPlay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        got = {}

        def change(api):
            # the current gameweek's first fixture is not finished yet: both its clubs are still to play
            boot = api["/bootstrap-static/"]
            cur = next(e["id"] for e in boot["events"] if e["is_current"])
            f = next(f for f in api["/fixtures/"] if f["event"] == cur)
            f["finished"] = f["finished_provisional"] = False
            got.update(cur=cur, clubs={f["team_h"], f["team_a"]},
                       team={e["id"]: e["team"] for e in boot["elements"]},
                       live={g: {x["id"]: x["stats"] for x in api[f"/event/{g}/live/"]["elements"]} for g in range(1, cur + 1)},
                       games={(t, g): sum(1 for x in api["/fixtures/"] if x["event"] == g and t in (x["team_h"], x["team_a"]))
                              for t in {f["team_h"], f["team_a"]} for g in range(1, cur + 1)})
        cls.repo, cls.D, cls.rc, _ = offline_build(cls, api_change=change)
        cls.got = got
        cls.mine = [p for p in cls.D["players"] if p["team"] in got["clubs"]]

    def test_no_unplayed_game_counted_as_a_start_missed(self):
        for p in self.mine:
            t = p["team"]
            weeks = sorted(g for g in range(1, self.got["cur"]) if self.got["games"][(t, g)])[-5:]
            games = sum(self.got["games"][(t, g)] for g in weeks)
            self.assertEqual(p["st5"][1], games, p["name"])
        # someone who started every one of those games now shows 5 of 5, not 4 of 5
        self.assertTrue(any(p["st5"][0] == p["st5"][1] and p["st5"][1] >= 5 for p in self.mine))

    def test_last_four_is_the_clubs_last_four_finished_weeks(self):
        live, cur = self.got["live"], self.got["cur"]
        for p in self.mine:
            weeks = list(range(1, cur))[-4:]   # the current week is left out, so GW cur-4 .. cur-1
            mins = sum(live[g].get(p["id"], {}).get("minutes", 0) for g in weeks)
            self.assertEqual(p["mins4"], mins, p["name"])
            self.assertEqual(p["pts4"], sum(live[g].get(p["id"], {}).get("total_points", 0) for g in weeks), p["name"])

    def test_other_clubs_unchanged(self):
        # clubs that have finished the week still count it
        live, cur = self.got["live"], self.got["cur"]
        others = [p for p in self.D["players"] if p["team"] not in self.got["clubs"] and p["mins4"]]
        self.assertTrue(others)
        for p in others[:50]:
            self.assertEqual(p["mins4"], sum(live[g].get(p["id"], {}).get("minutes", 0) for g in range(cur - 3, cur + 1)), p["name"])


if __name__ == "__main__":
    unittest.main()
