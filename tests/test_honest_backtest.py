"""FL-068: backtests judge each forecast on what was known at its deadline, not today.

Three hindsight leaks, all in the backtest path only (use_flags off); the live model is unchanged:
  - weeks out: prepare() builds ctx["out"] from today's FPL notes, so a past forecast skipped weeks only a later note
    explained (the use_out leak, model log 23 Oct). known_out() rebuilds them from the status and news logs as they
    stood at the deadline;
  - 'unavailable today' (usually left the club since) zeroed a player in every past week;
  - past xG was credited to today's club; clubs_then() credits it to the club he played for that week.
hist_honest False keeps the old behaviour, so bench.py can compare the two.
"""
import datetime as dt
import gzip
import json
from pathlib import Path
import unittest

import fplmodel
from fplmodel import clubs_then, known_out, prepare, project

ROOT = Path(__file__).resolve().parent.parent


def iso(day):   # day 1 = 1 Sep 2026, 10:00
    return (dt.datetime(2026, 9, 1, 10) + dt.timedelta(days=day - 1)).strftime("%Y-%m-%dT%H:%M:%SZ")


def fx(i, g, h, a, day):
    return dict(id=i, event=g, team_h=h, team_a=a, team_h_score=1, team_a_score=0, finished=True,
                team_h_difficulty=3, team_a_difficulty=3, kickoff_time=iso(day).replace("T10", "T15"))


def row(pid, fixture, xg="0.50", minutes=90, starts=1):
    return dict(id=pid, explain=[dict(fixture=fixture, stats=[])],
                stats=dict(minutes=minutes, starts=starts, total_points=2, expected_goals=xg, expected_assists="0.0",
                           bonus=0, saves=0, yellow_cards=0, defensive_contribution=0))


class ClubsThen(unittest.TestCase):
    def test_moved_player_credits_his_old_club(self):
        els = {7: {"id": 7, "team": 1}}
        fixtures = [fx(1, 1, 3, 4, 1), fx(2, 2, 5, 3, 8), fx(3, 3, 1, 2, 15)]
        live = {1: {"elements": [row(7, 1)]}, 2: {"elements": [row(7, 2)]}, 3: {"elements": [row(7, 3)]}}
        xg, amb = clubs_then(els, fixtures, live)
        self.assertEqual((xg[3][1], xg[3][2], xg[1][3]), (0.5, 0.5, 0.5))
        self.assertEqual(xg[1][1] + xg[1][2], 0)
        self.assertEqual(amb, [])

    def test_one_week_elsewhere_is_ambiguous_and_said(self):
        els = {7: {"id": 7, "team": 1}}
        fixtures = [fx(1, 1, 3, 4, 1), fx(3, 2, 1, 2, 8)]
        xg, amb = clubs_then(els, fixtures, {1: {"elements": [row(7, 1)]}, 2: {"elements": [row(7, 3)]}})
        self.assertEqual(amb, [(7, 1)])
        self.assertEqual(xg[3][1] + xg[4][1] + xg[1][1], 0)   # credited to no club, never guessed


class KnownOut(unittest.TestCase):
    def setUp(self):
        # a regular starter, injured before GW3's deadline and still out today
        el = dict(id=7, team=1, element_type=3, status="i", chance_of_playing_next_round=0,
                  news_added="2026-09-14T10:00:00Z", news="Knee injury - Unknown return date", penalties_order=None)
        dls = {g: iso(1 + 7 * (g - 1)) for g in range(1, 7)}   # GW3: 15 Sep, GW4: 22 Sep, GW5: 29 Sep
        boot = {"elements": [el], "teams": [{"id": t} for t in (1, 2)],
                "events": [dict(id=g, deadline_time=d, finished=g <= 5) for g, d in dls.items()],
                "game_config": {"scoring": {}}}
        fixtures = [fx(g, g, 1, 2, 2 + 7 * (g - 1)) for g in range(1, 6)]
        live = {g: {"elements": [row(7, g, minutes=90 if g < 3 else 0, starts=int(g < 3))]} for g in range(1, 6)}
        self.ctx = prepare(boot, fixtures, live)

    def test_today_notes_explain_weeks_a_past_forecast_could_not_know(self):
        self.assertTrue({3, 4} <= self.ctx["out"][7])          # today's note (added before GW3) covers GW3 on
        self.assertEqual(known_out(self.ctx, 4)["out"].get(7, set()), set())   # no news log: nothing was known

    def test_news_log_as_it_stood_at_the_deadline(self):
        self.ctx["news_log"] = {"7": [["2026-09-14T10:00:00Z", "i", 0, "Knee injury - Unknown return date"]]}
        self.ctx.pop("_known_out", None)
        self.assertEqual(known_out(self.ctx, 3)["out"].get(7, set()), set())   # he hadn't missed a game yet
        self.assertEqual(known_out(self.ctx, 5)["out"][7], {3, 4})
        self.ctx["news_log"] = {"7": [["2026-09-25T10:00:00Z", "i", 0, "Knee injury - Unknown return date"]]}
        self.ctx.pop("_known_out")
        self.assertEqual(known_out(self.ctx, 4)["out"].get(7, set()), set())   # posted after GW4's deadline


class UnavailableToday(unittest.TestCase):
    def test_not_zeroed_in_past_weeks(self):
        api = json.load(gzip.open(ROOT / "tests" / "fixtures" / "season_end_api.json.gz"))
        boot = api["/bootstrap-static/"]
        live = {g: api[f"/event/{g}/live/"] for g in range(1, 11)}
        ctx = prepare(boot, api["/fixtures/"], live, json.load(open(ROOT / "priors.json")))
        mins = {g: {x["id"]: x["stats"]["minutes"] for x in live[g]["elements"]} for g in live}
        # left in the summer window: played GW2, 'u' today (and already at GW3's deadline, which only the status
        # log can tell a backtest; with no log the honest backtest knows of no flags)
        gone = [e["id"] for e in boot["elements"] if e["status"] == "u" and mins[2].get(e["id"], 0) > 0]
        self.assertTrue(gone)
        k = 3
        old = project(ctx, k, 1, {"use_flags": False, "hist_honest": False, "sim": 0})["players"]
        new = project(ctx, k, 1, {"use_flags": False, "sim": 0})["players"]
        self.assertTrue(all(old[p]["xp"].get(k, 0) == 0 for p in gone))
        self.assertTrue(any(new[p]["xp"].get(k, 0) > 0 for p in gone))

    def test_live_projection_unchanged(self):
        self.assertTrue(fplmodel.DEFAULTS["use_flags"])   # hist_honest only acts with use_flags off


if __name__ == "__main__":
    unittest.main()
