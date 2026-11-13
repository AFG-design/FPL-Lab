"""FL-031: the doubtful-flag absence rule (doubtful_absences) can be switched off on its own (doubt_abs), apart from the
late-news rule (late_abs), so each injury adjustment can be tested one at a time. Backtest ablation result: both kept
(docs/model-log.md, 13 Nov).
"""
import unittest

from fplmodel import DEFAULTS, prepare, project
from tests.test_honest_backtest import fx, iso, row


def ctx_doubtful():
    # a regular starter (GW1-3), flagged 'd' 50% at GW4's deadline (status log) and then not starting GW4
    el = dict(id=7, team=1, element_type=3, status="a", chance_of_playing_next_round=None, news_added=None, news="",
              penalties_order=None, now_cost=60)
    boot = {"elements": [el], "teams": [{"id": t} for t in (1, 2)],
            "events": [dict(id=g, deadline_time=iso(1 + 7 * (g - 1)), finished=g <= 4) for g in range(1, 7)],
            "game_config": {"scoring": dict(short_play=1, long_play=2, assists=3, goals_scored={"MID": 5},
                                            clean_sheets={"MID": 1}, goals_conceded={"MID": 0},
                                            defensive_contribution={"MID": 2})}}
    fixtures = [fx(g, g, 1, 2, 2 + 7 * (g - 1)) for g in range(1, 5)]
    fixtures += [dict(fx(g, g, 1, 2, 2 + 7 * (g - 1)), finished=False, team_h_score=None, team_a_score=None) for g in (5, 6)]
    live = {g: {"elements": [row(7, g, minutes=0 if g == 4 else 90, starts=int(g != 4))]} for g in range(1, 5)}
    return prepare(boot, fixtures, live, status_log={"gws": {"4": {"7": ["d", 50]}}})


class Split(unittest.TestCase):
    def ret(self, **p):
        return project(ctx_doubtful(), 5, 1, dict(use_flags=False, xmins=False, sim=0, **p))["players"][7]["returning"]

    def test_defaults_on(self):
        self.assertTrue(DEFAULTS["late_abs"] and DEFAULTS["doubt_abs"])

    def test_each_rule_on_its_own(self):
        self.assertTrue(self.ret())                       # the doubtful week counts as an absence: back from it
        self.assertTrue(self.ret(late_abs=False))         # late_abs no longer reaches the doubtful rule
        self.assertFalse(self.ret(doubt_abs=False))       # read as dropped instead


if __name__ == "__main__":
    unittest.main()
