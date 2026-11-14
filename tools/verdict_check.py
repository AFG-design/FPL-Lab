#!/usr/bin/env python3
"""FL-127: do the Strong / Marginal / Coin flip cut-offs separate calls that come off from ones that don't?

    python3 tools/verdict_check.py            # needs raw/ and archive/ (as bench.py)

Home labels three decisions with verdict() in site/js/core/plan.js:
  - captain: projected gap between the captain and the next-best starter that week; Strong >= 1, Marginal >= 0.4
  - lineup:  projected gap between the weakest starter and the best bench player that week; same cut-offs
  - transfer: projected gain of a move over the plan (here 5 GWs, the planner's default); Strong >= 3, Marginal >= 1

Only three gameweeks of Home cards are saved (GW8-10), far too few, so the same decisions are rebuilt out of sample
on 2024/25 and 2025/26 (and this season for the 1-GW decisions), with the model's forecast made from data before each
week (as bench.py: no injury flags, fixture odds only for weeks they were out).

Squads: the archive has no ownership or prices per gameweek, so a squad is the model's own pick three weeks earlier
(top 2 GK, 5 DEF, 5 MID, 3 FWD by 5-GW xP, at most 3 per club). That is an assumption: real squads are cheaper and
older, which gives bigger transfer gains. Transfers compare each squad player with the best non-squad player in his
position whose end-of-season price (the only one the archive has, an assumed proxy) is at most £0.5m more.

For each decision: the projected gap g >= 0 and the real gain (the chosen player's real points minus the
alternative's; 5-GW totals for transfers; a player who didn't play scores 0). A call "comes off" when the real gain is
positive (a tie counts half). Reported by the current verdict bands and by finer gap bins, with 95% intervals by
bootstrap over gameweeks.
"""
import os, random, sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import bench
from fplmodel import project

H, LAG, B = 5, 3, 2000
KINDS = ("captain", "captain pairs", "lineup", "lineup pairs", "transfer")
SQUAD = {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}
MIN_XI = {"GKP": 1, "DEF": 3, "MID": 2, "FWD": 1}
# (strong, marginal) as site/js/core/plan.js had them before FL-127, and as it has them now. Transfers didn't change.
OLD_CUT = {"captain": (1.0, 0.4), "lineup": (1.0, 0.4), "transfer": (3.0, 1.0)}
NEW_CUT = {"captain": (2.0, 1.5), "lineup": (2.0, 1.5), "transfer": (3.0, 1.0)}
CUTS = {k: (OLD_CUT[k.split()[0]], NEW_CUT[k.split()[0]]) for k in ("captain", "captain pairs", "lineup", "lineup pairs", "transfer")}   # (strong, marginal), as core/plan.js
BINS = {"captain": [0, .2, .4, .7, 1, 1.5, 2.5, 99], "lineup": [0, .2, .4, .7, 1, 1.5, 2.5, 99],
        "captain pairs": [0, .4, 1, 1.5, 2, 3, 4, 99], "lineup pairs": [0, .4, 1, 1.5, 2, 3, 4, 99],
        "transfer": [0, .5, 1, 2, 3, 4, 6, 99]}


def forecasts(ctx, team_at, origins):
    """{k: {pid: (pos, club, [xp k..k+H-1])}} from data before k."""
    out = {}
    for k in origins:
        cx = ctx
        if team_at:
            cx = dict(ctx)
            cx["elements"] = {pid: dict(e, team=team_at(pid, k) or e["team"]) for pid, e in ctx["elements"].items()}
            cx["team_gw_xg"] = bench._xg_at(ctx, team_at, k)
        res = project(cx, k, H, {"use_flags": False, "sim": 0})["players"]
        out[k] = {pid: (bench.POS[cx["elements"][pid]["element_type"]], cx["elements"][pid]["team"],
                        [r["xp"].get(g, 0.0) for g in range(k, k + H)]) for pid, r in res.items()}
    return out


def squad(fc):
    """Top players per position by 5-GW xP, at most 3 per club."""
    per_club, picked = defaultdict(int), []
    need = dict(SQUAD)
    for pid, (pos, club, xs) in sorted(fc.items(), key=lambda kv: -sum(kv[1][2])):
        if need[pos] and per_club[club] < 3:
            picked.append(pid); need[pos] -= 1; per_club[club] += 1
        if not any(need.values()):
            break
    return picked


def best_xi(sq, xp1, pos):
    """Highest 1-GW xP XI in a legal formation: the minimum per position, then the best outfield players left."""
    by = sorted(sq, key=lambda p: -xp1.get(p, 0.0))
    xi = []
    for ps, n in MIN_XI.items():
        xi += [p for p in by if pos[p] == ps][:n]
    rest = [p for p in by if p not in xi and pos[p] != "GKP"]
    xi += rest[:11 - len(xi)]
    return xi, [p for p in by if p not in xi and pos[p] != "GKP"]


def decisions(ctx, team_at, origins, real_h):
    fc = forecasts(ctx, team_at, origins)
    pts = lambda pid, g: ctx["pts_gw"].get(pid, {}).get(g, 0)
    cost = {pid: e.get("now_cost") or 0 for pid, e in ctx["elements"].items()}
    rows = defaultdict(list)   # kind -> [(gw, gap, real gain)]
    for k in origins:
        if k - LAG not in fc:
            continue
        now = fc[k]
        sq = [p for p in squad(fc[k - LAG]) if p in now]
        pos = {p: now[p][0] for p in sq}
        xp1 = {p: now[p][2][0] for p in sq}
        xi, bench_ = best_xi(sq, xp1, pos)
        top = sorted(xi, key=lambda p: -xp1[p])
        if len(top) >= 2:
            rows["captain"].append((k, xp1[top[0]] - xp1[top[1]], pts(top[0], k) - pts(top[1], k)))
        # the swap Home weighs: the weakest outfield starter whose removal keeps the formation legal v the best sub
        if bench_:
            sub = bench_[0]
            cands = [p for p in xi if pos[p] != "GKP" and (pos[p] == pos[sub] or
                     sum(pos[q] == pos[p] for q in xi) > MIN_XI[pos[p]])]
            if cands:
                weak = min(cands, key=lambda p: xp1[p])
                rows["lineup"].append((k, xp1[weak] - xp1[sub], pts(weak, k) - pts(sub, k)))
        # More of the same kind of call, for a usable sample (pairs from one week share its luck, so the intervals
        # bootstrap over weeks): captain-like = any two of the five highest-projected starters; lineup-like = one
        # of the four lowest-projected outfield starters v one outfield bench player.
        for i, a in enumerate(top[:5]):
            for b in top[i + 1:5]:
                rows["captain pairs"].append((k, xp1[a] - xp1[b], pts(a, k) - pts(b, k)))
        low = sorted([p for p in xi if pos[p] != "GKP"], key=lambda p: xp1[p])[:4]
        for a in low:
            for b in bench_:
                hi_, lo_ = (a, b) if xp1[a] >= xp1[b] else (b, a)
                rows["lineup pairs"].append((k, xp1[hi_] - xp1[lo_], pts(hi_, k) - pts(lo_, k)))
        if real_h and all(g <= real_h for g in range(k, k + H)):
            owned = set(sq)
            for out in sq:
                p_out, _, xs_out = now[out]
                pool = [(sum(xs) - sum(xs_out), pid) for pid, (ps, _, xs) in now.items()
                        if ps == p_out and pid not in owned and cost[pid] <= cost[out] + 5]
                if not pool:
                    continue
                gain, inn = max(pool)
                if gain > 0:
                    real = sum(pts(inn, g) - pts(out, g) for g in range(k, k + H))
                    rows["transfer"].append((k, gain, real))
    return rows


def stats(rows, lo, hi):
    sel = [(k, r) for k, g, r in rows if lo <= g < hi]
    if not sel:
        return None
    by = defaultdict(list)
    for k, r in sel:
        by[k].append(r)
    ks = list(by)
    win = lambda rs: sum(1 if r > 0 else .5 if r == 0 else 0 for r in rs) / len(rs)
    flat = [r for _, r in sel]
    rng = random.Random(1); wins, means = [], []
    for _ in range(B):
        rs = [r for k in (rng.choice(ks) for _ in ks) for r in by[k]]
        wins.append(win(rs)); means.append(sum(rs) / len(rs))
    wins.sort(); means.sort()
    q = lambda v: (v[int(.025 * B)], v[int(.975 * B) - 1])
    return len(flat), win(flat), q(wins), sum(flat) / len(flat), q(means)


def report(name, rows):
    print(f"\n{name}: {len(rows)} decisions over {len({k for k, _, _ in rows})} GWs (gap = projected, real = actual gain)")
    for which, (strong, marg) in zip(("before", "now"), CUTS[name]):
        if which == "now" and CUTS[name][0] == CUTS[name][1]:
            continue
        print(f"  cut-offs {which} (Strong {strong:g}, Marginal {marg:g}):")
        for label, lo, hi in (("Coin flip", 0, marg), ("Marginal", marg, strong), ("Strong", strong, 1e9)):
            s = stats(rows, lo, hi)
            if s:
                n, w, wi, m, mi = s
                print(f"    {label:<9} gap {lo:g}+{'' if hi > 1e8 else f' to {hi:g}'}: n {n:4d}  comes off {w:.0%} "
                      f"[{wi[0]:.0%}, {wi[1]:.0%}]  real gain {m:+.2f} [{mi[0]:+.2f}, {mi[1]:+.2f}]")
    print("  finer bins:")
    b = BINS[name]
    for lo, hi in zip(b, b[1:]):
        s = stats(rows, lo, hi)
        if s:
            n, w, wi, m, mi = s
            print(f"    {lo:>4g} to {hi if hi < 99 else '':<4}: n {n:4d}  comes off {w:.0%} [{wi[0]:.0%}, {wi[1]:.0%}]  "
                  f"real gain {m:+.2f} [{mi[0]:+.2f}, {mi[1]:+.2f}]")


def main():
    every = defaultdict(list)
    for season in ("2024-25", "2025-26"):
        ctx, team_at = bench._season(season)
        rows = decisions(ctx, team_at, range(5, 39), 38)
        print(f"\n===== {season} =====")
        for name in KINDS:
            report(name, rows[name])
            every[name] += [(f"{season}:{k}", g, r) for k, g, r in rows[name]]
    ctx = bench.current_ctx(); cur = bench._CUR["cur"]
    rows = decisions(ctx, None, range(3, cur + 1), cur)
    print(f"\n===== this season (GW3 to {cur}) =====")
    for name in KINDS:
        if rows[name]:
            report(name, rows[name])
            every[name] += [(f"cur:{k}", g, r) for k, g, r in rows[name]]
    print("\n===== all seasons pooled =====")
    for name in KINDS:
        report(name, every[name])


if __name__ == "__main__":
    main()
