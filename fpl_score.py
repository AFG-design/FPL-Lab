"""Score a gameweek team the way FPL does, from what actually happened (F1a).

Used to put your real team and the Supercomputer's pick from the same 15 on equal terms (F1). Pure functions, no I/O.

    score_team(team, played, chip=None) -> {"total", "xi", "bench", "subs": [(out, in)], "captain", "multipliers", "captain_multiplier"}

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


def captain_multiplier(chip=None):
    """No chip (including missing active_chip) means ordinary captaincy; TC means treble."""
    return 3 if chip == "3xc" else 2


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
    mult = captain_multiplier(chip)
    cap = team["captain"] if mins.get(team["captain"], 0) > 0 else (
        team["vice"] if mins.get(team["vice"], 0) > 0 else None)
    multipliers = {i: (mult if i == cap else 1) for i in counted}
    total = sum(pts[i] * multipliers[i] for i in counted)
    return {"total": total, "xi": xi, "bench": bench, "subs": subs, "captain": cap, "multipliers": multipliers, "captain_multiplier": mult}


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


# ---------------------------------------------------------------- the Supercomputer's pick (F1b)
MAX = {"GKP": 1, "DEF": 5, "MID": 5, "FWD": 3}


def supercomputer_pick(squad, pos, xp):
    """What the model would have fielded from your 15, using only the forecast saved before the deadline.

    squad: your 15 ids (as submitted); pos: {id: position}; xp: {id: projected points} from history/proj_gwN.json.
    Returns score_team's team shape: the legal XI with the most projected points, captain = highest xP in it, vice =
    the next, bench = spare keeper first then outfield players by xP (highest first, so the likeliest point-scorer is
    first to come on).
    Missing / ambiguous: xp None (no saved forecast for that gameweek) -> None, never a re-run. A player missing from
    the saved forecast counts as 0 xP (the snapshot leaves out players projected 0 with no FPL estimate either).
    Equal xP is broken by the order you submitted, so the result never changes between builds.
    """
    if xp is None:
        return None
    order = {i: k for k, i in enumerate(squad)}
    rank = sorted(squad, key=lambda i: (-xp.get(i, 0.0), order[i]))
    xi, n = [], {k: 0 for k in MAX}
    for p_ in ("GKP", "DEF", "MID", "FWD"):          # the minimum of each position first, best first
        for i in [i for i in rank if pos[i] == p_][:MIN[p_]]:
            xi.append(i); n[p_] += 1
    for i in rank:                                    # then the best of the rest, within each position's maximum
        if len(xi) == 11:
            break
        if i not in xi and pos[i] != "GKP" and n[pos[i]] < MAX[pos[i]]:
            xi.append(i); n[pos[i]] += 1
    xi.sort(key=lambda i: order[i])
    by_xp = sorted(xi, key=lambda i: (-xp.get(i, 0.0), order[i]))
    rest = [i for i in rank if i not in xi]
    bench = [i for i in rest if pos[i] == "GKP"] + [i for i in rest if pos[i] != "GKP"]
    return {"xi": xi, "bench": bench, "captain": by_xp[0], "vice": by_xp[1], "pos": pos}


# ---------------------------------------------------------------- you vs the model: record and streak (F1c)
MILESTONES = [(3, "Hat-trick"), (6, "Six-pointer"), (10, "Double figures"), (19, "Half-season")]
MAX_WILDCARDS = 2


def expected(team, xp, chip=None):
    """What the model expected its pick to score, from the forecast saved before the deadline: the XI's projected
    points (all 15 with Bench Boost) plus the captain's again (twice again with Triple Captain). No auto-subs: this is
    the figure the model stood by at the deadline. A player missing from the saved forecast counts as 0."""
    counted = team["xi"] + (team["bench"] if chip == "bboost" else [])
    extra = captain_multiplier(chip) - 1
    return sum(xp.get(i, 0.0) for i in counted) + extra * xp.get(team["captain"], 0.0)


HIT = 4


def plan_suggestion(plans, key, gw):
    """Plan `key`'s week for gameweek gw as a suggestion: {"plan": key, "exp": net xP (xP less 4 per hit), "xp": gross
    xP, "hits", "out", "in", "captain", "xi", "captain_multiplier": 2}. The saved plans don't use your chip (FL-035:
    ordinary captaincy). Missing plan, or no week for gw -> None.

    FL-108 replaced best_suggestion (the highest single-week xP across every saved plan, which favoured the plan with
    the most transfers) with the one recommended plan: see recommended_suggestion."""
    wk = next((w for w in ((plans or {}).get(key) or {}).get("weeks", []) if w.get("gw") == gw), None)
    if wk is None:
        return None
    return {"plan": key, "exp": wk["xp"] - HIT * wk.get("hits", 0), "xp": wk["xp"], "hits": wk.get("hits", 0),
            "out": wk.get("out", []), "in": wk.get("in", []), "captain": wk.get("captain"), "xi": wk.get("xi", []),
            "captain_multiplier": captain_multiplier()}


def recommended_suggestion(snap, gw, mode="balanced"):
    """The recommended plan's week for gw from a deadline snapshot (history/deadline_gwN.json), FL-108: the same plan
    Home and the Planner open on (optimise.recommended), for the journal and You vs the model.

    The snapshot's own "recommended" (saved from FL-108 on) is used when present. Older snapshots (GW10, GW11 before
    FL-108) are never rewritten; for them the same rule is applied to the plans they saved (each has vs_roll), and the
    result says so with "derived": True. Balanced is used: the strategy a deadline was saved under isn't known (it is
    a per-device setting), and Balanced is the default.
    Missing: no snapshot, no plans, no recommendation for the strategy, or its plan has no week for gw -> None (the
    callers then fall back and mark the target assumed / leave the journal's model side empty, as before)."""
    if not snap or not snap.get("plans"):
        return None
    rec = snap.get("recommended")
    derived = not isinstance(rec, dict)
    if derived:
        import optimise   # the rule lives with the planner; imported here so fpl_score stays light for the browser tests
        rec = optimise.recommended(snap["plans"])
    key = rec.get(mode)
    s = plan_suggestion(snap["plans"], key, gw) if key else None
    if s:
        s["derived"] = derived
    return s


def suggested_team(snap, sug, gw, pos):
    """The recommended plan's team for gameweek gw in score_team's shape, so it can be scored on what happened with
    FPL's automatic substitutions (FL-109). snap: the deadline snapshot; sug: plan_suggestion / recommended_suggestion's
    result for gw; pos: {id: position}.

    Returns {"xi", "bench", "captain", "vice", "pos", "bench_src"}:
      - bench_src "saved": the plan week has the bench and vice the optimiser chose (saved from FL-109 on);
      - bench_src "derived": snapshots from before FL-109 (GW10, GW11) saved only the XI. The squad is rebuilt from the
        snapshot's squad and the plan's moves up to gw, and the bench and vice are put in the optimiser's own order
        (optimise.solve: spare keeper first, then outfield by that week's xP, highest first; vice = the highest xP in
        the XI after the captain), using the xP saved in the snapshot. Equal xP: lower id first, as the solver's
        sorted pool does. The xP is rounded to 0.01 there, so a near-tie can in principle come out the other way;
      - bench_src "missing": the squad can't be rebuilt (moves that don't add up to 15, an XI player not in the squad,
        or a player with no position): the XI is scored with no bench and no auto-subs, and no vice. Never a guess.
    """
    plan = (snap.get("plans") or {}).get(sug["plan"]) or {}
    wk = next((w for w in plan.get("weeks", []) if w.get("gw") == gw), {})
    xi, cap = list(sug["xi"]), sug["captain"]
    if wk.get("bench") is not None and wk.get("vice") is not None:
        return {"xi": xi, "bench": list(wk["bench"]), "captain": cap, "vice": wk["vice"], "pos": pos,
                "bench_src": "saved"}
    squad = list(snap.get("squad") or [])
    for w in plan.get("weeks", []):
        if w.get("gw", 0) > gw:
            break
        squad = [i for i in squad if i not in set(w.get("out", []))] + list(w.get("in", []))
    if len(set(squad)) != 15 or not set(xi) <= set(squad) or any(i not in pos for i in squad):
        return {"xi": xi, "bench": [], "captain": cap, "vice": None, "pos": pos, "bench_src": "missing"}
    k = (snap.get("plan_gws") or []).index(gw) if gw in (snap.get("plan_gws") or []) else None
    x = lambda i: ((snap.get("xp") or {}).get(str(i)) or [0] * 5)[k] if k is not None else 0.0
    bench = sorted((i for i in squad if i not in xi), key=lambda i: (pos[i] != "GKP", -x(i), i))
    vice = (sorted((i for i in xi if i != cap), key=lambda i: (-x(i), i)) or [cap])[0]
    return {"xi": xi, "bench": bench, "captain": cap, "vice": vice, "pos": pos, "bench_src": "derived"}


def suggested_target(snap, sug, gw, played, pos):
    """You vs the model's target for a week with a saved suggestion (FL-109, actual v actual): the recommended plan's
    team (suggested_team) scored on what happened by FPL's rules, auto-subs and vice included, with no chip (the saved
    plans don't use one, FL-035), less 4 per hit. par = actual: the whole-number score to beat.
    Also kept, for the pitch: its projected score (exp, xP less hits), each player's xP saved before the deadline for gw
    and actual points, the auto-subs and who wore the armband."""
    team = suggested_team(snap, sug, gw, pos)
    sc = score_team(team, played)
    gws = snap.get("plan_gws") or []
    k = gws.index(gw) if gw in gws else None
    ids = sug["xi"] + team["bench"]
    xp = lambda i: (((snap.get("xp") or {}).get(str(i)) or [])[k:k + 1] or [0])[0] if k is not None else 0
    actual = sc["total"] - HIT * sug["hits"]
    return {"basis": "suggested", "assumed": False, "exp": round(sug["exp"], 1), "plan": sug["plan"],
            "captain_multiplier": sc["captain_multiplier"], "xp": sug["xp"], "hits": sug["hits"], "out": sug["out"],
            "in": sug["in"], "captain": sug["captain"], "xi": sug["xi"], "bench": team["bench"], "vice": team["vice"],
            "bench_src": team["bench_src"], "armband": sc["captain"], "subs": sc["subs"], "pts": sc["total"],
            "actual": actual, "par": actual,
            "xi_xp": {str(i): xp(i) for i in ids}, "xi_pts": {str(i): played.get(i, (0, 0))[1] for i in ids}}


def pair_moves(outs, ins, pos):
    """Transfers as FPL makes them: each player out paired with a player in for the same position. The optimiser lists
    outs and ins separately (in no particular pairing), so pairing by list order can show a midfielder replaced by a
    defender. Within a position the original order is kept. Ambiguous input (positions that don't balance, or a player
    missing from pos) -> ValueError, never a made-up pairing."""
    outs, ins = list(outs), list(ins)
    if len(outs) != len(ins) or any(i not in pos for i in outs + ins):
        raise ValueError(f"can't pair moves {outs} -> {ins}")
    left, pairs = list(ins), []
    for o in outs:
        i = next((x for x in left if pos[x] == pos[o]), None)
        if i is None:
            raise ValueError(f"no {pos[o]} coming in for {o}")
        left.remove(i); pairs.append((o, i))
    return [o for o, _ in pairs], [i for _, i in pairs]


def result(you, par):
    """W, D or L for you: your actual points after hits against the model's target. From FL-109 the target is what the
    model's suggested team actually scored after its hits (actual v actual); before, it was its expected points."""
    return "W" if you > par else "L" if you < par else "D"


def streak(results, season_from_gw1=False):
    """Record and winning run from the weeks' results in order (["W", "D", "L", ...]).

    Rules (agreed 4 Nov):
      - the run counts wins against the model in a row; a draw always ends it (a wildcard can't save a draw);
      - a defeat ends it unless you hold a Streak Wildcard: one is used and the run carries on, that week adding nothing;
        with no run going (run 0) a defeat costs nothing and no wildcard is used;
      - each milestone of the current run (3, 6, 10, 19 wins) earns one wildcard, held up to 2 (one earned with 2 held
        is lost, and counted as such); wildcards are kept when a run ends;
      - Invincibles: every one of the season's 38 gameweeks won. Only possible when the record covers GW1
        (season_from_gw1); this season's record starts at GW8, so it stays locked.
    Returns {"record": {W, D, L}, "run", "best", "held", "used", "earned", "lost", "trail", "milestones": [...],
    "invincible"}. trail has one entry per week: {"run" after it, "held" after it, "saved" (a wildcard saved a defeat),
    "earned" (milestone name or None), "ended" (a run of 1+ ended), "lost" (only when a wildcard was earned with 2 held)}.
    """
    run = best = held = used = earned = lost = 0
    got = set()                                   # milestones reached in the current run
    trail = []                                    # per week, for the streak card (F1e)
    for r in results:
        step = {"saved": False, "earned": None, "ended": False}
        if r == "W":
            run += 1
            for n, name in MILESTONES:
                if run == n and n not in got:
                    got.add(n); earned += 1; step["earned"] = name
                    if held < MAX_WILDCARDS:
                        held += 1
                    else:
                        lost += 1; step["lost"] = True
        elif r == "D":
            step["ended"] = run > 0
            run, got = 0, set()
        elif r == "L":
            if run > 0 and held > 0:
                held -= 1; used += 1; step["saved"] = True
            else:
                step["ended"] = run > 0
                run, got = 0, set()
        best = max(best, run)
        step["run"], step["held"] = run, held
        trail.append(step)
    rec = {k: results.count(k) for k in "WDL"}
    return {"record": rec, "run": run, "best": best, "held": held, "used": used, "earned": earned, "lost": lost,
            "trail": trail,
            "milestones": [{"n": n, "name": name, "reached": run >= n, "best": best >= n} for n, name in MILESTONES]
                          + [{"n": 38, "name": "Invincibles", "reached": False, "best": False,
                              "locked": not season_from_gw1}],
            "invincible": bool(season_from_gw1 and rec["W"] == 38)}
