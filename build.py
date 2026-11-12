#!/usr/bin/env python3
"""FPL Lab data builder.

Fetches the public FPL API, projects every player with fplmodel, plans transfers
with optimise, measures the model against past gameweeks and writes data.json.

Usage:  python3 build.py [TEAM_ID] [OUT_PATH]
"""
import json, os, sys, time, urllib.request, datetime as dt
from collections import Counter, defaultdict

from fplmodel import prepare, project, POS, DEFAULTS, unfinished_team_weeks
from backtest import evaluate, baseline, evaluate_horizons, band, head_to_head
import optimise
import squad_state
import fpl_score
import decision_journal
import deadline_snapshot
import setpiece_log

TEAM_ID = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("FPL_TEAM_ID", 8122679))
OUT = sys.argv[2] if len(sys.argv) > 2 else "data.json"
API = "https://fantasy.premierleague.com/api"
HORIZON = 6
PLAN_GWS = 5
# Strategy settings and points budgets live in optimise.py (STRATEGY, SAFE_BUDGET, CHASE_BUDGET, MIN_PROFIT); the
# browser Re-plan uses the same numbers (js/core/model.js)
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


def finished_only(g, data):
    """A gameweek's live rows for the model: only players whose club has finished all its matches that week.
    Mid-gameweek, players yet to play show 0 minutes, which the model would read as being dropped."""
    pending = {t for t, week in unfinished_team_weeks(fixtures) if week == g}
    if not pending:
        return data
    team = {e["id"]: e["team"] for e in boot["elements"]}
    return dict(data, elements=[x for x in data["elements"] if team.get(x["id"]) not in pending])


model_live = {g: finished_only(g, d) for g, d in live.items()}
picks_gw = entry.get("current_event") or cur_gw
picks = get(f"/entry/{TEAM_ID}/event/{picks_gw}/picks/") if picks_gw else None
# The squad you own going forward (squad_state.owned_picks): after a Free Hit, the restored pre-Free-Hit squad and bank.
# `picks` still drives this GW's live score, rivals and review; `own_picks` drives the squad, bank, value and plans.
own_picks, squad_gw, fh_active = squad_state.owned_picks(
    picks, picks_gw, next_gw, lambda g: get(f"/entry/{TEAM_ID}/event/{g}/picks/"))
try:
    priors = json.load(open(os.path.join(HERE, "priors.json")))
except Exception:
    priors = None

try:
    market = json.load(open(os.path.join(HERE, "odds", "odds.json")))
except Exception:
    market = None
try:
    player_odds = json.load(open(os.path.join(HERE, "odds", "players.json")))
except Exception:
    player_odds = None
try:
    from fplmodel import understat_sp
    sp_data = understat_sp(boot, fixtures, json.load(open(os.path.join(HERE, "understat", "shots.json"))),
                           json.load(open(os.path.join(HERE, "understat", "fpl_players.json")))["players"])
except Exception:
    sp_data = None
# injury / suspension log: each player's status at every deadline, so the model can tell
# "injured" from "dropped" later in the season (FPL keeps no history of this)
STATUS_LOG = os.path.join(HERE, "history", "status.json")
# How the log loaded goes to meta.status_log (FL-072): "ok", "missing" (no file: normal before the first deadline, the
# log is lost after it) or "unreadable". Either of the last two leaves the model without the injury history for this
# build, so validate.py makes it an error once the season has started.
status_ok, status_state, status_err = True, "ok", None
try:
    status_log = json.load(open(STATUS_LOG))
    if not isinstance(status_log.get("gws"), dict):
        raise ValueError("no 'gws' table")
except FileNotFoundError:
    status_log, status_state = {"gws": {}}, "missing"
except Exception as ex:
    # never overwrite a log that failed to load: it can't be rebuilt
    print("history/status.json unreadable, not updating it:", ex)
    status_log, status_ok, status_state, status_err = {"gws": {}}, False, "unreadable", str(ex)[:200]
status_loaded_gws = len(status_log["gws"])   # before this build adds the coming deadline
# When the previous refresh ran: the status log's own "updated" stamp, read before this build rewrites it. It goes
# to meta.prev_built so validate.py can warn when refreshes are far apart close to a deadline (GitHub's schedule is
# best effort and has left gaps of 8 hours). Missing or unreadable log, or a stamp that isn't a timestamp: None, and
# validate.py says the gap can't be checked rather than assuming it was fine.
prev_built = status_log.get("updated") if status_ok and isinstance(status_log.get("updated"), str) else None
if status_ok and next_ev and dt.datetime.now(dt.timezone.utc) < dt.datetime.fromisoformat(next_ev["deadline_time"].replace("Z", "+00:00")):
    # latest status before this deadline; only players not fully available, to keep it small
    status_log["gws"][str(next_gw)] = {str(e["id"]): [e["status"], e["chance_of_playing_next_round"]]
                                       for e in boot["elements"] if e["status"] != "a"}
    status_log["updated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    os.makedirs(os.path.dirname(STATUS_LOG), exist_ok=True)
    tmp = STATUS_LOG + ".tmp"
    with open(tmp, "w") as f:
        json.dump(status_log, f, separators=(",", ":"))
    os.replace(tmp, STATUS_LOG)   # atomic: a crash mid-write can't leave a half-written log
# transfer-count log for the next deadline (cadence and format in transfer_log.py); never breaks the build
try:
    import transfer_log
    transfer_log.update(boot, next_ev, dt.datetime.now(dt.timezone.utc),
                        os.path.join(HERE, "history", f"transfers_gw{next_ev['id']}.json") if next_ev else None)
except Exception as ex:
    print("transfer log skipped:", ex)
ctx = prepare(boot, fixtures, model_live, priors, market, sp_data, status_log)

# European midweek congestion: small rotation risk for league games within ~3 days of a European match.
# A competition marked "confirmed": false in europe.json (dates or teams guessed) is skipped: no rotation
# allowance and no "also plays" flag until someone confirms it.
# How it loaded goes to meta.europe (FL-072): "ok", "missing" or "unreadable" (bad JSON, or an entry that fails part
# way: the competitions read before it keep their allowance, those after it get none), plus the unconfirmed ones
# skipped. validate.py warns on anything but a clean load, and lists the skipped competitions.
congestion, euro_flags, euro_skipped = {}, {}, []
euro_state, euro_err, euro_n = "ok", None, 0
try:
    europe = json.load(open(os.path.join(HERE, "europe.json")))["competitions"]
    short_to_id = {t["short_name"]: t["id"] for t in boot["teams"]}
    euro_n = len(europe)
    for comp, c in europe.items():
        if c.get("confirmed") is False:
            euro_skipped.append(comp)
            continue
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
except FileNotFoundError:
    euro_state = "missing"
    print("europe.json not found: no European rotation allowance")
except Exception as ex:
    euro_state, euro_err = "unreadable", f"{type(ex).__name__}: {ex}"[:200]
    print("europe.json not used:", ex)
ctx["congestion"] = congestion
elements, teams = ctx["elements"], ctx["teams"]
# Season end (FL-060): after GW38's deadline FPL lists no next gameweek. There is nothing left to forecast, but the
# site still needs every player's row (live scores, Review, season stats) and the team ratings, so project as of the
# week after the last one with no gameweeks ahead (horizon 0): every xP is empty, proj_gws is [], no plans are built,
# and meta.season_over tells the site and validate.py why. In season this branch never runs: projections unchanged.
season_over = not next_gw
if season_over:
    print(f"season over: FPL lists no next gameweek after GW{cur_gw}; no forecasts or plans, season stats only")
res = project(ctx, next_gw or cur_gw + 1, 0 if season_over else HORIZON, {"sim": 4000})
proj = res["players"] if res else {}
proj_gws = res["gws"] if res else []
upcoming = res["upcoming"] if res else {}
rating = res["rating"] if res else {}
finished_gws = [e["id"] for e in events if e["finished"]]

# ---------------------------------------------------------------- my squad, prices, free transfers
fh_events = {c["event"] for c in history["chips"] if c["name"] == "freehit"}
squad_ids = [p["element"] for p in own_picks["picks"]] if own_picks else []


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
bank = (own_picks["entry_history"]["bank"] if own_picks else 0) / 10   # restored bank after a Free Hit
team_value = squad_state.team_value(own_picks, bank, {i: e["now_cost"] for i, e in elements.items()}, fh_active)

# ---------------------------------------------------------------- per-player stats for the page
pstats = ctx["pstats"]


def done_gws(pid, n=None):
    """The last n gameweeks up to the current one (all of them for n None) for the form windows below, leaving out any
    week his club hasn't finished (FL-083). Mid-gameweek pstats has no row for a club still to play (or part way through
    a double), the model's rule (fplmodel.unfinished_team_weeks); counting that week anyway made an ever-present starter
    whose club plays on Monday show 4 starts from 5, and shortened every "last 4/6" window by a week. The window reaches
    one week further back instead.
    Missing / ambiguous: a fixture FPL hasn't given a gameweek (postponed) isn't pending and changes nothing; a blank
    week (no fixture) is still counted as a week, as before; a player who changed club is judged by his current club."""
    team = elements[pid]["team"]
    gws = [g for g in range(1, cur_gw + 1) if (team, g) not in ctx["pending_team_gws"]]
    return gws if n is None else gws[-n:]


def series(pid, key, cast=float):
    return [round(cast(pstats[pid][g][key]), 2) if g in pstats.get(pid, {}) else 0 for g in range(1, cur_gw + 1)]


def starts_record(pid, e, n=5):
    """[starts, games] over his club's last n finished gameweeks (a double counts each game): real starts, for the
    player sheet, which used to print the model's start chance as if it were a share of games."""
    pending = ctx["pending_team_gws"]   # FL-083: a game not finished yet isn't one he could have started
    gws = sorted({x[0] for x in ctx["team_fix"].get(e["team"], []) if x[0] and x[0] <= cur_gw and (e["team"], x[0]) not in pending})[-n:]
    s = pstats.get(pid, {})
    games = sum(sum(1 for x in ctx["team_fix"][e["team"]] if x[0] == g) for g in gws)
    return [min(games, sum(s[g]["starts"] for g in gws if g in s)), games]


def rolling(pid, n):
    gws = done_gws(pid, n)
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
    # last 6 gameweeks his club actually played (a blank week is not a dropped player)
    played = {x[0] for x in ctx["team_fix"].get(e["team"], [])}
    recent = [g for g in range(1, cur_gw + 1) if g in played and g in s][-6:]
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


# ---- defensive contribution points as FPL scored them, per player per gameweek, from the match explain rows.
# Same finished-matches-only rows as pstats, so a gameweek in progress counts only matches that are over. A hit in a
# game under 60 minutes, or two hits in a double, both count here (dc_record's hits/apps only counts 60+ minute games).
dc_pts_gw = defaultdict(dict)
for g, data in model_live.items():
    for x in data["elements"]:
        v = sum(s_["points"] for ex in x["explain"] for s_ in ex["stats"] if s_["identifier"] == "defensive_contribution")
        if v:
            dc_pts_gw[x["id"]][g] = v


def ga_window(pid, n):
    """Goals, assists, FPL (Opta) xG and xA, and minutes over the last n gameweeks his club has finished (done_gws).
    A player with no row in a gameweek (no fixture, or he didn't play) adds nothing for it."""
    s = pstats.get(pid, {})
    gws = [g for g in done_gws(pid, n) if g in s]
    tot = lambda k, cast=float: sum(cast(s[g][k]) for g in gws)
    return {"g": tot("goals_scored", int), "a": tot("assists", int), "xg": round(tot("expected_goals"), 2),
            "xa": round(tot("expected_assists"), 2), "mins": tot("minutes", int)}


def bonus_form(pid, n):
    gws = done_gws(pid, n)
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
    gws = done_gws(pid, n)
    s = pstats.get(pid, {})
    apps = [g for g in gws if s.get(g, {}).get("minutes", 0) >= 60]
    hits = sum(1 for g in apps if ctx["dc_hit"][pid].get(g))
    cbit = sum(s[g]["defensive_contribution"] for g in gws if g in s)
    mins = sum(s[g]["minutes"] for g in gws if g in s)
    pts = sum(dc_pts_gw.get(pid, {}).get(g, 0) for g in gws)
    return {"hits": hits, "apps": len(apps), "per90": round(cbit / mins * 90, 1) if mins >= 90 else 0.0,
            "pts": pts, "mins": mins}


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
    slope = DEFAULTS["cal_slope"]
    det_r = {k: round(v * slope, 2) for k, v in det.items()}
    # the calibration intercept (cal_int x chance he plays) and rounding: the line that makes the parts add up to xP
    det_r["appear_adj"] = round(xp.get(next_gw, 0) - sum(det_r.values()), 2)
    players[pid] = {
        "id": pid, "name": e["web_name"], "full": f'{e["first_name"]} {e["second_name"]}',
        "team": e["team"], "pos": pos, "price": e["now_cost"] / 10, "own": float(e["selected_by_percent"]),
        "form": float(e["form"]), "pts": e["total_points"], "mins": e["minutes"],
        "goals": e["goals_scored"], "assists": e["assists"], "starts": e.get("starts"), "cs": e["clean_sheets"], "bonus": e["bonus"],
        "xg": float(e["expected_goals"]), "xa": float(e["expected_assists"]),
        "g_xg": round(e["goals_scored"] - float(e["expected_goals"]), 2),
        "a_xa": round(e["assists"] - float(e["expected_assists"]), 2),
        "xgi90": round(r["xg90"] + r["xa90"], 2), "xg90": round(r["xg90"], 2), "xa90": round(r["xa90"], 2),
        "xgi90_4": round(xgi4, 2), "xgi90_6": round(xgi6, 2), "pts4": pts4, "pts6": pts6, "mins4": m4,
        "dc90": round(r["dc90"], 1), "dc_rate": round(r["p_dc"], 2), "p_start": round(r["p_start"], 2),
        # next gameweek, per match, after flags, rotation and return ramp: what the forecast used (p_start is before them)
        "start_next": None if r["start_next"] is None else round(r["start_next"], 2),
        "sub_next": None if r["sub_next"] is None else round(r["sub_next"], 2),
        "xmin": round(r["xmin"]), "status": e["status"], "news": e["news"], "chance": e["chance_of_playing_next_round"],
        "ret": cur_gw in ctx.get("out", {}).get(pid, ()),   # missed his club's last game through injury or a ban
        "yc": e["yellow_cards"], "rc": e["red_cards"], "upos": (US.get("players", {}).get(str(pid)) or {}).get("upos", ""),
        "psub": round(r.get("p_sub", 0), 2), "st5": starts_record(pid, e),
        "xp": xp, "assumed": r.get("assumed") or [],   # gameweeks whose xP rests on our defaults, not FPL data
        "xp1": round(sum(vals[:1]), 2), "xp3": round(sum(vals[:3]), 2),
        "xp5": round(sum(vals[:5]), 2), "xp6": round(sum(vals[:6]), 2),
        "xp_detail": det_r,
        # simulated outcomes per gameweek: [chance of 10+, chance of 6+, chance of 2 or fewer, low (10th pct), high (90th pct)]
        "dist": {g: [d["p10"], d["p6"], d["blank"], d["q10"], d["q90"]] for g, d in r.get("dist", {}).items()},
        "price_proj": [float(x["projected_percent"]) for x in (e.get("price_change_projections") or [])],
        "tin": e["transfers_in_event"], "tout": e["transfers_out_event"],
        "pen": e.get("penalties_order"), "ep_fpl": float(e["ep_next"] or 0),
        "last": {"season": pr["season"], "pts": pr["last_pts"], "mins": pr["last_mins"], "xgi": pr["last_xgi"]} if pr else None,
        "s_pts": series(pid, "total_points", int), "s_min": series(pid, "minutes", int),
        "s_xgi": series(pid, "expected_goal_involvements"),
        "ok": bool(e["can_select"]) and e["status"] in ("a", "d") and r["xmin_base"] > 10,
        "code": e["code"], "tcode": e["team_code"], "tmp": bool(e.get("has_temporary_code")),
        "bf4": bonus_form(pid, 4), "bf6": bonus_form(pid, 6), "bps_season": e["bps"],
        "us": shot_stats(pid, m4), "dcs": dc_record(pid), "dc6": dc_record(pid, 6), "ga6": ga_window(pid, 6),
        "s_bps": series(pid, "bps", int),
        "nailed": nailed(pid, e, r), "mflag": minutes_flag(pid, e),
        "sp": {"pen": e.get("penalties_order"), "cor": e.get("corners_and_indirect_freekicks_order"),
               "fk": e.get("direct_freekicks_order")},
    }

# ---------------------------------------------------------------- optimiser plans
plans, plan_notes = {}, []
sell = {i: selling_price(i) / 10 for i in squad_ids}
if squad_ids and proj_gws:
    opt_players = {i: {"pos": p["pos"], "team": p["team"], "price": p["price"], "xp": p["xp"], "ok": p["ok"],
                       "p10": {int(g): d[0] for g, d in (p.get("dist") or {}).items()}, "nailed": p.get("nailed", 100)}
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
    # strategies: Balanced, then Play safe and Chase rank held to points budgets against it (optimise.strategy_plans).
    # Without field ownership only Balanced is built; the note goes to the Health page via plan_notes.
    plans, plan_notes = optimise.strategy_plans(opt_players, squad_ids, sell, bank, min(ft, 5), gws, options,
                                                eo=eo_field or None)
    for n in plan_notes:
        print("plans:", n)
    for r in plans.values():
        for wk in r["weeks"]:
            mult = {i: 1 for i in wk["xi"]}
            mult[wk["captain"]] = 2
            wk["spread"] = round(optimise.spread(opt_players, mult, eo_field, wk["gw"]), 1) if eo_field else None
    for k, pl in plans.items():
        rk = "roll" if "_" not in k else k.split("_")[0] + "_roll"
        if rk in plans:
            pl["vs_roll"] = round(pl["xp_total"] + optimise.FT_VALUE * (pl["ft_left"] - plans[rk]["ft_left"]) - plans[rk]["xp_total"], 2)

# lineup for the current squad (no transfers)
lineup = {}
if "roll" in plans:
    w0 = plans["roll"]["weeks"][0]
    cur_xi = [p["element"] for p in own_picks["picks"] if p["position"] <= 11]
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

    def _err(e):  # MAE / RMSE overall and by return band (OpenFPL bands), rounded for the page
        r = lambda v: None if v is None else round(v, 2)
        return {"n": e["n"], "mae": r(e["mae"]), "rmse": r(e["rmse"]),
                "bands": {b: {"n": x["n"], "mae": r(x["mae"]), "rmse": r(x["rmse"]), "bias": r(x["bias"])}
                          for b, x in e["bands"].items()}}
    accuracy["compare"] = {"pool": _err(ev["pool"]), "all": _err(ev["all"]),
                           "base_pool": _err(bl["pool"]), "base_all": _err(bl["all"])}

    def _herr(e):
        o = _err(e)
        o["corr"] = None if e["corr"] is None else round(e["corr"], 3)
        return o
    accuracy["horizons"] = {str(h): {"model": _herr(v["model"]), "base": _herr(v["base"])}
                            for h, v in evaluate_horizons(ctx, test).items()}

# ---------------------------------------------------------------- weekly accuracy log
HIST = os.path.join(HERE, "history")
os.makedirs(HIST, exist_ok=True)
# snapshot this gameweek's projections (ours and FPL's own) until its deadline passes
if next_ev and dt.datetime.now(dt.timezone.utc) < dt.datetime.fromisoformat(next_ev["deadline_time"].replace("Z", "+00:00")):
    # [our xP, FPL's ep_next, FPL status, chance of playing] as known before the deadline
    snap = {str(i): [round(p["xp"].get(next_gw, 0), 2), p["ep_fpl"], p["status"], p["chance"]]
            for i, p in players.items() if p["xp"].get(next_gw, 0) > 0 or p["ep_fpl"] > 0}
    json.dump({"gw": next_gw, "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "players": snap},
              open(os.path.join(HIST, f"proj_gw{next_gw}.json"), "w"), separators=(",", ":"))
    # the rest of what we knew before the deadline: plan-horizon xP, minutes, outcome chances, odds and the strategy
    # plans (deadline_snapshot.py says what each part holds and what it does when an input is missing)
    deadline_snapshot.write(HIST, deadline_snapshot.build(next_gw, proj_gws[:PLAN_GWS], players, squad_ids, bank, ft,
                                                          plans, market, fixtures))


def corr_mae(pairs):
    if len(pairs) < 30:
        return None, None
    xs, ys = [p for p, _ in pairs], [a for _, a in pairs]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxy = sum((x - mx) * (y - my) for x, y in pairs)
    sxx = sum((x - mx) ** 2 for x in xs); syy = sum((y - my) ** 2 for y in ys)
    c = sxy / (sxx * syy) ** 0.5 if sxx and syy else None
    return (round(c, 3) if c is not None else None), round(sum(abs(x - y) for x, y in pairs) / len(pairs), 2)


from fplmodel import DEFAULTS as _MD
DEFAULTS_CAL = _MD["cal_slope"]
keep_extra = set()
acc_weeks = []
for g in [g for g in finished_gws if g >= 3]:
    ev1 = evaluate(ctx, [g])
    row = {"gw": g, "n": ev1["n"], "corr": round(ev1["corr"], 3), "mae": round(ev1["mae"], 2),
           "top_pred": round(ev1["top30"][0][2], 2), "top_act": round(ev1["top30"][0][1], 2), "live": None}
    fpath = os.path.join(HIST, f"proj_gw{g}.json")
    if os.path.exists(fpath):
        snap = json.load(open(fpath))["players"]
        ours, fplp = [], []
        for pid_s, v in snap.items():
            pid, xo, xf = int(pid_s), v[0], v[1]
            a = ctx["pts_gw"].get(pid, {}).get(g)
            if a is None or not any(pstats.get(pid, {}).get(k, {}).get("minutes", 0) > 0 for k in range(g - 3, g)):
                continue
            ours.append((xo, a)); fplp.append((xf, a))
        co, mo = corr_mae(ours); cf, mf = corr_mae(fplp)
        row["live"] = {"n": len(ours), "corr": co, "mae": mo, "fpl_corr": cf, "fpl_mae": mf}
    acc_weeks.append(row)

# ---- head to head: our live projections v FPL's own, as saved before each deadline, scored after the GW.
# Every player in the snapshot plus anyone who played in the previous 3 GWs (missing = projected 0 by both).
POS_OF = lambda pid: POS[elements[pid]["element_type"]] if pid in elements else ""
h2h_rows = []
for g in finished_gws:
    fpath = os.path.join(HIST, f"proj_gw{g}.json")
    if not os.path.exists(fpath):
        continue
    snap = json.load(open(fpath))["players"]
    ids = {int(k) for k in snap} | {pid for pid in ctx["pts_gw"] if g in ctx["pts_gw"][pid]
                                    and any(pstats.get(pid, {}).get(k, {}).get("minutes", 0) > 0 for k in range(g - 3, g))}
    for pid in sorted(ids):
        a = ctx["pts_gw"].get(pid, {}).get(g)
        if a is None or pid not in elements:
            continue
        v = snap.get(str(pid), [0, 0])
        s_ = pstats.get(pid, {}).get(g, {})
        mins = s_.get("minutes", 0)
        h2h_rows.append({
            "gw": g, "id": pid, "name": elements[pid]["web_name"], "team": teams[elements[pid]["team"]]["short_name"],
            "pos": POS_OF(pid), "ours": float(v[0]), "fpl": float(v[1]), "pts": a, "mins": mins,
            "started": int(bool(s_.get("starts"))), "band": band(a, mins),
            "pool": int(any(pstats.get(pid, {}).get(k, {}).get("minutes", 0) > 0 for k in range(g - 3, g))),
            "status": v[2] if len(v) > 2 else "", "chance": v[3] if len(v) > 3 and v[3] is not None else ""})
H2H_CSV = os.path.join(HIST, "head_to_head.csv")
if h2h_rows:
    import csv
    cols = ["gw", "id", "name", "team", "pos", "ours", "fpl", "pts", "mins", "started", "band", "pool", "status", "chance"]
    with open(H2H_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for r in h2h_rows:
            w.writerow({**r, "ours": f'{r["ours"]:.2f}', "fpl": f'{r["fpl"]:.2f}'})


def _h2h(rows):
    h = head_to_head(rows)
    r2 = lambda v: None if v is None else round(v, 2)
    side = lambda e: {"corr": None if e["corr"] is None else round(e["corr"], 3), "mae": r2(e["mae"]), "rmse": r2(e["rmse"]),
                      "bands": {b: {"n": x["n"], "rmse": r2(x["rmse"]), "bias": r2(x["bias"])} for b, x in e["bands"].items()}}
    return {"n": h["n"], "ours": side(h["ours"]), "fpl": side(h["fpl"])}


h2h = None
if h2h_rows:
    pool = [r for r in h2h_rows if r["pool"]]
    weeks = []
    for g in sorted({r["gw"] for r in pool}):
        wk = _h2h([r for r in pool if r["gw"] == g])
        wk["gw"] = g
        wk["all_mae"] = {k: round(sum(abs(r[k] - r["pts"]) for r in h2h_rows if r["gw"] == g) /
                                  max(1, sum(1 for r in h2h_rows if r["gw"] == g)), 2) for k in ("ours", "fpl")}
        weeks.append(wk)
    h2h = {"weeks": weeks, "season": _h2h(pool), "rows": len(h2h_rows),
           "csv": "https://raw.githubusercontent.com/AFG-design/FPL-Lab/main/history/head_to_head.csv"}
# ---- check of the cleared-news absence rule (fplmodel.news_absences): snapshot both projections for the
# gameweek after the absence, then score them against what happened once that gameweek is over
ABS_F = lambda g: os.path.join(HIST, f"absence_gw{g}.json")
if ctx.get("out_news"):
    g_chk = max(max(v) for v in ctx["out_news"].values()) + 1
    # only for the next gameweek and only before its deadline (deadline_snapshot.absence_snapshot_due says what
    # happens when the file exists, the gameweek isn't next, or the deadline is missing); a late one is never made
    abs_due, abs_why = deadline_snapshot.absence_snapshot_due(ABS_F(g_chk), g_chk, next_ev)
    if not abs_due and abs_why != "already written":
        print(f"absence_gw{g_chk}.json not written: {abs_why}")
    if abs_due:
        new_ = project(ctx, g_chk, 1)["players"]
        old_ = project(ctx, g_chk, 1, {"news_abs": False})["players"]
        snap = {str(pid): {"fix": [round(new_[pid]["xp"].get(g_chk, 0), 2), round(new_[pid]["xmin"])],
                           "old": [round(old_[pid]["xp"].get(g_chk, 0), 2), round(old_[pid]["xmin"])]}
                for pid, gs_ in ctx["out_news"].items() if g_chk - 1 in gs_ and pid in new_ and pid in old_}
        json.dump({"gw": g_chk, "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "players": snap},
                  open(ABS_F(g_chk), "w"), separators=(",", ":"))
absence_check = []
for f_ in sorted(os.listdir(HIST)):
    if not (f_.startswith("absence_gw") and f_.endswith(".json")):
        continue
    a = json.load(open(os.path.join(HIST, f_)))
    g_ = a["gw"]
    done_ = g_ in finished_gws
    rows_ = []
    for pid_s, v in a["players"].items():
        pid = int(pid_s)
        st = pstats.get(pid, {}).get(g_, {}) if done_ or g_ in live else {}
        rows_.append({"id": pid, "xp_fix": v["fix"][0], "xp_old": v["old"][0], "min_fix": v["fix"][1], "min_old": v["old"][1],
                      "mins": st.get("minutes"), "started": bool(st.get("starts")) if st else None,
                      "pts": ctx["pts_gw"].get(pid, {}).get(g_) if st else None})
        keep_extra.add(pid)
    sc = [r for r in rows_ if r["pts"] is not None] if done_ else []
    absence_check.append({"gw": g_, "done": done_, "rows": rows_,
                          "err_fix": round(sum(abs(r["pts"] - r["xp_fix"]) for r in sc) / len(sc), 2) if sc else None,
                          "err_old": round(sum(abs(r["pts"] - r["xp_old"]) for r in sc) / len(sc), 2) if sc else None,
                          "min_err_fix": round(sum(abs(r["mins"] - r["min_fix"]) for r in sc) / len(sc)) if sc else None,
                          "min_err_old": round(sum(abs(r["mins"] - r["min_old"]) for r in sc) / len(sc)) if sc else None})

# biggest misses each gameweek, and which part of the score they came from
CAT = {"minutes": "mins", "goals_scored": "goals", "assists": "assists", "clean_sheets": "cs", "goals_conceded": "gc",
       "saves": "saves", "defensive_contribution": "dc", "bonus": "bonus", "yellow_cards": "cards", "red_cards": "cards",
       "own_goals": "other", "penalties_missed": "other", "penalties_saved": "saves"}
GROUP = {"mins": "Minutes", "goals": "Attack", "assists": "Attack", "cs": "Defence", "gc": "Defence", "saves": "Defence",
         "dc": "Defence", "bonus": "Bonus", "cards": "Cards and other", "other": "Cards and other"}


def why_text(c, d, st, xd):
    mins = st["minutes"]
    if c == "mins":
        if mins == 0:
            return "Didn't play"
        return f"Only {mins} minutes" + (" off the bench" if not st["starts"] else "") if d < 0 else f"Played {mins} minutes (expected fewer)"
    if c == "goals":
        g = st["goals_scored"]
        return f"Scored {g} from {float(st['expected_goals']):.2f} xG" if g else f"No goal ({float(st['expected_goals']):.2f} xG)"
    if c == "assists":
        a = st["assists"]
        return f"{a} assist{'s' if a > 1 else ''} from {float(st['expected_assists']):.2f} xA" if a else f"No assist ({float(st['expected_assists']):.2f} xA)"
    if c in ("cs", "gc"):
        return "Clean sheet" if st["clean_sheets"] else f"Conceded {st['goals_conceded']}"
    if c == "dc":
        return "Hit the defensive contribution target" if d > 0 else "Missed the defensive contribution target"
    if c == "saves":
        return f"{st['saves']} saves" + (", penalty save" if st["penalties_saved"] else "")
    if c == "bonus":
        return f"{st['bonus']} bonus" if st["bonus"] else "No bonus"
    if c == "cards":
        return "Red card" if st["red_cards"] else "Booked"
    return "Own goal" if st["own_goals"] else "Missed a penalty" if st["penalties_missed"] else "Other"


misses = []
for g in [g for g in finished_gws if g >= 3][-4:]:
    try:
        pr_g = project(ctx, g, 1, {"use_flags": False})["players"]
    except Exception:
        continue
    lv_g = {x["id"]: x for x in live[g]["elements"]}
    rows, blame = [], defaultdict(float)
    for pid, r in pr_g.items():
        x = r["xp"].get(g, 0.0)
        L = lv_g.get(pid)
        if not L or not any(pstats.get(pid, {}).get(k, {}).get("minutes", 0) > 0 for k in range(g - 3, g)):
            continue
        act = defaultdict(float)
        for fx in L["explain"]:
            for it in fx["stats"]:
                act[CAT.get(it["identifier"], "other")] += it["points"]
        exp_ = {k: v * DEFAULTS_CAL for k, v in r["detail"].get(g, {}).items()}
        exp_["mins"] = exp_.get("mins", 0) + (x - sum(exp_.values()))   # calibration intercept counts as appearance
        diffs = {c: act.get(c, 0) - exp_.get(c, 0) for c in set(act) | set(exp_)}
        pts = L["stats"]["total_points"]
        for c, d in diffs.items():
            blame[GROUP.get(c, "Cards and other")] += abs(d)
        miss = pts - x
        cands = [(c, d) for c, d in diffs.items() if d * miss > 0] or list(diffs.items())
        c, d = max(cands, key=lambda cd: abs(cd[1]))
        rows.append({"id": pid, "xp": round(x, 1), "pts": pts, "miss": round(miss, 1), "why": why_text(c, d, L["stats"], exp_),
                     "cat": GROUP.get(c, "Cards and other")})
    tot = sum(blame.values()) or 1
    over = sorted([r for r in rows if r["xp"] >= 3], key=lambda r: r["miss"])[:8]
    under = sorted(rows, key=lambda r: -r["miss"])[:8]
    misses.append({"gw": g, "over": over, "under": under, "blame": {k: round(100 * v / tot) for k, v in sorted(blame.items(), key=lambda kv: -kv[1])},
                   "n": len(rows), "mae": round(sum(abs(r["miss"]) for r in rows) / max(1, len(rows)), 2)})
    for r in over + under:
        keep_extra.add(r["id"])
if accuracy is not None:
    accuracy["weeks"] = acc_weeks
    accuracy["h2h"] = h2h
    accuracy["h2h_next"] = min((int(f[7:-5]) for f in os.listdir(HIST) if f.startswith("proj_gw") and f.endswith(".json")
                                and int(f[7:-5]) not in finished_gws), default=None)
    accuracy["misses"] = misses
    accuracy["absence"] = absence_check

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
               "hits": picks["entry_history"]["event_transfers_cost"],
               "rows": [{"id": p["element"], "pos": p["position"], "mult": p["multiplier"], "cap": p["is_captain"],
                         "vice": p["is_vice_captain"], "pts": lv.get(p["element"], {}).get("total_points", 0),
                         "mins": lv.get(p["element"], {}).get("minutes", 0), "bps": lv.get(p["element"], {}).get("bps", 0),
                         "bonus": lv.get(p["element"], {}).get("bonus", 0)} for p in picks["picks"]]}
    # live mode: fixture status, provisional bonus (top 3 BPS in each match until FPL confirms it),
    # the other teams' players needed for the field average
    gw_fx = [f for f in fixtures if f["event"] == picks_gw]
    prov = {}
    for f in gw_fx:
        if not f["started"]:
            continue
        st = {x["identifier"]: x for x in f.get("stats", [])}
        if st.get("bonus") and (st["bonus"]["h"] or st["bonus"]["a"]):
            continue                                   # bonus confirmed: it's in total_points already
        bps = sorted([(x["value"], x["element"]) for side in ("h", "a") for x in st.get("bps", {}).get(side, [])], reverse=True)
        # FPL rules: ties share the higher award; awards stop once three players have bonus
        given, rank_pts, k = 0, [3, 2, 1], 0
        while k < len(bps) and given < 3:
            v = bps[k][0]
            tied = [e for (val, e) in bps if val == v]
            award = rank_pts[given] if given < 3 else 0
            for e in tied:
                prov[e] = award
            given += len(tied)
            k += len(tied)
    def fx_events(f):
        st = {x["identifier"]: x for x in f.get("stats", [])}
        ev = []
        for ident, kind in (("goals_scored", "g"), ("own_goals", "og"), ("assists", "a"), ("red_cards", "r"), ("penalties_missed", "pm"), ("penalties_saved", "ps")):
            for side in ("h", "a"):
                for x in (st.get(ident) or {}).get(side, []):
                    e = elements.get(x["element"])
                    ev.append([kind, side, e["web_name"] if e else "?", x["value"], x["element"]])
        return ev
    live_gw["fixtures"] = [{"id": f["id"], "h": f["team_h"], "a": f["team_a"], "ko": f["kickoff_time"], "started": bool(f["started"]),
                            "done": bool(f["finished"] or f.get("finished_provisional")), "mins": f.get("minutes", 0),
                            "hs": f["team_h_score"], "as": f["team_a_score"], "ev": fx_events(f) if f["started"] else []} for f in gw_fx]
    live_gw["in_play"] = any(f["started"] for f in gw_fx) and not ev["finished"]
    for r in live_gw["rows"]:
        r["team"] = elements[r["id"]]["team"]
        r["prov"] = prov.get(r["id"], 0)
    # what we projected for this gameweek before its deadline (the snapshot above stops updating at the deadline)
    snap_f = os.path.join(HIST, f"proj_gw{picks_gw}.json")
    if os.path.exists(snap_f):
        snap_gw = json.load(open(snap_f))
        if snap_gw.get("gw") == picks_gw:
            for r in live_gw["rows"]:
                r["xp"] = snap_gw["players"].get(str(r["id"]), [0])[0]
            live_gw["xp_built"] = snap_gw.get("built")
    # every player's live points + provisional bonus, for the field average (effective ownership x points)
    live_gw["pts_all"] = {str(i): lv[i]["total_points"] + prov.get(i, 0) for i in lv if lv[i]["total_points"] or prov.get(i)}

# ---------------------------------------------------------------- the field and mini-leagues
crowd_out = None
try:
    crowd = json.load(open(os.path.join(HERE, "crowd", "latest.json")))
except Exception:
    crowd = None
if crowd and not (all(k in crowd for k in ("gw", "built", "near", "top10k", "leagues", "rivals"))
                  and all(isinstance(crowd[k], dict) and "eo" in crowd[k] for k in ("near", "top10k"))):
    print("crowd/latest.json is missing fields, ignoring it")
    crowd = None
if crowd:
    G = crowd["gw"]
    lv = {x["id"]: x["stats"]["total_points"] for x in live[G]["elements"]} if G in live else {}
    g_ev = next(e for e in events if e["id"] == G)
    in_play = not g_ev["finished"]
    # FL-078: rivals' live points on the same basis as yours (live.js liveState) and FPL's own standings: points
    # BEFORE hits (FPL's event_total, which the table shows once matches end, is before hits: checked against picks
    # for rivals with a hit), with provisional bonus while it's unconfirmed (live_gw["pts_all"], the same top-3-BPS
    # rule as your rows). The hit stays on the row ("hits") for the tooltip. Missing / late: when the sample is for
    # another gameweek than your live one, there is no provisional bonus for it, so confirmed points only.
    pts_live = {int(k): v for k, v in live_gw["pts_all"].items()} if live_gw and live_gw["gw"] == G else lv

    def team_live(p):
        return sum(pts_live.get(el, 0) * m for el, m in p)

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
                         "live": team_live(pk["p"]) if pk and lv else None})
        rows.sort(key=lambda r: (r["rank"] or 1e9))
        leagues_out.append({"id": lg["id"], "name": lg["name"], "size": lg["size"],
                            "my_rank": (me_rank or {}).get("rank", lg["my_rank"]), "rows": rows})
    keep_ids = {str(i) for i in players}
    slim = lambda d: {k: v for k, v in d.items() if k in keep_ids}
    # live rank: sampled teams' live totals, re-paired with the sample's pre-GW ranks (best total -> best rank)
    if live_gw and G == picks_gw and crowd.get("teams") and lv:
        tm = crowd["teams"]
        lt = sorted((t["before"] + sum(live_gw["pts_all"].get(str(el), 0) * m for el, m in t["p"]) for t in tm), reverse=True)  # before already has the hit taken off
        rk = sorted(t["rank"] for t in tm)
        curve = list(zip(rk, lt))
        step = max(1, len(curve) // 80)
        live_gw["rank_curve"] = [list(c) for c in curve[::step]] + ([list(curve[-1])] if (len(curve) - 1) % step else [])
        prev_h = next((h for h in history["current"] if h["event"] == G - 1), None)
        live_gw["rank_before"] = prev_h["overall_rank"] if prev_h else None
        # same basis as the sample: overall total after this GW's hit, before this GW's points
        # this GW's hit as FPL records it (picks, or the history row if picks lag behind). Never infer it from
        # /entry/ summary totals: those can be stale by a bonus adjustment and invent a hit (GW8: 519 vs 523, no hit)
        cur_h = next((h for h in history["current"] if h["event"] == G), None)
        live_gw["hits"] = max(live_gw.get("hits") or 0, cur_h["event_transfers_cost"] if cur_h else 0)
        live_gw["total_before"] = (prev_h["total_points"] if prev_h else 0) - live_gw["hits"]
        live_gw["sample_n"] = len(tm)
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


def pre_deadline_xp(g):
    """{pid: xP} for gameweek g as saved before its deadline (history/proj_gw{g}.json), or None when there is no
    snapshot (before GW8). Review uses it so "projected before the deadline" is what the app actually showed."""
    try:
        snap = json.load(open(os.path.join(HIST, f"proj_gw{g}.json")))
    except Exception:
        return None
    if snap.get("gw") != g:
        return None
    return {int(k): v[0] for k, v in snap.get("players", {}).items()}


# ---- xP table's live column: every player's projection for the gameweek in progress, as saved before its deadline.
# Only while that gameweek is in progress. No snapshot (or one for another GW) -> no xp_cur on anyone and
# meta.xp_cur says why, so the table shows "–" with that reason (never 0) and validate.py warns. The snapshot
# only keeps players projected above 0 by us or by FPL, so a player absent from an existing one was projected 0:
# he gets xp_cur 0 and xp_cur_absent, and the table's tooltip says so. (A player signed after the deadline is
# absent too and also shows 0, with the same tooltip.)
xp_cur_meta = None
if cur_ev and not cur_ev["finished"]:
    snap_cur = pre_deadline_xp(cur_gw)
    if snap_cur is None:
        xp_cur_meta = {"gw": cur_gw, "status": f"missing: no pre-deadline snapshot history/proj_gw{cur_gw}.json"}
    else:
        for pid, prow in players.items():
            prow["xp_cur"] = round(snap_cur.get(pid, 0), 2)
            if pid not in snap_cur:
                prow["xp_cur_absent"] = True
        xp_cur_meta = {"gw": cur_gw, "status": "snapshot", "in_snapshot": len(snap_cur)}

review = {"weeks": [], "transfers": [], "totals": {}}
fh_set = {c["event"] for c in history["chips"] if c["name"] == "freehit"}
wc_set = {c["event"] for c in history["chips"] if c["name"] == "wildcard"}
hist_by = {h["event"]: h for h in history["current"]}
# Each finished gameweek's picks are fetched on their own (FL-070): before, one failed request emptied the whole dict,
# and Review, You vs the model, the template tracker and the journal all came out empty with no message.
# Missing / late: a week whose picks can't be fetched (after get()'s retries) is kept as None, so every section skips
# just that week and lists it in its own "skipped" (review["skipped"] here); validate.py warns on Data health.
past, review_skipped = {}, []
for g in finished_gws:
    if g not in hist_by:
        continue
    try:
        past[g] = picks if g == picks_gw else get(f"/entry/{TEAM_ID}/event/{g}/picks/")
    except Exception as ex:
        print(f"GW{g} picks not fetched:", type(ex).__name__)
        past[g] = None
        review_skipped.append(g)
review["skipped"] = review_skipped
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
    # how the model saw this gameweek beforehand: only the projection saved before its deadline
    # (history/proj_gw{g}.json, GW8 on). Missing (GW1-7, saving began at GW8): no projection, no model captain and
    # proj_src "none", so Review says "no saved forecast"; never a re-run with today's model, which would know things
    # the app didn't know at the time (agreed 4 Nov, F1f)
    sx = pre_deadline_xp(g)
    if sx is not None:
        xi_proj = sum(sx.get(i, 0.0) for i in xi_ids)
        model_cap = max(xi_ids, key=lambda i: sx.get(i, 0.0))
    else:
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
        "proj_src": "snapshot" if sx is not None else "none",   # saved before the deadline, or no saved forecast
        "xi_actual": sum(pts_of(i, g) for i in xi_ids),
    })
# decision score: judge each week's choices on the projections available before it (not on what happened)
def best_xi_by(ids, val):
    ps = sorted(ids, key=lambda i: -val(i))
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
    return xi


for w in review["weeks"]:
    g = w["gw"]
    pk = past.get(g)
    sx = pre_deadline_xp(g)
    if sx is None or not pk:   # no saved forecast (GW1-7): not graded, Review says why (F1f)
        continue
    try:
        pr = project(ctx, g, 3, {"use_flags": False})["players"]
    except Exception:
        continue
    # this gameweek as it was projected before the deadline; the two weeks after it (transfers are judged over 3)
    # from a projection made on data up to that deadline, as before
    xp1 = lambda i: sx.get(i, 0.0)
    xp3 = lambda i: sx.get(i, 0.0) + sum(v for k, v in pr.get(i, {}).get("xp", {}).items() if k != g)
    ids = [p["element"] for p in pk["picks"]]
    chip = pk.get("active_chip")
    xi = ids if chip == "bboost" else [p["element"] for p in pk["picks"] if p["position"] <= 11]
    cap = next(p["element"] for p in pk["picks"] if p["is_captain"])
    cm = 2 if chip == "3xc" else 1
    best_cap = max(xi, key=xp1)
    cap_loss = (xp1(best_cap) - xp1(cap)) * cm
    lineup_loss = 0.0 if chip == "bboost" else sum(xp1(i) for i in best_xi_by(ids, xp1)) - sum(xp1(i) for i in xi)
    tx_gain = sum(xp3(m["in"]) - xp3(m["out"]) for m in w["moves"]) - w["hits"]
    proj_total = sum(xp1(i) for i in xi) + xp1(cap) * cm
    loss = cap_loss + lineup_loss - min(0.0, tx_gain)
    grade = "A" if loss <= 0.5 and tx_gain >= -0.5 else "B" if loss <= 1.5 else "C" if loss <= 3 else "D"
    w["decision"] = {"cap_loss": round(cap_loss, 2), "model_cap": best_cap, "lineup_loss": round(max(0.0, lineup_loss), 2),
                     "tx_gain": round(tx_gain, 2) if w["moves"] else None, "proj": round(proj_total, 1),
                     "luck": round(w["pts"] - proj_total, 1), "grade": grade, "src": "snapshot"}

# each past team as picked: slot, multiplier, real points, and the projection made before that deadline
for w in review["weeks"]:
    pk = past.get(w["gw"])
    if not pk:
        continue
    g = w["gw"]
    sx = pre_deadline_xp(g)   # no saved forecast -> no xP on the cards (None), never a re-run
    w["team"] = [[p["element"], p["position"], p["multiplier"], pts_of(p["element"], g), mins_of(p["element"], g),
                  round(sx.get(p["element"], 0.0), 2) if sx is not None else None] for p in pk["picks"]]
    w["autosubs"] = [[a["element_in"], a["element_out"]] for a in pk.get("automatic_subs", [])]

# ---- template tracker: your team against the top-10k template, week by week
TPL_F = os.path.join(HERE, "crowd", "history.json")
try:
    TPL = json.load(open(TPL_F))
except Exception:
    TPL = {"gws": {}}
if crowd and crowd.get("complete", True) and TPL["gws"].get(str(crowd["gw"]), {}).get("source") != "sample":
    t10 = crowd["top10k"]
    TPL["gws"][str(crowd["gw"])] = {"n": t10["n"], "source": "sample",
                                    **{k: {i: v for i, v in t10[k].items() if v >= 0.5} for k in ("own", "eo", "cap")}}
    json.dump(TPL, open(TPL_F, "w"), separators=(",", ":"))
template = []
for w in review["weeks"]:
    g, pk, tg = w["gw"], past.get(w["gw"]), TPL["gws"].get(str(w["gw"]))
    if not pk or not tg:
        continue
    own, eo = {int(k): v for k, v in tg["own"].items()}, {int(k): v / 100 for k, v in tg["eo"].items()}
    mult = {x["element"]: x["multiplier"] for x in pk["picks"]}
    squad15 = set(mult)
    gain = loss = 0.0
    for i in set(mult) | set(eo):
        d = (min(mult.get(i, 0), 3) - eo.get(i, 0.0)) * pts_of(i, g)
        if d > 0:
            gain += d
        else:
            loss += d
    xi = [i for i, m in mult.items() if m > 0]
    missing = sorted([i for i, v in own.items() if v >= 40 and i not in squad15], key=lambda i: -own[i])
    diffs = [i for i in xi if own.get(i, 0) < 15]
    template.append({"gw": g, "source": tg["source"], "n": tg["n"],
                     "overlap": round(sum(own.get(i, 0) for i in xi) / max(1, len(xi)), 1),
                     "shared": sum(1 for i in squad15 if own.get(i, 0) >= 40), "tpl_size": sum(1 for v in own.values() if v >= 40),
                     "gain": round(gain, 1), "loss": round(loss, 1), "net": round(gain + loss, 1),
                     "missing": [[i, round(own[i]), pts_of(i, g)] for i in missing[:6]],
                     "diffs": [[i, round(own.get(i, 0), 1), pts_of(i, g) * mult[i]] for i in sorted(diffs, key=lambda i: -pts_of(i, g))]})

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
review["no_forecast"] = [w["gw"] for w in review["weeks"] if w["proj_src"] == "none"]
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

# ---------------------------------------------------------------- you vs the model on your own 15 (F1)
# Each finished gameweek, YOUR ACTUAL points (after hits) against the model's HIGHEST PROJECTED score for that week from
# what it suggested before the deadline (agreed 4 Nov): every strategy plan saved in history/deadline_gwN.json (best,
# safe, chase; roll, one or two transfers), each worth its week's xP less 4 per hit, and the best of them is the target
# (fpl_score.best_suggestion), rounded to the nearest point (fpl_score.target). Beat it: win; equal: draw; below: defeat.
# Then the record and winning run (fpl_score.streak).
# Missing / late / ambiguous:
#   - no saved suggestion for the week (history/deadline_gwN.json starts at GW10): the target is assumed instead, from
#     the model's best pick from your own 15 with the forecast saved before that deadline (proj_gwN.json, no hits),
#     and the week is marked target.basis = "your 15" and target.assumed = True so the tab says so;
#   - no saved forecast at all -> no head-to-head for that week, never a re-run with today's model (record starts GW8);
#   - a gameweek not finished yet -> not scored (players still to play would look like non-starters);
#   - picks or live data that couldn't be fetched -> that week is skipped and counted in "skipped".
# Both your team and the model's pick from your 15 are also scored on what happened by FPL's rules (auto-subs, vice,
# chips) for the side-by-side pitches; the suggested XI's actual points are shown too (no auto-subs: its bench isn't
# saved). These are information only. Your side is checked against FPL's own points ("fpl_pts") in validate.py.
vs_model = None
try:
    pos_all = {pid: POS[e["element_type"]] for pid, e in elements.items()}
    vm_weeks, vm_skipped = [], []
    for g, pk in sorted(past.items()):
        f_ = os.path.join(HERE, "history", f"proj_gw{g}.json")
        if not os.path.exists(f_):
            continue
        if not pk or g not in live:
            vm_skipped.append(g)
            continue
        sx = {int(k): v[0] for k, v in json.load(open(f_))["players"].items()}
        played_g = fpl_score.played_from_live(live[g])
        chip = pk.get("active_chip")
        you_t = fpl_score.as_submitted(pk, pos_all)
        squad_g = you_t["xi"] + you_t["bench"]
        mod_t = fpl_score.supercomputer_pick(squad_g, pos_all, sx)
        a, b = fpl_score.score_team(you_t, played_g, chip), fpl_score.score_team(mod_t, played_g, chip)
        side = lambda t, r: {"pts": r["total"], "xi": t["xi"], "bench": t["bench"], "cap": t["captain"], "vice": t["vice"],
                             "armband": r["captain"], "captain_multiplier": r["captain_multiplier"], "subs": r["subs"], "formation": "-".join(
                                 str(sum(pos_all[i] == k for i in r["xi"])) for k in ("DEF", "MID", "FWD"))}
        hits_g = pk["entry_history"].get("event_transfers_cost", 0) or 0
        dl_f = os.path.join(HERE, "history", f"deadline_gw{g}.json")
        dl_ = json.load(open(dl_f)) if os.path.exists(dl_f) else {}
        sug = fpl_score.best_suggestion(dl_.get("plans"), g)
        if sug:   # out[k] -> in[k] like for like (the optimiser doesn't pair them)
            sug["out"], sug["in"] = fpl_score.pair_moves(sug["out"], sug["in"], pos_all)
            sug_pts = sum(played_g.get(i, (0, 0))[1] for i in sug["xi"]) + (sug["captain_multiplier"] - 1) * played_g.get(sug["captain"], (0, 0))[1]
            tgt = {"basis": "suggested", "assumed": False, "exp": round(sug["exp"], 1), "plan": sug["plan"],
                   "captain_multiplier": sug["captain_multiplier"], "xp": sug["xp"], "hits": sug["hits"], "out": sug["out"], "in": sug["in"], "captain": sug["captain"],
                   "xi": sug["xi"], "actual": sug_pts - fpl_score.HIT * sug["hits"],
                   # per player, for the pitch (F1d): xP saved before the deadline (first plan gameweek) and actual
                   "xi_xp": {str(i): (dl_.get("xp", {}).get(str(i)) or [0])[0] for i in sug["xi"]},
                   "xi_pts": {str(i): played_g.get(i, (0, 0))[1] for i in sug["xi"]}}
        else:
            tgt = {"basis": "your 15", "assumed": True, "captain_multiplier": fpl_score.captain_multiplier(chip),
                   "exp": round(fpl_score.expected(mod_t, sx, chip), 1)}
        tgt["par"] = fpl_score.target(sug["exp"] if sug else fpl_score.expected(mod_t, sx, chip))
        you_net = a["total"] - hits_g
        vm_weeks.append({"gw": g, "chip": chip, "res": fpl_score.result(you_net, tgt["par"]), "target": tgt,
                         "you_net": you_net, "hits": hits_g,
                         "you": side(you_t, a), "model": side(mod_t, b), "fpl_pts": pk["entry_history"]["points"],
                         "xp": {str(i): round(sx.get(i, 0.0), 2) for i in squad_g},
                         "pts": {str(i): played_g.get(i, (0, 0))[1] for i in squad_g}})
    # the week to come (F1d): the model's best suggestion so far. The deadline snapshot is rewritten every build until
    # the deadline, so this target can still move until then; missing snapshot or plans -> "target": None (tab says so)
    vm_next = {"gw": next_gw, "deadline": next_ev["deadline_time"] if next_ev else None, "target": None}
    nf_ = os.path.join(HERE, "history", f"deadline_gw{next_gw}.json") if next_gw else None
    if nf_ and os.path.exists(nf_):
        nd_ = json.load(open(nf_))
        ns_ = fpl_score.best_suggestion(nd_.get("plans"), next_gw)
        if ns_:
            ns_["out"], ns_["in"] = fpl_score.pair_moves(ns_["out"], ns_["in"], pos_all)
            vm_next["target"] = {"exp": round(ns_["exp"], 1), "par": fpl_score.target(ns_["exp"]), "plan": ns_["plan"],
                                 "captain_multiplier": ns_["captain_multiplier"], "hits": ns_["hits"], "out": ns_["out"], "in": ns_["in"], "captain": ns_["captain"],
                                 "xi": ns_["xi"], "built": nd_.get("built")}
    if vm_weeks:
        st_ = fpl_score.streak([w["res"] for w in vm_weeks], season_from_gw1=vm_weeks[0]["gw"] == 1)
        vs_model = {"from_gw": vm_weeks[0]["gw"], "weeks": vm_weeks, "skipped": vm_skipped, **st_,
                    "next": vm_next}
except Exception as ex:   # never let this stop the build; the tab says it's unavailable
    print("you vs the model not built:", ex)
    vs_model = None

# ---------------------------------------------------------------- decision journal (D5a)
# Each gameweek whose deadline has passed and that has a deadline snapshot (history/deadline_gwN.json, GW10 on): your
# transfers and captain next to the model's suggestion for that week (the same plan the You vs the model target uses),
# with what the app knew about every player involved before the deadline (decision_journal.py has the rules).
# Missing / late / ambiguous: no snapshot -> no entry, the week is listed in "no_snapshot" (GW8 and GW9: saving began at
# GW10); picks for the week not fetched -> skipped and listed in "skipped"; the gameweek in progress counts once its
# deadline has passed (its picks are then final). Never stops the build: on an error, journal is None and the tab says so.
journal = None
try:
    jw, j_none, j_skip = [], [], []
    j_picks = dict(past)
    if picks and picks_gw and picks_gw not in j_picks:
        j_picks[picks_gw] = picks
    for g in sorted(set(j_picks) | ({picks_gw} if picks_gw else set())):
        if g < 8:
            continue
        dl_f = os.path.join(HIST, f"deadline_gw{g}.json")
        if not os.path.exists(dl_f):
            j_none.append(g)
            continue
        pk = j_picks.get(g)
        if not pk:
            j_skip.append(g)
            continue
        dl_ = json.load(open(dl_f))
        pj_f = os.path.join(HIST, f"proj_gw{g}.json")
        mine = [[t["element_out"], t["element_in"]] for t in sorted(transfers, key=lambda t: t["time"]) if t["event"] == g]
        best_ = fpl_score.best_suggestion(dl_.get("plans"), g)
        if best_:
            best_["out"], best_["in"] = fpl_score.pair_moves(best_["out"], best_["in"], pos_all)
        jw.append(decision_journal.entry(g, dl_, json.load(open(pj_f)) if os.path.exists(pj_f) else None, mine, pk,
                                         fixtures, best_,
                                         {pid: e["team"] for pid, e in elements.items()}))
    # how each call turned out so far (D5c): every finished gameweek's minutes, points and starts from FPL's live data
    j_played = {g: {el["id"]: (el["stats"]["minutes"], el["stats"]["total_points"], el["stats"].get("starts", 0))
                    for el in live[g]["elements"]} for g in finished_gws if g in live}
    for e_ in jw:
        e_["outcome"] = decision_journal.outcome(e_, j_played, finished_gws)
    journal = {"weeks": jw, "no_snapshot": j_none, "skipped": j_skip}
except Exception as ex:   # never let this stop the build
    print("decision journal not built:", ex)
    journal = None

# ---------------------------------------------------------------- set pieces (with change history)
sp_now = {}
for tid in teams:
    row = {}
    for key, field in (("pen", "penalties_order"), ("cor", "corners_and_indirect_freekicks_order"), ("fk", "direct_freekicks_order")):
        takers = sorted([e for e in elements.values() if e["team"] == tid and e.get(field)], key=lambda e: e[field])
        row[key] = [e["id"] for e in takers[:3]]
    sp_now[str(tid)] = row
# The change list is kept in history/setpieces.json (setpiece_log.py, FL-069), committed with the rest of history/.
# The deployed data.json, the list's old home, is only read when that file is missing (to seed it) or unreadable;
# setpieces["status"] says which, for Data health and the Stats page.


def _deployed():
    prev_url = os.environ.get("PAGES_DATA_URL", "https://afg-design.github.io/FPL-Lab/data.json")
    with urllib.request.urlopen(urllib.request.Request(prev_url, headers={"User-Agent": "fpl-lab"}), timeout=15) as r:
        return json.load(r)


sp_season = f"{events[0]['deadline_time'][:4]}-{str(int(events[0]['deadline_time'][:4]) + 1)[2:]}"
setpieces = setpiece_log.update(os.path.join(HERE, "history", "setpieces.json"), sp_now,
                                dt.datetime.now(dt.timezone.utc), sp_season, _deployed)
sp_changes = setpieces["changes"]

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
    team_out[tid] = {"id": tid, "short": t["short_name"], "name": t["name"], "code": t["code"],
                     "sp": ({"for": round(usT.get("sp_for", 0) / max(1, usT["games"]), 2), "against": round(usT.get("sp_against", 0) / max(1, usT["games"]), 2),
                             "op_for": round(usT.get("op_for", 0) / max(1, usT["games"]), 2), "op_against": round(usT.get("op_against", 0) / max(1, usT["games"]), 2),
                             "games": int(usT["games"])} if usT else None),
                     "att": round(rating[tid]["att"], 2), "def": round(rating[tid]["def"], 2), "trend": trend,
                     "fx": {g: [{"opp": o, "home": h, "xgf": round(mf, 2), "xga": round(ma, 2), "fdr": fd, "eu": euro_flags.get((tid, g))}
                                for (o, h, mf, ma, fd) in upcoming[tid].get(g, [])] for g in proj_gws},
                     # every remaining fixture for the rest of the season: [gw, opponent, home, FPL difficulty]. Fixture
                     # swings read the next 12 GWs; Fixtures shows up to GW38 (C5). A fixture FPL hasn't given a
                     # gameweek yet (postponed, gg None) isn't listed; FPL's difficulty is None if missing.
                     "far": sorted([gg, opp, home, f["team_h_difficulty"] if home else f["team_a_difficulty"]]
                                   for (gg, opp, home, f) in ctx["team_fix"][tid] if next_gw and gg and gg >= next_gw)}

# ---------------------------------------------------------------- AFG suggestion (fan-factor punt layer; the model is unchanged)
afg_out = None
try:
    import afg
    season = f"{events[0]['deadline_time'][:4]}-{str(int(events[0]['deadline_time'][:4]) + 1)[2:]}"
    afg_rec = afg.load_records()
    afg_R = afg.merge(afg_rec, afg.summarise(afg.residuals(afg.live_rows(boot, fixtures, model_live, season))))
    afg_teams = {tid: {"name": afg.canon(t["name"]), "short": t["short_name"]} for tid, t in teams.items()}
    afg_A = afg.suggest(afg_R, players, upcoming, afg_teams, next_gw, season, euro_flags, afg.load_manual()) if next_gw else {}
    afg_pk = afg.picks(squad_ids, sell, bank, players, afg_A) if squad_ids and afg_A else None
    if afg_pk:
        for m in afg_pk["punts"]:
            m["alt"] = afg.model_alt(m["out"], squad_ids, sell, bank, players, next_gw)
        # this week's calls, saved until the deadline so the scoreboard can mark them afterwards
        if next_ev and dt.datetime.now(dt.timezone.utc) < dt.datetime.fromisoformat(next_ev["deadline_time"].replace("Z", "+00:00")):
            json.dump({"gw": next_gw, "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                       "afg_cap": afg_pk["cap"], "afg_xi": afg_pk["xi"], "model_cap": lineup.get("captain"),
                       "model_xi": lineup.get("xi", []), "punts": afg_pk["punts"],
                       "players": {str(i): [a["m"], a["x"]] for i, a in afg_A.items()}},
                      open(os.path.join(HIST, f"afg_gw{next_gw}.json"), "w"), separators=(",", ":"))
    afg_board = []
    for g in finished_gws:
        fpath = os.path.join(HIST, f"afg_gw{g}.json")
        if os.path.exists(fpath):
            afg_board.append(afg.score_week(
                json.load(open(fpath)), lambda i, g=g: ctx["pts_gw"].get(i, {}).get(g, 0) if i else 0,
                lambda i, g=g: any(pstats.get(i, {}).get(k, {}).get("minutes", 0) > 0 for k in range(g - 3, g))))
    try:
        afg_bt = json.load(open(os.path.join(HERE, "afg", "backtest.json")))
        afg_bt.pop("weeks", None)
    except Exception:
        afg_bt = None
    afg_show = {i: a for i, a in afg_A.items() if i in squad_ids or a["m"] >= 2 or abs(a["n"]) >= 0.3}
    afg_out = {"gw": next_gw, "season": season, "records_built": afg_rec.get("built"), "seasons": afg_rec.get("seasons", []),
               "p": {i: {"x": a["x"], "m": a["m"], "n": a["n"], "why": a["why"]} for i, a in afg_show.items()},
               "picks": afg_pk, "board": afg_board, "backtest": afg_bt,
               "set": {k: afg.SET[k] for k in ("hot", "euro", "new_mgr", "cap")}}
    keep_extra |= set(afg_show)
    keep_extra |= {m[k] for m in (afg_pk or {}).get("punts", []) for k in ("in", "out", "alt") if m.get(k)}
    keep_extra |= {x for w in afg_board for x in [w["afg_cap"], w["model_cap"]] + [m[k] for m in w["punts"] for k in ("in", "out", "alt")] if x}
except Exception as ex:
    import traceback
    traceback.print_exc()
    print("AFG suggestion skipped:", ex)

keep = {i for i, p in players.items() if p["mins"] > 0 or p["xp5"] > 3 or i in squad_ids}
keep |= {t["element_in"] for t in transfers} | {t["element_out"] for t in transfers}
keep |= {w[k] for w in review["weeks"] for k in ("captain", "best_cap", "model_cap") if w.get(k)}
keep |= {i for row in sp_now.values() for v in row.values() for i in v}
keep |= {c[k] for c in sp_changes for k in ("old", "new") if c.get(k)}
keep |= keep_extra
keep |= {t[0] for w in review["weeks"] for t in w.get("team", [])}
keep |= {int(i) for t_ in [w["target"] for w in (vs_model or {}).get("weeks", [])] + [((vs_model or {}).get("next") or {}).get("target") or {}]
         for i in t_.get("xi", []) + t_.get("in", []) + t_.get("out", [])}
keep |= {int(i) for w in (vs_model or {}).get("weeks", []) for i in w["xp"]}
keep |= {int(i) for w in (journal or {}).get("weeks", []) for i in w["players"]}
keep |= {x[0] for t in template for k in ("missing", "diffs") for x in t[k]}
keep = {i for i in keep if i in players}
for i in set().union(*[set(w["in"]) | set(w["xi"]) | set(w["bench"]) for pl in plans.values() for w in pl["weeks"]]) if plans else set():
    keep.add(i)

# ---------------------------------------------------------------- history logs that can't be rebuilt
def load_log(path, empty, valid):
    """A history/ log this build updates (news.json, prices.json), protected the way status.json is (FL-120).
    Returns (data, ok). Missing file (first run): a fresh copy of `empty`, ok. Unreadable, or not the expected shape
    (valid(data) is False): an empty copy for this build only and ok False, so save_log leaves the file alone (its
    history can't be rebuilt) and data.json's sources say so for validate.py (Data health warning)."""
    try:
        with open(path) as f:
            data = json.load(f)
        if not valid(data):
            raise ValueError("unexpected shape")
        return data, True
    except FileNotFoundError:
        return json.loads(json.dumps(empty)), True
    except Exception as ex:
        print(f"{os.path.relpath(path, HERE)} unreadable, not updating it:", ex)
        return json.loads(json.dumps(empty)), False


def save_log(path, data, ok):
    if not ok:
        return                       # never overwrite a log that failed to load
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    os.replace(tmp, path)            # atomic: a crash mid-write can't leave a half-written log


# ---------------------------------------------------------------- injury news history
# Every change to a player's FPL status, chance of playing or news text, timed by FPL's own news_added
NEWS_F = os.path.join(HIST, "news.json")
NH, news_ok = load_log(NEWS_F, {}, lambda d: isinstance(d, dict) and all(isinstance(v, list) for v in d.values()))
now_iso = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
for e in elements.values():
    k = str(e["id"])
    cur = [e["status"], e.get("chance_of_playing_next_round"), (e.get("news") or "").strip()]
    hist = NH.get(k, [])
    if hist and hist[-1][1:] == cur:
        continue
    if not hist and cur[0] == "a" and not cur[2]:
        continue                     # fit and never flagged since we started: nothing to record
    when = e.get("news_added") or now_iso
    if hist and when <= hist[-1][0]:
        when = now_iso               # cleared or edited without a new timestamp
    NH[k] = (hist + [[when[:19] + "Z" if not when.endswith("Z") and "+" not in when else when] + cur])[-10:]
cut = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=90)).isoformat()
NH = {k: v for k, v in NH.items() if v[-1][0] > cut or v[-1][1] != "a"}
save_log(NEWS_F, NH, news_ok)
for k, v in NH.items():
    if int(k) in players:
        players[int(k)]["newsh"] = v
relevant = lambda i: i in players and (players[i]["mins"] > 0 or players[i]["xp5"] > 1 or i in squad_ids)
news_feed = sorted(([v[-1][0], int(k), v[-2][1:] if len(v) > 1 else None, v[-1][1:]] for k, v in NH.items()
                    if relevant(int(k))), reverse=True)[:60]
for _, pid, _, _ in news_feed:
    keep.add(pid)

# ---------------------------------------------------------------- price change tracker
# Before each nightly price update we keep FPL's projection for tonight and everyone's price; a few hours after it,
# we compare: who actually moved, and how often FPL's projection bands turned out right.
PRICE_F = os.path.join(HIST, "prices.json")
PH, prices_ok = load_log(PRICE_F, {"pending": {}, "nights": []},
                         lambda d: isinstance(d, dict) and isinstance(d.get("pending"), dict) and isinstance(d.get("nights"), list))
now_utc = dt.datetime.now(dt.timezone.utc)
pdl = [dt.datetime.fromisoformat(x.replace("Z", "+00:00")) for x in boot["game_config"]["settings"].get("price_change_deadlines", [])]
nxt = min((d for d in pdl if d > now_utc), default=None)
if nxt:
    key = nxt.isoformat()
    PH["pending"][key] = {"pred": {str(e["id"]): float(e["price_change_projections"][0]["projected_percent"])
                                   for e in elements.values() if e.get("price_change_projections")},
                          "cost": {str(e["id"]): e["now_cost"] for e in elements.values()}}
for key in sorted(PH["pending"]):
    if now_utc < dt.datetime.fromisoformat(key) + dt.timedelta(hours=4):
        continue                                     # changes land at about the listed time (midnight UK); 4h is a safe margin
    snap = PH["pending"].pop(key)
    rows = []
    for pid, c0 in snap["cost"].items():
        e = elements.get(int(pid))
        if not e:
            continue
        ch = e["now_cost"] - c0
        pr = snap["pred"].get(pid, 0.0)
        if ch or abs(pr) >= 50:
            rows.append([int(pid), round(pr, 1), ch])
    PH["nights"].append({"night": key, "rows": rows})
PH["nights"] = PH["nights"][-40:]
PH["pending"] = {k: v for k, v in PH["pending"].items() if dt.datetime.fromisoformat(k) > now_utc - dt.timedelta(days=3)}
save_log(PRICE_F, PH, prices_ok)

BANDS = [("100%+", 100, 1e9), ("90–100%", 90, 100), ("75–90%", 75, 90), ("50–75%", 50, 75)]
price_out = {"nights": len(PH["nights"]), "bands": [], "last": None, "pending_night": nxt.isoformat() if nxt else None}
for dirn, sgn_ in (("rise", 1), ("fall", -1)):
    for lab, lo, hi in BANDS:
        n = hit = 0
        for nt in PH["nights"]:
            for pid, pr, ch in nt["rows"]:
                if lo <= pr * sgn_ < hi:
                    n += 1; hit += (ch * sgn_ > 0)
        price_out["bands"].append({"dir": dirn, "band": lab, "lo": lo, "n": n, "hit": hit})
# surprise moves: changes FPL's projection didn't see coming (under 50%)
miss = sum(1 for nt in PH["nights"] for pid, pr, ch in nt["rows"] if ch and pr * (1 if ch > 0 else -1) < 50)
price_out["unpredicted"] = miss
price_out["changes"] = sum(1 for nt in PH["nights"] for r in nt["rows"] if r[2])
if PH["nights"]:
    lt = PH["nights"][-1]
    price_out["last"] = {"night": lt["night"], "rows": [r for r in lt["rows"] if r[2]]}
    for pid, _, _ in price_out["last"]["rows"]:
        if pid in players:
            keep.add(pid)

# ---------------------------------------------------------------- squad rating
# Your squad as it stands is compared with (a) the best 15 you could own for the same money, built once and
# held, and (b) the average top-10k team (effective ownership x projections), over the plan gameweeks.
rating = None
if squad_ids and proj_gws:
    gws_r = proj_gws[:PLAN_GWS]
    budget = bank + sum(sell.values())
    try:
        wc = optimise.solve(opt_players, [], {}, budget, 5, gws_r, hit=0, ft_value=0, max_moves_week=15, freeze_after=1, time_limit=60)
    except Exception as ex:
        print("squad rating solve failed:", ex); wc = None
    field_eo = {}
    try:
        field_eo = {int(k): v / 100 for k, v in json.load(open(os.path.join(HERE, "crowd", "latest.json")))["top10k"]["eo"].items()}
    except Exception:
        pass
    if wc:
        w0 = wc["weeks"][0]
        rating = {"gws": gws_r, "budget": round(budget, 1),
                  "best": {"squad": sorted(set(w0["xi"]) | set(w0["bench"])), "xi": w0["xi"], "captain": w0["captain"],
                           "weeks": [round(wk["xp"], 2) for wk in wc["weeks"]]},
                  "field": [round(sum(f * players[i]["xp"].get(g, 0) for i, f in field_eo.items() if i in players), 2) for g in gws_r] if field_eo else None}
        keep.update(i for i in rating["best"]["squad"] if i in players)

# ---------------------------------------------------------------- compare any team: watch.json + the overall leader
watch_out = []
try:
    wl = [w for w in json.load(open(os.path.join(HERE, "watch.json"))).get("teams", []) if int(w.get("id", 0)) != TEAM_ID]
except Exception:
    wl = []
try:
    lead = get("/leagues-classic/314/standings/")["standings"]["results"][0]
    wl = [{"id": lead["entry"], "label": "Overall leader", "auto": True}] + [w for w in wl if int(w["id"]) != lead["entry"]]
except Exception:
    pass
for w in wl[:20]:
    try:
        wid = int(w["id"])
        e = get(f"/entry/{wid}/", tries=2)
        hst = get(f"/entry/{wid}/history/", tries=2)
        g = e.get("current_event")
        pk = get(f"/entry/{wid}/event/{g}/picks/", tries=2) if g else None
    except Exception as ex:
        watch_out.append({"entry": int(w.get("id", 0)), "label": w.get("label"), "error": str(ex)[:80]})
        continue
    watch_out.append({
        "entry": wid, "label": w.get("label"), "auto": bool(w.get("auto")),
        "player": f'{e["player_first_name"]} {e["player_last_name"]}', "team": e["name"],
        "rank": e.get("summary_overall_rank"), "total": e.get("summary_overall_points"), "gw_pts": e.get("summary_event_points"),
        "gw": g, "picks": [[x["element"], x["multiplier"]] for x in pk["picks"]] if pk else None,
        "chip": pk.get("active_chip") if pk else None, "hits": pk["entry_history"]["event_transfers_cost"] if pk else 0,
        "bank": pk["entry_history"]["bank"] / 10 if pk else None, "value": pk["entry_history"]["value"] / 10 if pk else None,
        "chips": [{"name": c["name"], "event": c["event"]} for c in hst.get("chips", [])],
        "hist": [[h["event"], h["points"], h["overall_rank"]] for h in hst.get("current", [])]})
    for el, _ in (watch_out[-1]["picks"] or []):
        if el in players:
            keep.add(el)

# which minutes model fed next gameweek: validate.py fails the publish if xMins was on but players fell back to counts
_fx_next = {t for f in fixtures if f["event"] == next_gw for t in (f["team_h"], f["team_a"])}
_msrc = Counter(r["min_src"] for pid, r in (res["players"] if res else {}).items()
                if elements[pid]["team"] in _fx_next)
out = {
    "meta": {"built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "team_id": TEAM_ID,
             "minutes_model": {"xmins_on": bool(DEFAULTS["xmins"]), "xmins": _msrc.get("xmins", 0),
                               "counts": _msrc.get("counts", 0)},
             "understat": US.get("meta"),
             # finished Premier League matches so far, so the site and validate.py can say how many of them the
             # Understat file covers (it keeps its last good copy when Understat is down)
             "finished_fixtures": sum(1 for f in fixtures if f.get("event") and f.get("finished")),
             "odds": {"built": market.get("built"), "matches": len(market.get("matches", [])),
                      "upcoming": sum(1 for m in market.get("matches", []) if not m["played"])} if market else None,
             "player_odds": {"built": player_odds.get("built"), "gw": player_odds.get("gw"),
                             "fixtures": len(player_odds.get("fixtures", {})),
                             "players": sum(len(f["players"]) for f in player_odds.get("fixtures", {}).values()),
                             "unmatched": len(player_odds.get("unmatched_players", [])),
                             "credits_left": player_odds.get("credits_left")} if player_odds else None,
             "special_shirts": bool(boot["game_config"]["rules"].get("ui_use_special_shirts")),
             "special_excl": boot["game_config"]["rules"].get("ui_special_shirt_exclusions", []),
             "cur_gw": cur_gw, "next_gw": next_gw, "cur_finished": bool(cur_ev and cur_ev["finished"]),
             # FL-060: True after GW38's deadline (no next gameweek); last_gw lets validate.py tell that from an API fault
             "season_over": season_over, "last_gw": max((e["id"] for e in events), default=None),
             # The two model settings the site restates (clean-sheet %, far-fixture estimates), straight from DEFAULTS so
             # the browser never hard-codes them. Missing in an older data.json: the site falls back, see modelSet().
             "model": {"home": DEFAULTS["home"], "cs_k": DEFAULTS["cs_k"]},
             "xp_cur": xp_cur_meta,   # xP table live column: snapshot used, or why it's missing (None outside a live GW)
             "deadline": next_ev["deadline_time"] if next_ev else None, "proj_gws": proj_gws, "plan_gws": proj_gws[:PLAN_GWS],
             "league_goals": round(res["league"], 2) if res else None, "picks_gw": picks_gw, "finished_gws": finished_gws,
             "squad_gw": squad_gw, "fh_restored": fh_active,   # squad and bank come from GW squad_gw (the week before a Free Hit)
             "price_deadlines": boot["game_config"]["settings"].get("price_change_deadlines", []),
             # FL-072: whether the status log and europe.json loaded (validate.py check_sources)
             "status_log": {"state": status_state, "gws": status_loaded_gws, "error": status_err},
             "europe": {"state": euro_state, "competitions": euro_n, "unconfirmed": euro_skipped, "error": euro_err},
             "priors_season": next(iter((priors or {}).get("players", {}).values()), {}).get("season"),
             "prev_built": prev_built,   # the refresh before this one (None: unknown), for validate.py's gap warning
             "build_secs": None},
    "manager": {"name": f'{entry["player_first_name"]} {entry["player_last_name"]}', "team": entry["name"],
                "points": history["current"][-1]["total_points"] if history["current"] else entry["summary_overall_points"], "rank": entry["summary_overall_rank"],
                "gw_points": entry.get("summary_event_points"), "gw_rank": entry.get("summary_event_rank"),
                "bank": bank, "value": team_value,
                "free_transfers": ft, "total_players": boot["total_players"]},
    "history": [{"gw": h["event"], "pts": h["points"], "rank": h["overall_rank"], "gw_rank": h["rank"],
                 "bench": h["points_on_bench"], "tx": h["event_transfers"], "hit": h["event_transfers_cost"],
                 "chip": chips_by_gw.get(h["event"])} for h in history["current"]],
    "squad": [{"id": p["element"], "slot": p["position"], "cap": p["is_captain"], "vice": p["is_vice_captain"],
               "buy": purchase_price(p["element"]) / 10, "sell": selling_price(p["element"]) / 10}
              for p in (own_picks["picks"] if own_picks else [])],
    "lineup": lineup, "plans": plans, "plan_notes": plan_notes,
    "plan_rules": {"ft_value": optimise.FT_VALUE, "safe_budget": optimise.SAFE_BUDGET, "chase_budget": optimise.CHASE_BUDGET, "min_profit": optimise.MIN_PROFIT, "hit_gain": optimise.HIT_GAIN, "max_hits": optimise.MAX_HITS,
                   "tie": optimise.TIE, "strategy": optimise.STRATEGY},
    "accuracy": accuracy,
    "crowd": crowd_out, "watch": watch_out, "prices": price_out, "rating": rating, "template": template, "news": news_feed, "review": review, "vs_model": vs_model, "journal": journal, "setpieces": setpieces,
    "chips": chips, "gw_info": gw_info, "season_gws": season_gws, "live": live_gw, "teams": team_out, "afg": afg_out,
    "players": [players[i] for i in sorted(keep, key=lambda i: -players[i]["xp5"])],
}
# ---------------------------------------------------------------- club badges (downloaded once into site/badges/)
BADGE_DIR = os.path.join(os.path.dirname(os.path.abspath(OUT)), "badges")
os.makedirs(BADGE_DIR, exist_ok=True)
BADGE_URLS = ["https://resources.premierleague.com/premierleague25/badges-alt/{c}.png",
              "https://resources.premierleague.com/premierleague/badges/100/t{c}@x2.png",
              "https://resources.premierleague.com/premierleague/badges/70/t{c}.png",
              "https://resources.premierleague.com/premierleague/badges/t{c}.png"]
badges_ok = []
for t in boot["teams"]:
    dest = os.path.join(BADGE_DIR, f"{t['code']}.png")
    if not os.path.exists(dest):
        for u in BADGE_URLS:
            try:
                req = urllib.request.Request(u.format(c=t["code"]), headers={"User-Agent": "Mozilla/5.0 fpl-lab"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    data_ = r.read()
                if data_[:8] == b"\x89PNG\r\n\x1a\n" and len(data_) > 500:
                    open(dest, "wb").write(data_)
                    break
            except Exception:
                continue
    if os.path.exists(dest):
        badges_ok.append(t["code"])
out["meta"]["badges"] = badges_ok

# ---------------------------------------------------------------- shot maps (separate file, loaded when a player is opened)
try:
    shots_c = json.load(open(os.path.join(HERE, "understat", "shots.json")))
    us_to_fpl = {v["us_id"]: int(k) for k, v in US.get("players", {}).items()}
    RES = {"Goal": "G", "SavedShot": "S", "MissedShots": "M", "BlockedShot": "B", "ShotOnPost": "P", "OwnGoal": "O"}
    SIT = {"OpenPlay": "O", "FromCorner": "C", "SetPiece": "S", "DirectFreekick": "F", "Penalty": "P"}
    smap = defaultdict(list)
    for mid, m in sorted(shots_c.get("matches", {}).items(), key=lambda kv: kv[1]["date"]):
        for sh in m["shots"]:
            fid = us_to_fpl.get(sh[0])
            if fid in keep:
                smap[fid].append([round(sh[2] * 100, 1), round(sh[3] * 100, 1), round(sh[4], 2), RES.get(sh[5], "M"),
                                  SIT.get(sh[6], "O"), 1 if sh[9] == "Head" else 0, m["date"]])
    json.dump({"built": out["meta"]["built"], "players": smap}, open(os.path.join(os.path.dirname(os.path.abspath(OUT)), "shots.json"), "w"), separators=(",", ":"))
except Exception as ex:
    print("shot maps skipped:", ex)

# ---------------------------------------------------------------- this week: deadline, price updates, kick-offs, Europe
TBS = {t["short_name"]: t["id"] for t in boot["teams"]}
try:
    euro = json.load(open(os.path.join(HERE, "europe.json")))
except Exception:
    euro = {"competitions": {}}
if next_ev:
    nx_fx = sorted([f for f in fixtures if f["event"] == next_gw and f["kickoff_time"]], key=lambda f: f["kickoff_time"])
    after = next((e for e in events if e["id"] == next_gw + 1), None)
    end = max(nx_fx[-1]["kickoff_time"][:10] if nx_fx else next_ev["deadline_time"][:10], (after or next_ev)["deadline_time"][:10])
    start = dt.datetime.now(dt.timezone.utc).date().isoformat()
    out["week"] = {
        "gw": next_gw, "deadline": next_ev["deadline_time"],
        "price_updates": [d for d in out["meta"]["price_deadlines"] if start <= d[:10] <= end],
        "fixtures": [[f["kickoff_time"], f["team_h"], f["team_a"]] for f in nx_fx],
        "europe": [[c + (" (dates unconfirmed)" if v.get("confirmed") is False else ""), d, [TBS[t] for t in v["teams"] if t in TBS]]
                   for c, v in euro.get("competitions", {}).items() for d in v.get("dates", []) if start <= d <= end],
        "deadlines": [[e["id"], e["deadline_time"]] for e in events if e["deadline_time"] and e["deadline_time"] > dt.datetime.now(dt.timezone.utc).isoformat()],
    }

# ---------------------------------------------------------------- data health: when each source last updated
def _load(path):
    try:
        return json.load(open(os.path.join(HERE, path)))
    except Exception:
        return None
po_ = _load("odds/players.json") or {}
cr_ = _load("crowd/latest.json") or {}
st_ = _load("history/status.json") or {}
out["sources"] = {
    "fpl": {"built": out["meta"]["built"], "gw": cur_gw, "players": len(elements)},
    "understat": US.get("meta") or None,
    "odds": out["meta"].get("odds"),
    "player_odds": {"built": po_.get("built"), "gw": po_.get("gw"), "fixtures": len(po_.get("fixtures") or {}),
                    "credits_left": po_.get("credits_left"), "unmatched": len(po_.get("unmatched_players") or []),
                    "error": (po_.get("last_error") or {}) or None} if po_ else None,
    "crowd": {"gw": cr_.get("gw"), "built": cr_.get("built"), "top10k": (cr_.get("top10k") or {}).get("n"),
              "near": (cr_.get("near") or {}).get("n"), "teams": len(cr_.get("teams") or []), "rivals": len(cr_.get("rivals") or {})} if cr_ else None,
    # ok False: the file was unreadable, not updated, and this build's figures start from nothing (FL-120)
    "prices": {"nights": len(PH.get("nights", [])), "pending": len(PH.get("pending", {})), "ok": prices_ok},
    "news": {"players": len(NH), "ok": news_ok},
    "status": {"gws": sorted(int(g) for g in (st_.get("gws") or {})), "updated": st_.get("updated")},
    "template": {"gws": sorted(int(g) for g in TPL.get("gws", {}))},
    # pre-deadline snapshots kept (deadline_snapshot.py); data only, not shown yet
    "deadline": {"gws": sorted(int(f_[11:-5]) for f_ in os.listdir(HIST) if f_.startswith("deadline_gw") and f_.endswith(".json"))},
}

out["meta"]["build_secs"] = round(time.time() - t0, 1)
# Detail only Stats, Players and the player panel use goes in a second file the site loads in the background,
# so the main file (Home, Planner, Rivals) is small and opens quickly on a phone.
EXTRA_FIELDS = ("us", "bf4", "bf6", "dcs", "dc6", "ga6", "s_xgi", "s_min", "s_bps", "s_pts", "last", "xp_detail")
extra = {}
for p_ in out["players"]:
    ex = {k: p_.pop(k) for k in EXTRA_FIELDS if k in p_}
    if ex:
        extra[str(p_["id"])] = ex
with open(os.path.join(os.path.dirname(os.path.abspath(OUT)), "data-extra.json"), "w") as f:
    json.dump({"built": out["meta"]["built"], "players": extra,
               # Independent API history/picks evidence: never derive this from own_picks or fh_active.
               "squad_source": squad_state.validation_source(history, picks_gw, next_gw,
                   lambda g: get(f"/entry/{TEAM_ID}/event/{g}/picks/"), TEAM_ID)}, f, separators=(",", ":"))
with open(OUT, "w") as f:
    json.dump(out, f, separators=(",", ":"))
print(f"wrote {OUT}: {len(out['players'])} players, GW{next_gw}, FT {ft}, plans {list(plans)}, {out['meta']['build_secs']}s")
