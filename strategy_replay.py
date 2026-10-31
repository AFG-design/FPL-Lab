#!/usr/bin/env python3
"""Strategy replay: do Balanced, Play safe and Chase rank behave as their names say on real past seasons?

  python3 strategy_replay.py                  # 2025-26 and 2024-25, from GW5
  python3 strategy_replay.py 2025-26 --from 5 --to 20 --json out.json

For each season, three teams start from the same squad (the best £100m squad for the first 5 weeks, built with the
projections of the time). Every gameweek each team re-plans the next 5 weeks with its own strategy
(optimise.strategy_plans, the same code the site's plans use), makes only that week's moves, and scores the real
points of the XI and captain it picked, with simple auto-subs. Projections for gameweek k come from data before k only
(bench.py's rolling origin).

It reports per strategy: total real points, total projected points, hits, and how its score moved against the field:
  field   = the ownership-weighted points of the whole game that week (each player's points x the share of squads
            that owned him, x 11/15 for a starting XI, plus the most-owned player's points again as the captain),
            a stand-in for an average manager's score.
  spread  = standard deviation of (team - field) over the season: bigger means a bumpier ride.
  green / red = weeks at least 15 points better / worse against the field than the team's usual margin.
Chase rank should show the biggest spread and the most green weeks, Play safe the smallest spread and fewest red weeks.

Missing or approximate data, said out loud:
  - Past seasons have no "managers around your rank" ownership; overall ownership (merged_gw.csv `selected`) stands in
    for it, without captaincy. Safe/Chase therefore track the whole game, not a rank band.
  - No historical injury flags (as bench.py); nailed comes from the projected start chance and minutes.
  - A player missing from a week's price list can't be bought that week; a gameweek with no projection is skipped.
  - Auto-subs ignore formation limits beyond keeping one goalkeeper: an approximation that treats all teams alike.
Needs raw/bootstrap.json (scoring rules) like bench.py, and downloads the archive on first run (archive.py).
"""
import argparse, json, math, os, statistics, sys, time
from collections import defaultdict

import archive
import bench
import optimise
from fplmodel import project, POS

H = 5
MODES = ("balanced", "safe", "chase")


def fpl_sell(buy, price):
    b, p = round(buy * 10), round(price * 10)
    return (p if p <= b else b + (p - b) // 2) / 10


def season_tables(season):
    """{gw: {pid: price £m}}, {gw: {pid: ownership fraction}} from merged_gw.csv."""
    price, sel = defaultdict(dict), defaultdict(dict)
    for r in archive._rows(season, "gws/merged_gw.csv"):
        g, pid = int(r["GW"]), int(r["element"])
        v, s = archive._num(r.get("value")), archive._num(r.get("selected"))
        if v:
            price[g][pid] = v / 10
        if s is not None:
            sel[g][pid] = max(sel[g].get(pid, 0), s)
    own = {}
    for g, d in sel.items():
        managers = sum(d.values()) / 15 or 1      # every manager owns 15 players
        own[g] = {pid: n / managers for pid, n in d.items()}
    return price, own


def autosub(xi, bench, pts, mins, players):
    """Real points of an XI with simple auto-subs: a starter who didn't play is replaced by the first bench player
    of a compatible kind who did (goalkeeper for goalkeeper, outfield for outfield)."""
    xi, used = list(xi), set()
    for k, i in enumerate(xi):
        if mins.get(i, 0) > 0:
            continue
        gk = players[i]["pos"] == "GKP"
        for b in bench:
            if b in used or mins.get(b, 0) <= 0 or (players[b]["pos"] == "GKP") != gk:
                continue
            xi[k] = b; used.add(b); break
    return xi


def replay(season, k_from, k_to, sim, modes=MODES):
    ctx, team_at = bench._season(season)
    price, own = season_tables(season)
    last = max(price)
    k_to = min(k_to, last)
    t0 = time.time()

    def projections(k):
        cx = dict(ctx)
        cx["elements"] = {pid: dict(e, team=team_at(pid, k) or e["team"]) for pid, e in ctx["elements"].items()}
        gws = list(range(k, min(k + H, last + 1)))
        res = project(cx, k, len(gws), {"use_flags": False, "sim": sim})["players"]
        pl = {}
        for pid, r in res.items():
            if pid not in price.get(k, {}):
                continue
            el = cx["elements"][pid]
            pl[pid] = {"pos": POS[el["element_type"]], "team": el["team"], "price": price[k][pid],
                       "xp": {g: r["xp"].get(g, 0.0) for g in gws}, "ok": True,
                       "p10": {g: ((r.get("dist") or {}).get(g) or {}).get("p10", 0.0) for g in gws},
                       "nailed": int(round(100 * r.get("p_start", 1) * min(1.0, r.get("m_start", 90) / 85))),
                       "name": el.get("web_name", str(pid))}
        return pl, gws

    # the same starting squad for all three: best £100m squad for the first H weeks
    pl, gws = projections(k_from)
    wc = optimise.solve(pl, [], {}, 100.0, 1, gws, hit=0, ft_value=0, max_moves_week=15, freeze_after=1, time_limit=60)
    start = wc["weeks"][0]["xi"] + wc["weeks"][0]["bench"]
    bank0 = round(100.0 - sum(pl[i]["price"] for i in start), 1)
    teams = {m: {"squad": list(start), "buy": {i: pl[i]["price"] for i in start}, "bank": bank0, "ft": 1,
                 "real": [], "proj": [], "field": [], "hits": 0, "moves": 0} for m in modes}

    for k in range(k_from, k_to + 1):
        if k != k_from:
            pl, gws = projections(k)
        if not pl:
            print(f"  GW{k}: no projections, skipped"); continue
        pts = {pid: ctx["pts_gw"].get(pid, {}).get(k, 0) for pid in pl}
        mins = {pid: ctx["pstats"].get(pid, {}).get(k, {}).get("minutes", 0) for pid in pl}
        o = own.get(k, {})
        top = max(pl, key=lambda pid: o.get(pid, 0))     # captain stand-in: the most-owned player
        field = sum(o.get(pid, 0) * pts.get(pid, 0) for pid in pl) * 11 / 15 + pts.get(top, 0)
        eo = {pid: o.get(pid, 0.0) for pid in pl}
        for m in modes:
            t = teams[m]
            for i in t["squad"]:                      # a sold-out player still counts for the squad
                if i not in pl:
                    pl[i] = {"pos": POS[ctx["elements"][i]["element_type"]], "team": ctx["elements"][i]["team"],
                             "price": price.get(k, {}).get(i, t["buy"][i]), "xp": {g: 0.0 for g in gws}, "ok": False,
                             "p10": {}, "nailed": 0, "name": str(i)}
                    pts.setdefault(i, ctx["pts_gw"].get(i, {}).get(k, 0)); mins.setdefault(i, 0)
            sell = {i: fpl_sell(t["buy"][i], pl[i]["price"]) for i in t["squad"]}
            plans, _ = optimise.strategy_plans(pl, t["squad"], sell, t["bank"], min(t["ft"], 5), gws, [("best", None)],
                                               eo=eo, modes=("balanced", m), time_limit=20)
            key = "best" if m == "balanced" else f"{m}_best"
            r = plans.get(key) or plans.get("best")
            if not r:                                  # nothing usable: keep the squad, best XI by projection
                r = optimise.solve(pl, t["squad"], sell, t["bank"], min(t["ft"], 5), gws, week1_moves=0, freeze_after=0)
            w0 = r["weeks"][0]
            for o_ in w0["out"]:
                t["bank"] += sell[o_]; t["squad"].remove(o_); t["buy"].pop(o_, None)
            for i_ in w0["in"]:
                t["bank"] -= pl[i_]["price"]; t["squad"].append(i_); t["buy"][i_] = pl[i_]["price"]
            t["bank"] = round(t["bank"], 1)
            n = len(w0["in"])
            t["hits"] += w0["hits"]; t["moves"] += n
            t["ft"] = 1 if n > t["ft"] else min(5, t["ft"] - n + 1)
            xi = autosub(w0["xi"], w0["bench"], pts, mins, pl)
            cap = w0["captain"] if mins.get(w0["captain"], 0) > 0 else w0["vice"]
            real = sum(pts.get(i, 0) for i in xi) + (pts.get(cap, 0) if cap in xi else 0) - 4 * w0["hits"]
            t["real"].append(real); t["proj"].append(w0["xp"] - 4 * w0["hits"]); t["field"].append(field)
        line = "  ".join(f"{m[:4]} {teams[m]['real'][-1]:4.0f}" for m in modes)
        print(f"  {season} GW{k}: {line}   field {field:5.1f}   ({time.time() - t0:.0f}s)", flush=True)
    return teams


def summary(teams):
    out = {}
    for m, t in teams.items():
        d = [a - b for a, b in zip(t["real"], t["field"])]
        out[m] = {"weeks": len(d), "real": sum(t["real"]), "proj": round(sum(t["proj"]), 1), "hits": t["hits"],
                  "moves": t["moves"], "vs_field": round(sum(d), 1), "spread": round(statistics.pstdev(d), 2) if d else None,
                  # green/red count against the team's own usual margin, so a team that beats the field every week
                  # isn't all green: these are the big swings either way
                  "green": sum(1 for x in d if x - statistics.mean(d) >= 15), "red": sum(1 for x in d if x - statistics.mean(d) <= -15),
                  "worst": round(min(d), 1) if d else None, "best": round(max(d), 1) if d else None}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("seasons", nargs="*", default=["2025-26", "2024-25"])
    ap.add_argument("--from", dest="k_from", type=int, default=5)
    ap.add_argument("--to", dest="k_to", type=int, default=38)
    ap.add_argument("--sim", type=int, default=600, help="simulations per player for the 10+ point chance (default 600)")
    ap.add_argument("--json", help="write the results here")
    ap.add_argument("--modes", default=",".join(MODES), help="strategies to replay, e.g. chase (each team is independent)")
    ap.add_argument("--old", action="store_true", help="the settings before points budgets (for a before/after table)")
    a = ap.parse_args()
    if not os.path.exists(os.path.join(bench.HERE, "raw", "bootstrap.json")):
        sys.exit("strategy_replay: needs raw/bootstrap.json (the scoring rules); save bootstrap-static there first")
    if a.old:   # as optimise.py had them before the budgets: weak terms, ownership for 2 weeks, no floors
        optimise.STRATEGY = {"balanced": {}, "safe": {"lam": 0.02, "hit_margin": 2.0, "nail_w": 0.5}, "chase": {"lam": -0.03, "haul_w": 10.0}}
        optimise.SAFE_BUDGET = optimise.CHASE_BUDGET = 1e9
        optimise.MIN_PROFIT, optimise.EO_WEEKS = -1e9, 2
    res = {}
    for s in a.seasons:
        res[s] = summary(replay(s, a.k_from, a.k_to, a.sim, tuple(a.modes.split(","))))
        print(f"\n{s}  (GW{a.k_from}-{a.k_to})")
        print(f"{'':10s} {'real':>6s} {'proj':>7s} {'vs field':>9s} {'spread':>7s} {'green':>6s} {'red':>4s} {'hits':>5s} {'moves':>6s}")
        for m, r in res[s].items():
            print(f"{m:10s} {r['real']:6.0f} {r['proj']:7.1f} {r['vs_field']:+9.1f} {r['spread']:7.2f} {r['green']:6d} {r['red']:4d} {r['hits']:5d} {r['moves']:6d}")
    if a.json:
        json.dump(res, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
