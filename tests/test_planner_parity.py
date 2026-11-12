"""FL-075: the browser solver (site/plan-solver.js) reaches the server's plan value (optimise.solve) with the settings
data.json ships, for Balanced and Chase rank. Runs tests/parity/planner-parity.mjs with Node; it lives outside
`npm test` because it calls optimise.py, which needs PuLP (CI installs the Python packages after npm test).
Missing Node: the test fails, it isn't skipped."""
import os
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Parity(unittest.TestCase):
    def test_browser_matches_server(self):
        r = subprocess.run(["node", "--test", os.path.join("tests", "parity", "planner-parity.mjs")], cwd=ROOT,
                           capture_output=True, text=True, timeout=600)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
