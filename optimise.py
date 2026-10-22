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


def solve(players, squad, sell, bank, ft0, gws, *, decay=0.9, bench_w=0.1, ft_value=1.5,
          hit=4, week1_moves=None, max_moves_week=4, banned=(), locked=(), time_limit=40):
    """players: {id: {pos, team, price(£m), xp:{gw: float}, ok:bool}}; squad: list of ids;
    sell: {id: selling price £m}; bank £m; ft0: free transfers for the first gameweek."""
    gws = list(gws)
    W = range(len(gws))
    # candidate pool: current squad + best options per position by projected points
    pool = set(squad)
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

    obj = []
    for w in W:
        d = decay ** w
        obj.append(d * pulp.lpSum(xp[i, w] * (xi[i][w] + cp[i][w] + bench_w * (sq[i][w] - xi[i][w])) for i in pool))
        obj.append(-d * hit * hits[w])
    obj.append(ft_value * ft[len(gws)])
    m += pulp.lpSum(obj)
    status = m.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit))
    if pulp.LpStatus[status] not in ("Optimal", "Not Solved") or m.objective is None:
        return None
    v = lambda x: round(x.value() or 0)

    weeks = []
    for w in W:
        ins = [i for i in pool if v(tin[i][w])]
        outs = [i for i in pool if v(tout[i][w])]
        lineup = [i for i in pool if v(xi[i][w])]
        cap = next(i for i in pool if v(cp[i][w]))
        sqd = [i for i in pool if v(sq[i][w])]
        bench = sorted([i for i in sqd if i not in lineup], key=lambda i: (players[i]["pos"] != "GKP", -xp[i, w]))
        vice = sorted([i for i in lineup if i != cap], key=lambda i: -xp[i, w])[0]
        pts = sum(xp[i, w] for i in lineup) + xp[cap, w]
        weeks.append({
            "gw": gws[w], "in": ins, "out": outs, "xi": lineup, "bench": bench, "captain": cap, "vice": vice,
            "ft": v(ft[w]), "hits": v(hits[w]), "bank": round(bk[w].value() or 0, 1), "xp": round(pts, 2),
        })
    total = sum(wk["xp"] for wk in weeks) - hit * sum(wk["hits"] for wk in weeks)
    return {"weeks": weeks, "xp_total": round(total, 2), "objective": round(pulp.value(m.objective), 2),
            "ft_left": v(ft[len(gws)])}
