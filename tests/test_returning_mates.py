"""FL-094: returns are defined from the status log only (flagged at the previous deadline, cleared at this one),
never by whether he then started, so the check can't pick events by their outcome."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import returning_mates as rm


def st(starts, mins):
    return {"starts": starts, "minutes": mins}


class Events(unittest.TestCase):
    def ctx(self):
        el = {1: {"team": 1, "element_type": 2}, 2: {"team": 1, "element_type": 2}, 3: {"team": 1, "element_type": 2}}
        ps = {1: {g: st(1, 90) for g in range(1, 6)},                   # regular, then out GW6-7
              2: {**{g: st(0, 0) for g in range(1, 6)}, 6: st(1, 90), 7: st(1, 90)},   # covered GW6-7
              3: {g: st(1, 90) for g in range(1, 9)}}                    # another regular
        ps[1].update({6: st(0, 0), 7: st(0, 0), 8: st(0, 10)})          # back in GW8 but only on the bench
        return {"elements": el, "pstats": ps}

    def test_return_from_the_log_whether_or_not_he_started(self):
        log = {"gws": {str(g): {} for g in range(1, 9)}}
        log["gws"]["7"] = {"1": ["i", 0]}                                 # flagged at GW7's deadline, cleared at GW8's
        evs = rm.events(self.ctx(), log, 8)
        self.assertEqual([(k, r) for k, r, _ in evs], [(8, 1)])          # counted although he didn't start GW8
        self.assertEqual(evs[0][2], [2])                                  # the stand-in, not the other regular

    def test_no_log_entry_no_event(self):
        log = {"gws": {str(g): {} for g in range(1, 9)}}                  # never flagged: a drop, not a return
        self.assertEqual(rm.events(self.ctx(), log, 8), [])


if __name__ == "__main__":
    unittest.main()
