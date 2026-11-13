#!/usr/bin/env python3
"""FL-094 check: how the model projects a regular coming back from an absence, and the player who covered for him.

    python3 tools/returning_mates.py                             # needs raw/ (a local build) and history/status.json
    python3 tools/returning_mates.py '{"xmins_skip_out": true}'  # the same with model params

A return is defined only from what was known at the deadline (the status log): a regular (started >= 70% of his
club's games in the 10 before) flagged at the previous deadline and not flagged at this one, whether or not he then
started. His stand-ins: same club and position, started at least one of the 3 games before, and under 50% of the 10.
Printed: their projected start chance and minutes (forecast from data before that week, as bench.py) against what
happened.

Why only this season: the archive has no injury flags, so a past regular's injury weeks look like being dropped and
a "return" can only be spotted by his coming back and starting, which picks the events by their outcome. A first
version did that (13 Nov) and showed stand-ins +14 to +19 minutes over-projected and returners at a 15% start chance;
both were mostly that selection, not the model (see docs/model-log.md, FL-094).
"""
import json, os, sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import bench
from fplmodel import project


def events(ctx, log, cur):
    """[(k, returner, [stand-ins])] from the status log (log["gws"][gw] = {pid: [status, chance]})."""
    gws, el, ps = log["gws"], ctx["elements"], ctx["pstats"]
    flag = lambda pid, g: str(pid) in gws.get(str(g), {})
    out = []
    for k in range(4, cur + 1):
        if str(k) not in gws or str(k - 1) not in gws:
            continue
        for pid, e in el.items():
            s = ps.get(pid, {})
            before = [g for g in range(max(1, k - 10), k) if g in s]
            if not (flag(pid, k - 1) and not flag(pid, k)) or len(before) < 3:
                continue
            if sum(1 for g in before if s[g]["starts"]) < 0.7 * len(before):
                continue
            mates = [q for q, x in el.items() if q != pid and x["team"] == e["team"] and x["element_type"] == e["element_type"]
                     and any(ps.get(q, {}).get(g, {}).get("starts") for g in range(k - 3, k))
                     and sum(1 for g in before if ps.get(q, {}).get(g, {}).get("starts")) < 0.5 * len(before)]
            out.append((k, pid, mates))
    return out


def main():
    params = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    ctx = bench.current_ctx(); cur = bench._CUR["cur"]
    log = json.load(open(os.path.join(bench.HERE, "history", "status.json")))
    evs = events(ctx, log, cur)
    rows = defaultdict(list)
    for k in sorted({e[0] for e in evs}):
        res = project(ctx, k, 1, dict(params, use_flags=False, sim=0))["players"]
        act = lambda q: ctx["pstats"].get(q, {}).get(k, {})
        for kk, r, ms in evs:
            if kk != k:
                continue
            for who, q in [("returner", r)] + [("stand-in", q) for q in ms]:
                if q in res:
                    a = act(q)
                    rows[who].append((res[q]["ps_next"], res[q]["xmin"], 1 if a.get("starts") else 0, a.get("minutes", 0)))
    for who in ("returner", "stand-in"):
        L = rows[who]
        if not L:
            print(f"{who}s: none yet"); continue
        n = len(L); f = lambda i: sum(x[i] for x in L) / n
        print(f"{who}s (n={n}): start chance {f(0):.2f} v started {f(2):.2f}; xMin {f(1):.0f} v {f(3):.0f}")


if __name__ == "__main__":
    main()
