"""FL-152: crowd/history.json (the template tracker's week-by-week top-10k sample) is never reset and overwritten.

Before, it was read with a bare `except Exception` that fell back to an empty log, and the next time a gameweek's
sample was added that empty log was written over the file, losing every earlier week. template_backfill.py can't undo
that: it only re-creates survivorship-biased "backfill" weeks, never the real weekly samples. Now it is protected like
history/news.json and history/prices.json (FL-120): never overwritten when unreadable, written atomically, and
reported on Data health.
"""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_harness import offline_build  # noqa: E402

REL = Path("crowd") / "history.json"


class Unreadable(unittest.TestCase):
    CASES = {"cut off": '{"gws": {"7": {"n": 2000, "source": "sample", "own": {"1": 50.0}, ',
             "wrong shape": '{"gws": {"7": {"n": 2000, "source": "sample", "own": [1, 2]}}}'}

    def check(self, text):
        def prepare(repo):
            (repo / REL).write_text(text)
        repo, D, rc, _ = offline_build(self, prepare)
        self.assertEqual((repo / REL).read_text(), text)            # left untouched, even though a sample was due
        self.assertFalse((repo / "crowd" / "history.json.tmp").exists())
        self.assertIs(D["sources"]["template"]["ok"], False)
        self.assertEqual(rc, 0, D["health"]["errors"])                # a warning: the rest of the site publishes
        self.assertTrue(any(x.startswith("crowd/history.json is unreadable") for x in D["health"]["warnings"]),
                        D["health"]["warnings"])

    def test_cut_off(self):
        self.check(self.CASES["cut off"])

    def test_wrong_shape(self):
        self.check(self.CASES["wrong shape"])


class ExistingLogIsAddedTo(unittest.TestCase):
    """A good log keeps its old weeks and gains the new sample."""

    @classmethod
    def setUpClass(cls):
        cls.old = {"n": 500, "source": "backfill", "own": {"1": 12.5}, "eo": {"1": 12.5}, "cap": {}}

        def prepare(repo):
            cls.gw = json.loads((repo / "crowd" / "latest.json").read_text())["gw"]
            (repo / REL).write_text(json.dumps({"gws": {"1": cls.old}}))
        cls.repo, cls.D, cls.rc, _ = offline_build(cls, prepare)

    def test_old_week_kept_new_week_added(self):
        gws = json.loads((self.repo / REL).read_text())["gws"]
        self.assertEqual(gws["1"], self.old)
        self.assertEqual(gws[str(self.gw)]["source"], "sample")
        self.assertIs(self.D["sources"]["template"]["ok"], True)
        self.assertFalse(any("crowd/history.json" in x for x in self.D["health"]["warnings"]))


class FirstRun(unittest.TestCase):
    """No file yet: the build starts one from this week's sample, which is not a fault."""

    @classmethod
    def setUpClass(cls):
        cls.repo, cls.D, cls.rc, _ = offline_build(cls, lambda repo: (repo / REL).unlink())

    def test_started_and_not_reported(self):
        self.assertTrue(json.loads((self.repo / REL).read_text())["gws"])
        self.assertIs(self.D["sources"]["template"]["ok"], True)


if __name__ == "__main__":
    unittest.main()
