"""Exercise the production retry loop against a bare Git remote and a second writer."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.refresh import DATA, refresh


class RefreshRace(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.addCleanup(os.chdir, Path.cwd())
        os.chdir(self.root)
        self.git("init", "--bare", "-b", "main", "origin")
        self.git("clone", "origin", "runner")
        os.chdir("runner")
        self.identity()
        for path in DATA:
            Path(path).mkdir(parents=True)
            Path(path, "seed").touch()
        Path("history/status.json").write_text('{"gw":9}')
        self.commit("Base")
        self.git("push", "origin", "HEAD:main")
        self.git("clone", "../origin", "../rival")
        self.identity(self.root / "rival")

    def git(self, *args, cwd=None):
        return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()

    def identity(self, cwd=None):
        self.git("config", "user.name", "Refresh test", cwd=cwd)
        self.git("config", "user.email", "test@example.invalid", cwd=cwd)

    def commit(self, message, cwd=None):
        self.git("add", ".", cwd=cwd)
        self.git("commit", "-m", message, cwd=cwd)

    def test_competing_histories(self):
        rival = self.root / "rival"
        attempts = []

        def build():
            attempts.append(self.git("rev-parse", "HEAD"))
            if len(attempts) == 1:
                Path("history/absence_gw9.json").write_text("runner")
                Path("history/deadline_gw10.json").write_text("last pre-deadline sample")
                Path("history/status.json").write_text('{"gw":10}')
                (rival / "history/absence_gw9.json").write_text("main")
                (rival / "history/status.json").write_text('{"gw":11}')
                self.commit("Competing refresh", rival)
                self.git("push", cwd=rival)
            else:
                self.assertEqual(attempts[-1], self.git("rev-parse", "HEAD", cwd=rival))
                self.assertEqual(Path("history/status.json").read_text(), '{"gw":11}')

        refresh(build)
        for name, expected in [("absence_gw9.json", "main"), ("deadline_gw10.json", "last pre-deadline sample")]:
            self.assertEqual(self.git("show", f"origin/main:history/{name}"), expected)
        self.assertEqual(self.git("show", "origin/main^2:history/status.json"), '{"gw":10}')
        self.assertEqual(len(attempts), 2)

    def test_three_conflicts_fail(self):
        rival = self.root / "rival"
        attempts = []

        def build():
            attempts.append(1)
            Path("history/local").write_text(str(len(attempts)))
            (rival / "history/rival").write_text(str(len(attempts)))
            self.commit("Advance main", rival)
            self.git("push", cwd=rival)

        with self.assertRaisesRegex(RuntimeError, "attempt 3"):
            refresh(build)
        self.assertEqual(len(attempts), 3)
        self.assertEqual(self.git("show", "origin/main:history/rival"), "3")
