#!/usr/bin/env python3
"""Strategy replay: do Balanced, Play safe and Chase rank behave as their names say on real past seasons?

  python3 strategy_replay.py                  # 2025-26 and 2024-25, from GW5 (no chips, original mode)
  python3 strategy_replay.py 2025-26 --from 1 --to 38 --chips solver --seed 0 --json out.json

For each season, teams start from the same squad (the best £100m squad for the first 5 weeks, built with the
projections of the time). Every gameweek each team re-plans the next 5 weeks with its own strategy
(optimise.strategy_plans, the same code the site's plans use), makes only that week's moves, and scores the real
points of the XI and captain it picked, with simple auto-subs. Projections for gameweek k come from data before k only
(bench.py's rolling origin): for GW1 that is 100% pre-season priors + betting-market fixture odds (hist_gws empty);
for GW2-4 it adds only the completed gameweeks 1..k-1.

FL-230 extensions (analysis & replay tooling only; never changes fplmodel.py or optimise.py defaults):
  - --from 1: full-season GW1-38 replay.
  - --chips none|simple|solver: season-accurate chip rules (2024-25: WC1 GW1-19, WC2 GW20-38, FH/BB/TC GW1-38,
    Assistant Manager omitted; 2025-26: two full sets WC/FH/BB/TC, 1st half expires after GW19, 2nd half GW20-38).
    Neither simple nor solver ever reads real points.
  - --switch: pre-registered strategy-switching rule (FL-230 Lever 3b, written before running, never tuned):
      GW1-10: balanced.
      GW11-38: gap = cum_real - cum_field (strictly from completed GWs < k), left = 38 - k:
        gap >= 120 -> safe;
        gap < 40 or (left <= 10 and gap < 100) -> chase;
        otherwise -> balanced.
  - --balanced-hit-margin M: FL-230 Lever 3c, allow Balanced at most 1 hit/GW only when projected gain over the
    5-GW plan window exceeds 4 + M (i.e. value_with_hit >= value_no_hit + M * hits).
  - --hindsight: FL-230 Part 4 (HINDSIGHT DIAGNOSTIC ONLY — never shipped): each GW from the same current squad,
    solves all 3 strategies and keeps the one with highest THIS-WEEK real points (after hits).
  - --cache-dir DIR: cache/load precomputed rolling-origin projections (pickle) so multi-seed runs stay fast and
    share byte-identical projections.

Missing or approximate data, said out loud:
  - Past seasons have no "managers around your rank" ownership; overall ownership (merged_gw.csv `selected`) stands in
    for it, without captaincy. Safe/Chase therefore track the whole game, not a rank band.
  - No historical injury flags (as bench.py); nailed comes from the projected start chance and minutes.
  - A player missing from a week's price list can't be bought that week; a gameweek with no projection is skipped.
  - Auto-subs ignore formation limits beyond keeping one goalkeeper: an approximation that treats all teams alike.
  - 2024-25 Assistant Manager chip is omitted.
Needs raw/bootstrap.json (scoring rules) like bench.py, and downloads the archive on first run (archive.py).
"""
import argparse, copy, json, math, os, pickle, random, statistics, sys, time
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


def season_chips(season):
    """Real chip pool and legal GW windows {chip_id: (lo_gw, hi_gw)} for a season.
    2024-25: one set (WC1 GW1-19, WC2 GW20-38, FH/BB/TC GW1-38); Assistant Manager omitted.
    2025-26: two sets (one per half: WC/FH/BB/TC each); 1st-half chips expire after GW19.
    """
    if season == "2024-25":
        return {"WC1": (1, 19), "WC2": (20, 38), "FH": (1, 38), "BB": (1, 38), "TC": (1, 38)}
    return {
        "WC1": (1, 19), "FH1": (1, 19), "BB1": (1, 19), "TC1": (1, 19),
        "WC2": (20, 38), "FH2": (20, 38), "BB2": (20, 38), "TC2": (20, 38),
    }


def chip_kind(chip_id):
    return chip_id.rstrip("12")


def fixture_calendar(fixtures, last_gw=38):
    """Return (dgw_teams, bgw_teams) maps {gw: count_of_teams} using ONLY the fixture schedule (zero results/points)."""
    by_gw = defaultdict(lambda: defaultdict(int))
    teams = set()
    for f in fixtures:
        ev = f.get("event")
        if not ev:
            continue
        h, a = f.get("team_h"), f.get("team_a")
        if h:
            by_gw[ev][h] += 1; teams.add(h)
        if a:
            by_gw[ev][a] += 1; teams.add(a)
    dgw, bgw = {}, {}
    for g in range(1, last_gw + 1):
        cnt = by_gw[g]
        dgw[g] = sum(1 for t in teams if cnt.get(t, 0) >= 2)
        bgw[g] = sum(1 for t in teams if cnt.get(t, 0) == 0)
    return dgw, bgw


def simple_chip_schedule(season, dgw, bgw):
    """Pre-assign BB, TC, FH weeks for the 'simple' chip rule using ONLY fixture counts (never real points).
    WC is handled causally week-by-week (no future-projection lookahead).
    """
    pool = season_chips(season)
    sched = {}   # chip_id -> gw
    used = set()
    # Assign BB first (biggest DGW), then TC (next biggest DGW), then FH (biggest BGW)
    for kind in ("BB", "TC", "FH"):
        for cid, (lo, hi) in pool.items():
            if chip_kind(cid) != kind:
                continue
            cand = [g for g in range(lo, hi + 1) if g not in used]
            if kind in ("BB", "TC"):
                best_n = max(dgw.get(g, 0) for g in cand)
                if best_n > 0:
                    # tie-break: later GW in window
                    g_pick = max(g for g in cand if dgw.get(g, 0) == best_n)
                else:
                    # No DGW in window (e.g. 2025-26 1st half): place near end of half
                    g_pick = hi - 1 if kind == "BB" and (hi - 1) in cand else max(cand)
            else:  # FH
                best_n = max(bgw.get(g, 0) for g in cand)
                if best_n > 0:
                    g_pick = max(g for g in cand if bgw.get(g, 0) == best_n)
                else:
                    g_pick = hi - 2 if (hi - 2) in cand else max(cand)
            sched[cid] = g_pick
            used.add(g_pick)
    return sched


def switch_mode(k, cum_real, cum_field):
    """Pre-registered FL-230 Lever 3b strategy-switching rule (uses ONLY completed GWs < k)."""
    if k <= 10:
        return "balanced"
    gap = cum_real - cum_field
    left = 38 - k
    if gap >= 120:
        return "safe"
    if gap < 40 or (left <= 10 and gap < 100):
        return "chase"
    return "balanced"


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


def app_pick(plans, mode):
    """--pick app: the plan the app recommends for a strategy, worked out as build.py does."""
    pre = "" if mode == "balanced" else f"{mode}_"
    roll = plans.get(pre + "roll")
    if not roll:
        return None
    sub = {}
    for k in ("roll", "one", "two", "three"):
        p = plans.get(pre + k)
        if p:
            ft_diff = optimise.ft_bonus(p["ft_left"]) - optimise.ft_bonus(roll["ft_left"])
            sub[pre + k] = dict(p, vs_roll=p["xp_total"] + ft_diff - roll["xp_total"])
    if hasattr(optimise, "recommended"):
        return optimise.recommended(sub)[mode]
    keys = list(sub)
    top = max(sub[k]["vs_roll"] for k in keys)
    return next(k for k in keys if sub[k]["vs_roll"] >= top - optimise.MIN_PROFIT)


def make_projections(ctx, team_at, price, k, last, sim):
    """Compute rolling-origin projections for GW k using strictly data from GWs < k."""
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


def load_or_build_cache(season, k_from, k_to, sim, cache_dir, ctx, team_at, price, last):
    """Load or compute {k: (pl, gws)} for all GWs in [k_from, k_to]."""
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        path = os.path.join(cache_dir, f"{season}_gw{k_from}_{k_to}_sim{sim}.pkl")
        if os.path.exists(path):
            with open(path, "rb") as f:
                return pickle.load(f)
    t0 = time.time()
    cache = {}
    for k in range(k_from, k_to + 1):
        cache[k] = make_projections(ctx, team_at, price, k, last, sim)
    if cache_dir:
        tmp = path + f".tmp.{os.getpid()}"
        with open(tmp, "wb") as f:
            pickle.dump(cache, f)
        os.replace(tmp, path)
        print(f"  cached {season} GW{k_from}-{k_to} sim={sim} in {time.time() - t0:.1f}s -> {path}", flush=True)
    return cache


def audit_week(gw, squad, bank, ft, xi, bench, cap, pl, moved, chip_id, chip_pool, used_chips,
               hits, allow_hit, prev_held_over):
    """Strict independent FPL rule checker. Returns list of violation strings (empty = legal)."""
    errs = []
    if bank < -0.05:
        errs.append(f"GW{gw}: negative bank {bank}")
    if len(squad) != 15 or len(set(squad)) != 15:
        errs.append(f"GW{gw}: squad size {len(squad)} unique {len(set(squad))}")
    pos_cnt = defaultdict(int)
    club_cnt = defaultdict(int)
    for i in squad:
        pos_cnt[pl[i]["pos"]] += 1
        club_cnt[pl[i]["team"]] += 1
    for pos, req in optimise.SHAPE.items():
        if pos_cnt[pos] != req:
            errs.append(f"GW{gw}: {pos} count {pos_cnt[pos]} != {req}")
    for c, n in club_cnt.items():
        lim = optimise.CLUB_MAX if moved else optimise.CLUB_MAX + prev_held_over.get(c, 0)
        if n > lim:
            errs.append(f"GW{gw}: {n} players from club {c} (limit {lim})")
    if len(xi) != 11 or set(xi) | set(bench) != set(squad) or set(xi) & set(bench):
        errs.append(f"GW{gw}: invalid XI/bench partition")
    xi_pos = defaultdict(int)
    for i in xi:
        xi_pos[pl[i]["pos"]] += 1
    for pos in optimise.SHAPE:
        if xi_pos[pos] < optimise.XI_MIN[pos] or xi_pos[pos] > optimise.XI_MAX[pos]:
            errs.append(f"GW{gw}: XI {pos} count {xi_pos[pos]} out of bounds")
    if cap not in xi:
        errs.append(f"GW{gw}: captain {cap} not in XI")
    if not (1 <= ft <= 5):
        errs.append(f"GW{gw}: ft {ft} out of 1..5")
    if chip_id is not None:
        if chip_id not in chip_pool:
            errs.append(f"GW{gw}: unknown chip {chip_id}")
        elif chip_id in used_chips:
            errs.append(f"GW{gw}: chip {chip_id} used twice")
        else:
            lo, hi = chip_pool[chip_id]
            if not (lo <= gw <= hi):
                errs.append(f"GW{gw}: chip {chip_id} outside window {lo}..{hi}")
    if hits > 0 and not allow_hit:
        errs.append(f"GW{gw}: unexpected hit ({hits})")
    return errs


def solve_mode_plan(m, pl, squad, sell, bank, ft, gws, eo, pick, balanced_hit_margin=None, time_limit=5):
    """Solve one strategy's regular (non-chip) plan for GW gws[0]."""
    m_base, _, hw = m.partition("@")
    keep_hw = optimise.STRATEGY["chase"].get("haul_w")
    if hw:
        optimise.STRATEGY["chase"]["haul_w"] = float(hw)
    try:
        if pick == "app":
            opts = [("best", None), ("roll", 0), ("one", 1), ("two", 2)] + ([("three", 3)] if ft >= 3 else [])
        else:
            opts = [("best", None)]
        plans, _ = optimise.strategy_plans(pl, squad, sell, bank, min(ft, 5), gws, opts,
                                           eo=eo, modes=("balanced", m_base), time_limit=time_limit)
        if pick == "app":
            key = app_pick(plans, m_base) or app_pick(plans, "balanced")
            r = plans.get(key) if key else None
        else:
            key = "best" if m_base == "balanced" else f"{m_base}_best"
            r = plans.get(key) or plans.get("best")
        if not r:
            r = optimise.solve(pl, squad, sell, bank, min(ft, 5), gws, week1_moves=0, freeze_after=0)
        # FL-230 Lever 3c: selective 1 hit/GW for Balanced when 5-GW gain > 4 + margin
        if m_base == "balanced" and balanced_hit_margin is not None:
            r_hit = optimise.solve(pl, squad, sell, bank, min(ft, 5), gws, max_hits=1, time_limit=time_limit)
            if r_hit:
                h_tot = sum(w["hits"] for w in r_hit["weeks"])
                if h_tot > 0 and r_hit["value"] >= r["value"] + balanced_hit_margin * h_tot:
                    r = r_hit
        return r
    finally:
        optimise.STRATEGY["chase"]["haul_w"] = keep_hw


def choose_chip(chip_mode, k, pl, gws, squad, sell, bank, ft, base_plan,
                avail_chips, dgw, bgw, simple_sched, time_limit=4, wc_cache=None):
    """Decide whether to play an available chip on GW k using ONLY projections & fixture counts (zero real points).
    Returns (chip_id or None, chip_plan or None).
    """
    if chip_mode == "none" or not avail_chips:
        return None, None
    in_window = {cid: win for cid, win in avail_chips.items() if win[0] <= k <= win[1]}
    if not in_window:
        return None, None

    w0 = base_plan["weeks"][0]
    tot_budget = round(bank + sum(sell[i] for i in squad), 1)

    def _rebase_plan(plan, cur_squad):
        """Convert a fresh-squad plan (built from []) into in/out diffs against cur_squad."""
        if not plan:
            return None
        p = copy.deepcopy(plan)
        w = p["weeks"][0]
        new_sq = set(w["xi"]) | set(w["bench"])
        cur_set = set(cur_squad)
        w["in"] = sorted(new_sq - cur_set)
        w["out"] = sorted(cur_set - new_sq)
        return p

    def solve_wc():
        key = (k, tot_budget)
        if wc_cache is not None and key in wc_cache:
            return _rebase_plan(wc_cache[key], squad)
        raw = optimise.solve(pl, [], {}, tot_budget, 1, gws, hit=0, ft_value=0, ft_scale=None,
                             max_moves_week=15, freeze_after=1, time_limit=time_limit)
        if wc_cache is not None:
            wc_cache[key] = raw
        return _rebase_plan(raw, squad)

    def solve_fh():
        raw = optimise.solve(pl, [], {}, tot_budget, 1, [k], hit=0, ft_value=0, ft_scale=None,
                             max_moves_week=15, time_limit=time_limit)
        return _rebase_plan(raw, squad)

    if chip_mode == "simple":
        # Check scheduled BB / TC / FH first
        for cid, target_gw in simple_sched.items():
            if cid in in_window and target_gw == k:
                kind = chip_kind(cid)
                if kind == "FH":
                    fh = solve_fh()
                    if fh:
                        return cid, fh
                else:
                    return cid, base_plan
        # Check causal WC trigger on non-scheduled weeks
        sched_gws = {simple_sched[c] for c in in_window if c in simple_sched}
        for cid, (lo, hi) in in_window.items():
            if chip_kind(cid) != "WC":
                continue
            rem_free = [g for g in range(k, hi + 1) if g not in sched_gws]
            must_play = len(rem_free) <= 1
            if k >= lo + 3 or must_play:
                wc = solve_wc()
                if wc:
                    wc_val = wc["xp_total"] + optimise.ft_bonus(min(5, ft))
                    if must_play or (wc_val - base_plan["value"] >= 18.0):
                        return cid, wc
        return None, None

    # chip_mode == "solver": evaluate every available chip using GW k projections only
    candidates = []   # (forced_flag, net_score, cid, plan)
    # Group by window end `hi` to detect forced expiry (n_expiring >= remaining weeks in half)
    by_hi = defaultdict(list)
    for cid, (lo, hi) in in_window.items():
        by_hi[hi].append(cid)

    for cid, (lo, hi) in in_window.items():
        kind = chip_kind(cid)
        weeks_left = hi - k
        forced = len(by_hi[hi]) >= (weeks_left + 1)
        f_dgw_big = any(dgw.get(g, 0) >= 4 for g in range(k + 1, hi + 1))
        f_dgw_any = any(dgw.get(g, 0) >= 2 for g in range(k + 1, hi + 1))
        f_bgw_big = any(bgw.get(g, 0) >= 4 for g in range(k + 1, hi + 1))
        f_bgw_any = any(bgw.get(g, 0) >= 2 for g in range(k + 1, hi + 1))

        if kind == "TC":
            gain = pl[w0["captain"]]["xp"].get(k, 0.0)
            thr = 0.0 if forced else (13.0 if f_dgw_big else (10.5 if f_dgw_any else 7.0 + 0.15 * weeks_left))
            candidates.append((forced, gain - thr, cid, base_plan))
        elif kind == "BB":
            gain = sum(pl[i]["xp"].get(k, 0.0) for i in w0["bench"])
            thr = 0.0 if forced else (20.0 if f_dgw_big else (16.0 if f_dgw_any else 11.0 + 0.25 * weeks_left))
            candidates.append((forced, gain - thr, cid, base_plan))
        elif kind == "FH":
            fh = solve_fh()
            if fh:
                gain = fh["weeks"][0]["xp"] - (w0["xp"] - 4 * w0["hits"])
                thr = 0.0 if forced else (22.0 if f_bgw_big else (16.0 if f_bgw_any else 10.0 + 0.30 * weeks_left))
                candidates.append((forced, gain - thr, cid, fh))
        elif kind == "WC":
            if k < lo + 2 and not forced:
                continue
            wc = solve_wc()
            if wc:
                wc_val = wc["xp_total"] + optimise.ft_bonus(min(5, ft))
                gain = wc_val - base_plan["value"]
                thr = 0.0 if forced else (15.0 + 0.30 * weeks_left)
                candidates.append((forced, gain - thr, cid, wc))

    if not candidates:
        return None, None
    forced_cands = [c for c in candidates if c[0]]
    if forced_cands:
        best = max(forced_cands, key=lambda c: c[1])
        return best[2], best[3]
    best = max(candidates, key=lambda c: c[1])
    if best[1] > 0:
        return best[2], best[3]
    return None, None


def score_week(w0, chip_id, pts, mins, pl, pre_fh_xi_real=None):
    """Real points after hits for week 0, plus chip net-points attribution."""
    kind = chip_kind(chip_id) if chip_id else None
    hits = 0 if kind in ("WC", "FH") else w0["hits"]
    if kind == "BB":
        xi_all = list(w0["xi"]) + list(w0["bench"])
        cap = w0["captain"] if mins.get(w0["captain"], 0) > 0 else w0["vice"]
        real = sum(pts.get(i, 0) for i in xi_all) + (pts.get(cap, 0) if cap in xi_all else 0) - 4 * hits
        # Compare against normal XI with autosubs for BB attribution
        xi_norm = autosub(w0["xi"], w0["bench"], pts, mins, pl)
        norm_real = sum(pts.get(i, 0) for i in xi_norm) + (pts.get(cap, 0) if cap in xi_norm else 0) - 4 * hits
        chip_pts = real - norm_real
        return real, chip_pts
    xi = autosub(w0["xi"], w0["bench"], pts, mins, pl)
    cap = w0["captain"] if mins.get(w0["captain"], 0) > 0 else w0["vice"]
    cap_pts = pts.get(cap, 0) if cap in xi else 0
    if kind == "TC":
        real = sum(pts.get(i, 0) for i in xi) + 2 * cap_pts - 4 * hits
        return real, cap_pts
    real = sum(pts.get(i, 0) for i in xi) + cap_pts - 4 * hits
    if kind == "FH":
        chip_pts = real - pre_fh_xi_real if pre_fh_xi_real is not None else real
        return real, chip_pts
    if kind == "WC":
        return real, real
    return real, 0.0


def apply_week(t, w0, chip_id, sell, pl, gw, chip_pool, allow_hit, prev_held_over):
    """Apply week-0 transfers, FT update, chip consumption, and FPL rule audit to team state `t`."""
    kind = chip_kind(chip_id) if chip_id else None
    moved = len(w0["in"])
    hits = 0 if kind in ("WC", "FH") else w0["hits"]

    if kind == "FH":
        # Audit the FH week squad itself (15 players, budget, club limit, XI, captain)
        fh_squad = [i for i in t["squad"] if i not in w0["out"]] + list(w0["in"])
        fh_bank = round(t["bank"] + sum(sell[o_] for o_ in w0["out"]) - sum(pl[i_]["price"] for i_ in w0["in"]), 1)
        # FPL 2024/25+: FH keeps banked FTs unchanged (1..5), squad reverts after GW
        next_ft = max(1, min(5, t["ft"]))
        errs = audit_week(gw, fh_squad, fh_bank, next_ft, w0["xi"], w0["bench"], w0["captain"], pl,
                          moved, chip_id, chip_pool, t["used_chips"], 0, allow_hit, prev_held_over)
        t["ft"] = next_ft
    else:
        for o_ in w0["out"]:
            t["bank"] += sell[o_]; t["squad"].remove(o_); t["buy"].pop(o_, None)
        for i_ in w0["in"]:
            t["bank"] -= pl[i_]["price"]; t["squad"].append(i_); t["buy"][i_] = pl[i_]["price"]
        t["bank"] = round(t["bank"], 1)
        if kind == "WC":
            # FPL 2024/25+: WC keeps banked FTs unchanged (1..5)
            t["ft"] = max(1, min(5, t["ft"]))
        else:
            t["hits"] += hits
            t["moves"] += moved
            if moved == 0:
                t["rolls"] += 1
            t["ft"] = 1 if moved > t["ft"] else min(5, t["ft"] - moved + 1)
        errs = audit_week(gw, t["squad"], t["bank"], t["ft"], w0["xi"], w0["bench"], w0["captain"], pl,
                          moved, chip_id, chip_pool, t["used_chips"], hits, allow_hit, prev_held_over)

    if chip_id is not None:
        t["used_chips"].add(chip_id)
        t["avail_chips"].pop(chip_id, None)
    t["violations"].extend(errs)
    return hits


def replay(season, k_from, k_to, sim, modes=MODES, seed=0, pick="best",
           chips="none", switch=False, balanced_hit_margin=None, hindsight=False,
           cache_dir=None, quiet=False):
    ctx, team_at = bench._season(season)
    price, own = season_tables(season)
    last = max(price)
    k_to = min(k_to, last)
    dgw, bgw = fixture_calendar(ctx["fixtures"], last)
    chip_pool = season_chips(season) if chips != "none" else {}
    simple_sched = simple_chip_schedule(season, dgw, bgw) if chips == "simple" else {}
    proj_cache = load_or_build_cache(season, k_from, k_to, sim, cache_dir, ctx, team_at, price, last)
    t0 = time.time()

    # Starting squad: best £100m squad for the first H weeks. With seed > 0, ban 4 random players of it first.
    pl0, gws0 = proj_cache[k_from]
    pl0 = copy.deepcopy(pl0)
    wc = optimise.solve(pl0, [], {}, 100.0, 1, gws0, hit=0, ft_value=0, ft_scale=None,
                        max_moves_week=15, freeze_after=1, time_limit=60)
    if seed:
        best = wc["weeks"][0]["xi"] + wc["weeks"][0]["bench"]
        ban = random.Random(seed * 1000 + int(season[:4])).sample(best, 4)
        wc = optimise.solve(pl0, [], {}, 100.0, 1, gws0, hit=0, ft_value=0, ft_scale=None,
                            max_moves_week=15, freeze_after=1, time_limit=60, banned=ban)
    start = wc["weeks"][0]["xi"] + wc["weeks"][0]["bench"]
    bank0 = round(100.0 - sum(pl0[i]["price"] for i in start), 1)

    if hindsight:
        run_names = ("hindsight_weekly",)
    elif switch:
        run_names = ("switch",)
    else:
        run_names = tuple(modes)

    def init_team():
        return {
            "squad": list(start), "buy": {i: pl0[i]["price"] for i in start}, "bank": bank0, "ft": 1,
            "real": [], "proj": [], "field": [], "gws": [],
            "hits": 0, "moves": 0, "rolls": 0,
            "avail_chips": dict(chip_pool), "used_chips": set(), "chip_log": [],
            "mode_log": [], "violations": [],
        }

    teams = {name: init_team() for name in run_names}
    wc_cache = {}

    for k in range(k_from, k_to + 1):
        pl_raw, gws = proj_cache[k]
        if not pl_raw:
            if not quiet:
                print(f"  GW{k}: no projections, skipped")
            continue
        pl = copy.deepcopy(pl_raw)
        pts = {pid: ctx["pts_gw"].get(pid, {}).get(k, 0) for pid in pl}
        mins = {pid: ctx["pstats"].get(pid, {}).get(k, {}).get("minutes", 0) for pid in pl}
        o = own.get(k, {})
        top = max(pl, key=lambda pid: o.get(pid, 0))
        field = sum(o.get(pid, 0) * pts.get(pid, 0) for pid in pl) * 11 / 15 + pts.get(top, 0)
        eo = {pid: o.get(pid, 0.0) for pid in pl}

        # Ensure any held player missing from price list still exists in pl/pts/mins
        for t in teams.values():
            for i in t["squad"]:
                if i not in pl:
                    pl[i] = {"pos": POS[ctx["elements"][i]["element_type"]], "team": ctx["elements"][i]["team"],
                             "price": price.get(k, {}).get(i, t["buy"][i]), "xp": {g: 0.0 for g in gws}, "ok": False,
                             "p10": {}, "nailed": 0, "name": str(i)}
                    pts.setdefault(i, ctx["pts_gw"].get(i, {}).get(k, 0))
                    mins.setdefault(i, 0)

        for name in run_names:
            t = teams[name]
            sell = {i: fpl_sell(t["buy"][i], pl[i]["price"]) for i in t["squad"]}
            prev_held_over = optimise.club_over(t["squad"], pl)

            if hindsight:
                # Part 4 HINDSIGHT DIAGNOSTIC: solve all 3 strategies from the same current squad,
                # pick the one with highest THIS-WEEK real points (after hits)
                best_choice = None
                for m_cand in MODES:
                    base_r = solve_mode_plan(m_cand, pl, t["squad"], sell, t["bank"], t["ft"], gws, eo, pick)
                    c_id, c_plan = choose_chip(chips, k, pl, gws, t["squad"], sell, t["bank"], t["ft"], base_r,
                                               t["avail_chips"], dgw, bgw, simple_sched, wc_cache=wc_cache)
                    used_r = c_plan if c_plan is not None else base_r
                    w0 = used_r["weeks"][0]
                    pre_fh_real = None
                    if c_id and chip_kind(c_id) == "FH":
                        pre_fh_real, _ = score_week(base_r["weeks"][0], None, pts, mins, pl)
                    real_cand, chip_pts = score_week(w0, c_id, pts, mins, pl, pre_fh_real)
                    if best_choice is None or real_cand > best_choice[0]:
                        best_choice = (real_cand, chip_pts, m_cand, c_id, used_r)
                real, chip_pts, picked_m, c_id, used_r = best_choice
                allow_hit = (picked_m == "chase")
                t["mode_log"].append(picked_m)
            else:
                if switch:
                    m_cur = switch_mode(k, sum(t["real"]), sum(t["field"]))
                    t["mode_log"].append(m_cur)
                else:
                    m_cur = name
                base_r = solve_mode_plan(m_cur, pl, t["squad"], sell, t["bank"], t["ft"], gws, eo, pick,
                                         balanced_hit_margin=balanced_hit_margin)
                c_id, c_plan = choose_chip(chips, k, pl, gws, t["squad"], sell, t["bank"], t["ft"], base_r,
                                           t["avail_chips"], dgw, bgw, simple_sched, wc_cache=wc_cache)
                used_r = c_plan if c_plan is not None else base_r
                w0 = used_r["weeks"][0]
                pre_fh_real = None
                if c_id and chip_kind(c_id) == "FH":
                    pre_fh_real, _ = score_week(base_r["weeks"][0], None, pts, mins, pl)
                real, chip_pts = score_week(w0, c_id, pts, mins, pl, pre_fh_real)
                m_base = m_cur.partition("@")[0]
                allow_hit = (m_base == "chase") or (m_base == "balanced" and balanced_hit_margin is not None)

            w0 = used_r["weeks"][0]
            hits = apply_week(t, w0, c_id, sell, pl, k, chip_pool, allow_hit, prev_held_over)
            if c_id is not None:
                t["chip_log"].append({"chip": c_id, "gw": k, "pts": round(chip_pts, 1), "gw_real": round(real, 1)})
            t["real"].append(real)
            t["proj"].append(w0["xp"] - 4 * hits)
            t["field"].append(field)
            t["gws"].append(k)

        if not quiet:
            line = "  ".join(f"{m[:10]} {teams[m]['real'][-1]:4.0f}" for m in run_names)
            print(f"  {season} GW{k}: {line}   field {field:5.1f}   ({time.time() - t0:.0f}s)", flush=True)
    return teams


def summary(teams):
    out = {}
    for m, t in teams.items():
        d = [a - b for a, b in zip(t["real"], t["field"])]
        gw1_4 = sum(r for g, r in zip(t.get("gws", []), t["real"]) if g <= 4)
        mode_counts = {}
        for x in t.get("mode_log", []):
            mode_counts[x] = mode_counts.get(x, 0) + 1
        out[m] = {
            "weeks": len(d), "real": sum(t["real"]), "proj": round(sum(t["proj"]), 1),
            "field": round(sum(t["field"]), 1),
            "gw1_4": gw1_4,
            "hits": t["hits"], "moves": t["moves"], "rolls": t.get("rolls", 0),
            "vs_field": round(sum(d), 1), "spread": round(statistics.pstdev(d), 2) if d else None,
            "green": sum(1 for x in d if x - statistics.mean(d) >= 15),
            "red": sum(1 for x in d if x - statistics.mean(d) <= -15),
            "worst": round(min(d), 1) if d else None, "best": round(max(d), 1) if d else None,
            "chips": t.get("chip_log", []),
            "mode_counts": mode_counts,
            "violations": len(t.get("violations", [])),
            "violation_list": t.get("violations", [])[:10],
        }
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("seasons", nargs="*", default=["2025-26", "2024-25"])
    ap.add_argument("--from", dest="k_from", type=int, default=5)
    ap.add_argument("--to", dest="k_to", type=int, default=38)
    ap.add_argument("--sim", type=int, default=600, help="simulations per player for the 10+ point chance (default 600)")
    ap.add_argument("--json", help="write the results here")
    ap.add_argument("--modes", default=",".join(MODES), help="strategies to replay, e.g. chase (each team is independent)")
    ap.add_argument("--seed", type=int, default=0, help="0: best starting squad; N: ban 4 random players of it first")
    ap.add_argument("--old", action="store_true", help="the settings before points budgets (for a before/after table)")
    ap.add_argument("--pick", choices=("best", "app"), default="best",
                    help="best: plan with week 1 left free; app: plan the app recommends (Roll, 1, 2 or 3 moves)")
    ap.add_argument("--chips", choices=("none", "simple", "solver"), default="none",
                    help="chip mode: none (original), simple (DGW/BGW rule), solver (projection-driven)")
    ap.add_argument("--switch", action="store_true", help="FL-230 Lever 3b: pre-registered strategy-switching rule")
    ap.add_argument("--balanced-hit-margin", type=float, default=None,
                    help="FL-230 Lever 3c: allow Balanced <=1 hit/GW when 5-GW gain > 4 + M")
    ap.add_argument("--hindsight", action="store_true",
                    help="FL-230 Part 4 (HINDSIGHT DIAGNOSTIC ONLY): pick best strategy each week using real points")
    ap.add_argument("--cache-dir", default=None, help="directory to cache/load rolling-origin projections")
    ap.add_argument("--quiet", action="store_true", help="suppress per-GW progress output")
    a = ap.parse_args()
    if not os.path.exists(os.path.join(bench.HERE, "raw", "bootstrap.json")):
        sys.exit("strategy_replay: needs raw/bootstrap.json (the scoring rules); save bootstrap-static there first")
    if a.old:
        optimise.STRATEGY = {"balanced": {}, "safe": {"lam": 0.02, "hit_margin": 2.0, "nail_w": 0.5}, "chase": {"lam": -0.03, "haul_w": 10.0}}
        optimise.SAFE_BUDGET = optimise.CHASE_BUDGET = 1e9
        optimise.MIN_PROFIT, optimise.EO_WEEKS = -1e9, 2
    res = {}
    for s in a.seasons:
        res[s] = summary(replay(
            s, a.k_from, a.k_to, a.sim, tuple(a.modes.split(",")), a.seed, a.pick,
            chips=a.chips, switch=a.switch, balanced_hit_margin=a.balanced_hit_margin,
            hindsight=a.hindsight, cache_dir=a.cache_dir, quiet=a.quiet,
        ))
        print(f"\n{s}  (GW{a.k_from}-{a.k_to}, chips={a.chips}, seed={a.seed})")
        print(f"{'':16s} {'real':>6s} {'gw1-4':>6s} {'proj':>7s} {'field':>7s} {'vs_fld':>8s} {'hits':>5s} {'moves':>6s} {'rolls':>6s} {'viol':>5s}")
        for m, r in res[s].items():
            print(f"{m:16s} {r['real']:6.0f} {r['gw1_4']:6.0f} {r['proj']:7.1f} {r['field']:7.1f} {r['vs_field']:+8.1f} "
                  f"{r['hits']:5d} {r['moves']:6d} {r['rolls']:6d} {r['violations']:5d}")
            if r["chips"]:
                cstr = ", ".join(f"{c['chip']}@GW{c['gw']}({c['pts']:+.0f})" for c in r["chips"])
                print(f"  chips: {cstr}")
            if r["mode_counts"]:
                print(f"  modes: {r['mode_counts']}")
    if a.json:
        json.dump(res, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
