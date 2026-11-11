"""validate.check_sources: priors, match odds and the ownership sample are reported when missing or out of date."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import validate

BUILT = "2026-11-10T19:39:57+00:00"


class Sources(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "priors.json").write_text(json.dumps({"built": "2026-11-09T12:58:32Z", "players": {}}))
        self.D = {"meta": {"built": BUILT, "cur_gw": 10, "priors_season": "2025/26",
                           "odds": {"built": "2026-11-10T19:38:46Z", "matches": 110, "upcoming": 0}},
                  "crowd": {"gw": 10}}

    def run_check(self):
        warnings = []
        with patch.object(validate, "HERE", str(self.root)):
            validate.check_sources(self.D, warnings)
        return warnings

    def test_everything_fresh_is_quiet(self):
        self.assertEqual(self.run_check(), [])

    def test_older_data_without_the_sections_is_not_checked(self):
        self.D = {"meta": {"built": BUILT, "cur_gw": 10}}
        self.assertEqual(self.run_check(), [])

    def test_priors_missing_stale_or_undated(self):
        self.D["meta"]["priors_season"] = None
        self.assertIn("priors didn't load", self.run_check()[0])
        self.D["meta"]["priors_season"] = "2025/26"
        (self.root / "priors.json").write_text(json.dumps({"built": "2026-10-20T04:17:00Z"}))
        self.assertIn("priors are 22 days old", self.run_check()[0])
        (self.root / "priors.json").write_text(json.dumps({"built": "2026-10-26T19:39:57Z"}))   # exactly 15 days
        self.assertEqual(self.run_check(), [])
        (self.root / "priors.json").write_text(json.dumps({}))
        self.assertIn("priors: age unknown", self.run_check()[0])
        (self.root / "priors.json").unlink()
        self.assertIn("priors: age unknown", self.run_check()[0])

    def test_odds_missing_stale_or_undated(self):
        self.D["meta"]["odds"] = None
        self.assertIn("Match odds didn't load", self.run_check()[0])
        self.D["meta"]["odds"] = {"built": "2026-11-07T19:39:57Z"}
        self.assertIn("Match odds are 3.0 days old", self.run_check()[0])
        self.D["meta"]["odds"] = {"built": "2026-11-08T19:39:57Z"}                                # exactly 48 hours
        self.assertEqual(self.run_check(), [])
        self.D["meta"]["odds"] = {"matches": 110}
        self.assertIn("Match odds: age unknown", self.run_check()[0])

    def test_crowd_missing_or_for_another_gameweek(self):
        self.D["crowd"] = None
        self.assertIn("Ownership sample didn't load", self.run_check()[0])
        self.D["crowd"] = {"gw": 9}
        self.assertIn("Ownership sample is for GW9, not the current GW10", self.run_check()[0])
        self.D["crowd"] = {}
        self.assertIn("Ownership sample didn't load", self.run_check()[0])

    def test_before_the_season_no_sample_is_expected(self):
        self.D["meta"]["cur_gw"] = 0
        self.D["crowd"] = None
        self.assertEqual(self.run_check(), [])

    def test_chase_budget_default_matches_the_optimiser(self):
        import optimise
        src = Path(validate.__file__).read_text()
        self.assertIn(f'rules.get("chase_budget", {optimise.CHASE_BUDGET})', src)


if __name__ == "__main__":
    unittest.main()
