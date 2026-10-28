#!/usr/bin/env python3
"""Backtest the projection model: for each finished gameweek k, project it from
data before k only and compare with real points."""
import json, math, sys
from fplmodel import prepare, project

# Return bands, as in the OpenFPL paper (Groos 2025), so figures line up with published ones
BANDS = [("zero", "Didn't play"), ("blank", "Played, 2 pts or fewer"), ("ticker", "3-4 pts"), ("haul", "5+ pts")]


def band(pts, mins):
    if mins <= 0:
        return "zero"
    return "blank" if pts <= 2 else "ticker" if pts <= 4 else "haul"


def errors(rows):
    """rows: (predicted, actual, band). Overall and per-band MAE, RMSE and bias."""
    def stats(rs):
        n = len(rs)
        if not n:
            return {"n": 0, "mae": None, "rmse": None, "bias": None}
        return {"n": n, "mae": sum(abs(p - a) for p, a, _ in rs) / n,
                "rmse": math.sqrt(sum((p - a) ** 2 for p, a, _ in rs) / n),
                "bias": sum(p - a for p, a, _ in rs) / n}
    out = stats(rows)
    out["bands"] = {b: stats([r for r in rows if r[2] == b]) for b, _ in BANDS}
    return out


def corr(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs); syy = sum((y - my) ** 2 for y in ys)
    if not sxx or not syy:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sxx * syy)


def head_to_head(rows):
    """rows: dicts with ours, fpl, pts, band. Both projections scored on the same players."""
    out = {"n": len(rows)}
    for key in ("ours", "fpl"):
        e = errors([(r[key], r["pts"], r["band"]) for r in rows])
        e["corr"] = corr([r[key] for r in rows], [r["pts"] for r in rows])
        out[key] = e
    return out


def _mins(ctx, pid, g):
    return ctx["pstats"].get(pid, {}).get(g, {}).get("minutes", 0)


def _in_pool(ctx, pid, k):
    """a-priori pool: anyone who played in the previous 3 gameweeks"""
    return any(_mins(ctx, pid, g) > 0 for g in range(k - 3, k))


def evaluate(ctx, gws, params=None, verbose=False):
    pred, act = [], []
    buckets = {}
    top_hits = []
    pool_rows, all_rows = [], []
    for k in gws:
        res = project(ctx, k, horizon=1, params=dict(params or {}, use_flags=False))
        rows = []
        for pid, r in res["players"].items():
            x = r["xp"].get(k, 0.0)
            a = ctx["pts_gw"].get(pid, {}).get(k)
            if a is None:
                continue
            bd = band(a, _mins(ctx, pid, k))
            all_rows.append((x, a, bd))
            if not _in_pool(ctx, pid, k):
                continue
            pool_rows.append((x, a, bd))
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
           "top30": top_hits, "pool": errors(pool_rows), "all": errors(all_rows)}
    if verbose:
        print(f"n={n} MAE={mae:.3f} RMSE={rmse:.3f} corr={corr:.3f} bias={mp-ma:+.3f}")
        for b, (c, px, pa) in out["buckets"].items():
            print(f"  xP {b}-{b+1}: n={c:4d} predicted {px:.2f} actual {pa:.2f}")
        for k, a, x in top_hits:
            print(f"  GW{k} top-30 projected: predicted {x:.2f} actual {a:.2f}")
        for key, label in (("pool", "Played in the last 3 GWs"), ("all", "Every player")):
            e = out[key]
            print(f"  {label}: n={e['n']} MAE={e['mae']:.3f} RMSE={e['rmse']:.3f}")
            for b, name in BANDS:
                x = e["bands"][b]
                if x["n"]:
                    print(f"    {name:24} n={x['n']:5d} RMSE={x['rmse']:.3f} MAE={x['mae']:.3f} bias={x['bias']:+.2f}")
    return out

def baseline(ctx, gws):
    """Average of each player's points over the previous 4 gameweeks."""
    pred, act = [], []
    pool_rows, all_rows = [], []
    for k in gws:
        for pid, pg in ctx["pts_gw"].items():
            if k not in pg:
                continue
            prev = [pg.get(g, 0) for g in range(max(1, k - 4), k)]
            x, a = sum(prev) / len(prev), pg[k]
            bd = band(a, _mins(ctx, pid, k))
            all_rows.append((x, a, bd))
            if not _in_pool(ctx, pid, k):
                continue
            pool_rows.append((x, a, bd))
            pred.append(x); act.append(a)
    n = len(pred); mp, ma = sum(pred) / n, sum(act) / n
    cov = sum((p - mp) * (a - ma) for p, a in zip(pred, act))
    corr = cov / math.sqrt(sum((p - mp) ** 2 for p in pred) * sum((a - ma) ** 2 for a in act))
    rmse = math.sqrt(sum((p - a) ** 2 for p, a in zip(pred, act)) / n)
    return {"n": n, "corr": corr, "rmse": rmse, "pool": errors(pool_rows), "all": errors(all_rows)}


def evaluate_horizons(ctx, gws, horizons=(1, 2, 3), params=None):
    """Accuracy 1, 2 and 3 gameweeks ahead. Each origin gameweek k is projected once (from data before k,
    horizon = max(horizons)); target k+h-1 is scored for each h. Every horizon is scored on the same target
    weeks (those in `gws`), over every player with a points entry that week. The Last-5 baseline is the mean of
    the player's points over the 5 gameweeks before the origin, i.e. what was known when the projection was made.
    Returns {h: {"model": errors + corr, "base": errors + corr}}."""
    hmax = max(horizons)
    gws = {t for t in gws if t - hmax + 1 >= 3}   # targets every horizon can reach from an origin of GW3+
    if not gws:
        return {}
    rows ={h: {"model": [], "base": []} for h in horizons}
    xs = {h: {"model": ([], []), "base": ([], [])} for h in horizons}
    for k in range(max(3, min(gws) - hmax + 1), max(gws) + 1):
        if not any(k + h - 1 in gws for h in horizons):
            continue
        res = project(ctx, k, horizon=hmax, params=dict(params or {}, use_flags=False))["players"]
        for pid, pg in ctx["pts_gw"].items():
            prev = [pg.get(g, 0) for g in range(max(1, k - 5), k)]
            b5 = sum(prev) / len(prev) if prev else 0.0
            xp = res[pid]["xp"] if pid in res else {}
            for h in horizons:
                t = k + h - 1
                if t not in gws or t not in pg:
                    continue
                a, bd = pg[t], band(pg[t], _mins(ctx, pid, t))
                for key, x in (("model", xp.get(t, 0.0)), ("base", b5)):
                    rows[h][key].append((x, a, bd))
                    xs[h][key][0].append(x); xs[h][key][1].append(a)
    out = {}
    for h in horizons:
        out[h] = {}
        for key in ("model", "base"):
            e = errors(rows[h][key])
            e["corr"] = corr(*xs[h][key])
            out[h][key] = e
    return out


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else "raw"
    boot = json.load(open(f"{raw}/bootstrap.json"))
    fixtures = json.load(open(f"{raw}/fixtures.json"))
    cur = max(e["id"] for e in boot["events"] if e["finished"])
    live = {g: json.load(open(f"{raw}/live{g}.json")) for g in range(1, cur + 1)}
    priors = json.load(open("priors.json"))
    try:
        market = json.load(open("odds/odds.json"))
    except Exception:
        market = None
    ctx = prepare(boot, fixtures, live, priors, market)
    print("With last-season priors"); evaluate(ctx, range(3, cur + 1), verbose=True)
    ctx0 = prepare(boot, fixtures, live, None)
    print("Without priors"); evaluate(ctx0, range(3, cur + 1), verbose=True)
    print("Baseline (average of last 4 GWs points)", baseline(ctx, range(3, cur + 1)))
