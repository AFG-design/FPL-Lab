#!/usr/bin/env python3
"""Model test bench: rolling-origin backtests on this season AND last season, scored on
accuracy and on the decisions the app makes (who to pick, who to captain).

  python3 bench.py                     # current model (DEFAULTS)
  python3 bench.py '{"recency":0.8}'   # compare a parameter set against the current model
  python3 bench.py --no-archive-odds   # past seasons without odds (the setup before odds_archive.py)
  python3 bench.py --no-h5             # skip the 5-GW totals check (planner horizon; the slow part)

Each gameweek k is projected from data before k only. Past seasons come from archive.py, with betting
odds from odds/archive/<season>.json (odds_archive.py) when present, as the live model has. A season with
no odds file runs odds-free and says so; `--no-archive-odds` forces that, to reproduce older log figures.
There are no historical injury flags in the archive, so both sides of any comparison run without them. The archive's FPL "xP" column is not a usable benchmark (mostly zeros, and
filled in after the fact), so FPL's own projection is compared only in the live log (history/).

Injury flags in this season's backtest come only from history/status.json (saved before each deadline);
the hindsight flags in ctx["out"] are not used for them. Decisions should rest on corr / rank / picks.
Captain (cap) and top-5 are noisy (the top two projections are ~0.2 pts apart), so a candidate's cap and
top5 differences are only meaningful when the paired bootstrap 95% CI (over gameweeks) excludes 0.

Under each model line, "all players" scores the pool plus everyone outside it who played that GW (no minutes in
the 3 GWs before: new signings, returners), with that outside-pool group on its own, so a change
that helps or hurts them is visible. It is reported only; the decision metrics above still use the pool.

FL-161 adds lines only (every earlier line prints exactly as before):
- "part scores": a proper score for each scoring part on its raw projection, before the final calibration
  (backtest.part_scores; lower is better): log-loss for clean sheets, Brier for start chance, 60+ and defensive
  contributions, Poisson deviance for goals and assists, squared error for bonus and saves. Per season, with a paired
  95% CI for the candidate. Pool players in one-fixture weeks only. 2024/25 had no defensive contributions, so its DC
  score is 0 for both sides and only dilutes the pooled DC figure; read DC on 2025/26.
- "pooled 2025-26 + 2024-25": one paired bootstrap 95% CI per candidate over both past seasons together, for 5-GW picks
  and each part score. Gameweeks are resampled within each season, then pooled.
"""
import json, math, os, random, sys
from collections import defaultdict

from fplmodel import prepare, project, POS, europe_dates, euro_weeks
import archive, selling
from backtest import part_scores, mean_scores, scores_ci, fmt_scores, fmt_scores_ci

HERE = os.path.dirname(os.path.abspath(__file__))
TOPN = {"GKP": 5, "DEF": 15, "MID": 15, "FWD": 10}
ARCHIVE_ODDS = True   # set False by --no-archive-odds
H5 = 5                # gameweeks summed for the planner-horizon check (0 = off, --no-h5)


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
    per = {"cap1": {}, "cap5": {}, "picks": {}}   # per-gameweek series and captain ids, for paired CIs
    capid = {}
    for g, rows in rows_by_gw.items():
        if not rows:
            continue
        for _, pos, p, a in rows:
            P.append(p); A.append(a)
            pos_pa[pos][0].append(p); pos_pa[pos][1].append(a)
        spear.append(_corr(_ranks([r[2] for r in rows]), _ranks([r[3] for r in rows])))
        top = sorted(rows, key=lambda r: -r[2])
        cap1.append(top[0][3]); cap5.append(sum(r[3] for r in top[:5]) / 5)
        per["cap1"][g] = cap1[-1]; per["cap5"][g] = cap5[-1]; capid[g] = top[0][0]
        tot = cnt = 0
        for pos, n in TOPN.items():
            best = [r for r in top if r[1] == pos][:n]
            tot += sum(r[3] for r in best); cnt += len(best)
        picks.append(tot / cnt)
        per["picks"][g] = picks[-1]
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
        "gws": len(rows_by_gw), "_per": per, "_capid": capid,
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


def all_rows(ctx, k, pred):
    """FL-137: the pool plus everyone outside it who played in GW k, for the "all players" line. The pool
    (pool_rows: minutes in one of the 3 GWs before) leaves out new signings and returners, about 6% of appearances,
    which the model projects far too low (docs/archive/parts-audit.md, section 4). Rows are (pid, pos, pred, actual, in_pool).
    The in-pool rows are exactly pool_rows (so "all" = pool + the appearances it misses). An outside-pool player with
    no projection counts as projected 0, never dropped, so a gap in the model shows up here instead of hiding.
    Outside-pool players who didn't play GW k aren't scored (nothing would tell them apart from everyone unused)."""
    rows = []
    for pid, e in ctx["elements"].items():
        a = ctx["pts_gw"].get(pid, {}).get(k)
        if a is None:
            continue
        in_pool = any(ctx["pstats"].get(pid, {}).get(g, {}).get("minutes", 0) > 0 for g in range(k - 3, k))
        if in_pool and pid not in pred:   # as pool_rows
            continue
        if not in_pool and ctx["pstats"].get(pid, {}).get(k, {}).get("minutes", 0) <= 0:
            continue
        rows.append((pid, POS[e["element_type"]], pred.get(pid, 0.0), a, in_pool))
    return rows


def score_all(rows_by_gw):
    """Accuracy over all_rows: every player who played, and the part outside the pool on its own."""
    rows = [r for rs in rows_by_gw.values() for r in rs]
    out = [r for r in rows if not r[4]]

    def part(rs):
        if not rs:
            return {"n": 0, "mae": float("nan"), "corr": float("nan"), "bias": float("nan"),
                    "pred": float("nan"), "real": float("nan")}
        P, A = [r[2] for r in rs], [r[3] for r in rs]
        n = len(rs)
        return {"n": n, "mae": sum(abs(p - a) for p, a in zip(P, A)) / n, "corr": _corr(P, A) if n > 1 else float("nan"),
                "bias": (sum(P) - sum(A)) / n, "pred": sum(P) / n, "real": sum(A) / n}
    return {"all": part(rows), "outside": part(out)}


def fmt_all(name, m):
    a, o = m["all"], m["outside"]
    share = f"{100 * o['n'] / a['n']:.1f}%" if a["n"] else "–"
    return (f"  all players   {name:<16} n={a['n']:5d} MAE {a['mae']:.3f} corr {a['corr']:.3f} bias {a['bias']:+.2f}"
            f" | outside pool n={o['n']} ({share}) projected {o['pred']:.2f} v real {o['real']:.2f}, MAE {o['mae']:.3f}")


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
    try:   # genuine at-the-time flags; grows with each build
        status_log = json.load(open(os.path.join(HERE, "history", "status.json")))
    except Exception:
        status_log = None
    _CUR["ctx"] = prepare(boot, fixtures, live, priors, market, status_log=status_log)
    # FL-115: the European weeks the live build cuts (europe.json), so the bench tests the model as it runs
    _CUR["ctx"]["congestion"] = euro_weeks(fixtures, europe_dates(os.path.join(HERE, "europe.json"), boot["teams"]))
    try:   # FPL's notes as they stood at each deadline, for the honest weeks-out rebuild (fplmodel.known_out, FL-068)
        _CUR["ctx"]["news_log"] = json.load(open(os.path.join(HERE, "history", "news.json")))
    except FileNotFoundError:
        print("history/news.json missing: weeks out come from the status log only")
    try:   # selling counts per round (selling.py; history/sell_hist.json from the live build) for xmins_sell
        _CUR["ctx"]["sell"] = selling.from_rounds(json.load(open(os.path.join(HERE, "history", "sell_hist.json")))["rounds"])
    except FileNotFoundError:
        pass   # no table: a run with xmins_sell on raises in xmins.predict_sell rather than guessing
    _CUR["cur"] = cur
    return _CUR["ctx"]


def run_current(params, gws=None, everyone=None, scores=None):
    """everyone: optional dict, filled with all_rows per GW for the "all players" line (the pool is unchanged).
    scores: optional dict, filled with backtest.part_scores per GW (FL-161), from the same projections."""
    ctx = current_ctx()
    out = {}
    for k in (gws or range(3, _CUR["cur"] + 1)):
        res = project(ctx, k, 1, dict(params, use_flags=False))["players"]
        pred = {pid: r["xp"].get(k, 0.0) for pid, r in res.items()}
        out[k] = pool_rows(ctx, k, pred)
        if everyone is not None:
            everyone[k] = all_rows(ctx, k, pred)
        if scores is not None:
            scores[k] = part_scores(ctx, k, res)
    return out


_SEASON = {}


def _season(season):
    if season not in _SEASON:
        boot_now = json.load(open(os.path.join(HERE, "raw", "bootstrap.json")))
        boot, fixtures, live, priors, team_at = archive.load_season(season, boot_now)
        market = archive.load_odds(season) if ARCHIVE_ODDS else None
        if market is None:
            why = "--no-archive-odds" if not ARCHIVE_ODDS else f"no odds/archive/{season}.json (run odds_archive.py)"
            print(f"[{season}] running WITHOUT betting odds: {why}")
        else:
            print(f"[{season}] with betting odds for {len(market['matches'])} of {market['fixtures']} fixtures")
        ctx = prepare(boot, fixtures, live, priors, market)
        ctx["sell"] = selling.from_archive(season)   # pre-deadline transfer counts for xmins_sell
        # FL-115: past European weeks (europe_hist.json, openfootball). A season or club with no dates gets no cut.
        ctx["congestion"] = euro_weeks(fixtures, europe_dates(os.path.join(HERE, "europe_hist.json"), boot["teams"], season))
        print(f"[{season}] European weeks: {len(ctx['congestion'])} club-gameweeks")
        # credit each gameweek's xG to the club the player was at then
        tgx = defaultdict(lambda: defaultdict(float))
        for pid, gs in ctx["pstats"].items():
            for g, s in gs.items():
                t = team_at(pid, g + 1) or ctx["elements"][pid]["team"]
                tgx[t][g] += float(s["expected_goals"])
        ctx["team_gw_xg_then"] = tgx   # the archive's own club per week (same as clubs_then)
        # FL-065: his club each week from the archive, for his past opponents (fplmodel reads ctx["club_then"])
        ctx["club_then"] = {(pid, g): team_at(pid, g + 1) or ctx["elements"][pid]["team"]
                            for pid, gs in ctx["pstats"].items() for g in gs}
        _SEASON[season] = (ctx, team_at)
    return _SEASON[season]


def _xg_at(ctx, team_at, k):
    """Old behaviour (xg_club_then off), as the live model then ran at GW k's deadline: every past week's xG credited
    to the club each player was at by GW k."""
    t = defaultdict(lambda: defaultdict(float))
    for pid, gs in ctx["pstats"].items():
        c = team_at(pid, k) or ctx["elements"][pid]["team"]
        for g, s in gs.items():
            if g < k:
                t[c][g] += float(s["expected_goals"])
    return t


def run_archive(params, season="2025-26", gws=range(4, 39), everyone=None, scores=None):
    ctx, team_at = _season(season)
    out = {}
    for k in gws:
        cx = dict(ctx)
        cx["elements"] = {pid: dict(e, team=team_at(pid, k) or e["team"]) for pid, e in ctx["elements"].items()}
        cx["team_gw_xg"] = _xg_at(ctx, team_at, k)
        res = project(cx, k, 1, dict(params, use_flags=False))["players"]
        pred = {pid: r["xp"].get(k, 0.0) for pid, r in res.items()}
        out[k] = pool_rows(cx, k, pred)
        if everyone is not None:
            everyone[k] = all_rows(cx, k, pred)
        if scores is not None:
            scores[k] = part_scores(cx, k, res)
    return out


def run_horizon(params, season, H):
    """Planner check: from each origin k, project k..k+H-1 from data before k and compare each pool player's
    H-week total with his real H-week total (the solver plans over several weeks, while score() judges one).
    Origins: every k whose H weeks have all finished (this season: from GW3; archive: GW5 to 39-H).
    Returns {k: [(pid, pos, projected total, real total)]}; a player missing a week scores 0 for it."""
    if season == "current":
        ctx, team_at = current_ctx(), None
        origins = range(3, _CUR["cur"] - H + 2)
    else:
        ctx, team_at = _season(season)
        origins = range(5, 39 - H + 1)
    out = {}
    for k in origins:
        cx = ctx
        if team_at:
            cx = dict(ctx)
            cx["elements"] = {pid: dict(e, team=team_at(pid, k) or e["team"]) for pid, e in ctx["elements"].items()}
            cx["team_gw_xg"] = _xg_at(ctx, team_at, k)
        res = project(cx, k, H, dict(params, use_flags=False))["players"]
        rows = []
        for pid, r in res.items():
            if not any(cx["pstats"].get(pid, {}).get(g, {}).get("minutes", 0) > 0 for g in range(k - 3, k)):
                continue
            pg = cx["pts_gw"].get(pid, {})
            rows.append((pid, POS[cx["elements"][pid]["element_type"]], sum(r["xp"].get(g, 0.0) for g in range(k, k + H)),
                         sum(pg.get(g, 0) for g in range(k, k + H))))
        out[k] = rows
    return out


def score_h(per):
    """corr of H-week totals (all origins pooled) and picks: avg real H-week total of the model's top-N per position."""
    P = [r[2] for rs in per.values() for r in rs]; A = [r[3] for rs in per.values() for r in rs]
    picks = {}
    for k, rs in per.items():
        top = sorted(rs, key=lambda r: -r[2])
        best = [r for pos, n in TOPN.items() for r in [x for x in top if x[1] == pos][:n]]
        if best:
            picks[k] = sum(r[3] for r in best) / len(best)
    return {"n": len(P), "origins": len(picks), "corr": _corr(P, A) if P else float("nan"),
            "picks": sum(picks.values()) / len(picks) if picks else float("nan"), "_per": picks}


def fmt(name, m):
    pc = " ".join(f"{p}:{m['pos_corr'].get(p, float('nan')):.3f}" for p in ("GKP", "DEF", "MID", "FWD"))
    return (f"{name:<22} n={m['n']:5d} MAE {m['mae']:.3f} RMSE {m['rmse']:.3f} corr {m['corr']:.3f} "
            f"rank {m['spearman']:.3f} bias {m['bias']:+.2f} | picks {m['picks']:.2f} cap {m['cap1']:.2f} top5 {m['cap5']:.2f} | {pc}")


def paired_ci(base, cand, n=2000, seed=1):
    """Paired bootstrap over gameweeks of cand - base for cap1, cap5 and picks (mean diff, 95% CI),
    plus how many gameweeks the captain changed."""
    out = {}
    for key in ("cap1", "cap5", "picks"):
        a, b = base["_per"][key], cand["_per"][key]
        d = [b[g] - a[g] for g in sorted(set(a) & set(b))]
        rng = random.Random(seed)
        means = sorted(sum(d[rng.randrange(len(d))] for _ in d) / len(d) for _ in range(n))
        out[key] = (sum(d) / len(d), means[int(0.025 * n)], means[int(0.975 * n) - 1])
    ids = sorted(set(base["_capid"]) & set(cand["_capid"]))
    out["cap_changed"] = (sum(1 for g in ids if base["_capid"][g] != cand["_capid"][g]), len(ids))
    return out


def fmt_ci(ci):
    f = lambda k: f"{ci[k][0]:+.2f} [{ci[k][1]:+.2f}, {ci[k][2]:+.2f}]" + ("" if ci[k][1] > 0 or ci[k][2] < 0 else " ~0")
    return (f"  paired 95% CI (cand - current, bootstrap over GWs): cap {f('cap1')} top5 {f('cap5')} picks {f('picks')}"
            f" | captain changed in {ci['cap_changed'][0]} of {ci['cap_changed'][1]} weeks")


def compare(variants, seasons=("current", "2025-26", "2024-25"), quiet=False):
    """variants: {name: params}. Returns {season: {name: metrics}}."""
    res = {}
    for s in seasons:
        res[s] = {}
        if not quiet:
            print(f"--- {s} ---")
        for name, p in variants.items():
            ev, sc = {}, {}
            if s == "current":
                m = score(run_current(p, everyone=ev, scores=sc))
            else:
                m = score(run_archive(p, s, everyone=ev, scores=sc))
            res[s][name] = m
            m["_all"] = score_all(ev)
            m["_scores"] = sc
            if not quiet:
                print(fmt(name, m))
                print(fmt_all(name, m["_all"]))
                print(fmt_scores(name, mean_scores(sc)))
        names = list(variants)
        for name in names[1:]:
            ci = res[s].setdefault("_ci", {})[name] = paired_ci(res[s][names[0]], res[s][name])
            if not quiet:
                print(fmt_ci(ci))
                print(f"  part scores, paired 95% CI ({name} - {names[0]}, bootstrap over GWs; lower loss is better):")
                for line in fmt_scores_ci(scores_ci({s: res[s][names[0]]["_scores"]}, {s: res[s][name]["_scores"]}),
                                          indent="    "):
                    print(line)
        if H5:
            hs = {name: score_h(run_horizon(p, s, H5)) for name, p in variants.items()}
            res[s]["_h5"] = hs
            if not quiet:
                if not hs[names[0]]["origins"]:
                    print(f"  {H5}-GW totals: not enough finished gameweeks yet")
                for name in names:
                    h = hs[name]
                    if not h["origins"]:
                        continue
                    line = f"  {H5}-GW totals  {name:<16} corr {h['corr']:.3f} picks {h['picks']:.2f} ({h['origins']} origins)"
                    if name != names[0]:
                        b = hs[names[0]]["_per"]
                        d = [h["_per"][k] - b[k] for k in sorted(set(b) & set(h["_per"]))]
                        rng = random.Random(1)
                        ms = sorted(sum(d[rng.randrange(len(d))] for _ in d) / len(d) for _ in range(2000))
                        lo, hi = ms[50], ms[1949]
                        line += (f" | vs current: corr {h['corr'] - hs[names[0]]['corr']:+.3f}, picks "
                                 f"{sum(d) / len(d):+.2f} [{lo:+.2f}, {hi:+.2f}]" + ("" if lo > 0 or hi < 0 else " ~0"))
                    print(line)
    pooled(res, list(variants), quiet)
    return res


POOL = ("2025-26", "2024-25")   # FL-161: the past seasons pooled for the deciding interval


def pooled(res, names, quiet=False, n=2000, seed=1):
    """FL-161: one paired bootstrap 95% interval per candidate over 2024/25 and 2025/26 together, for 5-GW picks and
    for each part's proper score. Gameweeks (5-GW origins for picks) are resampled with replacement within each
    season, keeping each season's count, then pooled: the statistic is the mean over all resampled weeks (picks; each
    origin counts once) or total loss difference / total player-weeks (part scores). The per-season intervals above
    are unchanged. Missing: if either past season wasn't run, or --no-h5 is on (no 5-GW picks), the line says so
    instead of pooling one season and calling it pooled. Stored in res["_pooled"][name]."""
    if len(names) < 2:
        return
    have = [s for s in POOL if s in res]
    if len(have) < len(POOL):
        if not quiet:
            print(f"--- pooled {' + '.join(POOL)}: skipped, {', '.join(s for s in POOL if s not in res)} not run ---")
        return
    if not quiet:
        print(f"--- pooled {' + '.join(POOL)} (paired bootstrap, GWs resampled within each season, then pooled) ---")
    for name in names[1:]:
        out = res.setdefault("_pooled", {})[name] = {}
        if all("_h5" in res[s] for s in POOL):
            per = []
            for s in POOL:
                b, c = res[s]["_h5"][names[0]]["_per"], res[s]["_h5"][name]["_per"]
                per.append([c[k] - b[k] for k in sorted(set(b) & set(c))])
            per = [d for d in per if d]
            tot = [x for d in per for x in d]
            rng = random.Random(seed)
            ms = []
            for _ in range(n):
                draw = [d[rng.randrange(len(d))] for d in per for _ in d]
                ms.append(sum(draw) / len(draw))
            ms.sort()
            lo, hi = ms[int(0.025 * n)], ms[int(0.975 * n) - 1]
            out["h5_picks"] = (sum(tot) / len(tot), lo, hi, len(tot))
            if not quiet:
                print(f"  {H5}-GW picks     {name:<16} {sum(tot) / len(tot):+.3f} [{lo:+.3f}, {hi:+.3f}]"
                      + ("" if lo > 0 or hi < 0 else " ~0") + f" ({len(tot)} origins)")
        elif not quiet:
            print(f"  {H5 or 5}-GW picks: not run (--no-h5), so no pooled deciding interval")
        out["scores"] = scores_ci({s: res[s][names[0]]["_scores"] for s in POOL},
                                  {s: res[s][name]["_scores"] for s in POOL})
        if not quiet:
            print(f"  part scores ({name} - {names[0]}; lower loss is better, so negative = better):")
            for line in fmt_scores_ci(out["scores"], indent="    "):
                print(line)


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--no-archive-odds" in args:
        ARCHIVE_ODDS = False
        args.remove("--no-archive-odds")
    if "--no-h5" in args:
        H5 = 0
        args.remove("--no-h5")
    variants = {"current model": {}}
    if args:
        variants["candidate"] = json.loads(args[0])
    compare(variants)
