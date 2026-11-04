"""Personal decision journal (D5a): what you did each gameweek next to what the model suggested, with what both relied on.

One entry per gameweek whose deadline has passed and that has a deadline snapshot (history/deadline_gw{N}.json, GW10 on).
Everything is read from files saved BEFORE the deadline, so an entry shows what was known at the time:

    entry(gw, dl, proj, my_moves, picks, fixtures, best) -> {
      "gw", "chip", "hits",
      "you":   {"moves": [[out, in], ...], "captain"},
      "model": {"plan", "moves": [[out, in], ...], "hits", "captain"},
      "both":     [[out, in], ...]   moves you and the model both made (same player in, any player out counts as the same
                                     signing only when the player out matches too; otherwise it is "yours" + "skipped")
      "yours":    [[out, in], ...]   your moves the model didn't suggest
      "skipped":  [[out, in], ...]   the model's moves you didn't make
      "players":  {pid: {"xp1", "xp5", "start", "xmin", "status", "chance", "fx": [[opp, home], ...], "absent"}}
    }

dl: the deadline snapshot; proj: history/proj_gw{N}.json (status and chance before the deadline); my_moves: your FPL
transfers that gameweek ([[out, in], ...], from /entry/{id}/transfers/); picks: FPL's picks for the gameweek;
fixtures: FPL fixtures; best: fpl_score.best_suggestion(dl["plans"], gw) -- the same plan the You vs the model target
uses, so the two sections on that tab always talk about the same suggestion.

Missing / late / ambiguous:
  - no deadline snapshot for the gameweek (GW8, GW9) -> no entry; the caller lists it in "no_snapshot";
  - no saved plans in the snapshot (solver failed) -> model is None, every move of yours is "yours", nothing skipped;
  - a player missing from the snapshot (projected 0 everywhere) -> zeros with "absent": True, never left out;
  - start chance or minutes missing for a player -> None (shown as "–"), never 0;
  - a Free Hit week: the moves are temporary and are still listed, with chip "freehit" so the page can say so.
"""


def _moves(pairs):
    return [[int(o), int(i)] for o, i in pairs]


def compare(mine, model):
    """(both, yours, skipped). A move matches only when the same player goes out AND the same player comes in."""
    m = {tuple(x) for x in model}
    y = {tuple(x) for x in mine}
    return ([list(x) for x in mine if tuple(x) in m], [list(x) for x in mine if tuple(x) not in m],
            [list(x) for x in model if tuple(x) not in y])


def player_row(pid, dl, proj, fixtures, gw, team):
    """What the app knew about one player before the deadline. team: his club id (for this gameweek's fixtures)."""
    k = str(pid)
    xp = dl.get("xp", {}).get(k)
    mins = dl.get("mins", {}).get(k) or [None, None, None]
    pr = (proj or {}).get("players", {}).get(k)
    fx = [[f["team_a"], 1] if f["team_h"] == team else [f["team_h"], 0]
          for f in fixtures if f.get("event") == gw and team in (f["team_h"], f["team_a"])]
    return {"xp1": round(xp[0], 2) if xp else 0.0, "xp5": round(sum(xp), 2) if xp else 0.0,
            "xp": [round(x, 2) for x in xp] if xp else [0.0] * len(dl.get("plan_gws") or [gw]),
            "start": mins[0], "xmin": mins[2], "status": pr[2] if pr and len(pr) > 2 else None,
            "chance": pr[3] if pr and len(pr) > 3 else None, "fx": fx, "absent": xp is None}


def entry(gw, dl, proj, my_moves, picks, fixtures, best, team_of):
    """The journal entry for gameweek gw (see the module docstring). team_of: {pid: team id} for the fixtures."""
    mine = _moves(my_moves)
    cap = next((p["element"] for p in picks["picks"] if p["is_captain"]), None)
    model = None
    if best:
        model = {"plan": best["plan"], "moves": _moves(zip(best["out"], best["in"])), "hits": best["hits"],
                 "captain": best["captain"]}
    both, yours, skipped = compare(mine, model["moves"] if model else [])
    ids = {i for mv in mine + (model["moves"] if model else []) for i in mv} | {cap} | (
        {model["captain"]} if model else set())
    ids.discard(None)
    return {"gw": gw, "chip": picks.get("active_chip"), "hits": picks["entry_history"].get("event_transfers_cost", 0),
            "you": {"moves": mine, "captain": cap}, "model": model, "both": both, "yours": yours, "skipped": skipped,
            "players": {str(i): player_row(i, dl, proj, fixtures, gw, team_of.get(i)) for i in sorted(ids)}}


# ---------------------------------------------------------------- how it turned out (D5c)
WINDOW = 5   # transfers are judged over the five gameweeks from the one they were made for (agreed 4 Nov)


def outcome(e, played, finished):
    """How the entry's calls turned out so far. played: {gw: {pid: (minutes, points, starts)}} for finished gameweeks
    (FPL's live data, a double gameweek already summed); finished: the finished gameweek numbers.

    Each move is judged on the two players' own points over the gameweeks from e["gw"] to e["gw"] + 4 that have
    finished, whether or not you started them (it judges the signing, not the lineup), next to what the forecast saved
    before the deadline projected for the same gameweeks. A Free Hit week is judged on that week only (the moves were
    undone after it). The deadline week also gets an assumptions check: did each player start, and how many minutes
    against the minutes expected.
    Missing / late: no finished gameweek in the window yet -> None (the page says when results start); a player with no
    entry in a finished gameweek (no match, or not in FPL's data) played 0 minutes and scored 0; a player whose
    forecast was missing ("absent") projects 0 and the page already says he wasn't in the forecast.
    Returns {"gws": [done], "of": window length, "moves": {"out-in": {...}}, "captain": {...}} or None.
    """
    g0 = e["gw"]
    span = [g0] if e.get("chip") == "freehit" else list(range(g0, g0 + WINDOW))
    done = [g for g in span if g in set(finished) and g in played]
    if not done:
        return None
    P = e["players"]
    pts = lambda i, g: played[g].get(i, (0, 0, 0))[1]
    xp_at = lambda i, k: (P[str(i)].get("xp") or [0.0] * WINDOW)[k] if k < len(P[str(i)].get("xp") or []) else 0.0
    proj = lambda i: sum(xp_at(i, g - g0) for g in done)
    act = lambda i: sum(pts(i, g) for g in done)

    def check(i):
        m, _, st = played.get(g0, {}).get(i, (0, 0, 0)) if g0 in done else (None, None, None)
        return None if m is None else {"started": bool(st), "mins": m, "start_chance": P[str(i)].get("start"),
                                       "xmin": P[str(i)].get("xmin")}

    moves = {}
    for o, i in e["you"]["moves"] + ((e.get("model") or {}).get("moves") or []):
        k = f"{o}-{i}"
        if k in moves:
            continue
        moves[k] = {"out": o, "in": i, "out_pts": act(o), "in_pts": act(i), "gain": act(i) - act(o),
                    "proj_gain": round(proj(i) - proj(o), 2), "check": {"out": check(o), "in": check(i)}}
    cap = None
    if g0 in done:
        yc, mc = e["you"]["captain"], (e.get("model") or {}).get("captain")
        cap = {"you": yc, "you_pts": pts(yc, g0), "model": mc, "model_pts": pts(mc, g0) if mc else None}
    return {"gws": done, "of": len(span), "moves": moves, "captain": cap}
