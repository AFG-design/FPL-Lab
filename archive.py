#!/usr/bin/env python3
"""Past seasons for backtesting, rebuilt from the public vaastav/Fantasy-Premier-League archive.

load_season("2025-26") returns (boot, fixtures, live, priors, team_at) in the same shape as the live
FPL API, so fplmodel.prepare() and project() run on it unchanged:
  - live[g]["elements"] has one entry per player with a fixture in GW g (doubles summed),
    with a synthetic `explain` carrying defensive-contribution points;
  - priors are built from the two seasons before, the same way make_priors.py does;
  - team_at(pid, gw) gives the player's club at that point (January moves are handled).
Caveats: no betting odds (football-data.co.uk is not used here), injury flags are not
historical, and penalty order is the end-of-season order for every gameweek.
Files are cached in archive/<season>/ (not committed).
"""
import csv, json, os, urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master/data"
INT = ("minutes", "starts", "bonus", "bps", "saves", "yellow_cards", "red_cards", "goals_scored", "assists",
       "clean_sheets", "goals_conceded", "own_goals", "penalties_saved", "penalties_missed", "total_points",
       "defensive_contribution", "clearances_blocks_interceptions", "recoveries", "tackles")
FLT = ("expected_goals", "expected_assists", "expected_goal_involvements", "expected_goals_conceded")
DC_THR = {"DEF": 10, "MID": 12, "FWD": 12}
POS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


def _file(season, name):
    d = os.path.join(HERE, "archive", season)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, os.path.basename(name))
    if not os.path.exists(path):
        req = urllib.request.Request(f"{BASE}/{season}/{name}", headers={"User-Agent": "fpl-lab"})
        with urllib.request.urlopen(req, timeout=120) as r, open(path, "wb") as f:
            f.write(r.read())
    return path


def _rows(season, name):
    with open(_file(season, name), encoding="utf-8", errors="ignore") as f:
        return list(csv.DictReader(f))


def _num(v, cast=float):
    try:
        return cast(float(v))
    except (TypeError, ValueError):
        return cast(0)


def _priors(season, code_to_id):
    """Per-90 priors from the two seasons before `season` (weights 1:2), like make_priors.py."""
    y = int(season[:4])
    seasons = [f"{y - 2}-{str(y - 1)[2:]}", f"{y - 1}-{str(y)[2:]}"]
    tot = defaultdict(lambda: defaultdict(float))
    last = {}
    for wt, s in zip((1.0, 2.0), seasons):
        try:
            rows = _rows(s, "players_raw.csv")
        except Exception:
            continue
        for r in rows:
            pid = code_to_id.get(r["code"])
            m = _num(r["minutes"])
            if not pid or m < 1:
                continue
            t = tot[pid]
            t["w"] += wt
            t["minutes"] += wt * m
            for k, src in (("xg", "expected_goals"), ("xa", "expected_assists"), ("bonus", "bonus"), ("saves", "saves"),
                           ("yc", "yellow_cards"), ("pts", "total_points"), ("starts", "starts")):
                t[k] += wt * _num(r.get(src))
            if r.get("defensive_contribution") not in (None, ""):
                t["dc"] += wt * _num(r["defensive_contribution"])
                t["dc_min"] += wt * m
            last[pid] = (s, r)
    out = {}
    for pid, t in tot.items():
        m = t["minutes"]
        s, r = last[pid]
        out[str(pid)] = {"season": s, "mins": round(m / t["w"]), "xg90": t["xg"] / m * 90, "xa90": t["xa"] / m * 90,
                         "bonus90": t["bonus"] / m * 90, "saves90": t["saves"] / m * 90,
                         "dc90": t["dc"] / m * 90,
                         "yc90": t["yc"] / m * 90, "pts90": t["pts"] / m * 90, "last_pts": _num(r["total_points"], int),
                         "last_mins": _num(r["minutes"], int), "last_xgi": _num(r.get("expected_goal_involvements"))}
    return {"players": out}


def load_season(season, scoring_from):
    """scoring_from: a current bootstrap-static (for game_config scoring rules)."""
    teams = {int(r["id"]): r for r in _rows(season, "teams.csv")}
    name_to_id = {r["name"]: tid for tid, r in teams.items()}
    praw = {int(r["id"]): r for r in _rows(season, "players_raw.csv")}
    gw_rows = _rows(season, "gws/merged_gw.csv")

    fixtures = []
    for r in _rows(season, "fixtures.csv"):
        if not r["event"]:
            continue
        hs = r["team_h_score"]
        fixtures.append({"id": int(r["id"]), "event": int(float(r["event"])), "team_h": int(r["team_h"]),
                         "team_a": int(r["team_a"]), "team_h_score": int(float(hs)) if hs not in ("", None) else None,
                         "team_a_score": int(float(r["team_a_score"])) if hs not in ("", None) else None,
                         "team_h_difficulty": _num(r["team_h_difficulty"], int), "team_a_difficulty": _num(r["team_a_difficulty"], int),
                         "kickoff_time": r["kickoff_time"], "finished": True})

    live = defaultdict(dict)
    club = defaultdict(dict)  # pid -> gw -> team id
    for r in gw_rows:
        pid, g = int(r["element"]), int(r["GW"])
        if pid not in praw:
            continue
        pos = POS[int(praw[pid]["element_type"])]
        tid = name_to_id.get(r["team"])
        if tid:
            club[pid][g] = tid
        st = {k: _num(r.get(k), int) for k in INT}
        st.update({k: _num(r.get(k)) for k in FLT})
        dcp = 2 if pos in DC_THR and st["defensive_contribution"] >= DC_THR[pos] else 0
        ex = {"fixture": int(r["fixture"]), "stats": [{"identifier": "defensive_contribution", "points": dcp}]}
        cur = live[g].get(pid)
        if cur is None:
            live[g][pid] = {"id": pid, "stats": st, "explain": [ex]}
        else:  # double gameweek: sum the two fixtures
            for k in INT + FLT:
                cur["stats"][k] += st[k]
            cur["explain"].append(ex)
    for g in live:
        for x in live[g].values():
            for k in FLT:
                x["stats"][k] = f'{x["stats"][k]:.2f}'
    live = {g: {"elements": list(v.values())} for g, v in sorted(live.items())}

    elements = []
    for pid, r in praw.items():
        po = r.get("penalties_order")
        elements.append({"id": pid, "element_type": int(r["element_type"]), "team": int(r["team"]), "web_name": r["web_name"],
                         "code": r["code"], "status": "a", "chance_of_playing_next_round": None, "removed": False,
                         "penalties_order": int(float(po)) if po not in ("", None, "None") else None})
    boot = {"elements": elements, "teams": [{"id": tid, "short_name": t["short_name"], "name": t["name"]} for tid, t in teams.items()],
            "game_config": scoring_from["game_config"],
            "events": [{"id": g, "finished": True} for g in range(1, 39)]}
    priors = _priors(season, {r["code"]: pid for pid, r in praw.items()})

    def team_at(pid, gw):
        c = club.get(pid)
        if not c:
            return None
        before = [g for g in c if g < gw]
        return c[max(before)] if before else c[min(c)]

    return boot, fixtures, live, priors, team_at
