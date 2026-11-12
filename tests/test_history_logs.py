"""FL-120: history/news.json and history/prices.json are never reset and overwritten when they can't be read.

Before, each was loaded with a bare `except Exception` that fell back to an empty log, which the build then wrote over
the file: one bad read (a half-written file, a merge conflict, the wrong shape) lost 90 days of injury news or 40 nights
of price changes for good. Now they are protected the way history/status.json is: never overwritten when unreadable,
written atomically, and reported on Data health.
"""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_harness import offline_build  # noqa: E402

BROKEN = {"news.json": '{"12": [["2026-11-01T10:00:00Z", "i", 0, "Knee injury"]], ',   # cut off mid-write
          "prices.json": '{"pending": {}, "nights": "not a list"}'}                     # valid JSON, wrong shape


class Unreadable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def prepare(repo):
            for name, text in BROKEN.items():
                (repo / "history" / name).write_text(text)
        cls.repo, cls.D, cls.rc, _ = offline_build(cls, prepare)

    def test_files_left_untouched(self):
        for name, text in BROKEN.items():
            self.assertEqual((self.repo / "history" / name).read_text(), text, name)
            self.assertFalse((self.repo / "history" / (name + ".tmp")).exists())

    def test_reported(self):
        self.assertEqual((self.D["sources"]["news"]["ok"], self.D["sources"]["prices"]["ok"]), (False, False))
        self.assertEqual(self.rc, 0, self.D["health"]["errors"])   # a warning: the rest of the site still publishes
        w = self.D["health"]["warnings"]
        for key in ("news", "prices"):
            self.assertTrue(any(x.startswith(f"history/{key}.json is unreadable") for x in w), (key, w))


class FirstRun(unittest.TestCase):
    """No file yet: the build starts one, which is not a fault."""

    @classmethod
    def setUpClass(cls):
        def prepare(repo):
            for name in BROKEN:
                (repo / "history" / name).unlink(missing_ok=True)
        cls.repo, cls.D, cls.rc, _ = offline_build(cls, prepare)

    def test_files_started_and_not_reported(self):
        news = json.loads((self.repo / "history" / "news.json").read_text())
        prices = json.loads((self.repo / "history" / "prices.json").read_text())
        self.assertGreater(len(news), 0)   # every flagged player gets a first entry
        self.assertIsInstance(prices["nights"], list)
        self.assertEqual((self.D["sources"]["news"]["ok"], self.D["sources"]["prices"]["ok"]), (True, True))
        self.assertFalse(any("unreadable" in x for x in self.D["health"]["warnings"]))


class ExistingLogIsKept(unittest.TestCase):
    """A good log is read and added to, never replaced."""

    @classmethod
    def setUpClass(cls):
        cls.old = [["2026-01-01T00:00:00Z", "i", 0, "Old injury"]]

        def prepare(repo):
            (repo / "history" / "news.json").write_text(json.dumps({"999999": cls.old}))
        cls.repo, cls.D, cls.rc, _ = offline_build(cls, prepare)

    def test_old_entry_survives(self):
        news = json.loads((self.repo / "history" / "news.json").read_text())
        self.assertEqual(news["999999"], self.old)   # still flagged, so the 90-day trim keeps it
        self.assertTrue(self.D["sources"]["news"]["ok"])


if __name__ == "__main__":
    unittest.main()
