"""FL-089: unit tests for the model and data-source functions that had none (audit 13 Nov).

Each test checks a function against an independent calculation or a hand-built case, so a quiet bug in the maths or a
join shows up here instead of in a review. Covered:
  fplmodel: poisson, p_at_least, exp_floor_div (goals, saves, DefCon and goals-conceded points rest on them),
            out_weeks, late_news_absences, news_absences (the injured-v-dropped rules)
  odds: outcome_probs, fit_lambdas, match_fixtures (market odds -> expected goals, joined to FPL fixtures)
  understat: match_players (one-to-one Understat -> FPL, too-close matches rejected)
  odds_players: match_player (bookmaker names -> FPL ids)
  transfer_log: _due (snapshot cadence before a deadline)
  xmins: features and predict (no history -> missing inputs, never 0; outputs in range)
Not covered, and why: crowd.py runs as a script at import (no functions to call without the network; its FL-082 flags
are checked in test_assumed_defaults); odds_archive.season_odds downloads a season (its parts, odds.rows_from and
match_fixtures, are covered here and in test_odds_*).
"""
import datetime as dt
import gzip
import json
import math
from pathlib import Path
import unittest

import fplmodel as fm
import odds
import odds_players
import transfer_log
import understat

ROOT = Path(__file__).resolve().parent.parent


def pois_ref(k, mu):
    return math.exp(-mu + k * math.log(mu) - math.lgamma(k + 1)) if mu > 0 else float(k == 0)


class ModelMaths(unittest.TestCase):
    def test_poisson_is_a_distribution(self):
        for mu in (0.05, 0.4, 1.3, 3.0, 8.0):
            self.assertAlmostEqual(sum(fm.poisson(k, mu) for k in range(60)), 1.0, 9)
            self.assertAlmostEqual(sum(k * fm.poisson(k, mu) for k in range(60)), mu, 9)
            for k in (0, 1, 5):
                self.assertAlmostEqual(fm.poisson(k, mu), pois_ref(k, mu), 12)

    def test_p_at_least(self):
        self.assertEqual(fm.p_at_least(0, 3), 0.0)
        self.assertEqual(fm.p_at_least(2.0, 0), 1.0)
        for mu, k in ((1.0, 1), (10.5, 10), (12.0, 12), (3.0, 7)):
            ref = 1 - sum(pois_ref(i, mu) for i in range(k))
            self.assertAlmostEqual(fm.p_at_least(mu, k), ref, 10)
        xs = [fm.p_at_least(mu, 10) for mu in (4, 6, 8, 10, 12)]
        self.assertEqual(xs, sorted(xs))   # more expected contributions, more likely to reach 10

    def test_exp_floor_div_matches_the_full_sum(self):
        # goals conceded: FPL takes a point per whole 2 conceded. The model only calls this for goals against (d=2), at
        # rates up to ~4; kmax=15 is exact to 0.001 there. (It drifts above ~5: -0.002 at 5, -0.04 at 7, never reached.)
        for mu, d in ((0.3, 2), (0.8, 2), (2.5, 2), (4.0, 2), (3.0, 3)):
            ref = sum((k // d) * pois_ref(k, mu) for k in range(200))
            self.assertAlmostEqual(fm.exp_floor_div(mu, d), ref, 3, (mu, d))


def el(pid, team=1, status="a", chance=None, news="", added=None):
    return dict(id=pid, team=team, element_type=3, status=status, chance_of_playing_next_round=chance,
                news=news, news_added=added)


def iso(day, hour=10):
    return (dt.datetime(2026, 9, 1, hour) + dt.timedelta(days=day - 1)).strftime("%Y-%m-%dT%H:%M:%SZ")


class AbsenceRules(unittest.TestCase):
    def setUp(self):
        # club 1 plays GW1-5 weekly (deadlines day 1, 8, 15, ...; kick-offs a day later); player 7 started GW1-3 and
        # missed GW4
        self.events = [dict(id=g, deadline_time=iso(1 + 7 * (g - 1)), finished=g <= 4) for g in range(1, 6)]
        self.fixtures = [dict(id=g, event=g, team_h=1, team_a=2, finished=g <= 4, kickoff_time=iso(2 + 7 * (g - 1), 15))
                         for g in range(1, 6)]
        self.team_fix = {1: [(g, 2, True, f) for g, f in zip(range(1, 6), self.fixtures)]}
        self.pstats = {7: {g: {"starts": int(g < 4), "minutes": 90 if g < 4 else 0} for g in range(1, 5)}}

    def boot(self, *els):
        return {"events": self.events, "elements": list(els)}

    def test_out_weeks_hindsight_switch(self):
        log = {"gws": {"3": {"7": ["i", 0]}}}
        b = self.boot(el(7, status="i", chance=0, added=iso(17)))
        self.assertEqual(fm.out_weeks(b, log, hindsight=False)[7], {3})
        self.assertEqual(fm.out_weeks(b, log)[7], {3, 4, 5})   # today's note (day 17) covers every later deadline

    def test_late_news_explains_a_regular_non_start(self):
        e = el(7, status="d", chance=50, news="Knock", added=iso(23, 18))   # posted after GW4's deadline, before it ended
        res = fm.late_news_absences(self.boot(e), {7: e}, self.pstats, self.team_fix, self.fixtures)
        self.assertEqual(res, {7: {4}})
        e2 = el(7, status="d", chance=50, news="Knock", added=iso(5))      # news from GW1: says nothing about GW4
        self.assertEqual(fm.late_news_absences(self.boot(e2), {7: e2}, self.pstats, self.team_fix, self.fixtures), {})

    def test_cleared_news_counts_only_near_the_game(self):
        e = el(7, news="", added=iso(20))     # available now; a note posted the week before GW4's deadline
        self.assertEqual(fm.news_absences(self.boot(e), {7: e}, self.pstats, self.team_fix, {}), {7: {4}})
        e2 = el(7, news="", added=iso(2))     # posted in GW1's week: too early to explain GW4
        self.assertEqual(fm.news_absences(self.boot(e2), {7: e2}, self.pstats, self.team_fix, {}), {})


class Odds(unittest.TestCase):
    def test_outcome_probs_add_up_and_are_symmetric(self):
        w, d, l, o = odds.outcome_probs(1.4, 1.4)
        self.assertAlmostEqual(w + d + l, 1.0, 6)
        self.assertAlmostEqual(w, l, 5)   # the draw/over fits are numerical; equal to 1e-5
        self.assertGreater(odds.outcome_probs(2.0, 1.5)[3], odds.outcome_probs(1.0, 0.8)[3])   # more goals, more overs

    def test_fit_lambdas_recovers_the_rates(self):
        for lh, la in ((1.8, 0.9), (1.2, 1.3), (2.6, 0.6)):
            w, d, l, o = odds.outcome_probs(lh, la)
            fh, fa = odds.fit_lambdas(w, l, o)
            self.assertAlmostEqual(fh, lh, delta=0.03)
            self.assertAlmostEqual(fa, la, delta=0.03)

    def test_match_fixtures_never_guesses(self):
        fixtures = [{"id": 10, "event": 5, "team_h": 1, "team_a": 2, "kickoff_time": "2026-09-20T14:00:00Z"}]
        short = {"ARS": 1, "AVL": 2}
        row = {"home": "Arsenal", "away": "Aston Villa", "p_h": 0.6, "p_d": 0.22, "p_a": 0.18, "p_over": 0.55, "played": False}
        out, unmatched, no_fx = odds.match_fixtures([dict(row, date="2026-09-21")], short, fixtures)
        self.assertEqual([m["fixture"] for m in out], [10])
        self.assertGreater(out[0]["lam_h"], out[0]["lam_a"])
        out, _, no_fx = odds.match_fixtures([dict(row, date="2026-09-30")], short, fixtures)   # 9 days out
        self.assertEqual((out, len(no_fx)), ([], 1))
        out, unmatched, _ = odds.match_fixtures([dict(row, home="Arsenal FC", date="2026-09-21")], short, fixtures)
        self.assertEqual((out, unmatched), ([], {"Arsenal FC"}))


class NameMatching(unittest.TestCase):
    def fpl(self, i, first, second, web, minutes=900):
        return {"id": i, "first_name": first, "second_name": second, "web_name": web, "minutes": minutes}

    def test_understat_one_to_one(self):
        by_team = {1: [self.fpl(1, "Bukayo", "Saka", "Saka"), self.fpl(2, "Martin", "Ødegaard", "Ødegaard"),
                       self.fpl(3, "Gabriel", "dos Santos Magalhães", "Gabriel")]}
        us = {"10": {"player_name": "Bukayo Saka", "team_title": "Arsenal", "time": "900"},
              "11": {"player_name": "Martin Odegaard", "team_title": "Arsenal", "time": "880"},
              "12": {"player_name": "Bukayo Saka", "team_title": "Arsenal", "time": "10"}}   # a duplicate name
        m, rej = understat.match_players(us, by_team, {"Arsenal": 1})
        self.assertEqual(m["10"][0], 1)
        self.assertEqual(m["11"][0], 2)
        self.assertNotIn("12", m)                      # FPL 1 is already taken by the better-scoring row
        self.assertIn("12", rej)

    def test_understat_too_close_is_rejected(self):
        by_team = {1: [self.fpl(1, "Joe", "Smith", "Smith", 500), self.fpl(2, "Joe", "Smith", "Smith", 500)]}
        m, rej = understat.match_players({"9": {"player_name": "Joe Smith", "team_title": "X", "time": "500"}}, by_team, {"X": 1})
        self.assertEqual(m, {})
        self.assertIn("too close", rej["9"])

    def test_bookmaker_names(self):
        squad = [self.fpl(1, "Gabriel", "Martinelli Silva", "Martinelli"), self.fpl(2, "Gabriel", "dos Santos Magalhães", "Gabriel"),
                 self.fpl(3, "Bukayo", "Saka", "Saka")]
        self.assertEqual(odds_players.match_player("Bukayo Saka", squad), 3)
        self.assertEqual(odds_players.match_player("Gabriel Martinelli", squad), 1)
        self.assertIsNone(odds_players.match_player("Erling Haaland", squad))
        self.assertIsNone(odds_players.match_player("", squad))


class TransferLog(unittest.TestCase):
    def test_snapshot_cadence(self):
        dl = dt.datetime(2026, 11, 21, 11, tzinfo=dt.timezone.utc)
        at = lambda h: dl - dt.timedelta(hours=h)
        self.assertFalse(transfer_log._due(at(100), at(96), dl))            # 4 h apart, far out: every 6 h
        self.assertTrue(transfer_log._due(at(102), at(96), dl))
        self.assertTrue(transfer_log._due(at(21), at(20), dl))              # inside 48 h: hourly
        self.assertFalse(transfer_log._due(at(2.5), at(2.2), dl))           # inside 3 h: every 25 min
        self.assertTrue(transfer_log._due(at(2.6), at(2.1), dl))


class XMins(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        api = json.load(gzip.open(ROOT / "tests" / "fixtures" / "season_end_api.json.gz"))
        boot = json.loads(json.dumps(api["/bootstrap-static/"]))
        live = {g: api[f"/event/{g}/live/"] for g in range(1, 11)}
        # a player with no history at all: drop his live rows
        cls.ghost = boot["elements"][0]["id"]
        for g in live:
            live[g] = dict(live[g], elements=[x for x in live[g]["elements"] if x["id"] != cls.ghost])
        cls.ctx = fm.prepare(boot, api["/fixtures/"], live, json.load(open(ROOT / "priors.json")))
        cls.nxt = next(e["id"] for e in boot["events"] if e["is_next"])

    def test_no_history_is_missing_not_zero_and_outputs_in_range(self):
        import xmins
        res = fm.project(self.ctx, self.nxt, 1, {"sim": 0})
        team_gws = {}
        # features for the whole league, via the same inputs project() builds
        kick, upcoming = {}, res["upcoming"]
        for f in self.ctx["fixtures"]:
            if f.get("event") and f.get("kickoff_time"):
                for t in (f["team_h"], f["team_a"]):
                    kick[(t, f["event"])] = dt.datetime.fromisoformat(f["kickoff_time"].replace("Z", "+00:00"))
                    if f.get("finished"):
                        team_gws.setdefault(t, set()).add(f["event"])
        feats = xmins.features(self.ctx, self.nxt, team_gws, kick, upcoming)
        names = xmins._load()[0]
        g = dict(zip(names, feats[self.ghost]))
        self.assertEqual(g["history_gws"], 0)
        self.assertTrue(math.isnan(g["minutes_avg_3"]) and math.isnan(g["last_minutes"]))
        pred = xmins.predict(self.ctx, self.nxt, team_gws, kick, upcoming)
        for ps, pc, ms, mc in pred.values():
            self.assertTrue(0 <= ps <= 1 and 0 <= pc <= 1 and 0 <= ms <= 90 and 1 <= mc <= 90)


if __name__ == "__main__":
    unittest.main()
