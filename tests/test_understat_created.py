"""Chances created in understat.py (audit B9): a player's created tally must not depend on him having shot.

Synthetic shot rows only: no network. The last class runs understat.main() end to end with the FPL and Understat
fetches replaced, to check the lookup is wired into the file it writes."""
import contextlib
import io
import json
import os
import tempfile
import unittest
import warnings
from collections import defaultdict
from unittest.mock import patch

import understat
import validate


def tally(rows):
    """Shot-row tallies the way main() keeps them: rows are (club code, assister name, xG, in the last 4 GWs)."""
    per = defaultdict(lambda: defaultdict(float))
    for code, assister, xg, recent in rows:
        k = ("a", code, assister)
        per[k]["cc"] += 1
        per[k]["bcc"] += xg >= 0.3
        if recent:
            per[k]["cc_4"] += 1
            per[k]["bcc_4"] += xg >= 0.3
    return per


class CreatedCounts(unittest.TestCase):
    def test_creator_with_no_shots(self):
        per = tally([("ARS", "Pure Creator", 0.1, False), ("ARS", "Pure Creator", 0.4, False)])
        self.assertEqual(understat.created_counts(per, ["ARS"], "Pure Creator"),
                         {"cc": 2, "bcc": 1, "cc_4": 0, "bcc_4": 0})

    def test_last_four_gameweeks(self):
        per = tally([("ARS", "A", 0.1, False), ("ARS", "A", 0.5, True), ("ARS", "A", 0.2, True)])
        self.assertEqual(understat.created_counts(per, ["ARS"], "A"), {"cc": 3, "bcc": 1, "cc_4": 2, "bcc_4": 1})

    def test_moved_club_sums_both(self):
        per = tally([("ARS", "Mover", 0.1, False), ("CHE", "Mover", 0.35, True), ("CHE", "Other", 0.9, True)])
        self.assertEqual(understat.created_counts(per, ["ARS", "CHE"], "Mover"),
                         {"cc": 2, "bcc": 1, "cc_4": 1, "bcc_4": 1})

    def test_same_name_at_another_club_is_not_his(self):
        per = tally([("ARS", "Same Name", 0.1, False), ("CHE", "Same Name", 0.1, False)])
        self.assertEqual(understat.created_counts(per, ["CHE"], "Same Name")["cc"], 1)

    def test_nothing_created_and_no_club(self):
        zero = {"cc": 0, "bcc": 0, "cc_4": 0, "bcc_4": 0}
        self.assertEqual(understat.created_counts(tally([]), ["ARS"], "Nobody"), zero)
        self.assertEqual(understat.created_counts(tally([("ARS", "A", 0.1, True)]), [], "A"), zero)

    def test_club_listed_twice_counts_once(self):
        per = tally([("ARS", "A", 0.1, False)])
        self.assertEqual(understat.created_counts(per, ["ARS", "ARS"], "A")["cc"], 1)

    def test_lookup_does_not_grow_the_tally(self):
        per = tally([])
        understat.created_counts(per, ["ARS"], "A")
        self.assertEqual(len(per), 0)


class Codes(unittest.TestCase):
    T = {"Arsenal": "ARS", "Chelsea": "CHE"}

    def test_codes_and_unknown_title(self):
        self.assertEqual(understat.player_codes({"team_title": "Arsenal,Chelsea"}, self.T), (["ARS", "CHE"], []))
        self.assertEqual(understat.player_codes({"team_title": "Arsenal, Nowhere"}, self.T), (["ARS"], ["Nowhere"]))

    def test_shared_name_at_same_club(self):
        us = {1: {"player_name": "John Smith", "team_title": "Arsenal"},
              2: {"player_name": "John Smith", "team_title": "Chelsea,Arsenal"},
              3: {"player_name": "John Smith", "team_title": "Chelsea"},
              4: {"player_name": "Someone Else", "team_title": "Arsenal"}}
        # 2 and 3 also share Chelsea: every shared club/name pair is reported
        self.assertEqual(understat.shared_creator_keys(us, self.T),
                         {("ARS", "John Smith"): [1, 2], ("CHE", "John Smith"): [2, 3]})

    def test_same_name_different_clubs_is_not_shared(self):
        us = {1: {"player_name": "John Smith", "team_title": "Arsenal"},
              3: {"player_name": "John Smith", "team_title": "Chelsea"}}
        self.assertEqual(understat.shared_creator_keys(us, self.T), {})


class ValidateWarning(unittest.TestCase):
    def warn(self, meta):
        w = []
        validate.check_created(meta, w)
        return w

    def test_old_file_without_fields_is_not_checked(self):
        self.assertEqual(self.warn({}), [])
        self.assertEqual(self.warn({"players": 453}), [])

    def test_threshold(self):
        self.assertEqual(self.warn({"kp_no_cc": 10, "cc_ambiguous": 0, "cc_no_code": 0}), [])
        w = self.warn({"kp_no_cc": 11, "cc_ambiguous": 0, "cc_no_code": 0})
        self.assertEqual(len(w), 1)
        self.assertIn("11 matched players", w[0])

    def test_ambiguous_and_missing_code_are_surfaced(self):
        w = self.warn({"kp_no_cc": 0, "cc_ambiguous": 2, "cc_no_code": 1})
        self.assertEqual(len(w), 2)


def us_player(i, name, title, kp=0, shots=0):
    return {"id": str(i), "player_name": name, "team_title": title, "time": "900", "games": "10", "position": "M",
            "shots": str(shots), "key_passes": str(kp), "npxG": "0.5", "xGChain": "1.0", "xGBuildup": "0.5"}


def element(i, team, first, second):
    return {"id": i, "team": team, "first_name": first, "second_name": second, "web_name": second,
            "known_name": "", "minutes": 900}


def shot(pid, name, xg, assister, side):
    return {"player_id": str(pid), "player": name, "X": "0.9", "Y": "0.5", "xG": str(xg), "result": "SavedShot",
            "situation": "OpenPlay", "player_assisted": assister, "shotType": "RightFoot"}


class MainWritesCreated(unittest.TestCase):
    """understat.main() on a two-match season: GW1 Arsenal v Chelsea, GW6 Chelsea v Arsenal (current GW 6, so only
    GW6 is in the last four)."""

    def run_main(self, players, matches):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        boot = {"events": [{"id": g, "finished": True, "deadline_time": f"2026-08-{g:02d}T10:00:00Z"} for g in range(1, 7)],
                "teams": [{"id": 1, "short_name": "ARS"}, {"id": 2, "short_name": "CHE"}],
                "elements": [element(11, 1, "Pure", "Creator"), element(12, 1, "Shot", "Taker"),
                             element(13, 2, "Mid", "Mover"), element(14, 1, "John", "Smith"),
                             element(15, 1, "Johnny", "Smith")]}
        fixtures = [{"event": 1, "kickoff_time": "x", "team_h": 1, "team_a": 2},
                    {"event": 6, "kickoff_time": "x", "team_h": 2, "team_a": 1}]
        sides = {"ARS": {"title": "Arsenal", "short_title": "ARS"}, "CHE": {"title": "Chelsea", "short_title": "CHE"}}
        league = {"players": players,
                  "dates": [{"id": "m1", "isResult": True, "datetime": "2026-08-01 15:00:00", "h": sides["ARS"], "a": sides["CHE"]},
                            {"id": "m6", "isResult": True, "datetime": "2026-09-20 15:00:00", "h": sides["CHE"], "a": sides["ARS"]}]}

        def fetch(url, referer):
            return league if "getLeagueData" in url else {"shots": matches[url.rsplit("/", 1)[1]]}

        out = io.StringIO()
        warnings.simplefilter("ignore", ResourceWarning)   # main() leaves its output files to the garbage collector
        self.addCleanup(warnings.resetwarnings)
        with patch.object(understat, "fpl", lambda path: boot if "bootstrap" in path else fixtures), \
                patch.object(understat, "fetch", fetch), patch.object(understat, "OUTDIR", os.path.join(tmp.name, "understat")), \
                patch.object(understat, "HERE", tmp.name), patch.object(understat, "SEASON", "2026"), \
                patch.object(understat.time, "sleep", lambda s: None), contextlib.redirect_stdout(out):
            understat.main()
        with open(os.path.join(tmp.name, "understat", "fpl_players.json")) as f:
            return json.load(f), out.getvalue()

    MATCHES = {
        # GW1 Arsenal (h) v Chelsea (a): the creator sets up two, the taker sets one up, the mover (then at Arsenal) one
        "m1": {"h": [shot(2, "Shot Taker", 0.4, "Pure Creator", "h"), shot(2, "Shot Taker", 0.1, "Pure Creator", "h"),
                     shot(9, "Extra Man", 0.1, "Shot Taker", "h"), shot(9, "Extra Man", 0.5, "Mid Mover", "h")],
               "a": []},
        # GW6 Chelsea (h) v Arsenal (a): the mover is now at Chelsea
        "m6": {"h": [shot(8, "Blue Striker", 0.35, "Mid Mover", "h")],
               "a": [shot(2, "Shot Taker", 0.5, "Pure Creator", "a")]},
    }

    def test_no_shots_shooter_and_mover(self):
        players = [us_player(1, "Pure Creator", "Arsenal", kp=3), us_player(2, "Shot Taker", "Arsenal", kp=1, shots=3),
                   us_player(3, "Mid Mover", "Arsenal,Chelsea", kp=2)]
        d, _ = self.run_main(players, self.MATCHES)
        P = d["players"]
        pick = lambda r: (r["cc"], r["bcc"], r["cc_4"], r["bcc_4"])
        self.assertEqual(pick(P["11"]), (3, 2, 1, 1))     # never shot: was 0, 0, 0, 0 before the fix
        self.assertEqual(P["11"]["bc"], 0)
        self.assertEqual(pick(P["12"]), (1, 0, 0, 0))     # shoots and creates
        self.assertEqual((P["12"]["bc"], P["12"]["bc_4"]), (2, 1))   # shot tallies untouched
        self.assertEqual(pick(P["13"]), (2, 2, 1, 1))     # one at each club
        self.assertEqual((d["meta"]["kp_no_cc"], d["meta"]["cc_ambiguous"], d["meta"]["cc_no_code"]), (0, 0, 0))

    def test_same_name_same_club_credits_neither_and_says_so(self):
        players = [us_player(4, "John Smith", "Arsenal", kp=4), us_player(5, "John Smith", "Arsenal", kp=1),
                   us_player(2, "Shot Taker", "Arsenal", kp=1, shots=3)]
        matches = {"m1": {"h": [shot(2, "Shot Taker", 0.4, "John Smith", "h")], "a": []}, "m6": {"h": [], "a": []}}
        d, printed = self.run_main(players, matches)
        smiths = [r for r in d["players"].values() if r["us_id"] in (4, 5)]
        self.assertTrue(smiths)
        self.assertTrue(all(r["cc"] == 0 and r["bcc"] == 0 for r in smiths))
        self.assertEqual(d["meta"]["cc_ambiguous"], len(smiths))
        self.assertIn("John Smith (ARS) is Understat ids [4, 5]", printed)
        # the one with 3+ key passes shows up in the health figure if he was matched
        self.assertEqual(d["meta"]["kp_no_cc"], sum(1 for r in smiths if r["kp"] >= 3))

    def test_title_without_code_is_printed_and_counts_nothing(self):
        players = [us_player(1, "Pure Creator", "Arsenal,Nowhere FC", kp=3), us_player(2, "Shot Taker", "Arsenal", shots=3)]
        d, printed = self.run_main(players, self.MATCHES)
        self.assertEqual(d["players"]["11"]["cc"], 3)
        self.assertEqual(d["meta"]["cc_no_code"], 1)
        self.assertIn("'Nowhere FC'", printed)


if __name__ == "__main__":
    unittest.main()
