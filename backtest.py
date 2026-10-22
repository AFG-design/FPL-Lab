#!/usr/bin/env python3
"""Backtest the projection model: for each finished gameweek k, project it from
data before k only and compare with real points."""
import json, math, sys
from fplmodel import prepare, project


def evaluate(ctx, gws, params=None, verbose=False):
    pred, act = [], []
    buckets = {}
    top_hits = []
    for k in gws:
        res = project(ctx, k, horizon=1, params=dict(params or {}, use_flags=False))
        rows = []
        for pid, r in res["players"].items():
            x = r["xp"].get(k, 0.0)
            a = ctx["pts_gw"].get(pid, {}).get(k)
            if a is None:
                continue
            # a-priori pool: anyone who played in the previous 3 gameweeks
            if not any(ctx["pstats"].get(pid, {}).get(g, {}).get("minutes", 0) > 0 for g in range(k - 3, k)):
                continue
            pred.append(x)
            act.append(a)
            rows.append((x, a))
            b = min(8, int(x))
            s = buckets.setdefault(b, [0, 0.0, 0.0])
            s[0] += 1; s[1] += x; s[2] += a
        rows.sort(reverse=True)
        top = rows[:30]
        top_hits.append((k, sum(a for _, a in top) / len(top), sum(x for x, _ in top) / len(top)))
    n = len(pred)
    mae = sum(abs(p - a) for p, a in zip(pred, act)) / n
    rmse = math.sqrt(sum((p - a) ** 2 for p, a in zip(pred, act)) / n)
    mp, ma = sum(pred) / n, sum(act) / n
    cov = sum((p - mp) * (a - ma) for p, a in zip(pred, act))
    corr = cov / math.sqrt(sum((p - mp) ** 2 for p in pred) * sum((a - ma) ** 2 for a in act))
    out = {"n": n, "mae": mae, "rmse": rmse, "corr": corr, "bias": mp - ma,
           "buckets": {b: (c, px / c, pa / c) for b, (c, px, pa) in sorted(buckets.items())},
           "top30": top_hits}
    if verbose:
        print(f"n={n} MAE={mae:.3f} RMSE={rmse:.3f} corr={corr:.3f} bias={mp-ma:+.3f}")
        for b, (c, px, pa) in out["buckets"].items():
            print(f"  xP {b}-{b+1}: n={c:4d} predicted {px:.2f} actual {pa:.2f}")
        for k, a, x in top_hits:
            print(f"  GW{k} top-30 projected: predicted {x:.2f} actual {a:.2f}")
    return out

def baseline(ctx, gws):
    pred, act = [], []
    for k in gws:
        for pid, pg in ctx["pts_gw"].items():
            if k not in pg:
                continue
            if not any(ctx["pstats"][pid].get(g, {}).get("minutes", 0) > 0 for g in range(k - 3, k)):
                continue
            prev = [pg.get(g, 0) for g in range(max(1, k - 4), k)]
            pred.append(sum(prev) / len(prev)); act.append(pg[k])
    n = len(pred); mp, ma = sum(pred) / n, sum(act) / n
    cov = sum((p - mp) * (a - ma) for p, a in zip(pred, act))
    corr = cov / math.sqrt(sum((p - mp) ** 2 for p in pred) * sum((a - ma) ** 2 for a in act))
    rmse = math.sqrt(sum((p - a) ** 2 for p, a in zip(pred, act)) / n)
    return {"n": n, "corr": corr, "rmse": rmse}



if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else "raw"
    boot = json.load(open(f"{raw}/bootstrap.json"))
    fixtures = json.load(open(f"{raw}/fixtures.json"))
    cur = max(e["id"] for e in boot["events"] if e["finished"])
    live = {g: json.load(open(f"{raw}/live{g}.json")) for g in range(1, cur + 1)}
    priors = json.load(open("priors.json"))
    ctx = prepare(boot, fixtures, live, priors)
    print("With last-season priors"); evaluate(ctx, range(3, cur + 1), verbose=True)
    ctx0 = prepare(boot, fixtures, live, None)
    print("Without priors"); evaluate(ctx0, range(3, cur + 1), verbose=True)
    print("Baseline (average of last 4 GWs points)", baseline(ctx, range(3, cur + 1)))
