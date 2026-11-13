"""FL-147: the FPL School relay address (fpl_school.json) reaches data.json only as an https:// address; validate.py
warns about anything else, so the tab's "not set up" message has a reason on Health."""
import unittest

import validate


class SchoolRelay(unittest.TestCase):
    def test_warns_on_a_non_https_address(self):
        w = []
        validate.check_school({"school": {"relay": None, "relay_raw": "http://example"}}, w)
        self.assertIn("isn't an https:// address", w[0])

    def test_quiet_when_set_or_unset(self):
        for sc in ({"relay": "https://x.workers.dev", "relay_raw": "https://x.workers.dev"}, {"relay": None, "relay_raw": None}, None):
            w = []
            validate.check_school({"school": sc} if sc is not None else {}, w)
            self.assertEqual(w, [])

    def test_config_file_ships_empty(self):
        import json
        from pathlib import Path
        self.assertEqual(json.load(open(Path(__file__).resolve().parent.parent / "fpl_school.json")), {"relay": ""})


if __name__ == "__main__":
    unittest.main()
