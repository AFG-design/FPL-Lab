"""FL-128: build.py is a list of steps run by main(); importing it downloads and writes nothing.

Before, build.py ran top to bottom on import, so no part of it could be loaded or tested on its own. The split was
checked with tools/build_replay.py: the same recorded downloads and frozen clock gave byte-identical data.json,
data-extra.json, shots.json and history files before and after, at four different times of the week.
"""
import ast
import datetime
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(ROOT, "build.py")).read()


class ImportRunsNothing(unittest.TestCase):
    def test_import_makes_no_request_and_writes_nothing(self):
        code = ("import urllib.request as u\n"
                "def no(*a, **k): raise AssertionError('import made a request')\n"
                "u.urlopen = no\n"
                "import builtins\n_open = builtins.open\n"
                "def ro(f, mode='r', *a, **k):\n"
                "    assert not any(c in mode for c in 'wax+'), f'import wrote {f}'\n"
                "    return _open(f, mode, *a, **k)\n"
                "builtins.open = ro\n"
                "import build\n"
                "print(len(build.STEPS), callable(build.main))")
        r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr[-800:])
        n, ok = r.stdout.split()
        self.assertGreater(int(n), 30)
        self.assertEqual(ok, "True")


class OnlyDefinitionsAtTopLevel(unittest.TestCase):
    """New build code goes in a step (or a new step in STEPS), never back at the top level where it would run on import."""

    def test_top_level(self):
        tree = ast.parse(SRC)
        for st in tree.body:
            if isinstance(st, (ast.Import, ast.ImportFrom, ast.FunctionDef)):
                continue
            if isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant):   # the module docstring
                continue
            if isinstance(st, ast.If) and ast.unparse(st.test) == "__name__ == '__main__'":
                continue
            if isinstance(st, ast.Assign):
                # constants and the step list only: nothing that calls anything except int(os.environ.get(...))
                calls = [ast.unparse(c.func) for c in ast.walk(st.value) if isinstance(c, ast.Call)]
                self.assertTrue(set(calls) <= {"int", "os.environ.get", "os.path.dirname", "os.path.abspath"},
                                f"line {st.lineno} runs code at import: {ast.unparse(st)[:80]}")
                continue
            self.fail(f"line {st.lineno}: {type(st).__name__} at the top level runs on import")

    def test_steps_are_this_modules_functions_in_order(self):
        tree = ast.parse(SRC)
        defs = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
        steps = next(n for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == "STEPS")
        names = [e.id for e in steps.value.elts]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(set(names) <= set(defs))
        self.assertEqual(names, [d for d in defs if d in names], "STEPS runs in the order the steps are written")
        # every other function is a helper, not a forgotten step
        self.assertEqual(sorted(set(defs) - set(names)), ["get", "main"])


class ReplayClock(unittest.TestCase):
    def test_frozen_now(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import build_replay
        real = datetime.datetime, datetime.date
        try:
            pin = real[0](2026, 11, 21, 10, 30, tzinfo=datetime.timezone.utc)
            build_replay.freeze(pin)
            self.assertEqual(datetime.datetime.now(datetime.timezone.utc), pin)
            self.assertEqual(datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                             "2026-11-21T10:30:00+00:00")
            self.assertEqual(datetime.datetime.utcnow(), pin.replace(tzinfo=None))
        finally:
            datetime.datetime, datetime.date = real


if __name__ == "__main__":
    unittest.main()
