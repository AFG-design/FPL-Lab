"""Each FL-084 validation change has passing and rejecting inputs, through the publish gate."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import validate
from squad_state import validation_source


def fixture():
    return {
        "meta": {"team_id": 42, "built": "2026-11-08T12:00:00+00:00", "picks_gw": 10,
                 "squad_gw": 10, "next_gw": 11, "cur_gw": 10, "fh_restored": False, "finished_gws": [9]},
        "manager": {"free_transfers": 3, "bank": 0.7}, "history": [],
        "squad": [{"id": i, "buy": 5.0, "sell": 5.1} for i in range(1, 16)],
        "players": [{"id": i, "name": f"Player {i}", "price": 5.3, "starts": 1, "mins": 90,
                     "pos": "MID", "xp": {"11": 2.0}} for i in range(1, 16)],
    }


class Validator(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "history").mkdir()
        self.D = fixture()
        self.detail = {"built": self.D["meta"]["built"], "players": {}, "squad_source": {
            "team_id": 42, "picks_gw": 10, "chips": [], "before_free_hit": None}}

    def run_check(self, expected=None):
        path = self.root / "data.json"
        path.write_text(json.dumps(self.D))
        (self.root / "data-extra.json").write_text(json.dumps(self.detail))
        with patch.object(validate, "HERE", str(self.root)), contextlib.redirect_stdout(io.StringIO()):
            result = validate.main(path)
        health = json.loads(path.read_text())["health"]
        if expected is None:
            self.assertEqual(result, 0, health["errors"])
            self.assertTrue(health["ok"])
        else:
            self.assertEqual(result, 1, health)
            self.assertTrue(any(expected in e for e in health["errors"]), health["errors"])
        return health

    def free_hit(self):
        self.D["meta"].update(fh_restored=True, squad_gw=9)
        self.D["history"] = [{"gw": 10, "chip": "freehit"}]
        self.detail["squad_source"].update(chips=[{"event": 10, "name": "freehit"}],
            before_free_hit={"gw": 9, "ids": list(range(1, 16))})

    def test_free_transfers(self):
        for n in range(6):
            self.D["manager"]["free_transfers"] = n
            self.run_check()
        for n in (-1, 6, 1.5, None, True, float("nan")):
            self.D["manager"]["free_transfers"] = n
            self.run_check("free_transfers")

    def test_bank(self):
        for n in (0, 0.7, 100):
            self.D["manager"]["bank"] = n
            self.run_check()
        for n in (-0.1, None, True, float("nan"), float("inf")):
            self.D["manager"]["bank"] = n
            self.run_check("bank")

    def test_selling_rule_rise_odd_profit_fall_unchanged(self):
        for current, expected in ((5.4, 5.2), (5.3, 5.1), (4.8, 4.8), (5.0, 5.0)):
            with self.subTest(current=current):
                self.D["players"][0]["price"] = current
                self.D["squad"][0]["sell"] = expected
                self.run_check()
                self.D["squad"][0]["sell"] = expected - 0.1
                self.run_check("FPL profit rule")

    def test_sell_no_higher_than_current_and_valid_tenths(self):
        self.run_check()
        self.D["squad"][0]["sell"] = 5.4
        self.run_check("exceeds current")
        for n in (-1, 5.11, None, float("nan"), float("inf")):
            self.D["squad"][0]["sell"] = n
            self.run_check("buy/sell/current prices")

    def test_price_inputs_missing_or_invalid_fail(self):
        self.run_check()
        del self.D["squad"][0]["buy"]
        self.run_check("buy/sell/current prices")
        self.D["squad"][0]["buy"] = 5
        del self.D["players"][0]["price"]
        self.run_check("buy/sell/current prices")

    def test_restore_compares_players_not_metadata(self):
        self.free_hit()
        self.run_check()
        self.D["squad"][0]["id"] = 16  # leave both consistent metadata fields unchanged
        self.D["players"].append(dict(self.D["players"][0], id=16))
        self.run_check("differs from FPL GW9 picks")

    def test_history_catches_false_restore_flag_and_wrong_week(self):
        self.free_hit()
        self.run_check()
        self.D["meta"].update(fh_restored=False, squad_gw=10)
        self.run_check("flag disagrees")
        self.D["meta"]["fh_restored"] = True
        self.run_check("FPL history requires GW9")

    def test_restore_requires_complete_matching_evidence(self):
        self.free_hit()
        self.run_check()
        good = copy.deepcopy(self.detail)
        for key, value in (("team_id", 43), ("picks_gw", 8), ("chips", None)):
            self.detail = copy.deepcopy(good)
            self.detail["squad_source"][key] = value
            self.run_check("source evidence")
        self.detail = copy.deepcopy(good)
        self.detail["built"] = "old"
        self.run_check("source evidence")
        for before in (None, {"gw": 8, "ids": list(range(1, 16))}, {"gw": 9, "ids": [1] * 15}):
            self.detail = copy.deepcopy(good)
            self.detail["squad_source"]["before_free_hit"] = before
            self.run_check("no complete pre-Free-Hit picks")
        del self.detail["squad_source"]
        self.run_check("no independent FPL")

    def test_normal_week_and_gw38_do_not_restore(self):
        self.run_check()
        self.D["meta"]["fh_restored"] = True
        self.run_check("flag disagrees")
        self.D["meta"]["fh_restored"] = False
        self.D["meta"]["next_gw"] = None
        self.detail["squad_source"]["chips"] = [{"name": "freehit", "event": 10}]
        self.run_check()

    def test_missing_legacy_detail_stays_a_warning_except_required_restore(self):
        self.detail = {}
        h = self.run_check()
        self.assertIn("data-extra.json missing or empty", " ".join(h["warnings"]))
        self.assertIn("No squad_source evidence", " ".join(h["warnings"]))

    def test_squad_cannot_be_empty_after_first_deadline(self):
        self.run_check()
        self.D["squad"] = []
        self.run_check("squad has 0 picks")
        self.D["meta"].update(picks_gw=0, squad_gw=0)
        self.detail["squad_source"]["picks_gw"] = 0
        self.run_check()

    def test_starts_checked_without_extra_and_nan_rejected(self):
        self.run_check()
        for n in (91, -1, float("nan")):
            self.D["players"][0]["starts"] = n
            self.run_check("starts with")

    def test_xp_detail_non_finite_and_empty_cannot_bypass_sum(self):
        for parts, expected in (({"goals": 2}, None), ({"goals": 1}, "xp_detail"),
                                ({"goals": float("nan")}, "xp_detail"), ({}, "xp_detail")):
            self.detail["players"] = {"1": {"xp_detail": parts}}
            self.run_check(expected)

    def test_snapshot_exists_but_projection_missing_fails(self):
        (self.root / "history/proj_gw9.json").write_text('{}')
        self.D["review"] = {"weeks": [{"gw": 9, "proj_src": "snapshot", "xi_proj": 30}]}
        self.run_check()
        self.D["review"]["weeks"][0].update(xi_proj=None, proj_src="none")
        self.run_check("pre-deadline snapshot exists")

    def test_empty_finished_weeks_does_not_disable_journal_check(self):
        self.D["journal"] = {"weeks": [{"gw": 9, "both": [], "yours": [], "skipped": [],
            "you": {"moves": [], "captain": None}, "players": {},
            "outcome": {"gws": [9], "of": 3, "moves": {}}}]}
        self.run_check()
        self.D["meta"]["finished_gws"] = []
        self.run_check("not finished")

    def test_plan_budgets_reject_nan_and_missing_hit_gain(self):
        self.D["plans"] = {"best": {"weeks": [], "vs_balanced": 0, "vs_none": 0}}
        self.D["plan_rules"] = {"hit_gain": 1, "ft_value": 1.5, "recommend_margin": 0.5}
        self.D["recommended"] = {"balanced": None, "safe": None, "chase": None}   # "best" is never the recommendation (FL-108)
        self.run_check()
        for field in ("vs_balanced", "vs_none"):
            self.D["plans"]["best"][field] = float("nan")
            self.run_check("budget figures")
            self.D["plans"]["best"][field] = 0
        self.D["plans"]["best"]["weeks"] = [{"hits": 1, "xi": list(range(1, 12)), "captain": 1}]
        self.D["plans"]["best"]["hit_gain"] = 1
        self.run_check()
        self.D["plans"]["best"]["hit_gain"] = float("nan")
        self.run_check("budget figures")
        del self.D["plans"]["best"]["hit_gain"]
        self.run_check("budget figures")

    def test_recommended_plan_is_one_definition(self):
        """FL-108: data.json names one recommended plan per strategy, and it is the one the rule picks."""
        plan = lambda vs: {"weeks": [], "vs_balanced": 0, "vs_none": vs, "vs_roll": vs, "xp_total": 240 + vs, "ft_left": 1,
                           "value": 241.5 + vs}
        self.D["plans"] = {"roll": plan(0.0), "one": plan(-0.9), "two": plan(0.19), "three": plan(0.19)}
        self.D["plan_rules"] = {"hit_gain": 2, "ft_value": 1.5, "recommend_margin": 0.5}
        self.D["recommended"] = {"balanced": "roll", "safe": None, "chase": None}
        self.run_check()
        self.D["recommended"]["balanced"] = "three"            # the highest single-week score, not the rule's pick
        self.run_check("rule picks 'roll'")
        self.D["recommended"]["balanced"] = "safe_roll"
        self.run_check("isn't among the plans")
        del self.D["recommended"]
        self.run_check("without 'recommended'")
        self.D["recommended"] = {"balanced": "roll", "safe": None, "chase": None}
        del self.D["plan_rules"]["recommend_margin"]
        self.run_check("recommend_margin missing")
    def test_moves_this_week_must_beat_rolling(self):
        """FL-110: a plan with moves this week needs vs_roll >= min_profit (FL-073: Roll is no longer exempt)."""
        wk = lambda n: [{"in": list(range(20, 20 + n)), "out": list(range(1, 1 + n)), "hits": 0,
                         "xi": list(range(1, 12)), "captain": 1}]
        plan = lambda n, vs_roll, vs_none: {"weeks": wk(n), "vs_balanced": 0, "vs_none": vs_none, "vs_roll": vs_roll,
                                            "xp_total": 240 + vs_none, "ft_left": 1, "value": 241.5 + vs_none}
        self.D["players"] += [{"id": i, "name": f"P{i}", "price": 5.0, "pos": "MID", "xp": {}} for i in range(20, 23)]
        self.D["plans"] = {"roll": plan(0, 0.0, 4.0), "three": plan(3, 1.2, 5.2)}
        self.D["plan_rules"] = {"ft_value": 1.5, "min_profit": 1.0, "tie": 0.1, "recommend_margin": 1.0}
        self.D["recommended"] = {"balanced": "three", "safe": None, "chase": None}
        self.run_check()
        self.D["plans"]["three"].update(vs_roll=0.32, vs_none=4.32, xp_total=244.32, value=245.82)
        self.D["recommended"]["balanced"] = "roll"
        self.run_check("vs rolling this week, short of the profit rule")
        del self.D["plans"]["three"]["vs_roll"]
        self.run_check("has no vs_roll")

    def test_planner_gain_matches_vs_none(self):
        """FL-125: the Planner rebuilds vs_none from xp_total, ft_left and plan_rules.ft_value."""
        plan = lambda xp, ft, vs: {"weeks": [], "vs_balanced": 0, "vs_none": vs, "xp_total": xp, "ft_left": ft,
                                   "value": xp + 1.5 * ft}
        self.D["plans"] = {"roll": plan(243.0, 4, 5.88), "chase_roll": plan(242.54, 3, 3.92)}
        self.D["plan_rules"] = {"ft_value": 1.5, "tie": 0.1, "recommend_margin": 0.5}
        self.D["recommended"] = {"balanced": None, "safe": None, "chase": None}   # no vs_roll on these plans: nothing to compare
        self.run_check()
        del self.D["plan_rules"]["ft_value"]
        self.run_check("plan_rules.ft_value")
        self.D["plan_rules"]["ft_value"] = 1.5
        self.D["plans"]["roll"]["value"] += 1.5          # FT counted at a different rate from plan_rules
        self.run_check("isn't xP")
        self.D["plans"]["roll"] = plan(243.0, 4, 7.38)    # points-only gain: a different baseline from chase_roll
        self.run_check("no-transfers baseline")

    def test_deadline_parse_failure_remains_a_warning(self):
        self.D["meta"]["deadline"] = "2026-11-09T12:00:00+00:00"
        snapshot = {"gw": 11, "built": self.D["meta"]["built"],
                    "xp": {str(i): [2] for i in range(1, 16)}}
        path = self.root / "history/deadline_gw11.json"
        path.write_text(json.dumps(snapshot))
        h = self.run_check()
        self.assertNotIn("wasn't rewritten", " ".join(h["warnings"]))
        snapshot["built"] = "invalid timestamp"
        path.write_text(json.dumps(snapshot))
        h = self.run_check()
        self.assertIn("wasn't rewritten", " ".join(h["warnings"]))

    def test_next_target_non_finite_does_not_bypass_tolerance(self):
        self.D["vs_model"] = {"next": {"target": {"xi": list(range(1, 12)), "exp": 30, "par": None}}}
        self.run_check()
        self.D["vs_model"]["next"]["target"]["exp"] = float("nan")
        self.run_check("next week's target doesn't add up")
        self.D["vs_model"]["next"]["target"]["exp"] = 30
        self.D["vs_model"]["next"]["target"]["par"] = 30          # FL-109: nothing to beat before it is played
        self.run_check("hasn't been played")


class Evidence(unittest.TestCase):
    def test_source_uses_history_and_raw_picks_not_restore_metadata(self):
        calls = []
        def fetch(g):
            calls.append(g)
            return {"entry_history": {"event": g}, "picks": [{"element": i} for i in range(1, 16)]}
        src = validation_source({"chips": [{"event": 10, "name": "freehit"}]}, 10, 11, fetch, 42)
        self.assertEqual(calls, [9])
        self.assertEqual(src["before_free_hit"], {"gw": 9, "ids": list(range(1, 16))})
        self.assertEqual(validation_source({"chips": []}, 10, 11, fetch, 42)["before_free_hit"], None)
        self.assertEqual(calls, [9])

    def test_source_failure_is_not_swallowed(self):
        def fail(g):
            raise OSError("FPL unavailable")
        with self.assertRaises(OSError):
            validation_source({"chips": [{"event": 10, "name": "freehit"}]}, 10, 11, fail, 42)


if __name__ == '__main__':
    unittest.main()
