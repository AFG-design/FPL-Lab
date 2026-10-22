#!/usr/bin/env python3
"""Shots, shots in the box and big chances from Understat, matched to FPL players.

Understat's per-shot data has pitch location and xG. We count:
  shots in the box  - X >= 0.843 and 0.204 <= Y <= 0.796 (the penalty area, as pitch fractions)
  big chances       - shots worth 0.3 xG or more (close to Opta's definition, which averages ~0.38 xG)
  chances created   - shots a player assisted; big chances created likewise
Finished matches are cached in understat/shots.json, so each run only downloads new games.
Writes understat/fpl_players.json keyed by FPL element id.
Usage: python3 understat.py [SEASON_START_YEAR]
"""
import gzip, json, os, re, sys, time, unicodedata, urllib.request, difflib
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "understat")
SEASON = sys.argv[1] if len(sys.argv) > 1 else None
UA = {"User-Agent": "Mozilla/5.0 fpl-lab", "X-Requested-With": "XMLHttpRequest", "Accept-Encoding": "gzip"}
US_TO_FPL = {"BRI": "BHA", "FLH": "FUL", "LED": "LEE", "NOT": "NFO"}   # Understat code -> FPL short name


def fetch(url, referer):
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers=dict(UA, Referer=referer))
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
                    raw = gzip.decompress(raw)
                return json.loads(raw)
        except Exception:
            time.sleep(2 + 3 * i)
    return None


def fpl(path):
    req = urllib.request.Request("https://fantasy.premierleague.com/api" + path, headers={"User-Agent": "Mozilla/5.0 fpl-lab"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


boot = fpl("/bootstrap-static/")
fixtures = fpl("/fixtures/")
if not SEASON:
    first = min(e["deadline_time"] for e in boot["events"])
    SEASON = first[:4]
league = fetch(f"https://understat.com/getLeagueData/EPL/{SEASON}", f"https://understat.com/league/EPL/{SEASON}")
if not league:
    print("Understat unavailable; keeping previous data"); sys.exit(0)

os.makedirs(OUTDIR, exist_ok=True)
cache_path = os.path.join(OUTDIR, "shots.json")
try:
    cache = json.load(open(cache_path))
    if cache.get("season") != SEASON or cache.get("v") != 2:
        cache = {"season": SEASON, "v": 2, "matches": {}}
except Exception:
    cache = {"season": SEASON, "v": 2, "matches": {}}

done = [m for m in league["dates"] if m.get("isResult")]
new = [m for m in done if m["id"] not in cache["matches"]]
for m in new:
    d = fetch(f"https://understat.com/getMatchData/{m['id']}", f"https://understat.com/match/{m['id']}")
    if not d:
        continue
    shots = []
    for side in ("h", "a"):
        for s in d["shots"][side]:
            shots.append([int(s["player_id"]), s["player"], float(s["X"]), float(s["Y"]), round(float(s["xG"]), 4),
                          s["result"], s["situation"], s.get("player_assisted") or "", side, s.get("shotType", "")])
    cache["matches"][m["id"]] = {"date": m["datetime"][:10], "h": m["h"]["short_title"], "a": m["a"]["short_title"], "shots": shots}
    time.sleep(0.4)
json.dump(cache, open(cache_path, "w"), separators=(",", ":"))

# ---- map Understat matches to FPL gameweeks (by teams and date)
fpl_teams = {t["short_name"]: t["id"] for t in boot["teams"]}
fx_by = {}
for f in fixtures:
    if f["event"] and f["kickoff_time"]:
        fx_by[(f["team_h"], f["team_a"])] = f["event"]
gw_of = {}
for mid, m in cache["matches"].items():
    h = fpl_teams.get(US_TO_FPL.get(m["h"], m["h"])); a = fpl_teams.get(US_TO_FPL.get(m["a"], m["a"]))
    gw_of[mid] = fx_by.get((h, a))
cur_gw = max([e["id"] for e in boot["events"] if e["finished"]] or [0])

# ---- per Understat player: season and last-4-GW counts
def in_box(x, y):
    return x >= 0.843 and 0.204 <= y <= 0.796


per = defaultdict(lambda: defaultdict(float))
name_team = {}
SET = {"FromCorner", "SetPiece", "DirectFreekick"}
team_sp = defaultdict(lambda: defaultdict(float))   # FPL team id -> sp_for/sp_against/op_for/op_against/games
for mid, m in cache["matches"].items():
    g = gw_of.get(mid)
    recent = g is not None and g > cur_gw - 4
    tids = {side: fpl_teams.get(US_TO_FPL.get(m[side], m[side])) for side in ("h", "a")}
    for side in ("h", "a"):
        team_sp[tids[side]]["games"] += 1
    for pid, pname, x, y, xg, res, sit, assister, side, stype in m["shots"]:
        team = m[side]
        other = "a" if side == "h" else "h"
        kind = "sp" if sit in SET else ("pen" if sit == "Penalty" else "op")
        team_sp[tids[side]][kind + "_for"] += xg
        team_sp[tids[other]][kind + "_against"] += xg
        per[pid][kind + "_xg"] += xg
        per[pid][kind + "_shots"] += 1
        if stype == "Head":
            per[pid]["headers"] += 1
            per[pid]["head_xg"] += xg
            if sit in SET:
                per[pid]["sp_headers"] += 1
        for key, add in (("shots", 1), ("sib", in_box(x, y)), ("bc", xg >= 0.3), ("bc_scored", xg >= 0.3 and res == "Goal"),
                         ("npxg", xg if sit != "Penalty" else 0), ("headers", 0)):
            per[pid][key] += add
            if recent:
                per[pid][key + "_4"] += add
        name_team[pid] = (pname, team)
        if assister:
            per[("a", team, assister)]["cc"] += 1
            per[("a", team, assister)]["bcc"] += xg >= 0.3
            if recent:
                per[("a", team, assister)]["cc_4"] += 1
                per[("a", team, assister)]["bcc_4"] += xg >= 0.3

# ---- match Understat players to FPL elements (team + name similarity)
def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]", "", s).strip()


els = boot["elements"]
by_team = defaultdict(list)
for e in els:
    by_team[e["team"]].append(e)
us_players = {int(p["id"]): p for p in league["players"]}
# Understat team title -> FPL team id, via Understat's own short codes
title_to_fpl = {}
for m in league["dates"]:
    for side in ("h", "a"):
        code = US_TO_FPL.get(m[side]["short_title"], m[side]["short_title"])
        if code in fpl_teams:
            title_to_fpl[m[side]["title"]] = fpl_teams[code]
mapping = {}
for upid, p in us_players.items():
    # Understat lists a player's team title(s), "A,B" after a mid-season move; FPL has the current club
    titles = [x.strip() for x in p["team_title"].split(",")]
    cands = [e for x in titles for e in by_team.get(title_to_fpl.get(x), [])]
    if not cands:
        continue
    un = norm(p["player_name"])
    best, score = None, 0.0
    for e in cands:
        options = [norm(f'{e["first_name"]} {e["second_name"]}'), norm(e["web_name"]), norm(e["second_name"]), norm(e.get("known_name") or "")]
        sc = max(difflib.SequenceMatcher(None, un, o).ratio() for o in options if o)
        # surname contained in the Understat name is a strong signal
        if norm(e["second_name"]).split() and norm(e["second_name"]).split()[-1] in un.split():
            sc = max(sc, 0.86)
        if norm(e["web_name"]) and norm(e["web_name"]) in un.split():
            sc = max(sc, 0.84)
        # break ties with minutes played
        sc += 0.02 * (1 - min(1, abs(e["minutes"] - int(p["time"])) / 300))
        if sc > score:
            best, score = e, sc
    if best and score >= 0.72:
        mapping[upid] = (best["id"], round(score, 2))

out = {}
for upid, (eid, sc) in mapping.items():
    p = us_players[upid]
    c = per.get(upid, {})
    pname, team = name_team.get(upid, (p["player_name"], None))
    a = per.get(("a", team, p["player_name"]), {}) if team else {}
    mins = int(p["time"])
    out[str(eid)] = {
        "us_id": upid, "match": sc, "mins": mins, "games": int(p["games"]),
        "shots": int(p["shots"]), "kp": int(p["key_passes"]), "npxg": round(float(p["npxG"]), 2),
        "xgchain": round(float(p["xGChain"]), 2), "xgbuildup": round(float(p["xGBuildup"]), 2),
        "sib": int(c.get("sib", 0)), "bc": int(c.get("bc", 0)), "bc_scored": int(c.get("bc_scored", 0)),
        "cc": int(a.get("cc", 0)), "bcc": int(a.get("bcc", 0)),
        "shots_4": int(c.get("shots_4", 0)), "sib_4": int(c.get("sib_4", 0)), "bc_4": int(c.get("bc_4", 0)),
        "cc_4": int(a.get("cc_4", 0)), "bcc_4": int(a.get("bcc_4", 0)),
        "op_xg": round(c.get("op_xg", 0), 2), "sp_xg": round(c.get("sp_xg", 0), 2), "pen_xg": round(c.get("pen_xg", 0), 2),
        "sp_shots": int(c.get("sp_shots", 0)), "pen_shots": int(c.get("pen_shots", 0)),
        "headers": int(c.get("headers", 0)), "head_xg": round(c.get("head_xg", 0), 2), "sp_headers": int(c.get("sp_headers", 0)),
    }
meta = {"season": SEASON, "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "matches": len(cache["matches"]),
        "new_matches": len(new), "players": len(out), "unmatched": len(us_players) - len(mapping), "last4_from_gw": cur_gw - 3}
teams_out = {str(t): {k: round(v, 2) for k, v in d.items()} for t, d in team_sp.items() if t}
json.dump({"meta": meta, "players": out, "teams": teams_out}, open(os.path.join(OUTDIR, "fpl_players.json"), "w"), separators=(",", ":"))
print(meta)
