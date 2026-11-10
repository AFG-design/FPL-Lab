"""What the app knew before each deadline, beyond history/proj_gw{N}.json: history/deadline_gw{N}.json.

proj_gw{N} keeps next GW's xP, FPL's ep_next, status and chance. These are overwritten every build and were lost once the
deadline passed, so they're kept here, rewritten each build until the deadline (the last build before it stays):
  - xp: each player's xP for every plan gameweek (the 5-GW numbers the Planner uses, not only next GW)
  - mins: [start chance, chance of a sub appearance, expected minutes next GW], all as the forecast used them: after
    FPL's flag, rotation and the return ramp. Start and sub chances are per match, so a double can't show over 100%
  - dist: next GW's simulated outcomes [chance of 10+, chance of 6+, chance of 2 or fewer]
  - odds: the market's expected goals for each plan-gameweek fixture as they stood (odds/odds.json only keeps the latest)
  - plans: each strategy plan's moves, captains, hits and totals, and the squad, bank and free transfers it started from

Missing / late / ambiguous input (nothing is made up; each gap is recorded in "missing"):
  - no odds file, or no odds yet for a plan-gameweek fixture (football-data lists the next round late in the week):
    that fixture is listed under missing.odds_fixtures, and "odds" holds only fixtures that had odds
  - no plans (no squad yet, or the solver failed): "plans" is {} and missing.plans says why
  - no simulation for a player: no "dist" row for him
  - no match next gameweek (blank), or a player row without the figures: start and sub chance are None, never 0 or a
    number from before the flags (the journal shows "–"; validate.py warns if a player with xP has none)
Players are kept when they have any plan-gameweek xP above 0 or are in the squad, as in proj_gw{N}.
"""
import datetime as dt
import json
import os


def build(gw, plan_gws, players, squad_ids, bank, ft, plans, market, fixtures, built=None):
    """The snapshot as a dict. players: build.py's player rows; fixtures: FPL fixtures; market: odds/odds.json or None."""
    sq = set(squad_ids)
    keep = {i: p for i, p in players.items() if i in sq or any(p["xp"].get(g, 0) > 0 for g in plan_gws)}
    xp = {str(i): [round(p["xp"].get(g, 0), 2) for g in plan_gws] for i, p in keep.items()}
    mins = {str(i): [p.get("start_next"), p.get("sub_next"), p.get("xmin")] for i, p in keep.items()}
    dist = {}
    for i, p in keep.items():
        d = (p.get("dist") or {}).get(gw)
        if d:
            dist[str(i)] = list(d[:3])
    plan_fx = [f for f in fixtures if f.get("event") in plan_gws]
    by_fx = {m["fixture"]: m for m in (market or {}).get("matches", []) if m.get("fixture") is not None}
    odds, no_odds = [], []
    for f in plan_fx:
        m = by_fx.get(f["id"])
        if m:
            odds.append({"fixture": f["id"], "gw": f["event"], "h": f["team_h"], "a": f["team_a"],
                         "lam_h": m["lam_h"], "lam_a": m["lam_a"], "p_over": m.get("p_over")})
        else:
            no_odds.append(f["id"])
    pl = {}
    for k, r in (plans or {}).items():
        pl[k] = {"xp_total": r.get("xp_total"), "ft_left": r.get("ft_left"), "vs_roll": r.get("vs_roll"),
                 "weeks": [{"gw": w["gw"], "out": w["out"], "in": w["in"], "hits": w["hits"], "captain": w["captain"],
                            "xi": w["xi"], "xp": w["xp"]} for w in r.get("weeks", [])]}
    missing = {}
    if market is None:
        missing["odds"] = "no odds file this build"
    if no_odds:
        missing["odds_fixtures"] = no_odds
    if not pl:
        missing["plans"] = "no squad" if not squad_ids else "no plans built this build"
    return {"gw": gw, "built": built or dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "plan_gws": list(plan_gws), "odds_built": (market or {}).get("built"),
            "squad": list(squad_ids), "bank": bank, "ft": ft,
            "xp": xp, "mins": mins, "dist": dist, "odds": odds, "plans": pl, "missing": missing}


def write(hist_dir, snap):
    path = os.path.join(hist_dir, f"deadline_gw{snap['gw']}.json")
    with open(path, "w") as f:
        json.dump(snap, f, separators=(",", ":"))
    return path


def absence_snapshot_due(path, gw, next_ev, now=None):
    """Whether build.py should write history/absence_gw{gw}.json (the cleared-news absence rule's "before" snapshot).

    The file is write-once and has to be made before gw's deadline, or its "before" projection uses flags and news
    that came later. So it is written only when gw is the next gameweek and its deadline hasn't passed.
    Returns (due, reason); reason says why not, for the build log.
      - the file already exists: never rewritten, whatever else holds
      - no next gameweek (season over) or gw isn't it (the current gameweek, whose deadline has gone, or a later
        one, which is written once it becomes next): skipped. A gameweek whose deadline passed with no file stays
        without one; nothing is made late
      - next_ev without a deadline_time, or one that doesn't parse: raises (fails the build loudly), never guessed
    """
    if os.path.exists(path):
        return False, "already written"
    if not next_ev or next_ev.get("id") != gw:
        return False, f"GW{gw} is not the next gameweek"
    if "deadline_time" not in next_ev:
        raise ValueError(f"GW{gw} has no deadline_time; can't tell if the absence snapshot is before the deadline")
    deadline = dt.datetime.fromisoformat(next_ev["deadline_time"].replace("Z", "+00:00"))
    now = now or dt.datetime.now(dt.timezone.utc)
    if now >= deadline:
        return False, f"GW{gw} deadline has passed"
    return True, ""
