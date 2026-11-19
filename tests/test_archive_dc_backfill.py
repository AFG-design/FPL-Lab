"""FL-212: archive priors use FPL's backfilled 2024/25 DefCon.

Tests:
  - tools/dc_backfill.py extraction (exact season only, no hindsight from 2025/26+), safety checks (>2% failed, <85% kept)
  - archive._priors() merge with 1:2 weights when vaastav CSV lacks defensive_contribution
  - missing-player fallback (players absent from archive_dc keep dc_mins = 0, dc90 = 0.0)
  - switch off (use_dc_backfill=False) reproduces main exactly
  - hindsight guard: 2024/25 test season never uses 2024/25 backfill; 2025/26 test season uses only 2024/25
  - committed archive_dc/2024-25.json schema and (when vaastav CSVs are cached) code join & >=70% coverage check
"""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import archive
from fplmodel import DEFAULTS
from tools import dc_backfill

ROOT = Path(__file__).resolve().parent.parent
MIN_COVERAGE = 0.70


class DcBackfillTool(unittest.TestCase):
    def test_extract_reads_exact_target_season_only(self):
        hist = [
            {"season_name": "2023/24", "minutes": 3000, "defensive_contribution": 0},
            {"season_name": "2024/25", "minutes": 2700, "defensive_contribution": 240},
            {"season_name": "2025/26", "minutes": 3100, "defensive_contribution": 310},
        ]
        self.assertEqual(dc_backfill.extract_season_dc(hist, "2024/25"), {"dc": 240, "minutes": 2700})
        # No 2024/25 row -> None even when 2025/26 is present (no hindsight leak)
        self.assertIsNone(dc_backfill.extract_season_dc([hist[0], hist[2]], "2024/25"))
        # Zero minutes or None defensive_contribution -> omitted
        self.assertIsNone(dc_backfill.extract_season_dc([{"season_name": "2024/25", "minutes": 0, "defensive_contribution": 0}], "2024/25"))
        self.assertIsNone(dc_backfill.extract_season_dc([{"season_name": "2024/25", "minutes": 900, "defensive_contribution": None}], "2024/25"))

    def test_rejects_season_before_dc_first(self):
        with self.assertRaises(ValueError):
            dc_backfill.season_to_fpl_name("2023-24")
        self.assertEqual(dc_backfill.season_to_fpl_name("2024-25"), "2024/25")

    def test_safety_checks_fail_loudly(self):
        # > 2% failed downloads -> SystemExit
        with self.assertRaises(SystemExit):
            dc_backfill.check_counts(new=300, previous=300, failed=3, total=100)
        # <= 2% failed downloads -> OK
        dc_backfill.check_counts(new=300, previous=300, failed=2, total=100)
        # < 85% of previous count -> SystemExit
        with self.assertRaises(SystemExit):
            dc_backfill.check_counts(new=200, previous=300, failed=0, total=600)


class ArchiveBackfillMerge(unittest.TestCase):
    def _rows(self, season, name):
        base = {"element_type": "2", "expected_goals": "0", "expected_assists": "0", "bonus": "0",
                "saves": "0", "yellow_cards": "0", "total_points": "60", "starts": "20",
                "expected_goal_involvements": "0"}
        if season == "2023-24":
            return [
                dict(base, code="101", minutes="1800"),
                dict(base, code="202", minutes="1800"),
            ]
        if season == "2024-25":
            # vaastav 2024-25 has no defensive_contribution column
            return [
                dict(base, code="101", minutes="2700"),
                dict(base, code="202", minutes="1800"),  # left the game: absent from backfill
            ]
        if season == "2025-26":
            return [dict(base, code="101", minutes="900", defensive_contribution="100")]
        return []

    def _backfill(self, season):
        if season == "2024-25":
            return {"season": "2024-25", "players": {"101": {"dc": 270, "minutes": 2700}}}
        return None

    def test_default_on(self):
        self.assertTrue(DEFAULTS["archive_dc_backfill"])

    def test_merge_uses_backfill_with_1_to_2_weights(self):
        with patch.object(archive, "_rows", self._rows), patch.object(archive, "load_dc_backfill", self._backfill):
            p = archive._priors("2025-26", {"101": 1, "202": 2}, use_dc_backfill=True)["players"]
        # Player 101: 2023-24 has wt=1 (no DC), 2024-25 has wt=2 (dc=270, min=2700 from backfill) -> total w=3
        self.assertAlmostEqual(p["1"]["dc90"], 9.0)
        self.assertEqual(p["1"]["dc_mins"], round(2 * 2700 / 3))
        self.assertEqual(p["1"]["mins"], round((1800 + 2 * 2700) / 3))

    def test_missing_player_keeps_zero_dc_mins(self):
        with patch.object(archive, "_rows", self._rows), patch.object(archive, "load_dc_backfill", self._backfill):
            p = archive._priors("2025-26", {"101": 1, "202": 2}, use_dc_backfill=True)["players"]
        # Player 202 is absent from backfill -> keeps dc_mins = 0, dc90 = 0.0
        self.assertEqual((p["2"]["dc_mins"], p["2"]["dc90"]), (0, 0.0))

    def test_switch_off_reproduces_main_exactly(self):
        with patch.object(archive, "_rows", self._rows), patch.object(archive, "load_dc_backfill", self._backfill):
            off = archive._priors("2025-26", {"101": 1, "202": 2}, use_dc_backfill=False)
        with patch.object(archive, "_rows", self._rows), patch.object(archive, "load_dc_backfill", lambda s: None):
            main_equiv = archive._priors("2025-26", {"101": 1, "202": 2}, use_dc_backfill=True)
        self.assertEqual(off, main_equiv)
        self.assertEqual((off["players"]["1"]["dc_mins"], off["players"]["1"]["dc90"]), (0, 0.0))

    def test_no_hindsight_in_2024_25_test_season(self):
        # 2024-25 test season priors come from 2022-23 + 2023-24 (both < DC_FIRST): backfill must never be called
        calls = []
        with patch.object(archive, "_rows", self._rows), patch.object(archive, "load_dc_backfill", lambda s: calls.append(s) or self._backfill(s)):
            p = archive._priors("2024-25", {"101": 1}, use_dc_backfill=True)["players"]
        self.assertEqual(calls, [])
        self.assertEqual((p["1"]["dc_mins"], p["1"]["dc90"]), (0, 0.0))

    def test_csv_column_wins_over_backfill_when_present(self):
        # For 2026-27 (priors 2024-25 + 2025-26): 2024-25 uses backfill (wt=1), 2025-26 uses CSV column (wt=2)
        with patch.object(archive, "_rows", self._rows), patch.object(archive, "load_dc_backfill", self._backfill):
            p = archive._priors("2026-27", {"101": 1}, use_dc_backfill=True)["players"]["1"]
        expected_dc = 1.0 * 270 + 2.0 * 100
        expected_min = 1.0 * 2700 + 2.0 * 900
        self.assertAlmostEqual(p["dc90"], expected_dc / expected_min * 90)
        self.assertEqual(p["dc_mins"], round(expected_min / 3.0))


class CommittedArchiveDcFile(unittest.TestCase):
    def test_committed_file_schema(self):
        path = ROOT / "archive_dc" / "2024-25.json"
        self.assertTrue(path.exists(), "archive_dc/2024-25.json must be committed")
        data = json.loads(path.read_text())
        self.assertEqual(data["season"], "2024-25")
        self.assertEqual(data["season_name"], "2024/25")
        self.assertTrue(data.get("source"))
        self.assertTrue(data.get("fetched"))
        players = data["players"]
        self.assertEqual(data["player_count"], len(players))
        self.assertGreaterEqual(len(players), 250)
        for code, row in players.items():
            self.assertTrue(code.isdigit(), f"non-numeric FPL code {code!r}")
            self.assertGreater(row["minutes"], 0)
            self.assertGreaterEqual(row["dc"], 0)

    def test_joins_to_vaastav_and_meets_coverage_floor(self):
        p24 = ROOT / "archive" / "2024-25" / "players_raw.csv"
        p25 = ROOT / "archive" / "2025-26" / "players_raw.csv"
        if not (p24.exists() and p25.exists()):
            self.skipTest("vaastav archive CSVs not cached locally")
        bf = archive.load_dc_backfill("2024-25")["players"]
        rows24 = [r for r in archive._rows("2024-25", "players_raw.csv") if r.get("element_type") != "5"]
        rows25 = [r for r in archive._rows("2025-26", "players_raw.csv") if r.get("element_type") != "5"]
        codes24_all = {r["code"] for r in rows24}
        unmatched = set(bf) - codes24_all
        self.assertEqual(unmatched, set(), f"backfill codes not in 2024-25 players_raw.csv: {sorted(unmatched)[:10]}")
        eligible = {r["code"] for r in rows25} & {r["code"] for r in rows24 if archive._num(r["minutes"]) >= 1}
        covered = eligible & set(bf)
        cov = len(covered) / len(eligible)
        self.assertGreaterEqual(
            cov, MIN_COVERAGE,
            f"2025/26 DefCon backfill coverage {len(covered)}/{len(eligible)} ({cov:.1%}) below {MIN_COVERAGE:.0%}",
        )


if __name__ == "__main__":
    unittest.main()
