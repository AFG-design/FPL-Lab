#!/usr/bin/env python3
"""Player-level prior from last season's model residuals (actual - projected), keyed by FPL `code`.

residual_table(season) runs the model 1 GW ahead over a finished season (GW4-38, like bench.py) and
stores, per player code, the number of pool rows, sum(actual - xP) and sum(actual bonus - projected bonus).
build_prior(elements, table) maps that onto a target season's player ids, giving the
{pid: (sum_resid, n)} dicts fplmodel.project reads from ctx["resid_prior"] / ctx["resid_prior_bonus"]
(used only when params resid_w > 0). Tables are cached in archive/resid_<season>.json (gitignored).
"""
import json, os
import bench
from fplmodel import DEFAULTS, project

HERE = os.path.dirname(os.path.abspath(__file__))


def _cache(season):
    return os.path.join(HERE, "archive", f"resid_{season}.json")


def residual_table(season, force=False, gws=range(4, 39)):
    path = _cache(season)
    if not force and os.path.exists(path):
        return json.load(open(path))
    ctx, team_at = bench._season(season)
    slope = DEFAULTS["cal_slope"]
    tab = {}
    for k in gws:
        cx = dict(ctx)
        cx["elements"] = {pid: dict(e, team=team_at(pid, k) or e["team"]) for pid, e in ctx["elements"].items()}
        res = project(cx, k, 1, {"use_flags": False})["players"]
        pred = {pid: r["xp"].get(k, 0.0) for pid, r in res.items()}
        for pid, _, p, a in bench.pool_rows(cx, k, pred):
            code = str(ctx["elements"][pid]["code"])
            t = tab.setdefault(code, {"n": 0, "sum": 0.0, "bsum": 0.0, "name": ctx["elements"][pid]["web_name"]})
            t["n"] += 1
            t["sum"] += a - p
            t["bsum"] += ctx["pstats"][pid][k]["bonus"] - slope * res[pid]["detail"].get(k, {}).get("bonus", 0.0)
    json.dump(tab, open(path, "w"))
    return tab


def build_prior(elements, table):
    """elements: {pid: element with `code`} of the target season -> (total, bonus-only) dicts {pid: (sum, n)}."""
    tot, bon = {}, {}
    for pid, e in elements.items():
        t = table.get(str(e["code"]))
        if t:
            tot[pid] = (t["sum"], t["n"])
            bon[pid] = (t["bsum"], t["n"])
    return tot, bon


def attach(ctx, table):
    """Return a copy of ctx carrying the prior built from `table`."""
    tot, bon = build_prior(ctx["elements"], table)
    return dict(ctx, resid_prior=tot, resid_prior_bonus=bon)
