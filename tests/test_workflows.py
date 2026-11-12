"""FL-117: one push routine for every workflow that commits data, no duplicate workflows, no deprecated actions.

Before: crowd.yml and understat.yml re-ran steps the refresh job already runs and pushed with their own
`git pull --rebase && git push`, a third push routine beside scripts/push_data.py and refresh.py's own push; and every
action was pinned to a major on the Node 20 runtime, which GitHub has deprecated.
Missing / ambiguous: a workflow that adds an action not listed in MIN_MAJOR fails here, so its version is chosen on
purpose rather than copied from an old example.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows"
# First major of each action on the Node 24 runtime (upload-pages-artifact is composite: v5 is the first on
# upload-artifact v7). Checked against each action's action.yml on 12 Nov 2026.
MIN_MAJOR = {"checkout": 5, "setup-node": 5, "setup-python": 6, "upload-artifact": 6, "configure-pages": 6,
             "upload-pages-artifact": 5, "deploy-pages": 5}


def workflows():
    return {p.name: p.read_text() for p in sorted(WF.glob("*.yml"))}


class Workflows(unittest.TestCase):
    def test_duplicate_workflows_removed(self):
        self.assertFalse({"crowd.yml", "understat.yml"} & set(workflows()))

    def test_no_workflow_pushes_by_hand(self):
        for name, text in workflows().items():
            self.assertNotRegex(text, r"\bgit\s+(push|pull)\b", f"{name}: push through scripts/push_data.py")

    def test_every_data_workflow_uses_the_shared_routine(self):
        for name, text in workflows().items():
            if "contents: write" in text:
                self.assertRegex(text, r"scripts/(push_data|refresh)\.py", name)

    def test_only_push_data_runs_git_push(self):
        pushers = [p.name for p in (ROOT / "scripts").glob("*.py") if re.search(r"""['"]push['"]""", p.read_text())]
        self.assertEqual(pushers, ["push_data.py"])

    def test_actions_not_on_deprecated_runtime(self):
        for name, text in workflows().items():
            for action, major in re.findall(r"uses:\s*actions/([\w-]+)@v(\d+)", text):
                self.assertIn(action, MIN_MAJOR, f"{name}: choose a version for actions/{action}")
                self.assertGreaterEqual(int(major), MIN_MAJOR[action], f"{name}: actions/{action}@v{major}")


if __name__ == "__main__":
    unittest.main()
