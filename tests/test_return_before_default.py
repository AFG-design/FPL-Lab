"""FL-067: a flagged player with no chance given is checked against FPL's return date before the 50% default.

'Suspended until 21 Nov' with no chance was projected at 50% for a game before 21 Nov. FPL's date says he is out.
Missing / late / ambiguous: no date in the note, a date that has passed while he is still flagged, or no kick-off
(blank week) keep the 50% default, marked assumed; 'Unknown return date' stays at 0.
"""
import datetime as dt
import unittest

from fplmodel import availability_info, return_date

TODAY = dt.date(2026, 11, 13)


def el(status, news, chance=None, added="2026-11-10T09:00:00Z"):
    return {"id": 1, "status": status, "chance_of_playing_next_round": chance, "news": news, "news_added": added}


def av(e, kickoff, today=TODAY):
    return availability_info(e, 0, kickoff, return_date(e), today)


class ReturnDateFirst(unittest.TestCase):
    def test_kickoff_before_the_date_is_out(self):
        self.assertEqual(av(el("s", "Suspended until 21 Nov"), dt.date(2026, 11, 20)), (0.0, False))
        self.assertEqual(av(el("i", "Hamstring injury - Expected back 29 Nov"), dt.date(2026, 11, 21)), (0.0, False))

    def test_on_or_after_the_date_keeps_the_assumed_default(self):
        # 'Suspended until D' means available from D (return_date docstring)
        self.assertEqual(av(el("s", "Suspended until 21 Nov"), dt.date(2026, 11, 21)), (0.5, True))

    def test_missing_or_stale_input_keeps_the_assumed_default(self):
        self.assertEqual(av(el("i", "Knee injury"), dt.date(2026, 11, 21)), (0.5, True))                    # no date
        self.assertEqual(av(el("s", "Suspended until 21 Nov"), None), (0.5, True))                          # blank week
        self.assertEqual(av(el("i", "Knock - Expected back 12 Nov"), dt.date(2026, 11, 11), TODAY), (0.5, True))  # passed
        self.assertEqual(av(el("i", "Knee injury - Unknown return date"), dt.date(2026, 11, 21)), (0.0, False))

    def test_fpl_chance_still_wins(self):
        self.assertEqual(av(el("i", "Expected back 29 Nov", chance=0), dt.date(2026, 11, 21)), (0.0, False))


if __name__ == "__main__":
    unittest.main()
