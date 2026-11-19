#!/usr/bin/env python3
"""FL-223: mini-league title odds. Simulates the rest of the season for every member of a small mini-league at once
and counts how often each finishes 1st, in the top 3 and last; for your team, P(1st) with each of your top 3 captain
options next gameweek.

How it simulates (projections are the model's own, unchanged: fplmodel.project with fx_out on only returns each
fixture's simulation inputs; build.py runs it over every remaining gameweek):
- one scoreline per fixture per run, shared by both clubs' players. Goals for a club ~ Poisson(its expected goals);
  the goals its defence is judged on (clean sheets, goals conceded) are the opponent's goals thinned by the model's cs_k,
  so a clean sheet has exactly the projection's chance, exp(-cs_k * mu), and team-mates and opponents move together;
- each player's goals and assists are shares of his club's goals in that run (fplmodel._sim_fixture, the same player
  model build.py uses for points distributions); minutes, saves, defensive contributions, bonus and cards stay per player;
- the model's uncertainty about a player's true scoring rate (sim_sigma) is one draw per player per run for the whole
  season (a single gameweek's distribution draws it per fixture, which over 28 gameweeks would average it away);
- every player's runs are then shifted by whole points so his average equals his xP for that gameweek
  (fplmodel.match_mean, as the distributions do). validate.py checks the averages against the published xP.

Assumed (said on the page, `assumed` in data.json; nobody can know these):
- every manager keeps the squad and bench order of their latest saved picks for the rest of the season: no transfers,
  no hits, no chips;
- captain each gameweek: the highest-xP player in their XI (vice: the next highest); the armband passes to the vice when
  the captain doesn't play;
- FPL's automatic substitutions (bench order, legal formation, keeper for keeper; fpl_score.live_team_points' rules);
- ties split at random.

Missing, late or ambiguous:
- a manager whose picks failed to load, whose latest picks are a Free Hit (their real squad isn't in them) or who has no
  league total is left out and listed with the reason; the page says "N of M managers". Fewer than 2 left: no odds.
- a league with more members than crowd.py sampled (it keeps only the top 10 and your neighbours above 70 managers) gets
  no odds, and says why, rather than odds from part of the league.
- season over / nothing left to play: no odds, and says why.
- during a live gameweek the league totals include points so far, but that gameweek's unplayed matches aren't simulated
  (the projections start next gameweek); the page says so.
"""
import numpy as np

import fplmodel

RUNS = 2000        # simulated seasons. P(1st) to about +/-1 point (1 s.e.); 2000 keeps the whole step to a few seconds
MIN_LEGAL = {"DEF": 3, "MID": 2, "FWD": 1}


def _fixture_goals(upcoming, gws, runs, cs_k):
    """{(gw, home, away, n): (home goals, away goals, conceded by the home defence, conceded by the away defence)}, each
    an array over the runs. "Conceded" is the other side's goals thinned by cs_k: what clean sheets and goals conceded
    are judged on, so their chances match the projection's exp(-cs_k * mu)."""
    out = {}
    for tid, by_gw in upcoming.items():
        for g in gws:
            seen = {}
            for (opp, home, mf, ma, _fdr) in by_gw.get(g, []):
                if not home:
                    continue
                n = seen[opp] = seen.get(opp, -1) + 1
                rng = np.random.default_rng([223, g, tid, opp, n])
                gh, ga = rng.poisson(mf, runs), rng.poisson(ma, runs)
                # what each defence is judged on: the other side's goals thinned by cs_k (Poisson(cs_k * mu) marginal)
                out[(g, tid, opp, n)] = (gh, ga, rng.binomial(ga, min(1.0, cs_k)), rng.binomial(gh, min(1.0, cs_k)))
    return out


def player_points(pid, proj, gws, goals, scoring, P, runs):
    """{gw: (points, appeared)} arrays over the runs for one player, averaging his xP each gameweek."""
    pr = proj.get(pid)
    res = {}
    zero = np.zeros(runs)
    # his true scoring rate is unknown (sim_sigma): one draw per run for the WHOLE season, not one per fixture as in a
    # single gameweek's distribution, or a season of independent draws would average the uncertainty away
    s_ = P["sim_sigma"]
    q = np.exp(s_ * np.random.default_rng([223, pid, 7]).standard_normal(runs) - s_ ** 2 / 2) if s_ else 1.0
    P0 = dict(P, sim_sigma=0.0)
    for g in gws:
        fxs = (pr or {}).get("fx", {}).get(g, [])
        pts, app = zero.copy(), np.zeros(runs, bool)
        seen = {}
        for j, fx in enumerate(fxs):
            key = (fx["h"], fx["a"])
            n = seen[key] = seen.get(key, -1) + 1
            gh, ga, ch, ca = goals[(g, fx["h"], fx["a"], n)]   # ch / ca: what the home / away defence conceded
            gf, gc = (gh, ch) if fx["home"] else (ga, ca)
            rng = np.random.default_rng([223, pid, g, j])
            a = fx["args"]
            args = list(a[1:])
            args[5], args[6] = a[6] * q, a[7] * q          # goals and assists per 90, times this run's rate draw
            p_, ap = fplmodel._sim_fixture(rng, runs, a[0], scoring, P0, *args, gf=gf, ga=gc)
            pts, app = pts + p_, app | ap
        xp = (pr or {}).get("xp", {}).get(g, 0.0)
        if fxs:
            pts = fplmodel.match_mean(pts, app, xp, np.random.default_rng([223, pid, g, 99]))
        res[g] = (pts, app)
    return res


def _xi_points(p, pos, pp, xp_g, g, runs, cap_override=None):
    """One manager's points in gameweek g, per run: the XI with FPL's auto-subs and the captain rule."""
    xi, bench = [el for el, _ in p[:11]], [el for el, _ in p[11:]]
    pts = {el: pp[el][g][0] for el in xi + bench}
    app = {el: pp[el][g][1] for el in xi + bench}
    counted = {el: np.ones(runs, bool) for el in xi}         # starter still in the team in this run
    for el in bench:
        counted[el] = np.zeros(runs, bool)
    n = {k: np.full(runs, sum(pos[el] == k for el in xi)) for k in MIN_LEGAL}
    used = {el: np.zeros(runs, bool) for el in bench}
    for out in xi:
        need = ~app[out]                                      # he didn't play: look down the bench
        for cand in bench:
            if (pos[out] == "GKP") != (pos[cand] == "GKP"):
                continue
            ok = need & app[cand] & ~used[cand]
            if pos[out] != pos[cand] and pos[out] != "GKP":
                ok &= n[pos[out]] - 1 >= MIN_LEGAL[pos[out]]  # the formation stays legal
            if not ok.any():
                continue
            counted[out] &= ~ok
            counted[cand] |= ok
            used[cand] |= ok
            if pos[out] != pos[cand] and pos[out] != "GKP":
                n[pos[out]] = n[pos[out]] - ok
                n[pos[cand]] = n[pos[cand]] + ok
            need &= ~ok
    order = sorted(xi, key=lambda el: -xp_g(el))
    cap = cap_override if cap_override is not None else order[0]
    vice = next(el for el in order if el != cap)
    total = sum(np.where(counted[el], pts[el], 0.0) for el in counted)
    holder_pts = np.where(app[cap], pts[cap], np.where(app[vice], pts[vice], 0.0))
    return total + holder_pts


def league_odds(leagues, picks_of, totals_of, pos, proj, upcoming, gws, scoring, P, me, picks_gw, in_play, runs=RUNS):
    """Odds for each league. leagues: [{"id","size","members":[entry ids]}]; picks_of(entry) -> (picks, why_not);
    totals_of(league id, entry) -> league total or None. Returns ({league id: odds}, {pid: [sim mean, xP] next GW})."""
    if not gws:
        return {lg["id"]: {"ok": False, "why": "No gameweeks left to play."} for lg in leagues}, {}
    goals = _fixture_goals(upcoming, gws, runs, P["cs_k"])
    pp, out = {}, {}
    xp_g = lambda g: (lambda el: (proj.get(el) or {}).get("xp", {}).get(g, 0.0))
    for lg in leagues:
        mem = lg["members"]
        if len(mem) < (lg.get("size") or 0):
            out[lg["id"]] = {"ok": False, "why": f"{lg['size']} managers: too big to load every squad (only the top 10 "
                             "and the managers around you are sampled), so no odds rather than odds from part of it."}
            continue
        incl, left = [], []
        for e in mem:
            pk, why = picks_of(e)
            tot = totals_of(lg["id"], e)
            if why is None and tot is None:
                why = "no league total"
            if why:
                left.append({"entry": e, "why": why})
            else:
                incl.append((e, pk, tot))
        res = {"ok": len(incl) >= 2, "n": len(incl), "m": len(mem), "left_out": left, "runs": runs, "gws": [gws[0], gws[-1]],
               "n_gws": len(gws), "picks_gw": picks_gw, "in_play": in_play,
               "assumed": ["squads held from the latest saved picks: no transfers, hits or chips",
                           "captain: the highest-xP starter each gameweek"]}
        if not res["ok"]:
            res["why"] = f"Only {len(incl)} of {len(mem)} managers' squads loaded."
            out[lg["id"]] = res
            continue
        for _, pk, _ in incl:
            for el, _m in pk:
                if el not in pp:
                    pp[el] = player_points(el, proj, gws, goals, scoring, P, runs)
        score = {e: np.full(runs, float(tot)) for e, _, tot in incl}
        mine = next(((e, pk) for e, pk, _ in incl if e == me), None)
        cap_opts, cap_extra = [], {}
        if mine:
            g0 = gws[0]
            cap_opts = sorted((el for el, _ in mine[1][:11]), key=lambda el: -xp_g(g0)(el))[:3]
        for g in gws:
            for e, pk, _ in incl:
                score[e] += _xi_points(pk, pos, pp, xp_g(g), g, runs)
        if mine:
            g0 = gws[0]
            base0 = _xi_points(mine[1], pos, pp, xp_g(g0), g0, runs)
            for c in cap_opts:
                cap_extra[c] = score[me] - base0 + _xi_points(mine[1], pos, pp, xp_g(g0), g0, runs, cap_override=c)
        ids = [e for e, _, _ in incl]
        jit = np.random.default_rng([223, lg["id"]]).random((len(ids), runs)) * 1e-3   # ties split at random

        def finish(mat):
            rank = (-(mat + jit)).argsort(0).argsort(0)               # 0 = 1st, per run
            return rank

        mat = np.array([score[e] for e in ids])
        rank = finish(mat)
        rows = []
        for i, e in enumerate(ids):
            rows.append({"entry": e, "p1": round(float((rank[i] == 0).mean()), 4),
                         "p3": round(float((rank[i] < min(3, len(ids))).mean()), 4),
                         "plast": round(float((rank[i] == len(ids) - 1).mean()), 4),
                         "mean": round(float(score[e].mean()), 1)})
        rows.sort(key=lambda r: (-r["p1"], -r["mean"]))
        res["rows"] = rows
        if mine:
            mi = ids.index(me)
            caps = []
            for c in cap_opts:
                m2 = mat.copy()
                m2[mi] = cap_extra[c]
                caps.append({"id": c, "xp": round(xp_g(gws[0])(c), 2), "p1": round(float((finish(m2)[mi] == 0).mean()), 4)})
            res["captain"] = {"gw": gws[0], "options": caps}
        out[lg["id"]] = res
    g0 = gws[0]
    means = {str(el): [round(float(v[g0][0].mean()), 2), round((proj.get(el) or {}).get("xp", {}).get(g0, 0.0), 2)]
             for el, v in pp.items()}
    return out, means
