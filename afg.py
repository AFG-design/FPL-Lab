#!/usr/bin/env python3
"""AFG suggestion: a fan's-eye punt layer on top of the projection model.

The model (fplmodel.py) is not changed. This file takes its projections and nudges them
with the things a football fan weighs up:

  - record against this opponent (goals, assists, clean sheets, points)
  - record at this ground (how often he has played there and how he did)
  - home and away record (beyond the normal home advantage)
  - the club's head-to-head record (for keepers and defenders)
  - a hot run of returns
  - facing a former club, derbies (shown, see below)
  - a European game a few days before (europe.json)
  - a new manager (afg_manual.json, edited by hand)

Every record is turned into "points beyond expectation": points in a 60+ minute game, minus
the player's own average that season, minus what players in his position averaged against
that opponent at that venue that season. That takes out the opponent's strength (which the
model already has), leaving what is about him and that fixture. Records are shrunk: a few
games count for little.

Honest note (tested on 2019/20-2025/26, 55,000 starts, records from earlier seasons only):
none of the venue or opponent records predicted later games once opponent strength was
taken out (correlations about 0.00). Derbies made no difference; facing a former club came
out slightly below par. So this is a punt layer, deliberately small, and the scoreboard
(history/afg_gw*.json) tracks whether it beats the model this season.

  python3 afg.py records     # rebuild afg/records.json from the vaastav archive (weekly)
  python3 afg.py backtest    # AFG v the model on 2025/26, week by week
"""
import json, os, sys, datetime as dt
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SEASONS = ["2019-20", "2020-21", "2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]
POS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
RECORDS = os.path.join(HERE, "afg", "records.json")
MANUAL = os.path.join(HERE, "afg_manual.json")

# How hard each nudge pushes. k = pseudo-games of "no effect" mixed into a record, so a record
# needs about k games before it counts for half its face value. Points are per game for a
# 60+ minute start; they are scaled down for players less sure to play.
SET = {
    "k_opp": 10.0,     # record v this opponent
    "k_ground": 10.0,  # record at this ground (away games; at home it is his home record)
    "k_split": 15.0,   # home / away record
    "k_club": 8.0,     # club v this opponent, keepers and defenders (per meeting)
    "w": 1.0,          # multiplier on the record nudges
    "cap_one": 1.0,    # largest single nudge, points
    "cap": 1.5,        # largest total nudge, points
    "hot": 0.25,       # returned in each of his last 3 starts
    "former": 0.0,     # facing a former club: shown, no nudge (archive: -0.2 pts/game, not significant)
    "derby": 0.0,      # derby: shown, no nudge (archive: +0.00 pts/game over 4,500 starts)
    "euro": -0.15,     # European game within 3 days before (on top of the model's rotation cut)
    "new_mgr": 0.2,    # new manager, first 4 league games
    "min_show": 3,     # games before a record is quoted
}

STADIUM = {
    "Arsenal": "the Emirates", "Aston Villa": "Villa Park", "Bournemouth": "the Vitality",
    "Brentford": "the Gtech", "Brighton": "the Amex", "Burnley": "Turf Moor", "Chelsea": "Stamford Bridge",
    "Coventry": "the CBS Arena", "Crystal Palace": "Selhurst Park", "Everton": "Hill Dickinson Stadium",
    "Fulham": "Craven Cottage", "Hull": "the MKM Stadium", "Ipswich": "Portman Road", "Leeds": "Elland Road",
    "Leicester": "the King Power", "Liverpool": "Anfield", "Luton": "Kenilworth Road", "Man City": "the Etihad",
    "Man Utd": "Old Trafford", "Newcastle": "St James' Park", "Norwich": "Carrow Road",
    "Nott'm Forest": "the City Ground", "Sheffield Utd": "Bramall Lane", "Southampton": "St Mary's",
    "Spurs": "Tottenham Hotspur Stadium", "Sunderland": "the Stadium of Light", "Watford": "Vicarage Road",
    "West Brom": "The Hawthorns", "West Ham": "the London Stadium", "Wolves": "Molineux",
}

DERBIES = [
    ("ARS", "TOT"), ("ARS", "CHE"), ("CHE", "TOT"), ("CHE", "FUL"), ("FUL", "BRE"), ("CHE", "BRE"),
    ("CRY", "BHA"), ("WHU", "TOT"), ("WHU", "CHE"), ("WHU", "ARS"), ("CRY", "CHE"), ("LIV", "EVE"),
    ("LIV", "MUN"), ("MCI", "MUN"), ("NEW", "SUN"), ("AVL", "WOL"), ("NFO", "LEI"), ("LEE", "MUN"),
    ("SOU", "BOU"), ("IPS", "NOR"), ("COV", "AVL"), ("COV", "LEI"), ("HUL", "LEE"),
]


def canon(name):
    """Club names differ slightly between seasons ("Ipswich" / "Ipswich Town")."""
    n = name.strip()
    fix = {"Manchester City": "Man City", "Manchester United": "Man Utd", "Nottingham Forest": "Nott'm Forest",
           "Tottenham": "Spurs", "Tottenham Hotspur": "Spurs", "Wolverhampton": "Wolves",
           "Sheffield United": "Sheffield Utd", "Brighton and Hove Albion": "Brighton"}
    if n in fix:
        return fix[n]
    if n in ("Man City", "Man Utd", "Sheffield Utd"):
        return n
    for suf in (" City", " Town", " United", " Utd", " Albion"):
        if n.endswith(suf):
            n = n[: -len(suf)]
    return fix.get(n, n)


def stadium(club, season):
    if club == "Everton" and season < "2025-26":
        return "Goodison Park"
    return STADIUM.get(club, club + "'s ground")


def is_derby(a, b, extra=()):
    pairs = set(DERBIES) | {tuple(x) for x in extra}
    return (a, b) in pairs or (b, a) in pairs


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


# ------------------------------------------------------------------ one row per player per match
def archive_rows(seasons=SEASONS):
    import archive
    rows = []
    for s in seasons:
        tcsv = archive._rows(s, "teams.csv")
        teams = {r["id"]: canon(r["name"]) for r in tcsv}
        short = {canon(r["name"]): r["short_name"] for r in tcsv}
        praw = {r["id"]: r for r in archive._rows(s, "players_raw.csv")}
        fx = {r["id"]: r for r in archive._rows(s, "fixtures.csv")}
        for r in archive._rows(s, "gws/merged_gw.csv"):
            p, f = praw.get(r["element"]), fx.get(r["fixture"])
            if not p or not f or int(p["element_type"]) not in POS:
                continue  # element_type 5 = managers (2024/25 chip)
            home = r["was_home"] in ("True", "true", "1")
            team, opp = teams.get(f["team_h"] if home else f["team_a"]), teams.get(r["opponent_team"])
            if not team or not opp:
                continue
            rows.append({
                "code": str(p["code"]), "season": s, "gw": int(_num(r["GW"])), "ko": r["kickoff_time"][:10],
                "pos": POS[int(p["element_type"])], "team": team, "opp": opp, "home": home,
                "ts": short.get(team), "os": short.get(opp), "mins": int(_num(r["minutes"])),
                "g": int(_num(r["goals_scored"])), "a": int(_num(r["assists"])), "cs": int(_num(r["clean_sheets"])),
                "pts": int(_num(r["total_points"])), "name": p["web_name"],
                "gf": int(_num(f["team_h_score"] if home else f["team_a_score"])),
                "ga": int(_num(f["team_a_score"] if home else f["team_h_score"])),
            })
    return rows


def live_rows(boot, fixtures, live, season):
    """This season's rows from the FPL API (bootstrap, fixtures, /event/N/live)."""
    teams = {t["id"]: canon(t["name"]) for t in boot["teams"]}
    short = {t["id"]: t["short_name"] for t in boot["teams"]}
    els = {e["id"]: e for e in boot["elements"]}
    fx = {f["id"]: f for f in fixtures}
    rows = []
    for g, data in live.items():
        for x in data["elements"]:
            e = els.get(x["id"])
            exs = x.get("explain") or []
            if not e or not exs or e["element_type"] not in POS:
                continue
            for ex in exs:
                f = fx.get(ex["fixture"])
                if not f or f.get("team_h_score") is None or e["team"] not in (f["team_h"], f["team_a"]):
                    continue  # skip games for a former club this season rather than guess the side
                st = {s["identifier"]: s for s in ex["stats"]}
                one = len(exs) == 1
                mins = x["stats"]["minutes"] if one else st.get("minutes", {}).get("value", 0)
                if mins <= 0:
                    continue
                home = e["team"] == f["team_h"]
                opp = f["team_a"] if home else f["team_h"]
                val = lambda k: x["stats"][k] if one else st.get(k, {}).get("value", 0)
                rows.append({
                    "code": str(e["code"]), "season": season, "gw": int(g), "ko": (f.get("kickoff_time") or "")[:10],
                    "pos": POS[e["element_type"]], "team": teams[e["team"]], "opp": teams[opp], "home": home,
                    "ts": short[e["team"]], "os": short[opp], "mins": mins,
                    "g": val("goals_scored"), "a": val("assists"), "cs": val("clean_sheets"),
                    "pts": x["stats"]["total_points"] if one else sum(s["points"] for s in ex["stats"]),
                    "name": e["web_name"],
                    "gf": f["team_h_score"] if home else f["team_a_score"],
                    "ga": f["team_a_score"] if home else f["team_h_score"],
                })
    return rows


# ------------------------------------------------------------------ points beyond expectation
def residuals(rows, min_mins=60):
    """Adds r (v opponent / ground) and r_split (home-away) to every 60+ minute row."""
    starts = [r for r in rows if r["mins"] >= min_mins]
    own = defaultdict(lambda: [0.0, 0])
    for r in starts:
        o = own[(r["code"], r["season"])]; o[0] += r["pts"]; o[1] += 1
    for r in starts:
        s, n = own[(r["code"], r["season"])]
        r["r0"] = r["pts"] - s / n
    ctx, ha = defaultdict(lambda: [0.0, 0]), defaultdict(lambda: [0.0, 0])
    for r in starts:
        c = ctx[(r["season"], r["pos"], r["opp"], r["home"])]; c[0] += r["r0"]; c[1] += 1
        h = ha[(r["season"], r["pos"], r["home"])]; h[0] += r["r0"]; h[1] += 1
    for r in starts:
        s, n = ctx[(r["season"], r["pos"], r["opp"], r["home"])]
        r["r"] = r["r0"] - s / (n + 5)
        s2, n2 = ha[(r["season"], r["pos"], r["home"])]
        r["r_split"] = r["r0"] - s2 / n2
    return rows


# ------------------------------------------------------------------ summaries
# a record: [apps, goals, assists, clean sheets, points, 60+ starts, sum of points beyond expectation]
def _rec():
    return [0, 0, 0, 0, 0, 0, 0.0]


def _add(rec, r, rk="r"):
    rec[0] += 1; rec[1] += r["g"]; rec[2] += r["a"]; rec[3] += r["cs"]; rec[4] += r["pts"]
    if rk in r:
        rec[5] += 1; rec[6] = round(rec[6] + r[rk], 2)


def _blank_player(name):
    return {"name": name, "opp": {}, "gr": {}, "h": _rec(), "a": _rec(), "clubs": {}, "form": []}


def summarise(rows, codes=None):
    """{"players": {code: {...}}, "clubs": {...}} from rows that already carry residuals."""
    pl = {}
    meet = defaultdict(dict)                         # team -> opp -> {ko: [season, home, gf, ga]}
    cdef = defaultdict(lambda: defaultdict(list))    # (team, opp) -> ko -> defenders' residuals
    for r in sorted(rows, key=lambda r: r["ko"]):
        if r["mins"] <= 0:
            continue
        meet[r["team"]].setdefault(r["opp"], {})[r["ko"]] = [r["season"], int(r["home"]), r["gf"], r["ga"]]
        if r["pos"] in ("GKP", "DEF") and "r" in r:
            cdef[(r["team"], r["opp"])][r["ko"]].append(r["r"])
        if codes is not None and r["code"] not in codes:
            continue
        p = pl.setdefault(r["code"], _blank_player(r["name"]))
        p["name"] = r["name"]
        p["clubs"][r["team"]] = max(p["clubs"].get(r["team"], ""), r["season"])
        _add(p["opp"].setdefault(r["opp"], _rec()), r)
        if not r["home"]:
            _add(p["gr"].setdefault(stadium(r["opp"], r["season"]), _rec()), r)
        _add(p["h" if r["home"] else "a"], r, "r_split")
        if r["mins"] >= 60:
            ret = r["g"] + r["a"] > 0 or (r["cs"] > 0 and r["pos"] in ("GKP", "DEF"))
            p["form"] = (p["form"] + [[r["season"], int(ret)]])[-3:]
    clubs = {"meet": {}, "def": {}}
    for t, opps in meet.items():
        clubs["meet"][t] = {o: [v for _, v in sorted(ms.items())][-8:] for o, ms in opps.items()}
    for (t, o), byko in cdef.items():
        vals = [sum(v) / len(v) for v in byko.values()]
        clubs["def"].setdefault(t, {})[o] = [len(vals), round(sum(vals), 2)]
    return {"players": pl, "clubs": clubs}


def merge(a, b):
    """Add summary b (this season) to summary a (past seasons)."""
    out = {"players": dict(a["players"]), "clubs": {"meet": {t: dict(v) for t, v in a["clubs"]["meet"].items()},
                                                     "def": {t: dict(v) for t, v in a["clubs"]["def"].items()}}}
    addv = lambda x, y: [round(i + j, 2) for i, j in zip(x, y)]
    for code, q in b["players"].items():
        old = out["players"].get(code) or _blank_player(q["name"])
        p = {"name": q["name"], "opp": dict(old["opp"]), "gr": dict(old["gr"]), "h": addv(old["h"], q["h"]),
             "a": addv(old["a"], q["a"]), "clubs": dict(old["clubs"]), "form": (old.get("form", []) + q["form"])[-3:]}
        for kind in ("opp", "gr"):
            for k, rec in q[kind].items():
                p[kind][k] = addv(p[kind].get(k, _rec()), rec)
        for c, s in q["clubs"].items():
            p["clubs"][c] = max(p["clubs"].get(c, ""), s)
        out["players"][code] = p
    for t, opps in b["clubs"]["meet"].items():
        for o, ms in opps.items():
            out["clubs"]["meet"].setdefault(t, {})
            out["clubs"]["meet"][t][o] = (out["clubs"]["meet"][t].get(o, []) + ms)[-8:]
    for t, opps in b["clubs"]["def"].items():
        for o, (n, s) in opps.items():
            out["clubs"]["def"].setdefault(t, {})
            cur = out["clubs"]["def"][t].get(o, [0, 0.0])
            out["clubs"]["def"][t][o] = [cur[0] + n, round(cur[1] + s, 2)]
    return out


def make_records(codes=None):
    rows = residuals(archive_rows())
    summ = summarise(rows, codes)
    summ["built"] = dt.date.today().isoformat()
    summ["seasons"] = SEASONS
    os.makedirs(os.path.dirname(RECORDS), exist_ok=True)
    json.dump(summ, open(RECORDS, "w"), separators=(",", ":"))
    return summ


def load_records():
    try:
        return json.load(open(RECORDS))
    except Exception:
        return {"players": {}, "clubs": {"meet": {}, "def": {}}, "seasons": []}


def load_manual():
    try:
        return json.load(open(MANUAL))
    except Exception:
        return {}


# ------------------------------------------------------------------ the nudges
def _clip(x, c):
    return max(-c, min(c, x))


def _plural(n, word):
    return f"{int(n)} {word}{'' if n == 1 else 's'}"


def _line(rec, pos):
    """'6 games, 3 goals, 2 assists, 5.3 pts a game' for a record."""
    n, g, a, cs, pts = rec[:5]
    bits = [_plural(n, "game")]
    if pos in ("MID", "FWD") or g or a:
        bits.append(f"{_plural(g, 'goal')}, {_plural(a, 'assist')}")
    if pos in ("GKP", "DEF"):
        bits.append(_plural(cs, "clean sheet"))
    bits.append(f"{pts / n:.1f} pts a game")
    return ", ".join(bits)


def nudge(rec_p, clubs, pos, team, team_s, opp, opp_s, home, season, extra, S=SET):
    """Nudges for one fixture: (points, [[kind, points, text], ...])."""
    why = []
    w = S["w"]
    if rec_p:
        o = rec_p["opp"].get(opp)
        gr = rec_p["gr"].get(stadium(opp, season)) if not home else None
        parts = []
        if o and o[5]:
            parts.append(o[6] / (o[5] + S["k_opp"]))
        if gr and gr[5]:
            parts.append(gr[6] / (gr[5] + S["k_ground"]))
        txt = []
        if o and o[0] >= S["min_show"]:
            txt.append(f"v {opp}: {_line(o, pos)}")
        if gr and gr[0] >= S["min_show"]:
            txt.append(f"at {stadium(opp, season)}: {_line(gr, pos)}")
        if parts or txt:
            v = _clip(w * sum(parts) / len(parts), S["cap_one"]) if parts else 0.0
            if txt:
                why.append(["matchup", round(v, 2), "; ".join(txt)])
            elif abs(v) >= 0.1:
                why.append(["matchup", round(v, 2), f"v {opp}: only {_plural(o[0] if o else gr[0], 'game')} so far"])
        s, other = rec_p["h" if home else "a"], rec_p["a" if home else "h"]
        if s[5] >= 4 and s[0]:
            v = _clip(w * s[6] / (s[5] + S["k_split"]), S["cap_one"])
            if abs(v) >= 0.05:
                rest = f", {other[4] / other[0]:.1f} {'away' if home else 'at home'}" if other[0] else ""
                why.append(["split", round(v, 2), f"{'At home' if home else 'Away'}: {s[4] / s[0]:.1f} pts a game in {_plural(s[0], 'game')}{rest}"])
        f = rec_p.get("form") or []
        if len(f) == 3 and all(x[1] for x in f) and all(x[0] == season for x in f):
            why.append(["hot", S["hot"], "Returned in each of his last 3 starts"])
        if opp != team and opp in rec_p.get("clubs", {}):
            why.append(["former", S["former"], f"Former club (last played for them {rec_p['clubs'][opp].replace('-', '/')})"])
    if pos in ("GKP", "DEF"):
        d = (clubs.get("def", {}).get(team) or {}).get(opp)
        ms = (clubs.get("meet", {}).get(team) or {}).get(opp) or []
        if d and d[0] and ms:
            v = _clip(w * d[1] / (d[0] + S["k_club"]), S["cap_one"])
            cs = sum(1 for m in ms if m[3] == 0)
            res = ", ".join(("W" if m[2] > m[3] else "D" if m[2] == m[3] else "L") + f" {m[2]}-{m[3]}" for m in ms[-5:])
            why.append(["club", round(v, 2), f"{team} v {opp}, last {min(5, len(ms))}: {res} ({_plural(cs, 'clean sheet')} in {len(ms)})"])
    if is_derby(team_s, opp_s, extra.get("derbies", [])):
        why.append(["derby", S["derby"], "Derby day"])
    if extra.get("euro"):
        why.append(["euro", S["euro"], f"Plays {extra['euro']}"])
    if extra.get("new_mgr"):
        why.append(["mgr", S["new_mgr"], extra["new_mgr"]])
    return _clip(sum(x[1] for x in why), S["cap"]), why


def suggest(records, players, upcoming, teams, gw, season, euro_flags=None, manual=None, S=SET):
    """players: {id: {code, team, pos, xp: {gw: x}, xmin}}; upcoming: fplmodel upcoming;
    teams: {id: {"name": canonical name, "short": "ARS"}}.
    Returns {id: {"x": AFG xP, "m": model xP, "n": nudge, "why": [...]}} for gameweek gw."""
    manual, euro_flags = manual or {}, euro_flags or {}
    clubs = records["clubs"]
    out = {}
    for pid, p in players.items():
        fx = upcoming.get(p["team"], {}).get(gw, [])
        xm = p["xp"].get(gw, 0.0)
        if not fx or xm <= 0:
            continue
        rec_p = records["players"].get(str(p.get("code")))
        team, team_s = teams[p["team"]]["name"], teams[p["team"]]["short"]
        f = min(1.0, (p.get("xmin") or 0) / 75)
        tot, whys = 0.0, []
        for (opp_id, home, *_rest) in fx:
            extra = {"derbies": manual.get("derbies", [])}
            if euro_flags.get((p["team"], gw)):
                extra["euro"] = euro_flags[(p["team"], gw)]
            nm = (manual.get("new_managers") or {}).get(team_s)
            if nm and gw <= nm.get("until_gw", 0):
                extra["new_mgr"] = f"New manager bounce: {nm.get('name', 'new manager')}"
            n, why = nudge(rec_p, clubs, p["pos"], team, team_s, teams[opp_id]["name"], teams[opp_id]["short"],
                           home, season, extra, S)
            tot += n * f
            whys += why
        out[pid] = {"x": round(max(0.0, xm + tot), 2), "m": round(xm, 2), "n": round(tot, 2), "why": whys}
    return out


# ------------------------------------------------------------------ picks: captain, XI, punts
XI_MIN = {"GKP": 1, "DEF": 3, "MID": 2, "FWD": 1}
XI_MAX = {"GKP": 1, "DEF": 5, "MID": 5, "FWD": 3}


def best_xi(ids, val, pos):
    ps = sorted(ids, key=lambda i: -val(i))
    xi, cnt = [], defaultdict(int)
    for k, mn in XI_MIN.items():
        for i in [i for i in ps if pos[i] == k][:mn]:
            xi.append(i); cnt[k] += 1
    for i in ps:
        if len(xi) == 11:
            break
        if i not in xi and cnt[pos[i]] < XI_MAX[pos[i]]:
            xi.append(i); cnt[pos[i]] += 1
    return xi


def picks(squad, sell, bank, players, A):
    """The AFG calls on a squad: XI, captain and up to 3 punt transfers (one GW, fan-factor led)."""
    pos = {i: players[i]["pos"] for i in players}
    va = lambda i: A[i]["x"] if i in A else 0.0
    xi = best_xi(squad, va, pos)
    order = sorted(xi, key=lambda i: -va(i))
    clubs = defaultdict(int)
    for i in squad:
        clubs[players[i]["team"]] += 1
    punts = []
    for out_id in squad:
        budget = bank + sell.get(out_id, players[out_id]["price"])
        best = None
        for i, a in A.items():
            p = players.get(i)
            if not p or i in squad or p["pos"] != pos[out_id] or not p.get("ok") or p["price"] > budget + 1e-9:
                continue
            if clubs[p["team"]] - (players[out_id]["team"] == p["team"]) >= 3:
                continue
            gain = a["x"] - va(out_id)
            if a["n"] < 0.3 or gain < 0.5:
                continue  # a punt must be driven by the fan factors, not just the model
            if not best or gain > best[1]:
                best = (i, gain)
        if best:
            punts.append({"out": out_id, "in": best[0], "gain": round(best[1], 2)})
    punts.sort(key=lambda m: -m["gain"])
    seen, top = set(), []
    for m in punts:
        if m["in"] not in seen:
            seen.add(m["in"]); top.append(m)
    return {"xi": xi, "cap": order[0] if order else None, "vice": order[1] if len(order) > 1 else None, "punts": top[:3]}


def model_alt(out_id, squad, sell, bank, players, gw):
    """The model's own best like-for-like replacement for a punt's outgoing player (same GW)."""
    budget = bank + sell.get(out_id, players[out_id]["price"])
    best = None
    for i, p in players.items():
        if i in squad or p["pos"] != players[out_id]["pos"] or not p.get("ok") or p["price"] > budget + 1e-9:
            continue
        x = p["xp"].get(gw, 0.0)
        if not best or x > best[1]:
            best = (i, x)
    return best[0] if best else None


# ------------------------------------------------------------------ scoreboard
def score_week(snap, pts, played_recently):
    """snap: history/afg_gwN.json; pts(pid) -> real points that GW (0 if none);
    played_recently(pid) -> bool, for the accuracy pool (as the Model tab uses)."""
    a_cap, m_cap = snap.get("afg_cap"), snap.get("model_cap")
    row = {"gw": snap["gw"], "afg_cap": a_cap, "model_cap": m_cap,
           "afg_cap_pts": pts(a_cap) * 2 if a_cap else 0, "model_cap_pts": pts(m_cap) * 2 if m_cap else 0,
           "afg_xi_pts": sum(pts(i) for i in snap.get("afg_xi", [])) + (pts(a_cap) if a_cap else 0),
           "model_xi_pts": sum(pts(i) for i in snap.get("model_xi", [])) + (pts(m_cap) if m_cap else 0),
           "punts": [{"in": m["in"], "out": m["out"], "alt": m.get("alt"), "in_pts": pts(m["in"]),
                      "out_pts": pts(m["out"]), "alt_pts": pts(m["alt"]) if m.get("alt") else None}
                     for m in snap.get("punts", [])]}
    ma = aa = 0.0
    n = hits = calls = 0
    for pid_s, (xm, xa) in snap["players"].items():
        pid = int(pid_s)
        if not played_recently(pid):
            continue
        a = pts(pid)
        ma += abs(xm - a); aa += abs(xa - a); n += 1
        if abs(xa - xm) >= 0.4:
            calls += 1; hits += (a - xm) * (xa - xm) > 0
    row.update({"n": n, "mae_model": round(ma / n, 3) if n else None, "mae_afg": round(aa / n, 3) if n else None,
                "calls": calls, "calls_right": hits})
    return row


# ------------------------------------------------------------------ backtest on 2025/26
def backtest(season="2025-26", gws=range(4, 39)):
    """AFG v the model on a past season, with records from before each gameweek only."""
    import bench
    from fplmodel import project
    rows = residuals(archive_rows())
    base = summarise([r for r in rows if r["season"] < season])
    cur = [r for r in rows if r["season"] == season]
    ctx, team_at = bench._season(season)
    teams = {t["id"]: {"name": canon(t["name"]), "short": t["short_name"]} for t in ctx["boot"]["teams"]}
    code_of = {pid: str(e["code"]) for pid, e in ctx["elements"].items()}
    acc = defaultdict(list)
    calls = [0, 0]
    weeks = []
    for k in gws:
        kos = [f["kickoff_time"][:10] for f in ctx["fixtures"] if f["event"] == k and f.get("kickoff_time")]
        if not kos:
            continue
        before = [dict(r) for r in cur if r["ko"] < min(kos)]
        for r in before:
            for key in ("r", "r0", "r_split"):
                r.pop(key, None)
        R = merge(base, summarise(residuals(before)))
        cx = dict(ctx)
        cx["elements"] = {pid: dict(e, team=team_at(pid, k) or e["team"]) for pid, e in ctx["elements"].items()}
        pr = project(cx, k, 1, {"use_flags": False})
        pl = {pid: {"code": code_of[pid], "team": e["team"], "pos": POS[e["element_type"]],
                    "xp": pr["players"][pid]["xp"], "xmin": pr["players"][pid]["xmin"]}
              for pid, e in cx["elements"].items() if pid in pr["players"]}
        A = suggest(R, pl, pr["upcoming"], teams, k, season)
        rws = []
        for pid, a in A.items():
            act = ctx["pts_gw"].get(pid, {}).get(k)
            if act is None or not any(ctx["pstats"].get(pid, {}).get(g, {}).get("minutes", 0) > 0 for g in range(k - 3, k)):
                continue
            rws.append((pid, a["m"], a["x"], act))
            if abs(a["x"] - a["m"]) >= 0.4:
                calls[0] += 1; calls[1] += (act - a["m"]) * (a["x"] - a["m"]) > 0
        if not rws:
            continue
        acc["model"] += [abs(m - a) for _, m, _, a in rws]
        acc["afg"] += [abs(x - a) for _, _, x, a in rws]
        tm, ta = sorted(rws, key=lambda r: -r[1]), sorted(rws, key=lambda r: -r[2])
        weeks.append({"gw": k, "cap_model": tm[0][3] * 2, "cap_afg": ta[0][3] * 2,
                      "top10_model": sum(r[3] for r in tm[:10]), "top10_afg": sum(r[3] for r in ta[:10])})
        print(f"GW{k}: captain model {tm[0][3] * 2} v AFG {ta[0][3] * 2}", file=sys.stderr)
    av = lambda v: sum(v) / len(v)
    return {"season": season, "gws": len(weeks), "built": dt.date.today().isoformat(),
            "mae_model": round(av(acc["model"]), 3), "mae_afg": round(av(acc["afg"]), 3),
            "cap_model": sum(w["cap_model"] for w in weeks), "cap_afg": sum(w["cap_afg"] for w in weeks),
            "cap_diff_weeks": sum(1 for w in weeks if w["cap_model"] != w["cap_afg"]),
            "top10_model": sum(w["top10_model"] for w in weeks), "top10_afg": sum(w["top10_afg"] for w in weeks),
            "calls": calls[0], "calls_right": calls[1], "weeks": weeks}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "records"
    if cmd == "records":
        codes = None
        try:
            import urllib.request
            req = urllib.request.Request("https://fantasy.premierleague.com/api/bootstrap-static/", headers={"User-Agent": "Mozilla/5.0 fpl-lab"})
            codes = {str(e["code"]) for e in json.load(urllib.request.urlopen(req, timeout=30))["elements"]}
        except Exception as ex:
            print("bootstrap not reached, keeping every player:", ex)
        s = make_records(codes)
        print(f"wrote {RECORDS}: {len(s['players'])} players, {os.path.getsize(RECORDS) / 1e6:.1f} MB")
    elif cmd == "backtest":
        r = backtest()
        os.makedirs(os.path.join(HERE, "afg"), exist_ok=True)
        json.dump(r, open(os.path.join(HERE, "afg", "backtest.json"), "w"), indent=1)
        print(json.dumps({k: v for k, v in r.items() if k != "weeks"}, indent=1))
