#!/usr/bin/env python3
"""FPL Assistant data builder.

Fetches the public FPL API, projects expected points for every player over the
next six gameweeks, analyses one manager's squad and writes data.json for the
dashboard page.

Usage:  python3 build.py [TEAM_ID] [OUT_PATH]
"""
import json, math, sys, time, urllib.request, datetime as dt
from collections import defaultdict

TEAM_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 8122679
OUT = sys.argv[2] if len(sys.argv) > 2 else "data.json"
API = "https://fantasy.premierleague.com/api"
HORIZON = 6          # gameweeks projected
EVAL_GWS = 5         # gameweeks used to judge transfers
DECAY = 0.92         # weight on each later gameweek when judging transfers
RECENCY = 0.85       # weight on each older gameweek when measuring form


def get(path, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(API + path, headers={"User-Agent": "Mozilla/5.0 fpl-assistant"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def poisson(k, mu):
    return math.exp(-mu) * mu ** k / math.factorial(k)


def exp_floor_div(mu, d, kmax=15):
    """E[floor(X/d)] for X ~ Poisson(mu)."""
    return sum((k // d) * poisson(k, mu) for k in range(kmax))


# ---------------------------------------------------------------- fetch
boot = get("/bootstrap-static/")
fixtures = get("/fixtures/")
entry = get(f"/entry/{TEAM_ID}/")
history = get(f"/entry/{TEAM_ID}/history/")
transfers = get(f"/entry/{TEAM_ID}/transfers/")

events = boot["events"]
cur_ev = next((e for e in events if e["is_current"]), None)
next_ev = next((e for e in events if e["is_next"]), None)
cur_gw = cur_ev["id"] if cur_ev else 0
next_gw = next_ev["id"] if next_ev else None
started_gws = [e["id"] for e in events if e["id"] <= cur_gw]
live = {g: get(f"/event/{g}/live/") for g in started_gws}
picks_gw = entry.get("current_event") or cur_gw
picks = get(f"/entry/{TEAM_ID}/event/{picks_gw}/picks/") if picks_gw else None

scoring = boot["game_config"]["scoring"]
POS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
teams = {t["id"]: t for t in boot["teams"]}
elements = {e["id"]: e for e in boot["elements"]}

# per-gameweek player stats + DC hits
pstats = defaultdict(dict)   # pid -> gw -> stats
dc_hit = defaultdict(dict)   # pid -> gw -> bool
for g, data in live.items():
    for x in data["elements"]:
        pstats[x["id"]][g] = x["stats"]
        dc_hit[x["id"]][g] = any(s["identifier"] == "defensive_contribution" and s["points"] > 0
                                 for ex in x["explain"] for s in ex["stats"])

# ---------------------------------------------------------------- team ratings
team_fix = defaultdict(list)   # tid -> [(gw, opp, home)]
for f in fixtures:
    if f["event"]:
        team_fix[f["team_h"]].append((f["event"], f["team_a"], True, f))
        team_fix[f["team_a"]].append((f["event"], f["team_h"], False, f))

team_gw_xg = defaultdict(lambda: defaultdict(float))
for pid, gws in pstats.items():
    t = elements[pid]["team"] if pid in elements else None
    if not t:
        continue
    for g, s in gws.items():
        team_gw_xg[t][g] += float(s["expected_goals"])

games = defaultdict(list)  # tid -> (w, for, against, home)
for f in fixtures:
    if not f["finished"] and not f["finished_provisional"]:
        continue
    g = f["event"]
    w = 0.93 ** max(0, cur_gw - g)
    h, a = f["team_h"], f["team_a"]
    # blend xG (70%) and real goals (30%); single-fixture gameweeks assumed for xG split
    nh = sum(1 for x in team_fix[h] if x[0] == g)
    na = sum(1 for x in team_fix[a] if x[0] == g)
    xh = team_gw_xg[h][g] / nh if nh else 0
    xa = team_gw_xg[a][g] / na if na else 0
    fh = 0.7 * xh + 0.3 * (f["team_h_score"] or 0)
    fa = 0.7 * xa + 0.3 * (f["team_a_score"] or 0)
    games[h].append((w, fh, fa, True))
    games[a].append((w, fa, fh, False))

allg = [x for v in games.values() for x in v]
LEAGUE = (sum(x[1] for x in allg) / len(allg)) if allg else 1.35
HOME, AWAY = 1.12, 0.89
PRIOR_GAMES = 3.0
rating = {}
for tid in teams:
    gs = games.get(tid, [])
    W = sum(x[0] for x in gs)
    # remove venue effect before averaging
    gf = sum(x[0] * x[1] / (HOME if x[3] else AWAY) for x in gs)
    ga = sum(x[0] * x[2] / (AWAY if x[3] else HOME) for x in gs)
    att = (gf + PRIOR_GAMES * LEAGUE) / (W + PRIOR_GAMES) / LEAGUE
    dfn = (ga + PRIOR_GAMES * LEAGUE) / (W + PRIOR_GAMES) / LEAGUE
    rating[tid] = {"att": att, "def": dfn}
# one refinement pass adjusting for opposition strength
for _ in range(2):
    new = {}
    for tid in teams:
        gs = []
        for (g, opp, home, f) in team_fix[tid]:
            if not (f["finished"] or f["finished_provisional"]):
                continue
            gs.append(opp)
        oppdef = sum(rating[o]["def"] for o in gs) / len(gs) if gs else 1
        oppatt = sum(rating[o]["att"] for o in gs) / len(gs) if gs else 1
        new[tid] = {"att": rating[tid]["att"] / (oppdef ** 0.5), "def": rating[tid]["def"] / (oppatt ** 0.5)}
    ma = sum(v["att"] for v in new.values()) / len(new)
    md = sum(v["def"] for v in new.values()) / len(new)
    rating = {k: {"att": v["att"] / ma, "def": v["def"] / md} for k, v in new.items()}


def team_mu(tid, opp, home):
    return LEAGUE * rating[tid]["att"] * rating[opp]["def"] * (HOME if home else AWAY)


proj_gws = [g for g in range(next_gw, next_gw + HORIZON) if g <= 38] if next_gw else []
upcoming = defaultdict(lambda: defaultdict(list))  # tid -> gw -> [(opp, home, mu_for, mu_against, fdr)]
for tid, lst in team_fix.items():
    for (g, opp, home, f) in lst:
        if g in proj_gws:
            fdr = f["team_h_difficulty"] if home else f["team_a_difficulty"]
            upcoming[tid][g].append((opp, home, team_mu(tid, opp, home), team_mu(opp, tid, not home), fdr))

# ---------------------------------------------------------------- player model
def wavg(pid, key, per90=True):
    num = den = 0.0
    for g, s in pstats.get(pid, {}).items():
        w = RECENCY ** (cur_gw - g)
        num += w * float(s[key])
        den += w * (s["minutes"] if per90 else 1)
    return num, den


# positional priors (per 90) from regular players
prior = {}
for et in POS:
    xs = [e for e in boot["elements"] if e["element_type"] == et and e["minutes"] >= 270]
    m = sum(e["minutes"] for e in xs) or 1
    prior[et] = {
        "xg": sum(float(e["expected_goals"]) for e in xs) / m * 90,
        "xa": sum(float(e["expected_assists"]) for e in xs) / m * 90,
        "bonus": sum(e["bonus"] for e in xs) / m * 90,
        "saves": sum(e["saves"] for e in xs) / m * 90,
        "yc": sum(e["yellow_cards"] for e in xs) / m * 90,
    }
    hits = n60 = 0
    for e in xs:
        for g, s in pstats.get(e["id"], {}).items():
            if s["minutes"] >= 60:
                n60 += 1
                hits += dc_hit[e["id"]].get(g, False)
    prior[et]["dc"] = hits / n60 if n60 else 0


def shrink(num, mins, prior90, pseudo):
    return (num + prior90 * pseudo / 90) / (mins + pseudo) * 90


def availability(e, k):
    """Probability factor for being available k gameweeks ahead (k=0 next)."""
    c = e["chance_of_playing_next_round"]
    if e["status"] == "u" or e["removed"]:
        return 0.0
    if c is None:
        c = 100 if e["status"] == "a" else 50
    c /= 100
    if k == 0:
        return c
    if e["status"] == "s":
        return 1.0 if k >= 2 else c
    return min(1.0, c + (1 - c) * min(1, k / 3))


def expected_minutes(pid):
    gws = pstats.get(pid, {})
    recent = [g for g in sorted(gws)[-5:]]
    if not recent:
        return 0, 0, 0
    num = den = st = pl = s60 = 0.0
    for g in recent:
        w = RECENCY ** (cur_gw - g)
        s = gws[g]
        num += w * min(90, s["minutes"])
        den += w
        st += w * (s["starts"] > 0)
        pl += w * (s["minutes"] > 0)
        s60 += w * (s["minutes"] >= 60)
    return num / den, pl / den, s60 / den


players = {}
for pid, e in elements.items():
    et = e["element_type"]
    pos = POS[et]
    xg_n, mins = wavg(pid, "expected_goals")
    xa_n, _ = wavg(pid, "expected_assists")
    bo_n, _ = wavg(pid, "bonus")
    sv_n, _ = wavg(pid, "saves")
    yc_n, _ = wavg(pid, "yellow_cards")
    pr = prior[et]
    xg90 = shrink(xg_n, mins, pr["xg"], 200)
    xa90 = shrink(xa_n, mins, pr["xa"], 200)
    bo90 = shrink(bo_n, mins, pr["bonus"], 200)
    sv90 = shrink(sv_n, mins, pr["saves"], 200)
    yc90 = shrink(yc_n, mins, pr["yc"], 200)
    hits = n60 = 0
    for g, s in pstats.get(pid, {}).items():
        if s["minutes"] >= 60:
            n60 += 1
            hits += dc_hit[pid].get(g, False)
    dcr = (hits + pr["dc"] * 3) / (n60 + 3)
    xmin, pplay, p60 = expected_minutes(pid)
    tid = e["team"]
    t_xg = sum(team_gw_xg[tid].values()) / max(1, len(team_gw_xg[tid])) or LEAGUE
    per_gw, detail = {}, {}
    for k, g in enumerate(proj_gws):
        av = availability(e, k)
        tot = 0.0
        comp = defaultdict(float)
        for (opp, home, mu_f, mu_a, fdr) in upcoming[tid].get(g, []):
            m = xmin * av
            pp, p6 = pplay * av, p60 * av
            atk = mu_f / max(0.3, LEAGUE * rating[tid]["att"])  # fixture multiplier vs team norm
            eg = xg90 * atk * m / 90
            ea = xa90 * atk * m / 90
            comp["mins"] += pp * scoring["short_play"] + p6 * (scoring["long_play"] - scoring["short_play"])
            comp["goals"] += eg * scoring["goals_scored"][pos]
            comp["assists"] += ea * scoring["assists"]
            pcs = math.exp(-mu_a)
            comp["cs"] += pcs * p6 * scoring["clean_sheets"][pos]
            if scoring["goals_conceded"][pos]:
                comp["gc"] += scoring["goals_conceded"][pos] * exp_floor_div(mu_a, 2) * m / 90
            if pos == "GKP":
                sv = sv90 * (mu_a / LEAGUE) ** 0.6 * m / 90
                comp["saves"] += max(0.0, (sv - 1) / 3) * scoring["saves"]
            comp["dc"] += dcr * p6 * scoring["defensive_contribution"][pos]
            comp["bonus"] += bo90 * m / 90 * (atk ** 0.5 if pos in ("MID", "FWD") else (pcs / 0.3) ** 0.3)
            comp["cards"] -= yc90 * m / 90
        tot = sum(comp.values())
        per_gw[g] = round(tot, 2)
        detail[g] = {k2: round(v, 2) for k2, v in comp.items()}
    players[pid] = {
        "id": pid, "name": e["web_name"], "full": f'{e["first_name"]} {e["second_name"]}',
        "team": tid, "pos": pos, "price": e["now_cost"] / 10, "own": float(e["selected_by_percent"]),
        "form": float(e["form"]), "pts": e["total_points"], "mins": e["minutes"],
        "xg": float(e["expected_goals"]), "xa": float(e["expected_assists"]),
        "xgi90": round(xg90 + xa90, 2), "xg90": round(xg90, 2), "xa90": round(xa90, 2),
        "xmin": round(xmin * availability(e, 0)), "status": e["status"], "news": e["news"],
        "chance": e["chance_of_playing_next_round"], "dc_rate": round(dcr, 2),
        "xp": per_gw, "xp_detail": detail.get(next_gw, {}),
        "ep_fpl": float(e["ep_next"] or 0),
        "price_pct": e.get("price_change_percent"),
        "price_proj": [float(x["projected_percent"]) for x in (e.get("price_change_projections") or [])],
        "tin": e["transfers_in_event"], "tout": e["transfers_out_event"],
        "pen": e.get("penalties_order"),
    }
    xp = list(per_gw.values())
    players[pid]["xp1"] = round(sum(xp[:1]), 2)
    players[pid]["xp3"] = round(sum(xp[:3]), 2)
    players[pid]["xp5"] = round(sum(xp[:5]), 2)
    players[pid]["xp6"] = round(sum(xp[:6]), 2)

# ---------------------------------------------------------------- my squad
fh_events = {c["event"] for c in history["chips"] if c["name"] == "freehit"}
squad_ids = [p["element"] for p in picks["picks"]] if picks else []


def purchase_price(pid):
    ins = [t for t in transfers if t["element_in"] == pid and t["event"] not in fh_events]
    if ins:
        return max(ins, key=lambda t: t["time"])["element_in_cost"]
    e = elements[pid]
    return e["now_cost"] - e["cost_change_start"]


def selling_price(pid):
    now, buy = elements[pid]["now_cost"], purchase_price(pid)
    return now if now <= buy else buy + (now - buy) // 2


# free transfers (estimated from history)
chips_by_gw = {c["event"]: c["name"] for c in history["chips"]}
ft = 0
for h in history["current"]:
    g = h["event"]
    if g == 1:
        ft = 1
        continue
    if chips_by_gw.get(g) not in ("wildcard", "freehit"):
        ft = max(0, ft - h["event_transfers"])
    ft = min(5, ft + 1)
if cur_ev and not cur_ev["finished"] and picks_gw == cur_gw:
    pass  # mid-gameweek: value already reflects next-deadline count

bank = (picks["entry_history"]["bank"] if picks else 0)


def best_xi(ids, g):
    ps = sorted(ids, key=lambda i: -players[i]["xp"].get(g, 0))
    by = defaultdict(list)
    for i in ps:
        by[players[i]["pos"]].append(i)
    xi = by["GKP"][:1] + by["DEF"][:3] + by["MID"][:2] + by["FWD"][:1]
    cap = {"DEF": 5, "MID": 5, "FWD": 3}
    rest = [i for i in ps if i not in xi and players[i]["pos"] != "GKP"]
    for i in rest:
        if len(xi) == 11:
            break
        pos = players[i]["pos"]
        if sum(1 for j in xi if players[j]["pos"] == pos) < cap[pos]:
            xi.append(i)
    bench_out = sorted([i for i in ids if i not in xi and players[i]["pos"] != "GKP"],
                       key=lambda i: -players[i]["xp"].get(g, 0))
    bench_gk = [i for i in ids if i not in xi and players[i]["pos"] == "GKP"]
    return xi, bench_gk + bench_out


def squad_value(ids, gws=None, captain=True):
    gws = gws or proj_gws[:EVAL_GWS]
    tot = 0.0
    for k, g in enumerate(gws):
        xi, bench = best_xi(ids, g)
        v = sum(players[i]["xp"].get(g, 0) for i in xi)
        if captain:
            v += max(players[i]["xp"].get(g, 0) for i in xi)
        v += 0.1 * sum(players[i]["xp"].get(g, 0) for i in bench[1:])
        tot += v * DECAY ** k
    return tot


def club_ok(ids):
    c = defaultdict(int)
    for i in ids:
        c[players[i]["team"]] += 1
    return max(c.values()) <= 3


def fixture_str(tid, gws):
    out = []
    for g in gws:
        fx = upcoming[tid].get(g, [])
        if not fx:
            out.append("blank")
        for (opp, home, *_r) in fx:
            out.append(teams[opp]["short_name"] + ("(H)" if home else "(A)"))
    return ", ".join(out)


def reason_out(i):
    p = players[i]
    bits = []
    if p["status"] != "a":
        bits.append(p["news"] or "flagged")
    if p["xmin"] < 55:
        bits.append(f'only ~{p["xmin"]} expected mins')
    bits.append(f'{p["xp5"]:.1f} xP next 5')
    bits.append("fixtures " + fixture_str(p["team"], proj_gws[:3]))
    return "; ".join(bits)


def reason_in(i):
    p = players[i]
    bits = [f'{p["xp5"]:.1f} xP next 5', f'{p["xgi90"]:.2f} xGI/90']
    if p["pos"] in ("DEF", "GKP"):
        bits.append(f'{p["dc_rate"]*100:.0f}% DC rate' if p["pos"] == "DEF" else "")
    bits.append("fixtures " + fixture_str(p["team"], proj_gws[:3]))
    if p["price_proj"] and p["price_proj"][0] >= 100:
        bits.append("price rise imminent")
    return "; ".join(b for b in bits if b)


# candidate pool per position
pool = defaultdict(list)
for i, p in players.items():
    if elements[i]["can_select"] and p["status"] in ("a", "d") and p["xmin"] > 30:
        pool[p["pos"]].append(i)
for k in pool:
    pool[k] = sorted(pool[k], key=lambda i: -players[i]["xp5"])[:60]

plan = []
if squad_ids and proj_gws:
    cur = list(squad_ids)
    cur_bank = bank
    base = squad_value(cur)
    sold = set()
    for step in range(5):
        best = None
        for o in cur:
            if o in [pp["in"] for pp in plan]:
                continue
            sp = selling_price(o) if o in squad_ids else elements[o]["now_cost"]
            budget = cur_bank + sp
            for n in pool[players[o]["pos"]]:
                if n in cur or n in sold or elements[n]["now_cost"] > budget:
                    continue
                cand = [n if x == o else x for x in cur]
                if not club_ok(cand):
                    continue
                if players[n]["xp5"] < players[o]["xp5"] - 1:
                    continue
                v = squad_value(cand)
                if best is None or v > best[0]:
                    best = (v, o, n, budget - elements[n]["now_cost"])
        if not best or best[0] - base < 0.3:
            break
        v, o, n, nb = best
        plan.append({"out": o, "in": n, "gain": round(v - base, 2),
                     "out_sell": selling_price(o) / 10, "in_cost": elements[n]["now_cost"] / 10,
                     "bank_after": nb / 10, "why_out": reason_out(o), "why_in": reason_in(n),
                     "free": step < ft})
        sold.add(o)
        cur = [n if x == o else x for x in cur]
        cur_bank, base = nb, v

    # alternatives for each squad player (best like-for-like replacement)
    alts = {}
    for o in squad_ids:
        budget = bank + selling_price(o)
        opts = []
        for n in pool[players[o]["pos"]]:
            if n in squad_ids or elements[n]["now_cost"] > budget:
                continue
            cand = [n if x == o else x for x in squad_ids]
            if not club_ok(cand):
                continue
            opts.append((players[n]["xp5"], n))
        opts.sort(reverse=True)
        alts[o] = [n for _, n in opts[:3]]
else:
    alts = {}

# lineup, captaincy
lineup = {}
if squad_ids and next_gw:
    g = next_gw
    xi, bench = best_xi(squad_ids, g)
    capts = sorted(xi, key=lambda i: -players[i]["xp"].get(g, 0))
    cur_xi = [p["element"] for p in picks["picks"] if p["position"] <= 11]
    lineup = {
        "xi": xi, "bench": bench, "captain": capts[0], "vice": capts[1],
        "captain_options": [{"id": i, "xp": players[i]["xp"].get(g, 0),
                             "why": f'{fixture_str(players[i]["team"], [g])}; {players[i]["xgi90"]:.2f} xGI/90; '
                                    f'{players[i]["xmin"]} xMins; form {players[i]["form"]}'} for i in capts[:5]],
        "xp_best": round(sum(players[i]["xp"].get(g, 0) for i in xi) + players[capts[0]]["xp"].get(g, 0), 1),
        "xp_current": round(sum(players[i]["xp"].get(g, 0) for i in cur_xi) +
                            max(players[i]["xp"].get(g, 0) for i in cur_xi), 1),
        "current_xi": cur_xi,
    }

# ---------------------------------------------------------------- chips
used = [(c["name"], c["event"]) for c in history["chips"]]
chip_names = {"wildcard": "Wildcard", "freehit": "Free Hit", "bboost": "Bench Boost", "3xc": "Triple Captain"}
chips = []
for c in boot["chips"]:
    u = next((ev for (n, ev) in used if n == c["name"] and c["start_event"] <= ev <= c["stop_event"]), None)
    chips.append({"name": chip_names.get(c["name"], c["name"]), "key": c["name"], "from": c["start_event"],
                  "to": c["stop_event"], "used": u,
                  "available": u is None and (next_gw or 39) <= c["stop_event"]})
gw_info = []
for g in proj_gws:
    counts = defaultdict(int)
    for f in fixtures:
        if f["event"] == g:
            counts[f["team_h"]] += 1
            counts[f["team_a"]] += 1
    blanks = [teams[t]["short_name"] for t in teams if counts[t] == 0]
    doubles = [teams[t]["short_name"] for t in teams if counts[t] > 1]
    row = {"gw": g, "blanks": blanks, "doubles": doubles}
    if squad_ids:
        xi, bench = best_xi(squad_ids, g)
        row["bench_xp"] = round(sum(players[i]["xp"].get(g, 0) for i in bench), 1)
        top = max(squad_ids, key=lambda i: players[i]["xp"].get(g, 0))
        row["tc_player"] = top
        row["tc_xp"] = players[top]["xp"].get(g, 0)
        row["squad_playing"] = sum(1 for i in squad_ids if upcoming[players[i]["team"]].get(g))
    gw_info.append(row)
all_gw = []
for g in range(1, 39):
    counts = defaultdict(int)
    for f in fixtures:
        if f["event"] == g:
            counts[f["team_h"]] += 1
            counts[f["team_a"]] += 1
    all_gw.append({"gw": g, "blanks": [teams[t]["short_name"] for t in teams if counts[t] == 0],
                   "doubles": [teams[t]["short_name"] for t in teams if counts[t] > 1]})

# ---------------------------------------------------------------- live / last gameweek
live_gw = None
if picks and picks_gw in live:
    lv = {x["id"]: x["stats"] for x in live[picks_gw]["elements"]}
    rows = []
    for p in picks["picks"]:
        s = lv.get(p["element"], {})
        rows.append({"id": p["element"], "pos": p["position"], "mult": p["multiplier"],
                     "cap": p["is_captain"], "vice": p["is_vice_captain"],
                     "pts": s.get("total_points", 0), "mins": s.get("minutes", 0),
                     "bps": s.get("bps", 0), "bonus": s.get("bonus", 0)})
    ev = next(e for e in events if e["id"] == picks_gw)
    live_gw = {"gw": picks_gw, "finished": ev["finished"], "data_checked": ev.get("data_checked"),
               "average": ev.get("average_entry_score"), "highest": ev.get("highest_score"),
               "rows": rows, "points": picks["entry_history"]["points"],
               "chip": picks["active_chip"], "bench_pts": picks["entry_history"]["points_on_bench"]}

# ---------------------------------------------------------------- output
team_out = {}
for tid, t in teams.items():
    team_out[tid] = {"id": tid, "short": t["short_name"], "name": t["name"],
                     "att": round(rating[tid]["att"], 2), "def": round(rating[tid]["def"], 2),
                     "fx": {g: [{"opp": o, "home": h, "xgf": round(mf, 2), "xga": round(ma, 2), "fdr": fd}
                                for (o, h, mf, ma, fd) in upcoming[tid].get(g, [])] for g in proj_gws}}

keep = {i for i in players if players[i]["mins"] > 0 or players[i]["xp5"] > 3 or i in squad_ids}
out = {
    "meta": {
        "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "team_id": TEAM_ID, "cur_gw": cur_gw, "next_gw": next_gw,
        "cur_finished": bool(cur_ev and cur_ev["finished"]),
        "deadline": next_ev["deadline_time"] if next_ev else None,
        "proj_gws": proj_gws, "league_goals": round(LEAGUE, 2),
        "price_deadlines": boot["game_config"]["settings"].get("price_change_deadlines", []),
        "picks_gw": picks_gw,
    },
    "manager": {
        "name": f'{entry["player_first_name"]} {entry["player_last_name"]}', "team": entry["name"],
        "points": entry["summary_overall_points"], "rank": entry["summary_overall_rank"],
        "gw_points": entry.get("summary_event_points"), "gw_rank": entry.get("summary_event_rank"),
        "bank": bank / 10, "value": (picks["entry_history"]["value"] if picks else 0) / 10,
        "free_transfers": ft, "total_players": boot["total_players"],
    },
    "history": [{"gw": h["event"], "pts": h["points"], "rank": h["overall_rank"], "gw_rank": h["rank"],
                 "bench": h["points_on_bench"], "tx": h["event_transfers"], "hit": h["event_transfers_cost"],
                 "chip": chips_by_gw.get(h["event"])} for h in history["current"]],
    "squad": [{"id": p["element"], "slot": p["position"], "cap": p["is_captain"], "vice": p["is_vice_captain"],
               "buy": purchase_price(p["element"]) / 10, "sell": selling_price(p["element"]) / 10,
               "alts": alts.get(p["element"], [])} for p in (picks["picks"] if picks else [])],
    "lineup": lineup,
    "transfers": plan,
    "chips": chips, "gw_info": gw_info, "season_gws": all_gw,
    "live": live_gw,
    "teams": team_out,
    "players": [players[i] for i in sorted(keep, key=lambda i: -players[i]["xp5"])],
}
with open(OUT, "w") as f:
    json.dump(out, f, separators=(",", ":"))
print(f"wrote {OUT}: {len(out['players'])} players, next GW {next_gw}, FT {ft}, plan {len(plan)} moves")
