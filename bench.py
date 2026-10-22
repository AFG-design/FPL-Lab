#!/usr/bin/env python3
"""Model test bench: rolling-origin backtests on this season AND last season, scored on
accuracy and on the decisions the app makes (who to pick, who to captain).

  python3 bench.py                     # current model (DEFAULTS)
  python3 bench.py '{"recency":0.8}'   # compare a parameter set against the current model

Each gameweek k is projected from data before k only. Last season comes from archive.py
(no betting odds and no historical injury flags there, so both sides of any comparison run
without them). The archive's FPL "xP" column is not a usable benchmark (mostly zeros, and
filled in after the fact), so FPL's own projection is compared only in the live log (history/).
"""
import json, math, os, sys
from collections import defaultdict

from fplmodel import prepare, project, POS
import archive

HERE = os.path.dirname(os.path.abspath(__file__))
TOPN = {"GKP": 5, "DEF": 15, "MID": 15, "FWD": 10}


def _corr(xs, ys):
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return sxy / math.sqrt(sxx * syy) if sxx and syy else float("nan")


def _ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2
        i = j + 1
    return r


def score(rows_by_gw):
    """rows_by_gw: {gw: [(pid, pos, pred, actual)]} -> metrics dict."""
    P, A = [], []
    pos_pa = defaultdict(lambda: ([], []))
    spear, cap1, cap5, picks = [], [], [], []
    for g, rows in rows_by_gw.items():
        if not rows:
            continue
        for _, pos, p, a in rows:
            P.append(p); A.append(a)
            pos_pa[pos][0].append(p); pos_pa[pos][1].append(a)
        spear.append(_corr(_ranks([r[2] for r in rows]), _ranks([r[3] for r in rows])))
        top = sorted(rows, key=lambda r: -r[2])
        cap1.append(top[0][3]); cap5.append(sum(r[3] for r in top[:5]) / 5)
        tot = cnt = 0
        for pos, n in TOPN.items():
            best = [r for r in top if r[1] == pos][:n]
            tot += sum(r[3] for r in best); cnt += len(best)
        picks.append(tot / cnt)
    n = len(P)
    return {
        "n": n, "mae": sum(abs(p - a) for p, a in zip(P, A)) / n,
        "rmse": math.sqrt(sum((p - a) ** 2 for p, a in zip(P, A)) / n),
        "corr": _corr(P, A), "bias": (sum(P) - sum(A)) / n,
        "spearman": sum(spear) / len(spear),
        "pos_corr": {k: _corr(*v) for k, v in pos_pa.items()},
        "picks": sum(picks) / len(picks),     # avg real points of the model's top-N per position
        "cap1": sum(cap1) / len(cap1),        # avg real points of the top projected player
        "cap5": sum(cap5) / len(cap5),
        "gws": len(rows_by_gw),
    }


def pool_rows(ctx, k, pred):
    """The a-priori pool (played in one of the previous 3 GWs), as in backtest.py."""
    rows = []
    for pid, e in ctx["elements"].items():
        a = ctx["pts_gw"].get(pid, {}).get(k)
        if a is None:
            continue
        if not any(ctx["pstats"].get(pid, {}).get(g, {}).get("minutes", 0) > 0 for g in range(k - 3, k)):
            continue
        if pid not in pred:
            continue
        rows.append((pid, POS[e["element_type"]], pred[pid], a))
    return rows


_CUR = {}


def current_ctx():
    """This season's data from raw/ (written by a local build), prepared once."""
    if _CUR:
        return _CUR["ctx"]
    raw = os.path.join(HERE, "raw")
    boot = json.load(open(f"{raw}/bootstrap.json"))
    fixtures = json.load(open(f"{raw}/fixtures.json"))
    cur = max(e["id"] for e in boot["events"] if e["finished"])
    live = {g: json.load(open(f"{raw}/live{g}.json")) for g in range(1, cur + 1)}
    priors = json.load(open(os.path.join(HERE, "priors.json")))
    try:
        market = json.load(open(os.path.join(HERE, "odds", "odds.json")))
    except Exception:
        market = None
    _CUR["ctx"] = prepare(boot, fixtures, live, priors, market)
    _CUR["cur"] = cur
    return _CUR["ctx"]


def run_current(params, gws=None):
    ctx = current_ctx()
    out = {}
    for k in (gws or range(3, _CUR["cur"] + 1)):
        res = project(ctx, k, 1, dict(params, use_flags=False))["players"]
        out[k] = pool_rows(ctx, k, {pid: r["xp"].get(k, 0.0) for pid, r in res.items()})
    return out


_SEASON = {}


def _season(season):
    if season not in _SEASON:
        boot_now = json.load(open(os.path.join(HERE, "raw", "bootstrap.json")))
        boot, fixtures, live, priors, team_at = archive.load_season(season, boot_now)
        ctx = prepare(boot, fixtures, live, priors, None)
        # credit each gameweek's xG to the club the player was at then
        tgx = defaultdict(lambda: defaultdict(float))
        for pid, gs in ctx["pstats"].items():
            for g, s in gs.items():
                t = team_at(pid, g + 1) or ctx["elements"][pid]["team"]
                tgx[t][g] += float(s["expected_goals"])
        ctx["team_gw_xg"] = tgx
        _SEASON[season] = (ctx, team_at)
    return _SEASON[season]


def run_archive(params, season="2025-26", gws=range(4, 39)):
    ctx, team_at = _season(season)
    out = {}
    for k in gws:
        cx = dict(ctx)
        cx["elements"] = {pid: dict(e, team=team_at(pid, k) or e["team"]) for pid, e in ctx["elements"].items()}
        res = project(cx, k, 1, dict(params, use_flags=False))["players"]
        out[k] = pool_rows(cx, k, {pid: r["xp"].get(k, 0.0) for pid, r in res.items()})
    return out


def fmt(name, m):
    pc = " ".join(f"{p}:{m['pos_corr'].get(p, float('nan')):.3f}" for p in ("GKP", "DEF", "MID", "FWD"))
    return (f"{name:<22} n={m['n']:5d} MAE {m['mae']:.3f} RMSE {m['rmse']:.3f} corr {m['corr']:.3f} "
            f"rank {m['spearman']:.3f} bias {m['bias']:+.2f} | picks {m['picks']:.2f} cap {m['cap1']:.2f} top5 {m['cap5']:.2f} | {pc}")


def compare(variants, seasons=("current", "2025-26"), quiet=False):
    """variants: {name: params}. Returns {season: {name: metrics}}."""
    res = {}
    for s in seasons:
        res[s] = {}
        if not quiet:
            print(f"--- {s} ---")
        for name, p in variants.items():
            if s == "current":
                m = score(run_current(p))
            else:
                m = score(run_archive(p, s))
            res[s][name] = m
            if not quiet:
                print(fmt(name, m))
    return res


if __name__ == "__main__":
    variants = {"current model": {}}
    if len(sys.argv) > 1:
        variants["candidate"] = json.loads(sys.argv[1])
    compare(variants)
