"""FL-176: DefCon priors use only the minutes of seasons that recorded DefCon.

Old: FPL only records defensive_contribution from 2025/26 (backfilled for 2024/25 in history_past; the vaastav archive
has none before 2025-26). make_priors.py counted a season without it as 0 DefCon, archive._priors divided DefCon by all
minutes, and fplmodel gave the DefCon prior the all-minutes weight, so every DefCon prior was dragged towards 0.
New: dc90 = DefCon / DefCon-recorded minutes, "dc_mins" saved on the scale of "mins", and fplmodel weights the DefCon
prior by dc_mins (0 = no weight). A priors.json without dc_mins falls back to mins (the old behaviour).
"""
import contextlib
import copy
import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import archive
import make_priors as mp
from fplmodel import DEFAULTS, prepare, project
import validate

ROOT = Path(__file__).resolve().parent.parent


def season(name, minutes, dc=None):
    s = {"season_name": name, "minutes": minutes, "expected_goals": "1.0", "expected_assists": "0.5", "bonus": 3,
         "saves": 0, "yellow_cards": 1, "total_points": 50, "starts": minutes // 90, "expected_goal_involvements": "1.5"}
    if dc is not None:
        s["defensive_contribution"] = dc
    return s


class MakePriors(unittest.TestCase):
    def test_season_without_the_field_is_not_zero_defcon(self):
        p = mp.summarise([season("2024/25", 1800), season("2025/26", 900, dc=90)], 2026)
        self.assertAlmostEqual(p["dc90"], 9.0)                    # from the DefCon season only (was 90*2/(1800+1800)*90)
        self.assertEqual(p["dc_mins"], round(2 * 900 / 3))        # same 1:2 weights and per-season scale as mins
        self.assertEqual(p["mins"], round((1800 + 2 * 900) / 3))
        p = mp.summarise([season("2024/25", 1800)], 2026)
        self.assertEqual((p["dc_mins"], p["dc90"]), (0, 0.0))

    def test_field_at_zero_before_2024_25_is_not_recorded(self):
        # history_past carries defensive_contribution 0 for every season before 2024/25 (checked 19 Nov 2026)
        p = mp.summarise([season("2023/24", 3000, dc=0), season("2024/25", 900, dc=90)], 2025)
        self.assertAlmostEqual(p["dc90"], 9.0)
        self.assertEqual(p["dc_mins"], round(2 * 900 / 3))
        self.assertEqual(mp.summarise([season("2023/24", 3000, dc=0)], 2024)["dc_mins"], 0)

    def test_both_seasons_recorded_keeps_the_old_rate(self):
        p = mp.summarise([season("2024/25", 1800, dc=180), season("2025/26", 900, dc=90)], 2026)
        self.assertEqual(p["dc_mins"], p["mins"])
        self.assertAlmostEqual(p["dc90"], (180 + 2 * 90) / (1800 + 2 * 900) * 90)


class ArchivePriors(unittest.TestCase):
    def rows(self, season, name):
        base = {"code": "11", "element_type": "2", "expected_goals": "0", "expected_assists": "0", "bonus": "0",
                "saves": "0", "yellow_cards": "0", "total_points": "60", "starts": "20",
                "expected_goal_involvements": "0"}
        if season == "2024-25":
            return [dict(base, minutes="1800")]                           # vaastav: no DefCon column
        return [dict(base, minutes="900", defensive_contribution="90")]  # 2025-26 has it

    def test_mixed_two_seasons(self):
        with patch.object(archive, "_rows", self.rows):
            p = archive._priors("2026-27", {"11": 5})["players"]["5"]
        self.assertAlmostEqual(p["dc90"], 9.0)
        self.assertEqual(p["dc_mins"], round(2 * 900 / 3))

    def test_no_defcon_season_gives_zero_dc_mins(self):
        with patch.object(archive, "_rows", lambda s, n: self.rows("2024-25", n)):
            p = archive._priors("2025-26", {"11": 5})["players"]["5"]
        self.assertEqual((p["dc_mins"], p["dc90"]), (0, 0.0))


class ModelWeight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        api = json.load(gzip.open(ROOT / "tests" / "fixtures" / "season_end_api.json.gz"))
        cls.boot = api["/bootstrap-static/"]
        cls.fixtures = api["/fixtures/"]
        cls.live = {g: api[f"/event/{g}/live/"] for g in range(1, 11)}
        cls.priors = json.load(open(ROOT / "priors.json"))
        cls.nxt = next(e["id"] for e in cls.boot["events"] if e["is_next"])
        pid = {e["id"] for e in cls.boot["elements"] if e["element_type"] == 2}
        cls.pid = next(k for k, v in cls.priors["players"].items() if int(k) in pid and v["dc90"] > 5 and v["mins"] > 1500)

    def dc90(self, edit, params=None):
        pri = copy.deepcopy(self.priors)
        edit(pri["players"][self.pid])
        ctx = prepare(self.boot, self.fixtures, self.live, pri)
        return project(ctx, self.nxt, 1, dict({"sim": 0}, **(params or {})))["players"][int(self.pid)]["dc90"]

    def test_default_on(self):
        self.assertTrue(DEFAULTS["dc_prior_mins"])

    def test_dc_mins_zero_gives_the_prior_no_weight(self):
        a = self.dc90(lambda p: p.update(dc_mins=0, dc90=0.0))
        b = self.dc90(lambda p: p.update(dc_mins=0, dc90=20.0))
        self.assertAlmostEqual(a, b)                               # the prior's rate no longer matters
        c = self.dc90(lambda p: p.update(dc_mins=p["mins"], dc90=20.0))
        self.assertGreater(c, b)                                   # with DefCon minutes it does

    def test_old_priors_without_dc_mins_still_load_and_use_mins(self):
        old = self.dc90(lambda p: p.pop("dc_mins", None))
        same = self.dc90(lambda p: p.update(dc_mins=p["mins"]))
        self.assertAlmostEqual(old, same)

    def test_off_switch_rebuilds_the_all_minutes_rate(self):
        # dc_mins half of mins, dc90 over those minutes: off = all-minutes rate (half) at the all-minutes weight
        def half(p):
            p.update(dc_mins=p["mins"] // 2)
        def old(p):
            p.update(dc90=p["dc90"] * (p["mins"] // 2) / p["mins"])
            p.pop("dc_mins", None)
        self.assertAlmostEqual(self.dc90(half, {"dc_prior_mins": False}), self.dc90(old))



class ValidateFallbacks(unittest.TestCase):
    def health(self, players):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "history").mkdir()
            (root / "odds").mkdir()
            (root / "priors.json").write_text(json.dumps({"seasons": [2024, 2025], "players": players}))
            D = {"meta": {"built": "2026-11-12T12:00:00+00:00", "next_gw": 11, "cur_gw": 10, "team_id": 1},
                 "manager": {"free_transfers": 1, "bank": 0.0}, "squad": [], "players": [], "history": []}
            (root / "data.json").write_text(json.dumps(D))
            with patch.object(validate, "HERE", str(root)), contextlib.redirect_stdout(io.StringIO()):
                validate.main(root / "data.json")
            h = json.loads((root / "data.json").read_text())["health"]
            return ([w for w in h["warnings"] if "FL-176" in w], [e for e in h["errors"] if "dc_mins" in e])

    def test_counts_each_fallback(self):
        warn, err = self.health({"1": {"season": "2025/26", "mins": 2000},
                                 "2": {"season": "2025/26", "mins": 2000, "dc_mins": 0},
                                 "3": {"season": "2025/26", "mins": 2000, "dc_mins": 2000}})
        self.assertEqual(len(warn), 1)
        self.assertIn("1 of 3 priors have no dc_mins", warn[0])
        self.assertIn("1 have dc_mins 0", warn[0])
        self.assertEqual(err, [])

    def test_quiet_when_no_fallback_and_error_when_above_mins(self):
        self.assertEqual(self.health({"3": {"season": "2025/26", "mins": 2000, "dc_mins": 2000}}), ([], []))
        self.assertEqual(len(self.health({"3": {"season": "2025/26", "mins": 2000, "dc_mins": 2500}})[1]), 1)


if __name__ == "__main__":
    unittest.main()
