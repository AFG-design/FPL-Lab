"""Score a gameweek team the way FPL does, from what actually happened (F1a).

Used to put your real team and the Supercomputer's pick from the same 15 on equal terms (F1). Pure functions, no I/O.

    score_team(team, played, chip=None) -> {"total", "xi", "bench", "subs": [(out, in)], "captain", "multipliers"}

team:   {"xi": [11 ids], "bench": [4 ids: keeper first, then outfield in substitution order],
         "captain": id, "vice": id, "pos": {id: "GKP" | "DEF" | "MID" | "FWD"}}
played: {id: (minutes, points)} for the gameweek, every match added together (a double counts both games).
        A player missing from it, or with no fixture, played 0 minutes and scored 0.
chip:   None, "bboost" (all 15 count, no substitutions) or "3xc" (captain x3). Wildcard and Free Hit score normally.

FPL's rules, as applied here:
  - Automatic substitutions (not with Bench Boost): each starter with 0 minutes, taken in XI order, is replaced by the
    first bench player in order who played and keeps a legal formation (1 keeper, at least 3 defenders, 2 midfielders
    and 1 forward). The keeper can only be replaced by the bench keeper, and outfield players only by outfield ones.
    A bench player who didn't play is skipped. If nobody fits, the starter stays and scores 0.
  - Captain: double points (treble with Triple Captain) if he played. If he played 0 minutes, the vice-captain gets the
    multiplier instead, if he played. If neither played, nobody does. Whether the captain is subbed out doesn't matter:
    only his minutes do.
Only finished gameweeks should be scored: mid-gameweek, a player whose match is still to come shows 0 minutes and would
be subbed off here, where FPL waits.
"""

MIN = {"GKP": 1, "DEF": 3, "MID": 2, "FWD": 1}


def _legal(ids, pos):
    n = {k: 0 for k in MIN}
    for i in ids:
        n[pos[i]] += 1
    return n["GKP"] == 1 and all(n[k] >= MIN[k] for k in ("DEF", "MID", "FWD"))


def auto_subs(xi, bench, pos, mins):
    """(final XI, final bench, [(out, in)]) after FPL's automatic substitutions. mins: {id: minutes}."""
    xi, bench, subs = list(xi), list(bench), []
    for out in [i for i in xi if mins.get(i, 0) <= 0]:
        for cand in bench:
            if mins.get(cand, 0) <= 0:
                continue
            if (pos[out] == "GKP") != (pos[cand] == "GKP"):
                continue
            trial = [cand if i == out else i for i in xi]
            if not _legal(trial, pos):
                continue
            xi, subs = trial, subs + [(out, cand)]
            bench = [out if b == cand else b for b in bench]
            break
    return xi, bench, subs


def score_team(team, played, chip=None):
    pos, xi, bench = team["pos"], list(team["xi"]), list(team["bench"])
    mins = {i: played.get(i, (0, 0))[0] for i in xi + bench}
    pts = {i: played.get(i, (0, 0))[1] for i in xi + bench}
    subs = []
    if chip == "bboost":
        counted = xi + bench
    else:
        xi, bench, subs = auto_subs(xi, bench, pos, mins)
        counted = xi
    mult = 3 if chip == "3xc" else 2
    cap = team["captain"] if mins.get(team["captain"], 0) > 0 else (
        team["vice"] if mins.get(team["vice"], 0) > 0 else None)
    multipliers = {i: (mult if i == cap else 1) for i in counted}
    total = sum(pts[i] * multipliers[i] for i in counted)
    return {"total": total, "xi": xi, "bench": bench, "subs": subs, "captain": cap, "multipliers": multipliers}


def from_fpl_picks(picks, pos):
    """A team in score_team's shape from FPL's /entry/{id}/event/{gw}/picks/ response (positions 1-11 XI, 12-15 bench)."""
    rows = sorted(picks["picks"], key=lambda p: p["position"])
    return {"xi": [p["element"] for p in rows[:11]], "bench": [p["element"] for p in rows[11:]],
            "captain": next(p["element"] for p in rows if p["is_captain"]),
            "vice": next((p["element"] for p in rows if p["is_vice_captain"]), None), "pos": pos}


def as_submitted(picks, pos):
    """The team as you submitted it. FPL's picks response shows the team AFTER its automatic substitutions (the player
    who came on sits in the XI), so they are undone here using its automatic_subs list. Scoring this with score_team
    then redoes them, which is how FPL's own score can be checked, and how the Supercomputer gets the same chance."""
    t = from_fpl_picks(picks, pos)
    for s in reversed(picks.get("automatic_subs") or []):
        o, i = s["element_out"], s["element_in"]
        t["xi"] = [o if x == i else x for x in t["xi"]]
        t["bench"] = [i if x == o else x for x in t["bench"]]
    return t


def played_from_live(live):
    """{id: (minutes, points)} from FPL's /event/{gw}/live/ response (already summed over a double gameweek)."""
    return {e["id"]: (e["stats"]["minutes"], e["stats"]["total_points"]) for e in live["elements"]}
