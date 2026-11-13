#!/usr/bin/env python3
"""Double-gameweek check (FL-053): are players with two matches in a gameweek projected too low, and is it the double?

  python3 tools/dgw_check.py                 # 2025/26 and 2024/25 (needs raw/bootstrap.json, like bench.py)
  python3 tools/dgw_check.py '{"param": 1}'  # with model params

Two reports per season, from the same honest 1-GW-ahead forecasts bench.py makes (pool: played in the 3 GWs before):
  1. by scoring part (raw, before the calibration), single-match weeks v double weeks: real / projected per part.
     In a double, appearance points and DefCon are counted per match (dc_fx); goals conceded is the week's total
     halved down (FPL scores it per match: a small approximation).
  2. the same clubs' single-match weeks within 4 GWs of their double v the double itself: if both are under-projected
     by the same amount per match, the clubs are, not the double. Gap = real - xP per player-week, with a bootstrap
     95% interval over gameweeks (few doubles per season, so the interval is wide).
Missing: a season with no double gameweek prints none; an archive download that fails raises (archive.py).
"""
import json
import os
import random
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)


def fixture_counts(fixtures):
    """{(team, gw): number of fixtures}"""
    n = defaultdict(int)
    for f in fixtures:
        if f.get("event"):
            n[(f["team_h"], f["event"])] += 1
            n[(f["team_a"], f["event"])] += 1
    return n


def week_kinds(nfx, window=4):
    """{(team, gw): "double" | "near single"}: a club's double weeks, and its single-match weeks within `window` GWs."""
    dbl = {k for k, n in nfx.items() if n == 2}
    out = {k: "double" for k in dbl}
    for t, g in dbl:
        for g2 in range(g - window, g + window + 1):
            if nfx.get((t, g2)) == 1:
                out.setdefault((t, g2), "near single")
    return out


def boot(rows, n=2000, seed=1):
    """95% interval over gameweeks of the mean of (gw, value) rows."""
    by = defaultdict(list)
    for g, v in rows:
        by[g].append(v)
    ks, rng, ms = list(by), random.Random(seed), []
    for _ in range(n):
        pick = [x for k in (rng.choice(ks) for _ in ks) for x in by[k]]
        ms.append(sum(pick) / len(pick))
    ms.sort()
    return ms[int(0.025 * n)], ms[int(0.975 * n) - 1]


def main(params):
    import bench
    from backtest import PARTS, actual_parts
    from fplmodel import POS, project
    for season in ("2025-26", "2024-25"):
        ctx, team_at = bench._season(season)
        nfx = fixture_counts(ctx["fixtures"])
        kinds = week_kinds(nfx)
        parts = {k: defaultdict(lambda: [0, 0.0, 0.0]) for k in ("single", "double")}
        gaps = defaultdict(list)
        for k in range(5, 39):
            cx = dict(ctx)
            cx["elements"] = {pid: dict(e, team=team_at(pid, k) or e["team"]) for pid, e in ctx["elements"].items()}
            cx["team_gw_xg"] = bench._xg_at(ctx, team_at, k)
            res = project(cx, k, 1, dict(params, use_flags=False, sim=0))["players"]
            for pid, r in res.items():
                e, s = cx["elements"][pid], cx["pstats"].get(pid, {}).get(k)
                n = nfx.get((e["team"], k), 0)
                if s is None or n not in (1, 2) or k not in r["detail"]:
                    continue
                if not any(cx["pstats"].get(pid, {}).get(g, {}).get("minutes", 0) > 0 for g in range(k - 3, k)):
                    continue
                pos, sc = POS[e["element_type"]], cx["scoring"]
                act = actual_parts(s, pos, sc, False)
                fx = cx.get("dc_fx", {}).get(pid, {}).get(k) or []
                if n == 2 and fx:
                    act["mins"] = sum((sc["short_play"] if m > 0 else 0) + ((sc["long_play"] - sc["short_play"]) if m >= 60 else 0)
                                      for m, _, _ in fx)
                act["dc"] = sc["defensive_contribution"][pos] * (sum(1 for f in fx if f[1]) if fx else int(cx["dc_hit"][pid].get(k, False)))
                a = parts["double" if n == 2 else "single"]
                for part, _ in PARTS:
                    a[part][0] += 1; a[part][1] += r["detail"][k].get(part, 0.0); a[part][2] += act[part]
                kind = kinds.get((e["team"], k))
                if kind:
                    gaps[kind].append((k, ctx["pts_gw"][pid][k] - r["xp"][k], r["xp"][k], ctx["pts_gw"][pid][k]))
        print(f"{season}: double gameweeks {sorted({g for (t, g), n in nfx.items() if n == 2}) or 'none'}")
        print("  by part, real / projected (raw):   singles   doubles")
        for part, label in PARTS:
            r_ = [parts[k][part] for k in ("single", "double")]
            f_ = lambda x: f"{x[2] / x[1]:8.2f}" if x[0] and abs(x[1]) > 1e-9 else "       –"
            print(f"    {label:<28}{f_(r_[0])}  {f_(r_[1])}")
        for kind in ("near single", "double"):
            rs = gaps.get(kind)
            if not rs:
                continue
            n = len(rs)
            lo, hi = boot([(g, v) for g, v, _, _ in rs])
            print(f"  {kind:<12} n={n:5d} ({len({g for g, *_ in rs})} GWs) xP {sum(r[2] for r in rs) / n:.2f} real "
                  f"{sum(r[3] for r in rs) / n:.2f} gap {sum(r[1] for r in rs) / n:+.3f} [{lo:+.3f}, {hi:+.3f}]")


if __name__ == "__main__":
    main(json.loads(sys.argv[1]) if len(sys.argv) > 1 else {})
