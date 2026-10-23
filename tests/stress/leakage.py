#!/usr/bin/env python3
"""1. Look-ahead leakage: does a backtest at GW k use anything from GW k or later?
Each check removes one leak and re-scores; the difference is how much the leak flatters the bench."""
import json, copy
from collections import defaultdict
from common import *
from fplmodel import project, POS

C = cur_ctx(); K = range(3, cur_last() + 1)
A, TA = arch()
base1 = score(run_ctx(C, K)); base2 = score(run_ctx(A, range(4, 39), team_at=TA))
print(fmt("baseline [26/27]", base1)); print(fmt("baseline [25/26]", base2))
res = {}

# ---- L1: DC thresholds learned from all gameweeks (incl. GW k and later)
def thr_asof(ctx, k):
    thr = {}
    for pid, gws in ctx["dc_hit"].items():
        e = ctx["elements"].get(pid)
        if not e: continue
        pos = POS[e["element_type"]]
        for g, h in gws.items():
            if h and g < k:
                thr[pos] = min(thr.get(pos, 99), ctx["pstats"][pid][g]["defensive_contribution"])
    for p, v in (("DEF", 10), ("MID", 12), ("FWD", 12)): thr.setdefault(p, v)
    return thr

def run_thr(ctx, gws, fn, team_at=None):
    out = {}
    for k in gws:
        cx = dict(ctx); cx["dc_thr"] = fn(ctx, k)
        out.update(run_ctx(cx, [k], team_at=team_at))
    return out
m = score(run_thr(C, K, thr_asof)); res["L1 dc_thr as-of"] = delta(base1, m); print(fmt("L1 dc_thr as-of [26/27]", m))
m = score(run_thr(C, K, lambda c, k: {"DEF": 10, "MID": 12, "FWD": 12})); res["L1b dc_thr = FPL rules (FWD 12)"] = delta(base1, m)
print(fmt("L1b FPL rule thr [26/27]", m))

# ---- L2: past xG credited to the player's CURRENT club (current season; archive already fixes it)
fx = {f["id"]: f for f in C["fixtures"]}
import urllib.request
def summary(pid):
    req = urllib.request.Request(f"https://fantasy.premierleague.com/api/element-summary/{pid}/", headers={"User-Agent": "Mozilla/5.0 fpl-lab"})
    return json.load(urllib.request.urlopen(req, timeout=30))
tgx = defaultdict(lambda: defaultdict(float)); moved = 0; side = {}
lives = {g: json.load(open(f"raw/live{g}.json"))["elements"] for g in range(1, cur_last() + 1)}
for g, L in lives.items():
    for x in L:
        e = C["elements"].get(x["id"])
        if e and x["stats"]["minutes"] > 0 and any(e["team"] not in (fx[ex["fixture"]]["team_h"], fx[ex["fixture"]]["team_a"]) for ex in x["explain"]):
            if x["id"] not in side:
                side[x["id"]] = {h["fixture"]: h["was_home"] for h in summary(x["id"])["history"]}
for pid, gws in C["pstats"].items():
    e = C["elements"].get(pid)
    if not e: continue
    for g, st in gws.items():
        t = e["team"]
        if pid in side:
            for x in lives[g]:
                if x["id"] == pid and x["explain"]:
                    f = fx[x["explain"][0]["fixture"]]
                    if t not in (f["team_h"], f["team_a"]):
                        t = f["team_h"] if side[pid].get(f["id"], True) else f["team_a"]; moved += 1
        tgx[t][g] += float(st["expected_goals"])
C2 = dict(C); C2["team_gw_xg"] = tgx
m = score(run_ctx(C2, K)); res["L2 as-of club xG"] = delta(base1, m); print(fmt(f"L2 as-of club xG ({moved} rows) [26/27]", m))

# ---- L3: cleared-news absences (news_absences) feed the backtest's 'flag at that deadline' rule
C3 = dict(C); C3["out"] = {p: set(v) for p, v in C["out"].items()}
for pid, g in C["out_news"].items(): C3["out"][pid].discard(g)
m = score(run_ctx(C3, K)); res["L3 news_out removed from hist flags"] = delta(base1, m); print(fmt("L3 no news_out flags [26/27]", m))
# how the affected players were scored in GW7 with and without
p7 = {p: r["xp"][7] for p, r in project(C, 7, 1, {"use_flags": False})["players"].items()}
p7b = {p: r["xp"][7] for p, r in project(C3, 7, 1, {"use_flags": False})["players"].items()}
for pid in C["out_news"]:
    print(f"   {C['elements'][pid]['web_name']:<14} GW7 pred with leak {p7[pid]:.2f}, without {p7b[pid]:.2f}, actual {C['pts_gw'][pid].get(7)}")

# ---- L4: injury flags for past deadlines rebuilt from TODAY's FPL notes (news_added), no status log
m = score(run_ctx(C, K, {"hist_flags": False})); res["L4 hist_flags off (reference)"] = delta(base1, m); print(fmt("L4 hist_flags off [26/27]", m))
n4 = sum(1 for k in K for pid, w in C["out"].items() if k in w and C["pts_gw"].get(pid, {}).get(k) is not None)
print(f"   player-GW rows zeroed by today's flags in GW3-{cur_last()}: {n4}")

# ---- L5: penalty order is today's (and end-of-season in the archive) for every past gameweek
m1 = score(run_ctx(C, K, {"pen_xg": 0})); m2 = score(run_ctx(A, range(4, 39), {"pen_xg": 0}, team_at=TA))
res["L5 pen bonus off [26/27]"] = delta(base1, m1); res["L5 pen bonus off [25/26]"] = delta(base2, m2)
print(fmt("L5 pen_xg 0 [26/27]", m1)); print(fmt("L5 pen_xg 0 [25/26]", m2))

# ---- L6: calibration and other DEFAULTS were tuned on GW3-7 2026/27, the same weeks the bench scores.
# Refit the final calibration (slope, intercept) on 2025/26 only and apply it to 2026/27.
import numpy as np
def raw_pp(ctx, gws, team_at=None):
    X, Y = [], []
    for k in gws:
        cx = ctx
        if team_at:
            cx = dict(ctx); cx["elements"] = {pid: dict(e, team=team_at(pid, k) or e["team"]) for pid, e in ctx["elements"].items()}
        pr = project(cx, k, 1, {"use_flags": False})["players"]
        for (pid, pos, x, a) in pool_rows(cx, k, {p: r["xp"].get(k, 0.0) for p, r in pr.items()}):
            raw = sum(pr[pid]["detail"].get(k, {}).values())
            pp = (x - 0.86 * raw) / 0.33
            X.append((raw, pp)); Y.append(a)
    return np.array(X), np.array(Y)
Xa, Ya = raw_pp(A, range(4, 39), TA); Xc, Yc = raw_pp(C, K)
s, i = np.linalg.lstsq(Xa, Ya, rcond=None)[0]
print(f"L6 calibration fitted on 2025/26 only: slope {s:.3f} int {i:.3f} (DEFAULTS 0.86 / 0.33)")
for nm, (ss, ii) in (("defaults", (0.86, 0.33)), ("25/26-fit", (s, i))):
    p = ss * Xc[:, 0] + ii * Xc[:, 1]
    print(f"   2026/27 with {nm}: RMSE {np.sqrt(((p - Yc) ** 2).mean()):.3f} bias {(p - Yc).mean():+.3f} corr {np.corrcoef(p, Yc)[0,1]:.3f}")
json.dump({"leaks": res, "cal_2526": [round(float(s), 3), round(float(i), 3)]}, open(out_path("leakage.json"), "w"), indent=1)
