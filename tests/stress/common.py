"""Shared helpers for the stress tests: contexts for both seasons and a bench-style runner."""
import os, sys, json, copy
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import bench
from bench import score, pool_rows, fmt
from fplmodel import project, prepare, POS

def cur_ctx():
    return bench.current_ctx()

def cur_last():
    bench.current_ctx(); return bench._CUR["cur"]

def arch():
    return bench._season("2025-26")

def run_ctx(ctx, gws, params=None, team_at=None, pred_hook=None):
    """Like bench.run_current / run_archive but on any ctx. Returns {gw: rows}."""
    out = {}
    for k in gws:
        cx = ctx
        if team_at:
            cx = dict(ctx)
            cx["elements"] = {pid: dict(e, team=team_at(pid, k) or e["team"]) for pid, e in ctx["elements"].items()}
        res = project(cx, k, 1, dict(params or {}, use_flags=False))["players"]
        pred = {pid: r["xp"].get(k, 0.0) for pid, r in res.items()}
        if pred_hook:
            pred = pred_hook(k, pred, res, cx)
        out[k] = pool_rows(cx, k, pred)
    return out

def both(params=None, cur=None, arc=None, label="", quiet=False):
    """Score a parameter set (optionally on modified contexts) on both seasons."""
    c = cur or cur_ctx(); a, ta = arc if arc else arch()
    m1 = score(run_ctx(c, range(3, cur_last() + 1), params))
    m2 = score(run_ctx(a, range(4, 39), params, team_at=ta))
    if not quiet:
        print(fmt(label + " [26/27]", m1)); print(fmt(label + " [25/26]", m2))
    return m1, m2

def delta(a, b):
    keys = ("corr", "spearman", "rmse", "bias", "picks", "cap1", "cap5")
    return {k: round(b[k] - a[k], 4) for k in keys}

OUT = os.path.join(ROOT, "tests", "stress", "out")
os.makedirs(OUT, exist_ok=True)
def out_path(name): return os.path.join(OUT, name)
