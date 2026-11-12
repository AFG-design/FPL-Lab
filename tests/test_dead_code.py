"""FL-116: no dead site functions, no rejected model switches, no broken links to moved docs.

The 10 Nov audit (C1) found one-off scripts, switched-off model code, dead lines and unused front-end functions.
This keeps the clean-up from growing back.
"""
from pathlib import Path
import re
import unittest

import fplmodel

ROOT = Path(__file__).resolve().parent.parent


class DeadCode(unittest.TestCase):
    def test_every_top_level_site_function_is_used(self):
        files = list((ROOT / "site" / "js").rglob("*.js")) + [ROOT / "site" / "index.html", ROOT / "site" / "sw.js"]
        text = {f: f.read_text() for f in files}
        allt = "\n".join(text.values())
        unused = []
        for f, s in text.items():
            for m in re.finditer(r"^(?:async\s+)?function\s+(\w+)\s*\(|^const\s+(\w+)\s*=\s*(?:\([^)]*\)|\w+)\s*=>", s, re.M):
                name = m.group(1) or m.group(2)
                if len(re.findall(r"\b" + re.escape(name) + r"\b", allt)) <= 1:
                    unused.append(f"{f.relative_to(ROOT)}: {name}")
        self.assertEqual(unused, [])   # before FL-116: modeBar, rankSpark, vmPts, defClass, asmAttr

    def test_rejected_minutes_switches_are_gone(self):
        # p60_prior / mstart_prior: worse on both seasons at every weight (model log, 22 Oct); xmins_combine "A": more bias
        for p in ("p60_prior", "mstart_prior", "xmins_combine"):
            self.assertNotIn(p, fplmodel.DEFAULTS)
            self.assertNotIn(p, (ROOT / "fplmodel.py").read_text())

    def test_docs_named_in_code_exist(self):
        missing = []
        for f in list(ROOT.glob("*.py")) + list((ROOT / "scripts").glob("*.py")) + [ROOT / "README.md"]:
            for path in re.findall(r"docs/[\w./-]+\.(?:md|png|py)", f.read_text()):
                if not (ROOT / path).exists():
                    missing.append(f"{f.name}: {path}")
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
