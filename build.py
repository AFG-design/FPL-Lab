#!/usr/bin/env python3
"""FPL Lab data builder.

Fetches the public FPL API, projects every player with fplmodel, plans transfers
with optimise, measures the model against past gameweeks and writes data.json.

Usage:  python3 build.py [TEAM_ID] [OUT_PATH]
"""
import json, os, sys, time, urllib.request, datetime as dt
from collections import defaultdict

from fplmodel import prepare, project, POS
from backtest import evaluate, baseline
import optimise

TEAM_ID = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("FPL_TEAM_ID", 8122679))
OUT = sys.argv[2] if len(sys.argv) > 2 else "data.json"
API = "https://fantasy.premierleague.com/api"
HORIZON = 6
PLAN_GWS = 5
HERE = os.path.dirname(os.path.abspath(__file__))


def get(path, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(API + path, headers={"User-Agent": "Mozilla/5.0 fpl-lab"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(3 * (i + 1))


t0 = time.time()
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
live = {g: get(f"/event/{g}/live/") for g in range(1, cur_gw + 1)}
picks_gw = entry.get("current_event") or cur_gw
picks = get(f"/entry/{TEAM_ID}/event/{picks_gw}/picks/") if picks_gw else None
try:
    priors = json.load(open(os.path.join(HERE, "priors.json")))
except Exception:
    priors = None

ctx = prepare(boot, fixtures, live, priors)

# European midweek congestion: small rotation risk for league games within ~3 days of a European match
congestion, euro_flags = {}, {}
try:
    europe = json.load(open(os.path.join(HERE, "europe.json")))["competitions"]
    short_to_id = {t["short_name"]: t["id"] for t in boot["teams"]}
    for comp, c in europe.items():
        edates = [dt.date.fromisoformat(x) for x in c["dates"]]
        for short in c["teams"]:
            tid = short_to_id.get(short)
            for f in fixtures:
                if not tid or not f["event"] or f["finished"] or not f["kickoff_time"] or tid not in (f["team_h"], f["team_a"]):
                    continue
                kd = dt.date.fromisoformat(f["kickoff_time"][:10])
                near = [d for d in edates if -2 <= (kd - d).days <= 3 and (kd - d).days != 0]
                if near:
                    congestion[(tid, f["event"])] = 0.93
                    euro_flags[(tid, f["event"])] = f"{comp} {near[0].strftime('%a %d %b')}"
except Exception as ex:
    print("europe.json not used:", ex)
ctx["congestion"] = congestion
elements, teams = ctx["elements"], ctx["teams"]
res = project(ctx, next_gw, HORIZON) if next_gw else None
proj = res["players"] if res else {}
proj_gws = res["gws"] if res else []
upcoming = res["upcoming"] if res else {}
rating = res["rating"] if res else {}
finished_gws = [e["id"] for e in events if e["finished"]]

# ---------------------------------------------------------------- my squad, prices, free transfers
fh_events = {c["event"] for c in history["chips"] if c["name"] == "freehit"}
squad_ids = [p["element"] for p in picks["picks"]] if picks else []


def purchase_price(pid):
    ins = [t for t in transfers if t["element_in"] == pid and t["event"] not in fh_events]
    if ins:
        return max(ins, key=lambda t: t["time"])["element_in_cost"]
    e = elements[pid]
    return e["now_cost"] - e["cost_change_start"]


def selling_price(pid):
    now, b = elements[pid]["now_cost"], purchase_price(pid)
    return now if now <= b else b + (now - b) // 2


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
if cur_ev and not cur_ev["finished"]:
    pass
bank = (picks["entry_history"]["bank"] if picks else 0) / 10

# ---------------------------------------------------------------- per-player stats for the page
pstats = ctx["pstats"]


def series(pid, key, cast=float):
    return [round(cast(pstats[pid][g][key]), 2) if g in pstats.get(pid, {}) else 0 for g in range(1, cur_gw + 1)]


def rolling(pid, n):
    gws = [g for g in range(max(1, cur_gw - n + 1), cur_gw + 1)]
    s = pstats.get(pid, {})
    mins = sum(s[g]["minutes"] for g in gws if g in s)
    xgi = sum(float(s[g]["expected_goal_involvements"]) for g in gws if g in s)
    pts = sum(s[g]["total_points"] for g in gws if g in s)
    return mins, (xgi / mins * 90 if mins >= 90 else 0.0), pts


def nailed(pid, e, r):
    """0-100: how sure a player is to start and play most of the game."""
    from fplmodel import availability
    return int(round(100 * r["p_start"] * min(1.0, r["m_start"] / 85) * availability(e, 0)))


def minutes_flag(pid, e):
    """Spot players losing (or winning back) their place from the last 6 gameweeks."""
    s = pstats.get(pid, {})
    recent = [g for g in range(max(1, cur_gw - 5), cur_gw + 1)]
    starts = [bool(s.get(g, {}).get("starts")) for g in recent]
    mins = [s.get(g, {}).get("minutes", 0) for g in recent]
    if len(starts) >= 4 and sum(starts[:-2]) >= 3 and not any(starts[-2:]):
        return "Dropped? No start in the last 2 GWs" if e["status"] == "a" else None
    if len(starts) >= 4 and sum(starts[:-2]) <= 1 and all(starts[-2:]):
        return "Breaking in: started the last 2 GWs"
    if len(mins) >= 3 and starts[-1] and mins[-1] < 60 and mins[-2] < 60 and starts[-2]:
        return "Subbed early in the last 2 GWs"
    return None


# ---- bonus point form: per match, who finished in the top 3 of the bonus point system (BPS)
bps_top = defaultdict(dict)   # pid -> gw -> rank within his match (1 = highest BPS)
for g, data in live.items():
    by_fx = defaultdict(list)
    for x in data["elements"]:
        if x["stats"]["minutes"] <= 0:
            continue
        for ex in x["explain"]:
            by_fx[ex["fixture"]].append((x["stats"]["bps"], x["id"]))
    for fx, rows in by_fx.items():
        rows.sort(reverse=True)
        for rank, (bps, pid) in enumerate(rows, 1):
            bps_top[pid][g] = min(rank, bps_top[pid].get(g, 99))


def bonus_form(pid, n):
    gws = [g for g in range(max(1, cur_gw - n + 1), cur_gw + 1)]
    s = pstats.get(pid, {})
    mins = sum(s[g]["minutes"] for g in gws if g in s)
    bps = sum(s[g]["bps"] for g in gws if g in s)
    bonus = sum(s[g]["bonus"] for g in gws if g in s)
    played = [g for g in gws if s.get(g, {}).get("minutes", 0) > 0]
    top3 = sum(1 for g in played if bps_top[pid].get(g, 99) <= 3)
    return {"bps90": round(bps / mins * 90, 1) if mins >= 90 else 0.0, "bonus": bonus, "top3": top3, "apps": len(played)}


try:
    US = json.load(open(os.path.join(HERE, "understat", "fpl_players.json")))
except Exception:
    US = {"meta": {}, "players": {}}


def shot_stats(pid, mins4):
    u = US["players"].get(str(pid))
    if not u or u["mins"] < 1:
        return None
    m = u["mins"]
    p90 = lambda v, mm: round(v / mm * 90, 2) if mm >= 90 else 0.0
    return {"shots90": p90(u["shots"], m), "sib90": p90(u["sib"], m), "bc90": p90(u["bc"], m), "cc90": p90(u["cc"], m),
            "bcc90": p90(u["bcc"], m), "npxg90": p90(u["npxg"], m), "chain90": p90(u["xgchain"], m),
            "shots": u["shots"], "sib": u["sib"], "bc": u["bc"], "bc_scored": u["bc_scored"], "cc": u["cc"], "bcc": u["bcc"],
            "shots_4": u["shots_4"], "sib_4": u["sib_4"], "bc_4": u["bc_4"], "cc_4": u["cc_4"], "bcc_4": u["bcc_4"],
            "sib90_4": p90(u["sib_4"], mins4), "bc90_4": p90(u["bc_4"], mins4),
            "op_xg90": p90(u.get("op_xg", 0), m), "sp_xg90": p90(u.get("sp_xg", 0), m), "sp_xg": u.get("sp_xg", 0),
            "pen_xg": u.get("pen_xg", 0), "pen_shots": u.get("pen_shots", 0), "sp_shots": u.get("sp_shots", 0),
            "headers": u.get("headers", 0), "sp_headers": u.get("sp_headers", 0), "head_xg": u.get("head_xg", 0)}


def dc_record(pid, n=None):
    """Defensive contribution: games reaching the threshold, out of 60+ minute games."""
    gws = range(1, cur_gw + 1) if n is None else range(max(1, cur_gw - n + 1), cur_gw + 1)
    s = pstats.get(pid, {})
    apps = [g for g in gws if s.get(g, {}).get("minutes", 0) >= 60]
    hits = sum(1 for g in apps if ctx["dc_hit"][pid].get(g))
    cbit = sum(s[g]["defensive_contribution"] for g in gws if g in s)
    mins = sum(s[g]["minutes"] for g in gws if g in s)
    return {"hits": hits, "apps": len(apps), "per90": round(cbit / mins * 90, 1) if mins >= 90 else 0.0}


players = {}
for pid, e in elements.items():
    r = proj.get(pid)
    if not r:
        continue
    pos = POS[e["element_type"]]
    xp = {g: round(v, 2) for g, v in r["xp"].items()}
    vals = list(xp.values())
    m4, xgi4, pts4 = rolling(pid, 4)
    m6, xgi6, pts6 = rolling(pid, 6)
    pr = (priors or {}).get("players", {}).get(str(pid))
    det = r["detail"].get(next_gw, {})
    slope = 0.86
    players[pid] = {
        "id": pid, "name": e["web_name"], "full": f'{e["first_name"]} {e["second_name"]}',
        "team": e["team"], "pos": pos, "price": e["now_cost"] / 10, "own": float(e["selected_by_percent"]),
        "form": float(e["form"]), "pts": e["total_points"], "mins": e["minutes"],
        "goals": e["goals_scored"], "assists": e["assists"], "cs": e["clean_sheets"], "bonus": e["bonus"],
        "xg": float(e["expected_goals"]), "xa": float(e["expected_assists"]),
        "g_xg": round(e["goals_scored"] - float(e["expected_goals"]), 2),
        "a_xa": round(e["assists"] - float(e["expected_assists"]), 2),
        "xgi90": round(r["xg90"] + r["xa90"], 2), "xg90": round(r["xg90"], 2), "xa90": round(r["xa90"], 2),
        "xgi90_4": round(xgi4, 2), "xgi90_6": round(xgi6, 2), "pts4": pts4, "pts6": pts6, "mins4": m4,
        "dc90": round(r["dc90"], 1), "dc_rate": round(r["p_dc"], 2), "p_start": round(r["p_start"], 2),
        "xmin": round(r["xmin"]), "status": e["status"], "news": e["news"], "chance": e["chance_of_playing_next_round"],
        "xp": xp, "xp1": round(sum(vals[:1]), 2), "xp3": round(sum(vals[:3]), 2),
        "xp5": round(sum(vals[:5]), 2), "xp6": round(sum(vals[:6]), 2),
        "xp_detail": {k: round(v * slope, 2) for k, v in det.items()},
        "price_proj": [float(x["projected_percent"]) for x in (e.get("price_change_projections") or [])],
        "tin": e["transfers_in_event"], "tout": e["transfers_out_event"],
        "pen": e.get("penalties_order"), "ep_fpl": float(e["ep_next"] or 0),
        "last": {"season": pr["season"], "pts": pr["last_pts"], "mins": pr["last_mins"], "xgi": pr["last_xgi"]} if pr else None,
        "s_pts": series(pid, "total_points", int), "s_min": series(pid, "minutes", int),
        "s_xgi": series(pid, "expected_goal_involvements"),
        "ok": bool(e["can_select"]) and e["status"] in ("a", "d") and r["xmin"] > 10,
        "code": e["code"], "tcode": e["team_code"], "tmp": bool(e.get("has_temporary_code")),
        "bf4": bonus_form(pid, 4), "bf6": bonus_form(pid, 6), "bps_season": e["bps"],
        "us": shot_stats(pid, m4), "dcs": dc_record(pid), "dc6": dc_record(pid, 6),
        "s_bps": series(pid, "bps", int),
        "nailed": nailed(pid, e, r), "mflag": minutes_flag(pid, e),
        "sp": {"pen": e.get("penalties_order"), "cor": e.get("corners_and_indirect_freekicks_order"),
               "fk": e.get("direct_freekicks_order")},
    }

# ---------------------------------------------------------------- optimiser plans
plans = {}
sell = {i: selling_price(i) / 10 for i in squad_ids}
if squad_ids and proj_gws:
    opt_players = {i: {"pos": p["pos"], "team": p["team"], "price": p["price"], "xp": p["xp"], "ok": p["ok"]}
                   for i, p in players.items()}
    gws = proj_gws[:PLAN_GWS]
    options = [("best", None), ("roll", 0), ("one", 1), ("two", 2)]
    if ft >= 3:
        options.append(("three", 3))
    # rank-aware modes use the effective ownership of the managers around your rank
    eo_field = {}
    try:
        cr = json.load(open(os.path.join(HERE, "crowd", "latest.json")))
        src = cr["near"] if cr["near"]["n"] >= 100 else cr["top10k"]
        eo_field = {int(k): v / 100 for k, v in src["eo"].items()}
    except Exception:
        pass
    MODES = {"balanced": 0.0, "safe": 0.02, "chase": -0.03} if eo_field else {"balanced": 0.0}
    for mode, lam in MODES.items():
        for key, n in options:
            r = optimise.solve(opt_players, squad_ids, sell, bank, min(ft, 5), gws, week1_moves=n,
                               eo=eo_field or None, lam=lam)
            if r:
                for wk in r["weeks"]:
                    mult = {i: 1 for i in wk["xi"]}
                    mult[wk["captain"]] = 2
                    wk["spread"] = round(optimise.spread(opt_players, mult, eo_field, wk["gw"]), 1) if eo_field else None
                plans[key if mode == "balanced" else f"{mode}_{key}"] = r
    for k, pl in plans.items():
        rk = "roll" if "_" not in k else k.split("_")[0] + "_roll"
        if rk in plans:
            pl["vs_roll"] = round(pl["xp_total"] + 1.5 * pl["ft_left"] - plans[rk]["xp_total"] - 1.5 * plans[rk]["ft_left"], 2)

# lineup for the current squad (no transfers)
lineup = {}
if "roll" in plans:
    w0 = plans["roll"]["weeks"][0]
    cur_xi = [p["element"] for p in picks["picks"] if p["position"] <= 11]
    g = next_gw
    lineup = {
        "xi": w0["xi"], "bench": w0["bench"], "captain": w0["captain"], "vice": w0["vice"],
        "xp_best": w0["xp"], "current_xi": cur_xi,
        "xp_current": round(sum(players[i]["xp"].get(g, 0) for i in cur_xi) + max(players[i]["xp"].get(g, 0) for i in cur_xi), 2),
        "captain_options": [{"id": i, "xp": players[i]["xp"].get(g, 0)} for i in
                            sorted(squad_ids, key=lambda i: -players[i]["xp"].get(g, 0))[:6]],
    }

# ---------------------------------------------------------------- model accuracy (backtest)
accuracy = None
if len(finished_gws) >= 4:
    test = [g for g in finished_gws if g >= 3]
    ev = evaluate(ctx, test)
    bl = baseline(ctx, test)
    accuracy = {"gws": test, "n": ev["n"], "corr": round(ev["corr"], 3), "rmse": round(ev["rmse"], 2),
                "mae": round(ev["mae"], 2), "base_corr": round(bl["corr"], 3), "base_rmse": round(bl["rmse"], 2),
                "buckets": [[b, c, round(px, 2), round(pa, 2)] for b, (c, px, pa) in ev["buckets"].items()],
                "top30": [[k, round(x, 2), round(a, 2)] for k, a, x in ev["top30"]]}

# ---------------------------------------------------------------- chips, gameweeks
used = [(c["name"], c["event"]) for c in history["chips"]]
chip_names = {"wildcard": "Wildcard", "freehit": "Free Hit", "bboost": "Bench Boost", "3xc": "Triple Captain"}
chips = []
for c in boot["chips"]:
    u = next((ev for (n, ev) in used if n == c["name"] and c["start_event"] <= ev <= c["stop_event"]), None)
    chips.append({"name": chip_names.get(c["name"], c["name"]), "key": c["name"], "from": c["start_event"],
                  "to": c["stop_event"], "used": u, "available": u is None and (next_gw or 39) <= c["stop_event"]})


def gw_counts(g):
    counts = defaultdict(int)
    for f in fixtures:
        if f["event"] == g:
            counts[f["team_h"]] += 1
            counts[f["team_a"]] += 1
    return counts


season_gws = []
for g in range(1, 39):
    c = gw_counts(g)
    season_gws.append({"gw": g, "blanks": [teams[t]["short_name"] for t in teams if c[t] == 0],
                       "doubles": [teams[t]["short_name"] for t in teams if c[t] > 1]})
gw_info = []
if "roll" in plans:
    for wk in plans["roll"]["weeks"]:
        g = wk["gw"]
        gw_info.append({"gw": g, "bench_xp": round(sum(players[i]["xp"].get(g, 0) for i in wk["bench"]), 1),
                        "tc_player": wk["captain"], "tc_xp": players[wk["captain"]]["xp"].get(g, 0),
                        "squad_playing": sum(1 for i in squad_ids if upcoming[players[i]["team"]].get(g))})

# ---------------------------------------------------------------- live / last gameweek
live_gw = None
if picks and picks_gw in live:
    lv = {x["id"]: x["stats"] for x in live[picks_gw]["elements"]}
    ev = next(e for e in events if e["id"] == picks_gw)
    live_gw = {"gw": picks_gw, "finished": ev["finished"], "average": ev.get("average_entry_score"),
               "highest": ev.get("highest_score"), "points": picks["entry_history"]["points"],
               "chip": picks["active_chip"], "bench_pts": picks["entry_history"]["points_on_bench"],
               "rows": [{"id": p["element"], "pos": p["position"], "mult": p["multiplier"], "cap": p["is_captain"],
                         "vice": p["is_vice_captain"], "pts": lv.get(p["element"], {}).get("total_points", 0),
                         "mins": lv.get(p["element"], {}).get("minutes", 0), "bps": lv.get(p["element"], {}).get("bps", 0),
                         "bonus": lv.get(p["element"], {}).get("bonus", 0)} for p in picks["picks"]]}

# ---------------------------------------------------------------- the field and mini-leagues
crowd_out = None
try:
    crowd = json.load(open(os.path.join(HERE, "crowd", "latest.json")))
except Exception:
    crowd = None
if crowd:
    G = crowd["gw"]
    lv = {x["id"]: x["stats"]["total_points"] for x in live[G]["elements"]} if G in live else {}
    g_ev = next(e for e in events if e["id"] == G)
    in_play = not g_ev["finished"]

    def team_live(p, hits=0):
        return sum(lv.get(el, 0) * m for el, m in p) - hits

    leagues_out = []
    for lg in crowd["leagues"]:
        # fresh standings each run (cheap), rival picks from the per-gameweek cache
        fresh = {}
        try:
            d = get(f"/leagues-classic/{lg['id']}/standings/")
            for r in d["standings"]["results"]:
                fresh[r["entry"]] = r
            me_rank = next((r for r in d["standings"]["results"] if r["entry"] == TEAM_ID), None)
        except Exception:
            me_rank = None
        rows = []
        for mbr in lg["members"]:
            e_id = mbr["entry"]
            f = fresh.get(e_id, {})
            pk = crowd["rivals"].get(str(e_id)) if e_id != TEAM_ID else (
                {"p": [[x["element"], x["multiplier"]] for x in picks["picks"]], "chip": picks["active_chip"],
                 "hits": picks["entry_history"]["event_transfers_cost"]} if picks and picks_gw == G else None)
            used = history["chips"] if e_id == TEAM_ID else crowd.get("rival_chips", {}).get(str(e_id))
            rows.append({"chips": [{"name": c["name"], "event": c["event"]} for c in used] if used is not None else None,
                         "entry": e_id, "player": mbr["player"], "team": mbr["team"], "me": e_id == TEAM_ID,
                         "rank": f.get("rank"), "last_rank": f.get("last_rank"), "total": f.get("total"),
                         "gw_pts": f.get("event_total"), "picks": pk["p"] if pk else None,
                         "chip": pk["chip"] if pk else None, "hits": pk["hits"] if pk else 0,
                         "live": team_live(pk["p"], pk["hits"]) if pk and lv else None})
        rows.sort(key=lambda r: (r["rank"] or 1e9))
        leagues_out.append({"id": lg["id"], "name": lg["name"], "size": lg["size"],
                            "my_rank": (me_rank or {}).get("rank", lg["my_rank"]), "rows": rows})
    keep_ids = {str(i) for i in players}
    slim = lambda d: {k: v for k, v in d.items() if k in keep_ids}
    crowd_out = {"gw": G, "built": crowd["built"], "in_play": in_play,
                 "top10k": {k: (slim(v) if isinstance(v, dict) and k in ("own", "cap", "eo") else v) for k, v in crowd["top10k"].items()},
                 "near": {k: (slim(v) if isinstance(v, dict) and k in ("own", "cap", "eo") else v) for k, v in crowd["near"].items()},
                 "leagues": leagues_out}

# ---------------------------------------------------------------- weekly review
def pts_of(pid, g):
    return ctx["pts_gw"].get(pid, {}).get(g, 0)


def mins_of(pid, g):
    return pstats.get(pid, {}).get(g, {}).get("minutes", 0)


def hindsight(ids, g):
    """Best XI and captain from a 15-man squad, using real points."""
    ps = sorted(ids, key=lambda i: -pts_of(i, g))
    by = defaultdict(list)
    for i in ps:
        by[POS[elements[i]["element_type"]]].append(i)
    xi = by["GKP"][:1] + by["DEF"][:3] + by["MID"][:2] + by["FWD"][:1]
    lim = {"DEF": 5, "MID": 5, "FWD": 3}
    for i in ps:
        if len(xi) == 11:
            break
        pos = POS[elements[i]["element_type"]]
        if i not in xi and pos != "GKP" and sum(1 for j in xi if POS[elements[j]["element_type"]] == pos) < lim[pos]:
            xi.append(i)
    return xi, max(xi, key=lambda i: pts_of(i, g))


review = {"weeks": [], "transfers": [], "totals": {}}
fh_set = {c["event"] for c in history["chips"] if c["name"] == "freehit"}
wc_set = {c["event"] for c in history["chips"] if c["name"] == "wildcard"}
hist_by = {h["event"]: h for h in history["current"]}
try:
    past = {g: (picks if g == picks_gw else get(f"/entry/{TEAM_ID}/event/{g}/picks/")) for g in finished_gws if g in hist_by}
except Exception:
    past = {}
for g, pk in sorted(past.items()):
    if not pk:
        continue
    ids = [p["element"] for p in pk["picks"]]
    chip = pk.get("active_chip")
    cap = next(p for p in pk["picks"] if p["is_captain"])
    vice = next((p for p in pk["picks"] if p["is_vice_captain"]), cap)
    cmult = 3 if chip == "3xc" else 2
    eff_cap = cap["element"] if mins_of(cap["element"], g) > 0 else vice["element"]
    xi_ids = [p["element"] for p in pk["picks"] if p["position"] <= 11] if chip != "bboost" else ids
    best_xi, best_cap = hindsight(ids, g)
    best_cap_in_xi = max(xi_ids, key=lambda i: pts_of(i, g))
    cap_lost = (pts_of(best_cap_in_xi, g) - pts_of(eff_cap, g)) * (cmult - 1)
    h = hist_by[g]
    best_total = (sum(pts_of(i, g) for i in ids) if chip == "bboost" else sum(pts_of(i, g) for i in best_xi)) + pts_of(best_cap, g) * (cmult - 1)
    tx = [t for t in transfers if t["event"] == g]
    moves = []
    if g not in fh_set and g not in wc_set:
        for t in tx:
            moves.append({"in": t["element_in"], "out": t["element_out"], "in_pts": pts_of(t["element_in"], g),
                          "out_pts": pts_of(t["element_out"], g)})
    # how the model saw this gameweek beforehand (projection from data before it)
    try:
        if g < 3:
            raise ValueError("too early in the season to judge the model")
        pr = project(ctx, g, 1, {"use_flags": False})["players"]
        xi_proj = sum(pr[i]["xp"].get(g, 0) for i in xi_ids if i in pr)
        model_cap = max(xi_ids, key=lambda i: pr.get(i, {}).get("xp", {}).get(g, 0))
    except Exception:
        xi_proj, model_cap = None, None
    ev = next(e for e in events if e["id"] == g)
    review["weeks"].append({
        "gw": g, "pts": h["points"], "hits": h["event_transfers_cost"], "chip": chip, "rank": h["overall_rank"],
        "avg": ev.get("average_entry_score"), "highest": ev.get("highest_score"),
        "captain": eff_cap, "cap_pts": pts_of(eff_cap, g) * cmult, "best_cap": best_cap_in_xi,
        "best_cap_pts": pts_of(best_cap_in_xi, g) * cmult, "cap_lost": cap_lost, "model_cap": model_cap,
        "bench_pts": h["points_on_bench"], "best_possible": best_total, "left": max(0, best_total - h["points"]),
        "moves": moves, "wildcard": g in wc_set, "freehit": g in fh_set, "n_tx": len(tx),
        "xi_proj": round(xi_proj, 1) if xi_proj is not None else None,
        "xi_actual": sum(pts_of(i, g) for i in xi_ids),
    })
# season ledger: every transfer, judged on points while the new player stayed in the team
ledger = []
real_tx = sorted([t for t in transfers if t["event"] not in fh_set], key=lambda t: t["time"])
for k, t in enumerate(real_tx):
    sold = next((u["event"] for u in real_tx[k + 1:] if u["element_out"] == t["element_in"]), cur_gw + 1)
    window = [g for g in range(t["event"], min(sold, cur_gw + 1)) if g in finished_gws or g == cur_gw]
    gain = sum(pts_of(t["element_in"], g) - pts_of(t["element_out"], g) for g in window)
    ledger.append({"gw": t["event"], "in": t["element_in"], "out": t["element_out"], "gws": len(window), "gain": gain,
                   "wildcard": t["event"] in wc_set})
review["transfers"] = ledger
review["totals"] = {
    "cap_lost": sum(w["cap_lost"] for w in review["weeks"]),
    "bench": sum(w["bench_pts"] for w in review["weeks"] if w["chip"] != "bboost"),
    "hits": sum(w["hits"] for w in review["weeks"]),
    "tx_gain": sum(x["gain"] for x in ledger if not x["wildcard"]),
    "wc_gain": sum(x["gain"] for x in ledger if x["wildcard"]),
    "left": sum(w["left"] for w in review["weeks"]),
}
for x in [t["element_in"] for t in transfers] + [t["element_out"] for t in transfers] + \
        [w[k] for w in review["weeks"] for k in ("captain", "best_cap", "model_cap") if w.get(k)]:
    pass  # players referenced in the review are kept below

# ---------------------------------------------------------------- set pieces (with change history)
sp_now = {}
for tid in teams:
    row = {}
    for key, field in (("pen", "penalties_order"), ("cor", "corners_and_indirect_freekicks_order"), ("fk", "direct_freekicks_order")):
        takers = sorted([e for e in elements.values() if e["team"] == tid and e.get(field)], key=lambda e: e[field])
        row[key] = [e["id"] for e in takers[:3]]
    sp_now[str(tid)] = row
sp_changes = []
try:
    prev_url = os.environ.get("PAGES_DATA_URL", "https://afg-design.github.io/FPL-Lab/data.json")
    with urllib.request.urlopen(urllib.request.Request(prev_url, headers={"User-Agent": "fpl-lab"}), timeout=15) as r:
        prev = json.load(r)
    prev_sp = (prev.get("setpieces") or {})
    sp_changes = prev_sp.get("changes", [])
    for tid, row in sp_now.items():
        old = (prev_sp.get("now") or {}).get(tid)
        if not old:
            continue
        for key in row:
            a, b2 = (old.get(key) or [None])[0], (row[key] or [None])[0]
            if a != b2:
                sp_changes.insert(0, {"date": dt.date.today().isoformat(), "team": int(tid), "type": key, "old": a, "new": b2})
except Exception as ex:
    print("no previous deploy to compare set pieces:", type(ex).__name__)
setpieces = {"now": sp_now, "changes": sp_changes[:30]}

# ---------------------------------------------------------------- teams: fixtures and trends
team_out = {}
for tid, t in teams.items():
    trend = []
    for g in range(1, cur_gw + 1):
        for (gg, opp, home, f) in ctx["team_fix"][tid]:
            if gg == g and f["team_h_score"] is not None:
                trend.append({"gw": g, "opp": opp, "home": home,
                              "xgf": round(ctx["team_gw_xg"][tid][g], 2), "xga": round(ctx["team_gw_xg"][opp][g], 2),
                              "gf": f["team_h_score"] if home else f["team_a_score"],
                              "ga": f["team_a_score"] if home else f["team_h_score"]})
    usT = US.get("teams", {}).get(str(tid))
    team_out[tid] = {"id": tid, "short": t["short_name"], "name": t["name"],
                     "sp": ({"for": round(usT.get("sp_for", 0) / max(1, usT["games"]), 2), "against": round(usT.get("sp_against", 0) / max(1, usT["games"]), 2),
                             "op_for": round(usT.get("op_for", 0) / max(1, usT["games"]), 2), "op_against": round(usT.get("op_against", 0) / max(1, usT["games"]), 2),
                             "games": int(usT["games"])} if usT else None),
                     "att": round(rating[tid]["att"], 2), "def": round(rating[tid]["def"], 2), "trend": trend,
                     "fx": {g: [{"opp": o, "home": h, "xgf": round(mf, 2), "xga": round(ma, 2), "fdr": fd, "eu": euro_flags.get((tid, g))}
                                for (o, h, mf, ma, fd) in upcoming[tid].get(g, [])] for g in proj_gws}}

keep = {i for i, p in players.items() if p["mins"] > 0 or p["xp5"] > 3 or i in squad_ids}
keep |= {t["element_in"] for t in transfers} | {t["element_out"] for t in transfers}
keep |= {w[k] for w in review["weeks"] for k in ("captain", "best_cap", "model_cap") if w.get(k)}
keep |= {i for row in sp_now.values() for v in row.values() for i in v}
keep |= {c[k] for c in sp_changes for k in ("old", "new") if c.get(k)}
keep = {i for i in keep if i in players}
for i in set().union(*[set(w["in"]) | set(w["xi"]) | set(w["bench"]) for pl in plans.values() for w in pl["weeks"]]) if plans else set():
    keep.add(i)

out = {
    "meta": {"built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "team_id": TEAM_ID,
             "understat": US.get("meta"),
             "special_shirts": bool(boot["game_config"]["rules"].get("ui_use_special_shirts")),
             "special_excl": boot["game_config"]["rules"].get("ui_special_shirt_exclusions", []),
             "cur_gw": cur_gw, "next_gw": next_gw, "cur_finished": bool(cur_ev and cur_ev["finished"]),
             "deadline": next_ev["deadline_time"] if next_ev else None, "proj_gws": proj_gws, "plan_gws": proj_gws[:PLAN_GWS],
             "league_goals": round(res["league"], 2) if res else None, "picks_gw": picks_gw,
             "price_deadlines": boot["game_config"]["settings"].get("price_change_deadlines", []),
             "priors_season": next(iter((priors or {}).get("players", {}).values()), {}).get("season"),
             "build_secs": None},
    "manager": {"name": f'{entry["player_first_name"]} {entry["player_last_name"]}', "team": entry["name"],
                "points": entry["summary_overall_points"], "rank": entry["summary_overall_rank"],
                "gw_points": entry.get("summary_event_points"), "gw_rank": entry.get("summary_event_rank"),
                "bank": bank, "value": (picks["entry_history"]["value"] if picks else 0) / 10,
                "free_transfers": ft, "total_players": boot["total_players"]},
    "history": [{"gw": h["event"], "pts": h["points"], "rank": h["overall_rank"], "gw_rank": h["rank"],
                 "bench": h["points_on_bench"], "tx": h["event_transfers"], "hit": h["event_transfers_cost"],
                 "chip": chips_by_gw.get(h["event"])} for h in history["current"]],
    "squad": [{"id": p["element"], "slot": p["position"], "cap": p["is_captain"], "vice": p["is_vice_captain"],
               "buy": purchase_price(p["element"]) / 10, "sell": selling_price(p["element"]) / 10}
              for p in (picks["picks"] if picks else [])],
    "lineup": lineup, "plans": plans, "accuracy": accuracy,
    "crowd": crowd_out, "review": review, "setpieces": setpieces,
    "chips": chips, "gw_info": gw_info, "season_gws": season_gws, "live": live_gw, "teams": team_out,
    "players": [players[i] for i in sorted(keep, key=lambda i: -players[i]["xp5"])],
}
out["meta"]["build_secs"] = round(time.time() - t0, 1)
with open(OUT, "w") as f:
    json.dump(out, f, separators=(",", ":"))
print(f"wrote {OUT}: {len(out['players'])} players, GW{next_gw}, FT {ft}, plans {list(plans)}, {out['meta']['build_secs']}s")
