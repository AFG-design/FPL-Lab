"""FPL Lab projection model.

project(ctx, as_of, params) projects expected points for every player for the
gameweeks starting at `as_of`, using only information from gameweeks before it.
That makes the same code usable for live projections and for backtests.
"""
import math
from collections import defaultdict

POS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}

DEFAULTS = {
    # tuned by backtest.py / tune.py on GW3-7 of 2026/27; recency and minutes re-tested with bench.py
    # (GW3-7 of 2026/27 plus GW4-38 of 2025/26)
    "recency": 0.8,        # weight per gameweek back, player rates (0.7 before bench.py; 0.8 = same accuracy, better top picks)
    "team_recency": 0.93,  # weight per gameweek back, team ratings
    "xg_weight": 0.7,      # team ratings: share from xG (rest from real goals)
    "prior_games": 4.0,    # team ratings: games of league-average prior
    "home": 1.05,          # home goal multiplier (away = 1/home)
    "w_pos": 450.0,        # pseudo-minutes of positional average
    "w_last": 600.0,       # pseudo-minutes of last-season rate
    "pen_xg": 0.05,        # extra xG per 90 for the first-choice penalty taker
    "min_window": 5,       # gameweeks of minutes history
    "dc_blend": 4.0,       # pseudo-games for DC hit-rate shrinkage
    "bonus_scale": 0.8,
    "assist_mult": 1.2,    # FPL awards more assists than xA (rebounds, won pens, deflections)
    "goal_mult": 0.88,
    "cs_k": 0.9,           # P(clean sheet) = exp(-cs_k * mu); real CS rates beat a plain Poisson
    "cal_slope": 0.86,     # final calibration: xP = slope * raw + intercept * P(appears)
    "cal_int": 0.33,
    "use_flags": True,     # use FPL injury / availability flags
    "mkt_w": 0.7,          # weight of betting-market team ratings vs xG ratings (geometric blend); backtest GW3-7
    "direct_w": 0.85,      # weight of a fixture's own market expected goals, when its odds exist
    "mkt_recency": 0.9,    # weight per gameweek back for market ratings
    "opp_adj": 0.5,        # opponent-adjusted form: past xG/xA divided by (opponent defence rating) ** opp_adj.
                           # GW3-7: corr unchanged, top-30 over-projection +0.22 -> +0.13
    "sp_match": 0.0,       # set-piece matchups: set-piece xG scaled by (opponent set-piece xG conceded / average) ** sp_match.
                           # Off: GW3-7 corr 0.417 -> 0.416. Re-test with tune_v3.py as data grows
    "sp_prior": 4.0,       # games of league-average prior for team set-piece conceding
    "min_valid": True,     # minutes history: skip blank gameweeks and weeks before the player joined
    "min_recency": 0.4,    # weight per gameweek back for minutes: who starts changes faster than how good he is
}


def poisson(k, mu):
    return math.exp(-mu) * mu ** k / math.factorial(k)


def exp_floor_div(mu, d, kmax=15):
    return sum((k // d) * poisson(k, mu) for k in range(kmax))


def p_at_least(mu, k):
    if mu <= 0:
        return 0.0
    return max(0.0, 1 - sum(poisson(i, mu) for i in range(k)))


US_TO_FPL = {"BRI": "BHA", "FLH": "FUL", "LED": "LEE", "NOT": "NFO"}


def understat_sp(boot, fixtures, shots_cache, us_players):
    """Per-gameweek set-piece xG for each FPL player, and set-piece xG conceded by each FPL team."""
    SET = {"FromCorner", "SetPiece", "DirectFreekick"}
    short = {t["short_name"]: t["id"] for t in boot["teams"]}
    fx = {(f["team_h"], f["team_a"]): f["event"] for f in fixtures if f["event"]}
    us_to_fpl = {v["us_id"]: int(k) for k, v in (us_players or {}).items()}
    sp_player = defaultdict(lambda: defaultdict(float))
    sp_against = defaultdict(lambda: defaultdict(float))
    for m in (shots_cache or {}).get("matches", {}).values():
        h = short.get(US_TO_FPL.get(m["h"], m["h"])); a = short.get(US_TO_FPL.get(m["a"], m["a"]))
        g = fx.get((h, a))
        if not g:
            continue
        sp_against[h][g] += 0.0; sp_against[a][g] += 0.0  # mark the game as played
        for sh in m["shots"]:
            upid, xg, sit, side = sh[0], sh[4], sh[6], sh[8]
            if sit not in SET:
                continue
            conceding = a if side == "h" else h
            sp_against[conceding][g] += xg
            pid = us_to_fpl.get(upid)
            if pid:
                sp_player[pid][g] += xg
    return {"player": sp_player, "against": sp_against}


def prepare(boot, fixtures, live, priors=None, market=None, sp=None):
    """Index the raw API responses once; reused across projections."""
    elements = {e["id"]: e for e in boot["elements"]}
    teams = {t["id"]: t for t in boot["teams"]}
    pstats = defaultdict(dict)
    dc_hit = defaultdict(dict)
    pts_gw = defaultdict(dict)
    for g, data in live.items():
        for x in data["elements"]:
            pstats[x["id"]][g] = x["stats"]
            pts_gw[x["id"]][g] = x["stats"]["total_points"]
            dc_hit[x["id"]][g] = any(s["identifier"] == "defensive_contribution" and s["points"] > 0
                                     for ex in x["explain"] for s in ex["stats"])
    team_fix = defaultdict(list)
    for f in fixtures:
        if f["event"]:
            team_fix[f["team_h"]].append((f["event"], f["team_a"], True, f))
            team_fix[f["team_a"]].append((f["event"], f["team_h"], False, f))
    team_gw_xg = defaultdict(lambda: defaultdict(float))
    for pid, gws in pstats.items():
        t = elements.get(pid, {}).get("team")
        if t:
            for g, s in gws.items():
                team_gw_xg[t][g] += float(s["expected_goals"])
    # DC thresholds observed from the data (smallest raw count that earned points)
    thr = {}
    for pid, gws in dc_hit.items():
        e = elements.get(pid)
        if not e:
            continue
        pos = POS[e["element_type"]]
        for g, hit in gws.items():
            if hit:
                c = pstats[pid][g]["defensive_contribution"]
                thr[pos] = min(thr.get(pos, 99), c)
    thr.setdefault("DEF", 10)
    thr.setdefault("MID", 12)
    thr.setdefault("FWD", 12)
    return {
        "boot": boot, "fixtures": fixtures, "elements": elements, "teams": teams,
        "pstats": pstats, "dc_hit": dc_hit, "pts_gw": pts_gw, "team_fix": team_fix,
        "team_gw_xg": team_gw_xg, "scoring": boot["game_config"]["scoring"],
        "priors": (priors or {}).get("players", {}), "dc_thr": thr,
        "sp": sp,
        "market": (market or {}).get("matches", []),
        "market_fx": {m["fixture"]: (m["lam_h"], m["lam_a"]) for m in (market or {}).get("matches", [])},
    }


def team_ratings(ctx, as_of, P):
    fixtures, team_fix, team_gw_xg, teams = ctx["fixtures"], ctx["team_fix"], ctx["team_gw_xg"], ctx["teams"]
    H, A = P["home"], 1 / P["home"]
    games = defaultdict(list)
    for f in fixtures:
        g = f["event"]
        if not g or g >= as_of or f["team_h_score"] is None:
            continue
        w = P["team_recency"] ** max(0, as_of - 1 - g)
        h, a = f["team_h"], f["team_a"]
        nh = sum(1 for x in team_fix[h] if x[0] == g)
        na = sum(1 for x in team_fix[a] if x[0] == g)
        xh = team_gw_xg[h][g] / nh if nh else 0
        xa = team_gw_xg[a][g] / na if na else 0
        xw = P["xg_weight"]
        fh = xw * xh + (1 - xw) * f["team_h_score"]
        fa = xw * xa + (1 - xw) * f["team_a_score"]
        games[h].append((w, fh, fa, True, a))
        games[a].append((w, fa, fh, False, h))
    allg = [x for v in games.values() for x in v]
    league = (sum(x[1] for x in allg) / len(allg)) if allg else 1.35
    rating = {t: {"att": 1.0, "def": 1.0} for t in teams}
    for _ in range(4):
        new = {}
        for tid in teams:
            gs = games.get(tid, [])
            W = sum(x[0] for x in gs)
            gf = sum(x[0] * x[1] / ((H if x[3] else A) * rating[x[4]]["def"]) for x in gs)
            ga = sum(x[0] * x[2] / ((A if x[3] else H) * rating[x[4]]["att"]) for x in gs)
            pg = P["prior_games"]
            new[tid] = {"att": (gf + pg * league) / (W + pg) / league,
                        "def": (ga + pg * league) / (W + pg) / league}
        ma = sum(v["att"] for v in new.values()) / len(new)
        md = sum(v["def"] for v in new.values()) / len(new)
        rating = {k: {"att": v["att"] / ma, "def": v["def"] / md} for k, v in new.items()}
    w = P.get("mkt_w", 0.0)
    if w > 0:
        mrat, mleague = market_ratings(ctx, as_of, P)
        if mrat:
            rating = {k: {"att": rating[k]["att"] ** (1 - w) * mrat[k]["att"] ** w,
                          "def": rating[k]["def"] ** (1 - w) * mrat[k]["def"] ** w} for k in rating}
            league = league * (1 - w) + mleague * w
    return rating, league


def market_ratings(ctx, as_of, P):
    """Attack/defence ratings implied by betting odds on matches before `as_of` (venue and opponent adjusted)."""
    teams = ctx["teams"]
    H, A = P["home"], 1 / P["home"]
    games = defaultdict(list)
    for m in ctx["market"]:
        g = m.get("gw")
        if not g or g >= as_of:
            continue
        w = P["mkt_recency"] ** max(0, as_of - 1 - g)
        games[m["h"]].append((w, m["lam_h"], m["lam_a"], True, m["a"]))
        games[m["a"]].append((w, m["lam_a"], m["lam_h"], False, m["h"]))
    allg = [x for v in games.values() for x in v]
    if len(allg) < 20:
        return None, None
    league = sum(x[1] for x in allg) / len(allg)
    rating = {t: {"att": 1.0, "def": 1.0} for t in teams}
    for _ in range(6):
        new = {}
        for tid in teams:
            gs = games.get(tid, [])
            W = sum(x[0] for x in gs)
            gf = sum(x[0] * x[1] / ((H if x[3] else A) * rating[x[4]]["def"]) for x in gs)
            ga = sum(x[0] * x[2] / ((A if x[3] else H) * rating[x[4]]["att"]) for x in gs)
            new[tid] = {"att": (gf + 1.0 * league) / (W + 1.0) / league, "def": (ga + 1.0 * league) / (W + 1.0) / league}
        ma = sum(v["att"] for v in new.values()) / len(new)
        md = sum(v["def"] for v in new.values()) / len(new)
        rating = {k: {"att": v["att"] / ma, "def": v["def"] / md} for k, v in new.items()}
    return rating, league


def project(ctx, as_of, horizon=6, params=None):
    P = dict(DEFAULTS, **(params or {}))
    elements, teams, pstats, scoring = ctx["elements"], ctx["teams"], ctx["pstats"], ctx["scoring"]
    rating, league = team_ratings(ctx, as_of, P)
    H = P["home"]

    def mu(tid, opp, home):
        return league * rating[tid]["att"] * rating[opp]["def"] * (H if home else 1 / H)

    gws = [g for g in range(as_of, as_of + horizon) if g <= 38]
    upcoming = defaultdict(lambda: defaultdict(list))
    dw = P.get("direct_w", 0.0)
    for tid, lst in ctx["team_fix"].items():
        for (g, opp, home, f) in lst:
            if g in gws:
                fdr = f["team_h_difficulty"] if home else f["team_a_difficulty"]
                mf, ma_ = mu(tid, opp, home), mu(opp, tid, not home)
                mk = ctx.get("market_fx", {}).get(f["id"]) if dw > 0 else None
                if mk:  # this fixture's own odds: blend the market's expected goals in
                    lf, la = (mk[0], mk[1]) if home else (mk[1], mk[0])
                    mf, ma_ = (1 - dw) * mf + dw * lf, (1 - dw) * ma_ + dw * la
                upcoming[tid][g].append((opp, home, mf, ma_, fdr))

    hist_gws = [g for g in range(1, as_of)]
    # positional priors per 90 from this season's regulars (data before as_of)
    pos_prior = {}
    for et, pos in POS.items():
        num = defaultdict(float)
        mins = 0
        hits = n60 = 0
        for pid, e in elements.items():
            if e["element_type"] != et:
                continue
            gs = pstats.get(pid, {})
            m = sum(gs[g]["minutes"] for g in hist_gws if g in gs)
            if m < 180:
                continue
            mins += m
            for g in hist_gws:
                if g in gs:
                    s = gs[g]
                    num["xg"] += float(s["expected_goals"])
                    num["xa"] += float(s["expected_assists"])
                    num["bonus"] += s["bonus"]
                    num["saves"] += s["saves"]
                    num["yc"] += s["yellow_cards"]
                    num["dc"] += s["defensive_contribution"]
                    if s["minutes"] >= 60:
                        n60 += 1
                        hits += ctx["dc_hit"][pid].get(g, False)
        mins = mins or 1
        pos_prior[pos] = {k: num[k] / mins * 90 for k in ("xg", "xa", "bonus", "saves", "yc", "dc")}
        pos_prior[pos]["dchit"] = hits / n60 if n60 else 0

    opp_of = defaultdict(list)
    for tid, lst in ctx["team_fix"].items():
        for (g, opp, home, f) in lst:
            opp_of[(tid, g)].append(opp)
    sp = ctx.get("sp")
    sp_fac = {}
    if sp and P["sp_match"]:
        tot = {}
        for tid in teams:
            gsp = {g: v for g, v in sp["against"].get(tid, {}).items() if g < as_of}
            tot[tid] = (sum(gsp.values()), len(gsp))
        n_all = sum(n for _, n in tot.values()) or 1
        avg = sum(v for v, _ in tot.values()) / n_all or 0.3
        for tid, (v, n) in tot.items():
            sp_fac[tid] = ((v + P["sp_prior"] * avg) / (n + P["sp_prior"])) / avg

    team_gws = defaultdict(set)
    for tid, lst in ctx["team_fix"].items():
        for (g, opp, home, f) in lst:
            team_gws[tid].add(g)

    out = {}
    for pid, e in elements.items():
        pos = POS[e["element_type"]]
        gs = pstats.get(pid, {})
        # ---- per-90 rates: this season (recency weighted) + last season + position
        num = defaultdict(float)
        den = 0.0
        for g in hist_gws:
            if g not in gs:
                continue
            s = gs[g]
            w = P["recency"] ** (as_of - 1 - g)
            den += w * s["minutes"]
            if P["opp_adj"]:
                opps = opp_of.get((e["team"], g)) or []
                of = (sum(rating[o]["def"] for o in opps) / len(opps)) ** P["opp_adj"] if opps else 1.0
            else:
                of = 1.0
            num["xg"] += w * float(s["expected_goals"]) / of
            num["xa"] += w * float(s["expected_assists"]) / of
            if sp and P["sp_match"]:
                num["sp"] += w * sp["player"].get(pid, {}).get(g, 0.0) / of
            num["bonus"] += w * s["bonus"]
            num["saves"] += w * s["saves"]
            num["yc"] += w * s["yellow_cards"]
            num["dc"] += w * s["defensive_contribution"]
        pr = ctx["priors"].get(str(pid))
        pp = pos_prior[pos]
        w_last = P["w_last"] * min(1.0, pr["mins"] / 1500) if pr else 0.0
        key_last = {"xg": "xg90", "xa": "xa90", "bonus": "bonus90", "saves": "saves90", "yc": "yc90", "dc": "dc90"}

        def rate(k):
            last = pr[key_last[k]] if pr else 0.0
            return (num[k] + last * w_last / 90 + pp[k] * P["w_pos"] / 90) / (den + w_last + P["w_pos"]) * 90

        xg90, xa90, bo90, sv90, yc90, dc90 = (rate(k) for k in ("xg", "xa", "bonus", "saves", "yc", "dc"))
        sp90 = min(xg90, num["sp"] / (den + P["w_pos"]) * 90) if (sp and P["sp_match"]) else 0.0
        if e.get("penalties_order") == 1:
            xg90 += P["pen_xg"]

        # ---- minutes: start probability and minutes when starting / from the bench
        if P["min_valid"]:
            # only gameweeks where his club played and he was registered; a blank week or one
            # before he joined says nothing about whether he starts
            played = team_gws.get(e["team"], set())
            recent = [g for g in hist_gws if g in gs and g in played][-P["min_window"]:]
        else:
            recent = [g for g in hist_gws[-P["min_window"]:]]
        mrec = P["min_recency"] or P["recency"]
        wsum = st = sub = mstart = msub = p60s = 0.0
        for g in recent:
            w = mrec ** (as_of - 1 - g)
            wsum += w
            s = gs.get(g)
            if not s:
                continue
            if s["starts"] > 0:
                st += w
                mstart += w * min(90, s["minutes"])
                p60s += w * (s["minutes"] >= 60)
            elif s["minutes"] > 0:
                sub += w
                msub += w * s["minutes"]
        if wsum:
            p_start, p_sub = st / wsum, sub / wsum
            m_start = mstart / st if st else 75
            m_sub = msub / sub if sub else 20
            p60_given_start = p60s / st if st else 0.75
        else:
            p_start = p_sub = 0.0
            m_start, m_sub, p60_given_start = 75, 20, 0.75
        # ---- DC hit probability
        thr = ctx["dc_thr"].get(pos, 99)
        hits = n60 = 0
        for g in hist_gws:
            s = gs.get(g)
            if s and s["minutes"] >= 60:
                n60 += 1
                hits += ctx["dc_hit"][pid].get(g, False)
        p_dc_model = p_at_least(dc90 * min(90, m_start) / 90, thr) if pos != "GKP" else 0.0
        p_dc = (hits + p_dc_model * P["dc_blend"]) / (n60 + P["dc_blend"]) if pos != "GKP" else 0.0

        tid = e["team"]
        per_gw, detail = {}, {}
        for k, g in enumerate(gws):
            av = availability(e, k) if P["use_flags"] else (0.0 if e["status"] == "u" else 1.0)
            comp = defaultdict(float)
            cong = ctx.get("congestion", {}).get((tid, g), 1.0)
            for (opp, home, mu_f, mu_a, fdr) in upcoming[tid].get(g, []):
                ps, pb = p_start * av * cong, p_sub * av
                pb += p_start * av * (1 - cong) * 0.7  # rested starters usually still come off the bench
                m = ps * m_start + pb * m_sub
                p60 = ps * p60_given_start
                atk = mu_f / max(0.3, league * rating[tid]["att"])
                if sp90:  # set-piece threat scales with how much this opponent concedes from set pieces
                    eg = P["goal_mult"] * ((xg90 - sp90) * atk + sp90 * sp_fac.get(opp, 1.0) ** P["sp_match"]) * m / 90
                else:
                    eg = P["goal_mult"] * xg90 * atk * m / 90
                ea = P["assist_mult"] * xa90 * atk * m / 90
                comp["mins"] += (ps + pb) * scoring["short_play"] + p60 * (scoring["long_play"] - scoring["short_play"])
                comp["goals"] += eg * scoring["goals_scored"][pos]
                comp["assists"] += ea * scoring["assists"]
                pcs = math.exp(-P["cs_k"] * mu_a)
                comp["cs"] += pcs * p60 * scoring["clean_sheets"][pos]
                if scoring["goals_conceded"][pos]:
                    comp["gc"] += scoring["goals_conceded"][pos] * exp_floor_div(P["cs_k"] * mu_a, 2) * m / 90
                if pos == "GKP":
                    sv = sv90 * (mu_a / league) ** 0.6 * m / 90
                    comp["saves"] += sum((j // 3) * poisson(j, sv) for j in range(20)) * scoring["saves"]
                comp["dc"] += p_dc * p60 * scoring["defensive_contribution"][pos]
                comp["bonus"] += P["bonus_scale"] * bo90 * m / 90 * (atk ** 0.5 if pos in ("MID", "FWD") else (pcs / 0.3) ** 0.3)
                comp["cards"] -= yc90 * m / 90
            raw = sum(comp.values())
            nfx = len(upcoming[tid].get(g, []))
            pplay = min(1.0, (p_start + p_sub) * av)
            per_gw[g] = P["cal_slope"] * raw + P["cal_int"] * pplay * nfx if nfx else 0.0
            detail[g] = dict(comp)
        out[pid] = {
            "xp": per_gw, "detail": detail, "xg90": xg90, "xa90": xa90, "dc90": dc90, "p_dc": p_dc,
            "p_start": p_start, "p_sub": p_sub, "m_start": m_start,
            "xmin": (p_start * m_start + p_sub * m_sub) * (availability(e, 0) if P["use_flags"] else 1.0),
            "has_prior": bool(pr),
        }
    return {"players": out, "rating": rating, "league": league, "gws": gws, "upcoming": upcoming}


def availability(e, k):
    c = e["chance_of_playing_next_round"]
    if e["status"] == "u" or e.get("removed"):
        return 0.0
    if c is None:
        c = 100 if e["status"] == "a" else 50
    c /= 100
    if k == 0:
        return c
    if e["status"] == "s":
        return 1.0 if k >= 2 else c
    return min(1.0, c + (1 - c) * min(1, k / 3))
