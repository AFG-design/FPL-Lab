"""Regression tests for tests/build_harness.py GW-rollover isolation."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_harness  # noqa: E402


class AlignRepoToGw(unittest.TestCase):
    def test_prunes_future_gw_state_and_pins_crowd_latest(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "crowd").mkdir()
            (repo / "history").mkdir()
            # Simulate a future GW rollover (GW12) while the API fixture is frozen at GW10
            (repo / "crowd" / "latest.json").write_text(json.dumps({"gw": 12}))
            (repo / "crowd" / "history.json").write_text(json.dumps({"gws": {"9": {}, "10": {}, "11": {}, "12": {}}}))
            (repo / "history" / "status.json").write_text(json.dumps({"gws": {"9": {}, "10": {}, "11": {}, "12": {}}}))
            (repo / "history" / "awards.json").write_text(json.dumps({
                "leagues": {"1": {"name": "L", "gws": {"10": {}, "11": {}, "12": {}}}}
            }))
            (repo / "history" / "proj_gw10.json").write_text("{}")
            (repo / "history" / "proj_gw11.json").write_text("{}")
            (repo / "history" / "deadline_gw12.json").write_text("{}")

            build_harness._align_repo_to_gw(repo, cur=10)

            self.assertEqual(json.loads((repo / "crowd" / "latest.json").read_text())["gw"], 10)
            self.assertEqual(sorted(json.loads((repo / "crowd" / "history.json").read_text())["gws"]), ["10", "9"])
            self.assertEqual(sorted(json.loads((repo / "history" / "status.json").read_text())["gws"]), ["10", "9"])
            self.assertEqual(
                sorted(json.loads((repo / "history" / "awards.json").read_text())["leagues"]["1"]["gws"]),
                ["10"],
            )
            self.assertTrue((repo / "history" / "proj_gw10.json").exists())
            self.assertFalse((repo / "history" / "proj_gw11.json").exists())
            self.assertFalse((repo / "history" / "deadline_gw12.json").exists())


if __name__ == "__main__":
    unittest.main()
