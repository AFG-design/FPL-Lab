"""FL-148: the Chase rank points limit written in CLAUDE.md matches the one optimise.py uses.

The optimiser has always held Chase rank to CHASE_BUDGET points below Balanced, but CLAUDE.md (the rules the owner
reviews against) didn't say so. This keeps the two from drifting apart: change one and this fails until the other
matches. Missing: if CLAUDE.md loses the sentence, the test fails rather than passing silently.
"""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import optimise  # noqa: E402


class ChaseLimit(unittest.TestCase):
    def test_claude_md_states_the_optimiser_chase_budget(self):
        text = (ROOT / "CLAUDE.md").read_text()
        m = re.search(r"Chase rank may give up at most ([\d.]+) projected points \(`CHASE_BUDGET = ([\d.]+)`", text)
        self.assertIsNotNone(m, "CLAUDE.md doesn't state Chase rank's points limit")
        self.assertEqual(float(m.group(1)), optimise.CHASE_BUDGET)
        self.assertEqual(float(m.group(2)), optimise.CHASE_BUDGET)

    def test_claude_md_states_the_play_safe_budget(self):
        text = (ROOT / "CLAUDE.md").read_text()
        m = re.search(r"Play safe gives up none \(`SAFE_BUDGET = ([\d.]+)`\)", text)
        self.assertIsNotNone(m, "CLAUDE.md doesn't state Play safe's points limit")
        self.assertEqual(float(m.group(1)), optimise.SAFE_BUDGET)


if __name__ == "__main__":
    unittest.main()
