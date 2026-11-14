#!/usr/bin/env python3
"""FL-114: are team goals and clean sheets projected at the right level? Out of sample, all three seasons.

    python3 tools/team_level_check.py                # needs raw/ and archive/ (as bench.py)
    python3 tools/team_level_check.py '{"cs_k": 1.0}'  # the same with model params

For every match of gameweek k (5 to 38 in past seasons, 4 on this season), the model's forecast made from data before
k (as bench.py: no flags, fixture odds only for weeks they were out) gives each side's expected goals (after the
fixture's own odds are blended in) and its clean-sheet chance exp(-cs_k x expected goals against). Compared with the
goals scored and clean sheets kept, overall and by the side's FPL difficulty (FDR) for that match. 95% intervals by
bootstrap over gameweeks. A double gameweek's matches are each counted; a match without a score is skipped.
"""
import json, math, os, random, sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import bench
from fplmodel import project, DEFAULTS

B = 2000


def season(ctx, gws, params):
    P = dict(DEFAULTS, **params)
    score = {}
    for f in ctx["fixtures"]:
        if f.get("event") and f.get("team_h_score") is not None:
            score[(f["team_h"], f["event"], f["team_a"])] = (f["team_h_score"], f["team_a_score"])
    rows = []   # (gw, fdr, xg_for, goals_for, cs_prob, cs)
    for k in gws:
        up = project(ctx, k, 1, dict(params, use_flags=False, sim=0))["upcoming"]
        for tid, by_g in up.items():
            for opp, home, mf, ma, fdr in by_g.get(k, []):
                key = (tid, k, opp) if home else (opp, k, tid)
                if key not in score:
                    continue
                gf, ga = score[key] if home else score[key][::-1]
                rows.append((k, fdr, mf, gf, math.exp(-P["cs_k"] * ma), 1 if ga == 0 else 0))
    return rows


def summary(rows):
    by_gw = defaultdict(list)
    for r in rows:
        by_gw[r[0]].append(r)
    gws = list(by_gw)
    def stat(sel):
        rs = [r for g in sel for r in by_gw[g]]
        return (sum(r[2] for r in rs) / len(rs), sum(r[3] for r in rs) / len(rs), sum(r[4] for r in rs) / len(rs), sum(r[5] for r in rs) / len(rs))
    rnd = random.Random(5)
    bs = [stat([rnd.choice(gws) for _ in gws]) for _ in range(B)]
    ci = lambda i, j: sorted(b[i] / b[j] for b in bs)
    xg, g, cp, cs = stat(gws)
    gr, cr = ci(1, 0), ci(3, 2)
    return f"n={len(rows)} goals proj {xg:.2f} v real {g:.2f} (real/proj {g / xg:.2f} [{gr[50]:.2f}, {gr[-50]:.2f}]); CS proj {cp:.3f} v real {cs:.3f} (real/proj {cs / cp:.2f} [{cr[50]:.2f}, {cr[-50]:.2f}])"


def main():
    params = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    for label, ctx, gws in (("2024-25", bench._season("2024-25")[0], range(5, 39)), ("2025-26", bench._season("2025-26")[0], range(5, 39)),
                            ("this season", bench.current_ctx(), range(4, (bench.current_ctx() and bench._CUR["cur"]) + 1))):
        rows = season(ctx, gws, params)
        print(f"{label}: {summary(rows)}")
        for band, sel in (("FDR 2", lambda r: r[1] <= 2), ("FDR 3", lambda r: r[1] == 3), ("FDR 4-5", lambda r: r[1] >= 4)):
            rs = [r for r in rows if sel(r)]
            if rs:
                n = len(rs)
                print(f"   {band}: n={n} goals {sum(r[2] for r in rs) / n:.2f} v {sum(r[3] for r in rs) / n:.2f}; CS {sum(r[4] for r in rs) / n:.3f} v {sum(r[5] for r in rs) / n:.3f}")


if __name__ == "__main__":
    main()
