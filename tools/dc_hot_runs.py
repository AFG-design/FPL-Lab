#!/usr/bin/env python3
"""FL-224 supporting check: do players on a DefCon run keep it up? (report only, no model change)

  python3 tools/dc_hot_runs.py              # 2025/26, dc_blend 4 vs 15
  python3 tools/dc_hot_runs.py 4 15 30      # any dc_blend values

For each 2025/26 forecast week k (GW4-38, built as bench.run_archive does), picks outfield players on a run: an own
DefCon hit rate of 0.8+ over 5+ starts before k (FL-080 per-fixture starts, ctx["dc_fx"]). Compares their projected
per-start DefCon chance (p_dc) under each dc_blend with their real hit rate in their GW k starts. Players with no start
in GW k are skipped (no outcome to score). Prints early season (GW4-12), later (GW13-38) and all, with mean projected,
mean real and Brier. Needs raw/bootstrap.json and the archive, like bench.py. Small samples: read it as supporting
evidence beside bench.py, not as a deciding metric.
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bench
from fplmodel import project, POS

RUN_RATE, RUN_STARTS = 0.8, 5


def main(blends):
    ctx, team_at = bench._season("2025-26")
    rows = []
    for k in range(4, 39):
        cx = dict(ctx)
        cx["elements"] = {pid: dict(e, team=team_at(pid, k) or e["team"]) for pid, e in ctx["elements"].items()}
        cx["team_gw_xg"] = bench._xg_at(ctx, team_at, k)
        res = {b: project(cx, k, 1, {"dc_blend": b, "use_flags": False})["players"] for b in blends}
        for pid in res[blends[0]]:
            if POS[cx["elements"][pid]["element_type"]] == "GKP":
                continue
            fx = cx.get("dc_fx", {}).get(pid, {})
            st = [x for g in range(1, k) for x in fx.get(g, ()) if x[2]]
            if len(st) < RUN_STARTS or sum(x[1] for x in st) / len(st) < RUN_RATE:
                continue
            nxt = [x for x in fx.get(k, ()) if x[2]]
            if not nxt:
                continue
            rows.append((k, [res[b][pid]["p_dc"] for b in blends], sum(x[1] for x in nxt) / len(nxt)))
    for name, sel in (("GW4-12", lambda k: k <= 12), ("GW13-38", lambda k: k > 12), ("all", lambda k: True)):
        rs = [r for r in rows if sel(r[0])]
        if not rs:
            print(f"{name}: no player-weeks")
            continue
        n = len(rs)
        cells = " | ".join(f"dc_blend {b:g} {sum(r[1][i] for r in rs) / n:.3f} (Brier "
                           f"{sum((r[1][i] - r[2]) ** 2 for r in rs) / n:.4f})" for i, b in enumerate(blends))
        print(f"{name}: n={n} real {sum(r[2] for r in rs) / n:.3f} | {cells}")


if __name__ == "__main__":
    main([float(x) for x in sys.argv[1:]] or [4.0, 15.0])
