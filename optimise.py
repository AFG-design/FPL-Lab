"""Multi-gameweek transfer optimiser (mixed-integer programme, solved with CBC via PuLP).

Chooses transfers, lineups and captains for each of the next H gameweeks to
maximise projected points, respecting budget, squad shape, the 3-per-club rule
and FPL's free-transfer rules (1 per week, roll up to 5, extra moves cost 4).
"""
import pulp

SHAPE = {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}
XI_MIN = {"GKP": 1, "DEF": 3, "MID": 2, "FWD": 1}
XI_MAX = {"GKP": 1, "DEF": 5, "MID": 5, "FWD": 3}
POOL = {"GKP": 14, "DEF": 40, "MID": 45, "FWD": 25}


def _k(k, lam):
    """Chase (lam < 0) only rewards differentials; it never pushes you to drop what the field owns."""
    return max(0.0, k) if lam < 0 else k


def variance(pos, x):
    """Variance of a player's points for one fixture, fitted on GW3-7 backtest residuals."""
    if pos == "MID":
        return 1.9 * x + 0.23 * x * x
    return {"GKP": 2.8, "DEF": 3.3, "FWD": 3.8}.get(pos, 3.0) * x


def spread(players, mult, eo, gw):
    """Standard deviation of your score minus the field's for one gameweek (points)."""
    v = 0.0
    for i, p in players.items():
        x = p["xp"].get(gw, 0.0)
        if x <= 0:
            continue
        d = mult.get(i, 0) - eo.get(i, 0.0)
        if d:
            v += variance(p["pos"], x) * d * d
    return v ** 0.5


def solve(players, squad, sell, bank, ft0, gws, *, decay=0.9, bench_w=0.1, ft_value=1.5,
          hit=4, week1_moves=None, max_moves_week=4, banned=(), locked=(), time_limit=40,
          eo=None, lam=0.0, eo_weeks=2, freeze_after=None, haul_w=0.0, hit_margin=0.0, nail_w=0.0, floor=None):
    """players: {id: {pos, team, price(£m), xp:{gw: float}, ok:bool}}; squad: list of ids;
    sell: {id: selling price £m}; bank £m; ft0: free transfers for the first gameweek.

    eo/lam: rank-aware play. eo = {id: effective ownership as a fraction (captain = 2)} for the
    managers you are competing with. The variance of your score relative to theirs is
    sum_i var_i * (m_i - eo_i)^2, where m_i is your multiplier (0, 1 or 2). With m = xi + cp that
    is linear in xi and cp: var_i * (xi*(1 - 2eo) + cp*(3 - 2eo)) + const. lam > 0 penalises
    that variance (play safe, track the field); lam < 0 rewards it (chase rank with differentials).

    Strategy extras: haul_w rewards each starter's chance of 10+ points (players[i]["p10"][gw]), double for the
    captain, so upside can justify a move (chase); hit_margin makes the optimiser demand that many extra points
    before taking a hit, and nail_w marks down starters who may not play (players[i]["nailed"], 0-100) (safe).
    Reported totals are always plain projected points minus 4 per hit.

    floor: the plan's value (see VALUE below) must be at least this. The strategies use it so Play safe never gives
    up points against Balanced and Chase rank gives up at most a fixed amount (strategy_plans)."""
    gws = list(gws)
    W = range(len(gws))
    # candidate pool: current squad + best options per position by projected points
    pool = set(squad) | {i for i in locked if i in players}  # a lock outside the shortlist must still be honoured
    for pos, n in POOL.items():
        c = [i for i, p in players.items() if p["pos"] == pos and p["ok"] and i not in banned]
        c.sort(key=lambda i: -sum(players[i]["xp"].get(g, 0) for g in gws))
        pool.update(c[:n])
    pool = sorted(pool)
    init = {i: int(i in squad) for i in pool}
    buy = {i: players[i]["price"] for i in pool}
    sp = {i: (sell[i] if i in sell else players[i]["price"]) for i in pool}
    xp = {(i, w): players[i]["xp"].get(gws[w], 0.0) for i in pool for w in W}

    m = pulp.LpProblem("fpl", pulp.LpMaximize)
    B = pulp.LpBinary
    sq = pulp.LpVariable.dicts("sq", (pool, W), cat=B)
    xi = pulp.LpVariable.dicts("xi", (pool, W), cat=B)
    cp = pulp.LpVariable.dicts("cp", (pool, W), cat=B)
    tin = pulp.LpVariable.dicts("tin", (pool, W), cat=B)
    tout = pulp.LpVariable.dicts("tout", (pool, W), cat=B)
    ft = pulp.LpVariable.dicts("ft", range(len(gws) + 1), lowBound=0, upBound=5, cat="Integer")
    hits = pulp.LpVariable.dicts("hits", W, lowBound=0, cat="Integer")
    bk = pulp.LpVariable.dicts("bank", W, lowBound=0)

    m += ft[0] == ft0
    for w in W:
        for i in pool:
            prev = init[i] if w == 0 else sq[i][w - 1]
            m += sq[i][w] == prev + tin[i][w] - tout[i][w]
            m += tout[i][w] <= prev
            m += tin[i][w] + tout[i][w] <= 1
            m += xi[i][w] <= sq[i][w]
            m += cp[i][w] <= xi[i][w]
            if i in banned:
                m += sq[i][w] == 0
            if i in locked:
                m += sq[i][w] == 1
            if not players[i]["ok"]:
                m += tin[i][w] == 0
        for pos, n in SHAPE.items():
            ids = [i for i in pool if players[i]["pos"] == pos]
            m += pulp.lpSum(sq[i][w] for i in ids) == n
            m += pulp.lpSum(xi[i][w] for i in ids) >= XI_MIN[pos]
            m += pulp.lpSum(xi[i][w] for i in ids) <= XI_MAX[pos]
        m += pulp.lpSum(xi[i][w] for i in pool) == 11
        m += pulp.lpSum(cp[i][w] for i in pool) == 1
        for t in {players[i]["team"] for i in pool}:
            m += pulp.lpSum(sq[i][w] for i in pool if players[i]["team"] == t) <= 3
        prev_bank = bank if w == 0 else bk[w - 1]
        m += bk[w] == prev_bank + pulp.lpSum(sp[i] * tout[i][w] - buy[i] * tin[i][w] for i in pool)
        n_w = pulp.lpSum(tin[i][w] for i in pool)
        m += n_w <= max_moves_week
        m += hits[w] >= n_w - ft[w]
        m += ft[w + 1] <= ft[w] - n_w + hits[w] + 1
        m += ft[w + 1] >= 1
        if w == 0 and week1_moves is not None:
            m += n_w == week1_moves
        if freeze_after is not None and w >= freeze_after:
            m += n_w == 0          # e.g. a wildcard: rebuild once, then hold the squad

    obj = []
    for w in W:
        d = decay ** w
        obj.append(d * pulp.lpSum(xp[i, w] * (xi[i][w] + cp[i][w] + bench_w * (sq[i][w] - xi[i][w])) for i in pool))
        if haul_w:
            obj.append(d * haul_w * pulp.lpSum(players[i].get("p10", {}).get(gws[w], 0.0) * (xi[i][w] + cp[i][w]) for i in pool))
        if nail_w:
            obj.append(-d * nail_w * pulp.lpSum((1 - min(100, players[i].get("nailed", 100)) / 100) * xp[i, w] * xi[i][w] for i in pool))
        if eo is not None and lam and w < eo_weeks:  # ownership data goes stale after a week or two
            obj.append(-lam * d * pulp.lpSum(
                variance(players[i]["pos"], xp[i, w]) * (xi[i][w] * _k(1 - 2 * eo.get(i, 0.0), lam) + cp[i][w] * _k(3 - 2 * eo.get(i, 0.0), lam))
                for i in pool if xp[i, w] > 0))
        obj.append(-d * (hit + hit_margin) * hits[w])
    obj.append(ft_value * ft[len(gws)])
    m += pulp.lpSum(obj)
    # VALUE: plain projected points over the plan (XI + captain, no decay), minus 4 per hit, plus ft_value for each
    # free transfer still banked at the end. The same measure as vs_roll in build.py, so budgets read as points.
    value = (pulp.lpSum(xp[i, w] * (xi[i][w] + cp[i][w]) for i in pool for w in W)
             - hit * pulp.lpSum(hits[w] for w in W) + ft_value * ft[len(gws)])
    if floor is not None:
        m += value >= floor
    status = m.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit))
    # CBC can stop at the time limit with or without a plan, and PuLP doesn't always tell the two apart,
    # so anything short of "no solution exists" is read back and re-checked against the rules below.
    if m.sol_status in (pulp.LpSolutionInfeasible, pulp.LpSolutionUnbounded) or m.objective is None:
        print(f"optimise.solve: no usable plan ({pulp.LpStatus[status]}, {pulp.LpSolution.get(m.sol_status)})")
        return None
    v = lambda x: round(x.value() or 0)

    weeks = []
    for w in W:
        ins = [i for i in pool if v(tin[i][w])]
        outs = [i for i in pool if v(tout[i][w])]
        lineup = [i for i in pool if v(xi[i][w])]
        cap = next((i for i in pool if v(cp[i][w])), None)
        if cap is None:
            print("optimise.solve: no usable plan (no captain in the solution)")
            return None
        sqd = [i for i in pool if v(sq[i][w])]
        bench = sorted([i for i in sqd if i not in lineup], key=lambda i: (players[i]["pos"] != "GKP", -xp[i, w]))
        vice = (sorted([i for i in lineup if i != cap], key=lambda i: -xp[i, w]) or [cap])[0]
        pts = sum(xp[i, w] for i in lineup) + xp[cap, w]
        weeks.append({
            "gw": gws[w], "in": ins, "out": outs, "xi": lineup, "bench": bench, "captain": cap, "vice": vice,
            "ft": v(ft[w]), "hits": v(hits[w]), "bank": round(bk[w].value() or 0, 1), "xp": round(pts, 2),
        })
    problem = _check(weeks, players, squad, sp, buy, bank, init, locked, banned)
    if problem:
        print(f"optimise.solve: rejected plan ({problem})")
        return None
    optimal = m.sol_status == pulp.LpSolutionOptimal
    if not optimal:
        print("optimise.solve: time limit reached, using the best plan found so far")
    total = sum(wk["xp"] for wk in weeks) - hit * sum(wk["hits"] for wk in weeks)
    ft_left = v(ft[len(gws)])
    return {"weeks": weeks, "xp_total": round(total, 2), "objective": round(pulp.value(m.objective), 2),
            "ft_left": ft_left, "value": round(total + ft_value * ft_left, 2), "optimal": optimal}


# ---------------------------------------------------------------- strategies
# Each strategy is Balanced plus a risk preference, held to a points budget against Balanced:
#   Balanced    the most projected points.
#   Play safe   never gives up points against Balanced (budget 0); among plans worth the same it picks the one that
#               tracks what the managers around you own, avoids starters who may not play and avoids marginal hits.
#   Chase rank  gives up at most CHASE_BUDGET points to back differentials and players with a high chance of a haul,
#               and takes a hit only when it clears the same extra bar as Play safe (no hits just for upside).
# Every plan that makes a transfer must beat making no transfers at all by MIN_PROFIT points (the "no moves for the
# sake of it" rule); a move-count option that can't is dropped rather than shown.
# Budgets and profit are in VALUE points (plain projected points over the plan, minus hits, plus banked FTs).
SAFE_BUDGET = 0.0
CHASE_BUDGET = 4.0
MIN_PROFIT = 1.0
TIE = 0.1   # rounding room for "the same points" (the solver works to 0.1% gaps)
EO_WEEKS = None   # weeks the ownership term covers (None = the whole plan, fading with the plan's decay)
STRATEGY = {
    "balanced": {},
    "safe": {"lam": 0.1, "nail_w": 0.5, "hit_margin": 2.0},
    # hit_margin: a hit must clear 4 + 2 projected points, as for Play safe. Without it Chase took 3x Balanced's hits
    # in the replay (strategy_replay.py) and lost about 2 real points a week for one extra big week.
    "chase": {"lam": -0.15, "haul_w": 20.0, "hit_margin": 2.0},
}


def strategy_plans(players, squad, sell, bank, ft0, gws, options, eo=None, modes=("balanced", "safe", "chase"), **kw):
    """Plans per strategy and move option. options: [(key, week1_moves)]. Returns ({plan key: plan}, notes).
    Plan keys: "best", "roll", ... for Balanced and "safe_best", "chase_roll", ... for the others.

    Missing input: without field ownership (eo None or empty) Play safe and Chase rank can't be worked out, so only
    Balanced is returned and a note says why (the Planner shows a 'no plan' message, validate.py warns)."""
    notes = []
    base = dict(players=players, squad=squad, sell=sell, bank=bank, ft0=ft0, gws=gws, **kw)
    none = solve(**base, week1_moves=0, freeze_after=0)          # keep the squad for the whole plan
    if not none:
        return {}, ["no plan without transfers could be worked out"]
    v0 = none["value"]
    modes = [m for m in modes if m == "balanced" or eo]
    if not eo:
        notes.append("no field ownership: Play safe and Chase rank skipped")
    plans = {}
    for key, n in options:
        bal = solve(**base, week1_moves=n)
        if not bal:
            continue
        for mode in modes:
            if mode == "balanced":
                r = bal
            else:
                floor = bal["value"] - SAFE_BUDGET - TIE if mode == "safe" else bal["value"] - CHASE_BUDGET
                if bal["value"] >= v0 + MIN_PROFIT:
                    floor = max(floor, v0 + MIN_PROFIT)   # still a clear profit on doing nothing
                r = solve(**base, week1_moves=n, eo=eo, eo_weeks=EO_WEEKS or len(gws), floor=floor, **STRATEGY[mode]) or bal
            moves = sum(len(w["in"]) for w in r["weeks"])
            if moves and r["value"] < v0 + MIN_PROFIT and key != "roll":
                notes.append(f"{mode} {key}: {r['value'] - v0:+.1f} vs no transfers, below the {MIN_PROFIT:g} profit rule: dropped")
                continue
            r["vs_none"] = round(r["value"] - v0, 2)
            r["vs_balanced"] = round(r["value"] - bal["value"], 2)
            plans[key if mode == "balanced" else f"{mode}_{key}"] = r
    return plans, notes


def _check(weeks, players, squad, sp, buy, bank, init, locked, banned):
    """Re-check a plan against the FPL rules independently of the solver. Returns a reason, or None if it's legal."""
    have = {i for i, x in init.items() if x}
    money = bank
    for wk in weeks:
        if not set(wk["out"]) <= have or set(wk["in"]) & have:
            return f"GW{wk['gw']}: sells a player not owned or buys one already owned"
        money += sum(sp[i] for i in wk["out"]) - sum(buy[i] for i in wk["in"])
        have = (have - set(wk["out"])) | set(wk["in"])
        if money < -0.05:
            return f"GW{wk['gw']}: over budget by £{-money:.1f}m"
        if set(wk["xi"]) | set(wk["bench"]) != have:
            return f"GW{wk['gw']}: lineup doesn't match the squad"
        for pos, n in SHAPE.items():
            if sum(1 for i in have if players[i]["pos"] == pos) != n:
                return f"GW{wk['gw']}: wrong number of {pos}"
        clubs = {}
        for i in have:
            clubs[players[i]["team"]] = clubs.get(players[i]["team"], 0) + 1
        if max(clubs.values()) > 3:
            return f"GW{wk['gw']}: more than 3 from one club"
        if len(wk["xi"]) != 11 or wk["captain"] not in wk["xi"]:
            return f"GW{wk['gw']}: invalid starting XI or captain"
        if any(i not in have for i in locked if i in players) or have & set(banned):
            return f"GW{wk['gw']}: breaks a lock or ban"
    return None
