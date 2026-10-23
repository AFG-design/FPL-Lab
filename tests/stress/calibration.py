#!/usr/bin/env python3
"""3. Calibration slices: predicted vs actual by slice, with Brier scores for 3+, 6+ and 10+ points
(simulated distributions, sim=1000) and the naive baseline (average of the last 4 GWs)."""
import json, datetime as dt
from collections import defaultdict
from common import *
from fplmodel import project, POS

SIM = 1000
def rows_for(ctx, gws, season, team_at=None, euro=None):
    out = []
    order = None
    for k in gws:
        cx = ctx
        if team_at:
            cx = dict(ctx); cx["elements"] = {pid: dict(e, team=team_at(pid, k) or e["team"]) for pid, e in ctx["elements"].items()}
        res = project(cx, k, 1, {"use_flags": False, "sim": SIM})
        pr, up, rat = res["players"], res["upcoming"], res["rating"]
        top6 = set(sorted(rat, key=lambda t: -(rat[t]["att"] / rat[t]["def"]))[:6])
        for pid, pos, x, a in pool_rows(cx, k, {p: r["xp"].get(k, 0.0) for p, r in pr.items()}):
            e = cx["elements"][pid]; fx = up[e["team"]].get(k, [])
            d = pr[pid]["dist"].get(k, {})
            pg = ctx["pts_gw"][pid]; prev = [pg.get(g, 0) for g in range(max(1, k - 4), k)]
            outw = ctx.get("out", {}).get(pid, set())
            out.append({"season": season, "gw": k, "pid": pid, "pos": pos, "pred": x, "act": a,
                        "naive": sum(prev) / len(prev), "p_start": pr[pid]["p_start"],
                        "home": fx[0][1] if len(fx) == 1 else None, "dgw": len(fx) > 1,
                        "fdr": fx[0][4] if len(fx) == 1 else None, "top6": bool(fx) and all(f[0] in top6 for f in fx),
                        "price": e.get("now_cost", 0) / 10, "back": (k - 1) in outw and k not in outw,
                        "euro": bool(euro and (e["team"], k) in euro),
                        "p3": 1 - d.get("blank", 0) if d else None, "p6": d.get("p6"), "p10": d.get("p10")})
    return out

C = cur_ctx(); A, TA = arch()
# European weeks (current season), same rule as build.py
euro = set()
ej = json.load(open("europe.json"))["competitions"]; short = {t["short_name"]: t["id"] for t in C["boot"]["teams"]}
for comp in ej.values():
    ds = [dt.date.fromisoformat(x) for x in comp["dates"]]
    for s in comp["teams"]:
        tid = short.get(s)
        for f in C["fixtures"]:
            if tid in (f["team_h"], f["team_a"]) and f["event"] and f["kickoff_time"]:
                kd = dt.date.fromisoformat(f["kickoff_time"][:10])
                if any(-2 <= (kd - d).days <= 3 and (kd - d).days != 0 for d in ds): euro.add((tid, f["event"]))
rows = rows_for(C, range(3, cur_last() + 1), "26/27", euro=euro) + rows_for(A, range(4, 39), "25/26", team_at=TA)
json.dump(rows, open(out_path("calibration_rows.json"), "w"))

def summ(rs):
    n = len(rs)
    if n < 30: return None
    mp = sum(r["pred"] for r in rs) / n; ma = sum(r["act"] for r in rs) / n; mn = sum(r["naive"] for r in rs) / n
    mae = sum(abs(r["pred"] - r["act"]) for r in rs) / n; maen = sum(abs(r["naive"] - r["act"]) for r in rs) / n
    out = {"n": n, "pred": mp, "act": ma, "bias": mp - ma, "mae": mae, "mae_naive": maen}
    for t, key in ((3, "p3"), (6, "p6"), (10, "p10")):
        v = [r for r in rs if r[key] is not None]
        if v:
            out[f"brier{t}"] = sum((r[key] - (r["act"] >= t)) ** 2 for r in v) / len(v)
            base = sum(1 for r in v if r["act"] >= t) / len(v)
            out[f"clim{t}"] = sum((base - (r["act"] >= t)) ** 2 for r in v) / len(v)
            out[f"hit{t}"] = base; out[f"exp{t}"] = sum(r[key] for r in v) / len(v)
    return out

SLICES = {
    "position": lambda r: r["pos"],
    "price": lambda r: "<5" if r["price"] < 5 else "5-7" if r["price"] < 7 else "7-10" if r["price"] < 10 else "10+",
    "p_start": lambda r: "<0.5" if r["p_start"] < 0.5 else "0.5-0.8" if r["p_start"] < 0.8 else "0.8-0.95" if r["p_start"] < 0.95 else "0.95+",
    "venue": lambda r: None if r["home"] is None else ("home" if r["home"] else "away"),
    "gw type": lambda r: "DGW" if r["dgw"] else "SGW",
    "FDR": lambda r: r["fdr"],
    "opponent": lambda r: "top-6" if r["top6"] else "rest",
    "season part": lambda r: "GW3-12" if r["gw"] <= 12 else "GW13-25" if r["gw"] <= 25 else "GW26-38",
    "European week (26/27)": lambda r: None if r["season"] != "26/27" else ("Europe" if r["euro"] else "no"),
    "first GW back (26/27)": lambda r: None if r["season"] != "26/27" else ("back" if r["back"] else "no"),
}
table = {}
for sname, fn in SLICES.items():
    for season in ("26/27", "25/26"):
        g = defaultdict(list)
        for r in rows:
            if r["season"] == season:
                v = fn(r)
                if v is not None: g[v].append(r)
        for v, rs in sorted(g.items(), key=lambda x: str(x[0])):
            s = summ(rs)
            if s: table[f"{sname}|{v}|{season}"] = s
print(f"{'slice':<34}{'n':>6}{'pred':>6}{'act':>6}{'bias':>7}{'MAE':>6}{'naive':>6}{'B3':>7}{'B6':>7}{'B10':>7}  (Brier / climatology)")
for k, s in table.items():
    flag = " <-- bias" if abs(s["bias"]) >= 0.3 else ""
    flag += " <-- naive wins" if s["mae_naive"] < s["mae"] else ""
    print(f"{k:<34}{s['n']:>6}{s['pred']:>6.2f}{s['act']:>6.2f}{s['bias']:>+7.2f}{s['mae']:>6.2f}{s['mae_naive']:>6.2f}"
          f"{s.get('brier3', 0):>7.3f}{s.get('brier6', 0):>7.3f}{s.get('brier10', 0):>7.3f}  ({s.get('clim6', 0):.3f}){flag}")
json.dump(table, open(out_path("calibration.json"), "w"), indent=1)
# FPL's own ep_next: only snapshots of unfinished gameweeks exist so far
import glob
fin = cur_last(); snaps = [int(f.split("gw")[-1].split(".")[0]) for f in glob.glob("../../history/proj_gw*.json")]
print("FPL ep_next snapshots:", sorted(snaps), "finished GWs to compare against:", [g for g in snaps if g <= fin] or "none yet")
