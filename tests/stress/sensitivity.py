#!/usr/bin/env python3
"""4a. Sensitivity: each numeric DEFAULTS param at x0.8 and x1.2, scored on both seasons.
Also tests one new angle from the calibration slices: stronger fixture sensitivity (team ratings ** p)."""
import json, random
from common import *
import fplmodel
from fplmodel import DEFAULTS

C = cur_ctx(); A, TA = arch(); K1 = range(3, cur_last() + 1); K2 = range(4, 39)
def runs(params):
    return run_ctx(C, K1, params), run_ctx(A, K2, params, team_at=TA)
b1, b2 = runs({}); s1, s2 = score(b1), score(b2)
def capd(a, b):
    c = lambda rs: sorted(rs, key=lambda r: -r[2])[0][3]
    d = [c(b[g]) - c(a[g]) for g in a]
    random.seed(0); bs = sorted(sum(random.choice(d) for _ in d) / len(d) for _ in range(2000))
    return sum(d) / len(d), bs[50], bs[1950], sum(1 for g in a if sorted(a[g], key=lambda r: -r[2])[0][0] != sorted(b[g], key=lambda r: -r[2])[0][0])
SKIP = {"sim", "sim_match", "use_flags", "min_valid", "hist_flags", "use_out", "news_abs", "return_ramp"}
rows = []
for k, v in DEFAULTS.items():
    if k in SKIP or isinstance(v, bool) or not isinstance(v, (int, float)) or v == 0: continue
    for f in (0.8, 1.2):
        nv = v * f
        if k in ("recency", "team_recency", "mkt_recency", "min_recency", "xg_weight", "mkt_w", "direct_w"): nv = min(nv, 0.999)
        if k == "min_window": nv = max(1, round(nv))
        r1, r2 = runs({k: nv}); m1, m2 = score(r1), score(r2)
        c2 = capd(b2, r2)
        rows.append({"param": k, "x": f, "value": round(nv, 4), "corr26": round(m1["corr"] - s1["corr"], 4), "corr25": round(m2["corr"] - s2["corr"], 4),
                     "rmse25": round(m2["rmse"] - s2["rmse"], 4), "picks25": round(m2["picks"] - s2["picks"], 3), "cap25": round(c2[0], 2),
                     "cap25_ci": [round(c2[1], 2), round(c2[2], 2)], "cap_changed25": c2[3], "cap26": round(m1["cap1"] - s1["cap1"], 2)})
        r = rows[-1]; print(f"{k:<14} x{f}: corr {r['corr26']:+.4f}/{r['corr25']:+.4f} picks25 {r['picks25']:+.3f} cap25 {r['cap25']:+.2f} {r['cap25_ci']} changed {r['cap_changed25']}/35 cap26 {r['cap26']:+.2f}")
rows.sort(key=lambda r: -(abs(r["corr25"]) + abs(r["corr26"])))
print("\nMost fragile by corr:", [(r["param"], r["x"], r["corr26"], r["corr25"]) for r in rows[:6]])
sig = [r for r in rows if r["cap25_ci"][0] > 0 or r["cap25_ci"][1] < 0]
print("Captain changes outside the 95% bootstrap CI:", [(r["param"], r["x"], r["cap25"]) for r in sig] or "none")
json.dump(rows, open(out_path("sensitivity.json"), "w"), indent=1)

# ---- new angle: fixture sensitivity. Raise team ratings to a power p after they're computed.
orig = fplmodel.team_ratings
res_fx = {}
for p in (1.0, 1.25, 1.5):
    def tr(ctx, as_of, P, p=p):
        rat, lg = orig(ctx, as_of, P)
        return {t: {"att": v["att"] ** p, "def": v["def"] ** p} for t, v in rat.items()}, lg
    fplmodel.team_ratings = tr
    r1, r2 = runs({}); m1, m2 = score(r1), score(r2)
    fplmodel.team_ratings = orig
    c2 = capd(b2, r2)
    res_fx[p] = {"26/27": {k: round(m1[k], 4) for k in ("corr", "spearman", "rmse", "bias", "picks", "cap1", "cap5")},
                 "25/26": {k: round(m2[k], 4) for k in ("corr", "spearman", "rmse", "bias", "picks", "cap1", "cap5")}, "cap25_vs_base": [round(x, 2) for x in c2[:3]]}
    print(f"fixture power {p}: 26/27 {fmt('', m1)}\n                 25/26 {fmt('', m2)}  cap Δ {c2[0]:+.2f} CI [{c2[1]:+.2f}, {c2[2]:+.2f}]")
json.dump(res_fx, open(out_path("fixture_power.json"), "w"), indent=1)
