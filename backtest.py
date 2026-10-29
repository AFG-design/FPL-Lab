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


# ---------------------------------------------------------------- segment breakdown
PRICE_BANDS = [("<£5.0m", 0, 50), ("£5.0–6.9m", 50, 70), ("£7.0–9.9m", 70, 100), ("£10m+", 100, 10 ** 6)]
COMPARE_MAE, COMPARE_BIAS, COMPARE_N = 0.05, 0.2, 30   # --compare flags a segment past these with n >= 30


def _flagged_at(status_log, k):
    """{pid: True} for players flagged at GW k's deadline (status != 'a' or chance < 100), from the status log.
    None when the log has no entry for k: the flag is unknown, not 'unflagged'."""
    rows = (status_log or {}).get("gws", {}).get(str(k))
    if rows is None:
        return None
    return {int(pid) for pid, (st, ch) in rows.items() if st != "a" or (ch is not None and ch < 100)}


def segments(ctx, gws, params=None, flag_log=None):
    """Error by segment, on the same players and projections as evaluate() (pool: played in the last 3 GWs).
    flag_log: status log used only to label players flagged at each deadline (None: that split is skipped).
    Price is today's price from the bootstrap, not the price at each deadline (the API keeps no history of it).
    Returns {segment group: {segment name: {n, mae, corr, bias}}}."""
    from fplmodel import POS
    E = ctx["elements"]
    seg = {}

    def add(group, name, x, a):
        seg.setdefault(group, {}).setdefault(name, ([], []))
        seg[group][name][0].append(x); seg[group][name][1].append(a)

    for k in gws:
        res = project(ctx, k, horizon=1, params=dict(params or {}, use_flags=False))
        flagged = _flagged_at(flag_log, k) if flag_log else None
        rows = []
        for pid, r in res["players"].items():
            x = r["xp"].get(k, 0.0)
            a = ctx["pts_gw"].get(pid, {}).get(k)
            if a is None or not _in_pool(ctx, pid, k):
                continue
            rows.append((x, a, pid))
            e = E[pid]
            add("All", "all", x, a)
            add("Position", POS[e["element_type"]], x, a)
            c = e["now_cost"]
            add("Price (today's)", next(n for n, lo, hi in PRICE_BANDS if lo <= c < hi), x, a)
            if flag_log is not None:
                add("Flag at deadline", "unknown (no log for GW)" if flagged is None
                    else "flagged" if pid in flagged else "unflagged", x, a)
            add("Last-season prior", "has prior" if r.get("has_prior") else "no prior", x, a)
            add("Gameweek", f"GW{k}", x, a)
        rows.sort(key=lambda t: (t[0], t[1]), reverse=True)   # same order as evaluate()'s top 30
        for x, a, _ in rows[:30]:
            add("Top 30 projected", "top 30 each GW", x, a)
    out = {}
    for group, names in seg.items():
        out[group] = {}
        for name, (xs, ys) in names.items():
            n = len(xs)
            out[group][name] = {"n": n, "mae": sum(abs(p - q) for p, q in zip(xs, ys)) / n,
                                "corr": corr(xs, ys), "bias": sum(p - q for p, q in zip(xs, ys)) / n}
    return out


GROUP_ORDER = ["All", "Position", "Price (today's)", "Flag at deadline", "Top 30 projected", "Last-season prior", "Gameweek"]
NAME_ORDER = {"Position": ["GKP", "DEF", "MID", "FWD"], "Price (today's)": [b[0] for b in PRICE_BANDS],
              "Flag at deadline": ["flagged", "unflagged", "unknown (no log for GW)"]}


def _ordered(seg):
    for group in GROUP_ORDER + [g for g in seg if g not in GROUP_ORDER]:
        names = seg.get(group, {})
        order = NAME_ORDER.get(group, [])
        for name in [n for n in order if n in names] + sorted(n for n in names if n not in order):
            yield group, name, names[name]


def _f(v, fmt):
    return "–" if v is None else format(v, fmt)


def print_segments(seg, title):
    print(title)
    print(f"  {'Segment':20} {'':24} {'n':>5} {'MAE':>6} {'corr':>6} {'bias':>6}")
    last = None
    for group, name, s in _ordered(seg):
        print(f"  {group if group != last else '':20} {name:24} {s['n']:5d} {_f(s['mae'], '6.3f')} "
              f"{_f(s['corr'], '6.3f')} {_f(s['bias'], '+6.2f')}")
        last = group


def compare(base_path, new_path):
    """Print per-segment deltas (new − base) and flag segments with n >= 30 where MAE worsens by more than 0.05
    or bias moves by more than 0.2. Returns the number of flagged segments."""
    A, B = json.load(open(base_path)), json.load(open(new_path))
    for key in ("status_log", "flag_log"):
        if A.get(key) != B.get(key):
            print(f"Warning: {key} differs ({A.get(key)} vs {B.get(key)}): the runs are not like for like")
    ha, hb = A["headline"], B["headline"]
    print(f"Headline: corr {ha['corr']:.4f} -> {hb['corr']:.4f} ({hb['corr'] - ha['corr']:+.4f}), "
          f"MAE {ha['mae']:.4f} -> {hb['mae']:.4f} ({hb['mae'] - ha['mae']:+.4f}), "
          f"bias {ha['bias']:+.3f} -> {hb['bias']:+.3f}")
    print(f"  {'Segment':20} {'':24} {'n':>5} {'ΔMAE':>7} {'Δcorr':>7} {'Δbias':>7}")
    flagged, last = [], None
    sa = A["segments"]
    for group, name, b in _ordered(B["segments"]):
        a = sa.get(group, {}).get(name)
        if a is None:
            print(f"  {group if group != last else '':20} {name:24} {b['n']:5d}   (not in base)")
            last = group
            continue
        dm, db = b["mae"] - a["mae"], b["bias"] - a["bias"]
        dc = None if a["corr"] is None or b["corr"] is None else b["corr"] - a["corr"]
        n = min(a["n"], b["n"])
        why = [w for w, hit in (("MAE worse", dm > COMPARE_MAE), ("bias moved", abs(db) > COMPARE_BIAS)) if hit]
        bad = n >= COMPARE_N and why
        if bad:
            flagged.append(f"{group} / {name} ({', '.join(why)})")
        print(f"  {group if group != last else '':20} {name:24} {b['n']:5d} {dm:+7.3f} {_f(dc, '+7.3f')} {db:+7.3f}"
              + (f"   <-- {', '.join(why)}" if bad else ""))
        last = group
    for group, names in sa.items():
        for name in names:
            if name not in B["segments"].get(group, {}):
                print(f"  {group} / {name}: in base only")
    if flagged:
        print(f"{len(flagged)} segment(s) past the limits (MAE +{COMPARE_MAE}, bias ±{COMPARE_BIAS}, n >= {COMPARE_N}): "
              + "; ".join(flagged))
    else:
        print(f"No segment past the limits (MAE +{COMPARE_MAE}, bias ±{COMPARE_BIAS}, n >= {COMPARE_N}).")
    return len(flagged)


if __name__ == "__main__":
    import argparse, os
    ap = argparse.ArgumentParser(description="Backtest the projection model on this season's finished gameweeks.")
    ap.add_argument("raw", nargs="?", default="raw", help="folder with bootstrap.json, fixtures.json, live{g}.json")
    ap.add_argument("--status-log", nargs="?", const="history/status.json", default=None, metavar="PATH",
                    help="pass the deadline status log to the model, as the live build does (default path "
                         "history/status.json). Without it the model sees no injury flags (the original behaviour)")
    ap.add_argument("--json", metavar="OUT", help="write the headline and segment numbers to OUT for --compare")
    ap.add_argument("--compare", nargs=2, metavar=("BASE", "NEW"), help="compare two --json files and stop")
    args = ap.parse_args()
    if args.compare:
        sys.exit(1 if compare(*args.compare) else 0)
    raw = args.raw
    boot = json.load(open(f"{raw}/bootstrap.json"))
    fixtures = json.load(open(f"{raw}/fixtures.json"))
    cur = max(e["id"] for e in boot["events"] if e["finished"])
    live = {g: json.load(open(f"{raw}/live{g}.json")) for g in range(1, cur + 1)}
    priors = json.load(open("priors.json"))
    try:
        market = json.load(open("odds/odds.json"))
    except Exception:
        market = None
    status_log = json.load(open(args.status_log)) if args.status_log else None   # asked for: missing file fails
    # The flagged/unflagged split only labels players; it uses the log even when the model doesn't get it.
    flag_path = args.status_log or "history/status.json"
    flag_log = status_log if status_log is not None else (json.load(open(flag_path)) if os.path.exists(flag_path) else None)
    ctx = prepare(boot, fixtures, live, priors, market, status_log=status_log)
    gws = range(3, cur + 1)
    print("With last-season priors" + (f" (status log: {args.status_log})" if status_log else ""))
    head = evaluate(ctx, gws, verbose=True)
    ctx0 = prepare(boot, fixtures, live, None, status_log=status_log)
    print("Without priors"); evaluate(ctx0, gws, verbose=True)
    print("Baseline (average of last 4 GWs points)", baseline(ctx, gws))
    seg = segments(ctx, gws, flag_log=flag_log)
    print()
    print_segments(seg, f"Segment breakdown, with last-season priors, GW{min(gws)}-{max(gws)} "
                        f"(model status log: {args.status_log or 'none'}; bias = projected - actual)")
    if flag_log is None:
        print("  Flag at deadline: skipped, no status log found")
    print("  Price is today's price, not the price at each deadline. 'Assumed' values can't be split out: "
          "backtests run with use_flags off, so project() never marks a value assumed.")
    if args.json:
        with open(args.json, "w") as f:
            json.dump({"gws": list(gws), "status_log": args.status_log, "flag_log": flag_path if flag_log else None,
                       "headline": {k: head[k] for k in ("n", "mae", "rmse", "corr", "bias")},
                       "segments": seg}, f, indent=1)
        print(f"Wrote {args.json}")
