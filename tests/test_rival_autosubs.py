"""FL-153: rivals' live points with FPL's automatic substitutions, by the same rules as your own squad (liveState).

On GW10 data, 29 of 179 mini-league rows sat below FPL's score by up to what the bench scored: rivals' live totals
left auto-subs out. fpl_score.live_team_points applies them; build.py uses it for every rival row.
"""
import gzip
import json
from pathlib import Path
import unittest

import fpl_score
from fpl_score import live_team_points

ROOT = Path(__file__).resolve().parent.parent
POS = {1: "GKP", 2: "DEF", 3: "DEF", 4: "DEF", 5: "MID", 6: "MID", 7: "MID", 8: "MID", 9: "FWD", 10: "FWD", 11: "FWD",
       12: "GKP", 13: "DEF", 14: "MID", 15: "FWD"}
PICKS = [[i, 2 if i == 9 else (1 if i <= 11 else 0)] for i in range(1, 16)]   # 9 captain, 12-15 bench in order


def run(mins, state, pts=None, chip=None, vice=None, picks=PICKS):
    pts = pts or {i: 2 if mins.get(i, 0) > 0 else 0 for i in range(1, 16)}
    return live_team_points(picks, pts, mins, state, POS, chip, vice)


ALL = {i: 90 for i in range(1, 16)}
DONE = {i: "done" for i in range(1, 16)}


class AutoSubs(unittest.TestCase):
    def test_no_subs_when_everyone_played(self):
        r = run(ALL, DONE)
        self.assertEqual((r["total"], r["subs"]), (2 * 10 + 4, []))

    def test_starter_out_and_finished_is_replaced_by_first_legal_bench_player(self):
        r = run({**ALL, **{5: 0}}, DONE)
        self.assertEqual(r["subs"], [[5, 13, True]])   # 12 is a keeper, so 13 (first outfield) comes on
        self.assertEqual(r["total"], 24)

    def test_not_replaced_while_his_match_is_to_come(self):
        r = run({**ALL, **{5: 0}}, {**DONE, **{5: "to play"}})
        self.assertEqual(r["subs"], [])

    def test_bench_player_still_to_play_holds_the_place_but_adds_nothing_yet(self):
        r = run({**ALL, **{5: 0, 13: 0}}, {**DONE, **{13: "to play"}})
        self.assertEqual(r["subs"], [[5, 13, False]])
        self.assertEqual(r["total"], 22)

    def test_keeper_only_for_keeper(self):
        r = run({**ALL, **{1: 0}}, DONE)
        self.assertEqual(r["subs"], [[1, 12, True]])

    def test_formation_stays_legal(self):
        # two defenders out (only 3 DEF in the XI): the bench midfielder can't replace a defender below 3
        mins = {**ALL, **{2: 0, 13: 0}}
        r = run(mins, DONE)
        self.assertEqual(r["subs"], [])   # 13 (DEF) didn't play; 14 (MID) would leave 2 DEF; 15 (FWD) likewise

    def test_armband_to_the_vice_only_when_known(self):
        mins = {**ALL, **{9: 0}}
        self.assertEqual(run(mins, DONE, vice=10)["total"], 2 * 10 + 2 + 2)       # 15 on for 9, vice 10 doubled
        r = run(mins, DONE)
        self.assertEqual((r["total"], r["vice_known"]), (22, False))             # no vice known: armband not moved

    def test_bench_boost_counts_all_fifteen(self):
        self.assertEqual(run(ALL, DONE, chip="bboost")["total"], 2 * 15 + 2)

    def test_short_or_missing_picks_are_not_guessed(self):
        r = run(ALL, DONE, picks=PICKS[:14])
        self.assertEqual(r["subs"], [])
        r = run({**ALL, **{5: 0}}, {})   # no match states: treated as still to play, so no sub
        self.assertEqual(r["subs"], [])


class RealWeek(unittest.TestCase):
    def test_finished_gw10_matches_fpl(self):
        api = json.load(gzip.open(ROOT / "tests" / "fixtures" / "season_end_api.json.gz"))
        pk = api["/entry/8122679/event/10/picks/"]
        boot = api["/bootstrap-static/"]
        pos = {e["id"]: {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}[e["element_type"]] for e in boot["elements"]}
        live = {x["id"]: x["stats"] for x in api["/event/10/live/"]["elements"]}
        p = [[x["element"], x["multiplier"]] for x in sorted(pk["picks"], key=lambda x: x["position"])]
        vice = next(x["element"] for x in pk["picks"] if x["is_vice_captain"])
        r = live_team_points(p, {i: s["total_points"] for i, s in live.items()}, {i: s["minutes"] for i, s in live.items()},
                             {i: "done" for i in pos}, pos, pk["active_chip"], vice)
        team = fpl_score.from_fpl_picks(pk, pos)
        played = {i: (s["minutes"], s["total_points"]) for i, s in live.items()}
        self.assertEqual(r["total"], fpl_score.score_team(team, played, pk["active_chip"])["total"])



class Validate(unittest.TestCase):
    def test_subs_must_match_the_picks(self):
        import validate
        row = {"player": "A", "picks": PICKS, "live_subs": [[5, 13, True]]}
        D = {"crowd": {"leagues": [{"name": "L", "rows": [row]}]}}
        errs = []
        validate.check_rival_subs(D, errs)
        self.assertEqual(errs, [])
        row["live_subs"] = [[13, 5, True]]
        validate.check_rival_subs(D, errs)
        self.assertEqual(len(errs), 1)


if __name__ == "__main__":
    unittest.main()
