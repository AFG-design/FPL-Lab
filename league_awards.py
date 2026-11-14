"""Weekly honours for a mini-league: eight awards for one settled gameweek. Pure functions, no I/O (awards.py fetches).

    league_awards(members, gw, inputs, info, ranks=None, size=None) -> {"awards": {key: award}, "coverage": {...}}

members: [{"entry", "player"}] — the league's tracked managers (all of a small league; the top 10 and your neighbours
         in a big one, as crowd.py samples them).
inputs:  {entry: {"hist": FPL history row for gw or None, "picks": FPL picks response for gw or None,
                   "transfers": [FPL transfer records for gw] or None (None = not fetched)}}
info:    {"pts": {element: GW points}, "pos": {element: "GKP"|"DEF"|"MID"|"FWD"}, "team": {element: club id},
          "name": {element: web name}}
ranks:   {entry: (official league rank now, official league rank before this gw)} from FPL's league standings, or
         None when they can't be checked against this gameweek (see awards.py) -> Biggest Climber is unavailable.

Every award ranks by competition ranking (1, 2, 3, 3 and 1, 1, 3) and keeps places 1-3: rank 1 gold, 2 silver,
3 bronze, so a tie for gold leaves no silver. Fewer qualifiers -> fewer places; none -> status "none".
Points are FPL's GW points for a player (all his matches that gameweek, bonus included), before any captaincy.

Missing data: a manager whose input for an award is missing is left out of that award and counted in its "covered"
figure, so the page can say "among N tracked managers". Nothing is filled in with a default.
"""

MEDAL = {1: "gold", 2: "silver", 3: "bronze"}
ORDER = ["totw", "climber", "wall", "bench", "blueprint", "grain", "hits", "shuffler"]
GRAIN_SHARE = 0.2      # Against the Grain: starters in strictly fewer than 20% of the covered starting XIs
MIN_TEMPLATE = 3       # The Blueprint needs at least this many covered XIs for a league template to mean anything
XI_MAX = {"GKP": 1, "DEF": 5, "MID": 5, "FWD": 3}
XI_MIN = {"GKP": 1, "DEF": 3, "MID": 2, "FWD": 1}


def podium(rows):
    """rows: [{"entry", "value", ...}] of qualifiers; higher value is better. Competition ranking, places 1-3 kept.
    Equal values share a rank; the next rank skips (1, 1, 3). Ties are listed in entry order so output is stable."""
    rows = sorted(rows, key=lambda r: (-r["value"], r["entry"]))
    out = []
    for i, r in enumerate(rows):
        rank = out[-1]["rank"] if out and out[-1]["value"] == r["value"] else i + 1
        if rank > 3:
            break
        out.append(dict(r, rank=rank, medal=MEDAL[rank]))
    return out


def xi_as_picked(picks):
    rows = sorted(picks["picks"], key=lambda p: p["position"])
    return [p["element"] for p in rows[:11]]


def final_xi(picks):
    """The scoring XI: positions 1-11 with FPL's own confirmed automatic substitutions applied (picks["automatic_subs"],
    published once the gameweek is over). A Bench Boost has no substitutions; its bench is not part of the XI."""
    xi = xi_as_picked(picks)
    for s in picks.get("automatic_subs") or []:
        xi = [s["element_in"] if i == s["element_out"] else i for i in xi]
    return xi


def net_transfers(transfers):
    """Net player changes from a gameweek's transfer records: a player bought and sold again in the same week
    (A -> B, then B -> C) cancels out, leaving A -> C. Returns (ins, outs) as sorted lists."""
    ins = {t["element_in"] for t in transfers}
    outs = {t["element_out"] for t in transfers}
    return sorted(ins - outs), sorted(outs - ins)


def chip_of(inp):
    pk = inp.get("picks")
    if pk is not None:
        return pk.get("active_chip")
    return inp.get("chip")


def reference_xi(xis, pos, team):
    """The league's most-selected legal starting XI, built the same way every time:
    1. count how many covered XIs (as picked, before automatic subs) start each player;
    2. order players by that count, most first, ties broken by the lower FPL element id;
    3. take the top keeper, then the top 3 defenders, 2 midfielders and 1 forward, then fill the last 4 places from the
       best remaining outfield players, never above 5 defenders, 5 midfielders, 3 forwards or 3 players from one club.
    Returns (xi ids, {id: count})."""
    cnt = {}
    for xi in xis:
        for i in xi:
            cnt[i] = cnt.get(i, 0) + 1
    order = sorted((i for i in cnt if i in pos), key=lambda i: (-cnt[i], i))
    chosen, by_pos, by_club = [], {k: 0 for k in XI_MAX}, {}

    def take(i):
        chosen.append(i)
        by_pos[pos[i]] += 1
        by_club[team.get(i)] = by_club.get(team.get(i), 0) + 1

    def ok(i, cap):
        return i not in chosen and by_pos[pos[i]] < cap[pos[i]] and by_club.get(team.get(i), 0) < 3

    for p in ("GKP", "DEF", "MID", "FWD"):
        for i in order:
            if by_pos[p] >= XI_MIN[p]:
                break
            if pos[i] == p and ok(i, XI_MAX):
                take(i)
    for i in order:
        if len(chosen) >= 11:
            break
        if pos[i] != "GKP" and ok(i, XI_MAX):
            take(i)
    return chosen, cnt


def league_awards(members, gw, inputs, info, ranks=None, size=None):
    pts, pos, team, name = info["pts"], info["pos"], info["team"], info.get("name", {})
    P = lambda i: pts.get(i, 0)
    nm = lambda i: name.get(i, str(i))
    who = {m["entry"]: m["player"] for m in members}
    row = lambda e, value, **kw: dict({"entry": e, "player": who[e], "value": value}, **kw)
    inp = {m["entry"]: inputs.get(m["entry"]) or {} for m in members}
    has_hist = [e for e in who if inp[e].get("hist")]
    has_picks = [e for e in who if inp[e].get("picks")]
    has_tx = [e for e in who if inp[e].get("transfers") is not None and inp[e].get("hist")]
    awards = {}

    def award(key, rows, covered, **kw):
        awards[key] = dict({"places": podium(rows), "qualified": len(rows), "covered": covered,
                            "status": "ok" if rows else "none"}, **kw)

    # 1. Transfer of the Week: net arrivals' GW points - net departures' GW points - that week's hit cost.
    # Free Hit weeks are left out: the squad is borrowed for one week and goes back, so nothing was transferred.
    tw, hit_gain = [], {}
    for e in has_tx:
        ins, outs = net_transfers(inp[e]["transfers"])
        hit = inp[e]["hist"].get("event_transfers_cost") or 0
        if chip_of(inp[e]) == "freehit" or not (ins or outs):
            continue
        pin, pout = sum(P(i) for i in ins), sum(P(i) for i in outs)
        hit_gain[e] = pin - pout
        tw.append(row(e, pin - pout - hit, ins=[[nm(i), P(i)] for i in ins], outs=[[nm(i), P(i)] for i in outs],
                      pin=pin, pout=pout, hit=hit, chip=chip_of(inp[e])))
    award("totw", tw, len(has_tx), basis="free_hit_excluded")

    # 2. Biggest Climber: official league rank before the gameweek minus official rank after it, rises only.
    if ranks is None:
        awards["climber"] = {"places": [], "qualified": 0, "covered": 0, "status": "unavailable",
                             "why": "FPL only shows the current and previous league ranks, so this week's ranks weren't saved."}
    else:
        comparable = [e for e in who if e in ranks and ranks[e][0] and ranks[e][1]]
        cl = [row(e, ranks[e][1] - ranks[e][0], before=ranks[e][1], after=ranks[e][0]) for e in comparable
              if ranks[e][1] - ranks[e][0] > 0]
        award("climber", cl, len(comparable))

    # 3. The Wall: keeper and defenders in the final scoring XI, before captaincy.
    wl = []
    for e in has_picks:
        xi = final_xi(inp[e]["picks"])
        gk = sum(P(i) for i in xi if pos.get(i) == "GKP")
        df = sum(P(i) for i in xi if pos.get(i) == "DEF")
        wl.append(row(e, gk + df, gk=gk, df=df))
    award("wall", wl, len(has_picks))

    # 4. Bench Rescue: the best single confirmed automatic substitution (FPL's automatic_subs). Only one that scored
    # counts. A Bench Boost has no substitutions, so it can't qualify.
    br = []
    for e in has_picks:
        subs = [(P(s["element_in"]), s) for s in inp[e]["picks"].get("automatic_subs") or []]
        if subs:
            best, s = max(subs, key=lambda x: (x[0], -x[1]["element_in"]))
            if best > 0:
                br.append(row(e, best, sub_in=nm(s["element_in"]), sub_out=nm(s["element_out"]), subs=len(subs)))
    award("bench", br, len(has_picks))

    # 5. The Blueprint and 6. Against the Grain share one basis: the covered XIs as picked (before automatic subs).
    xis = {e: xi_as_picked(inp[e]["picks"]) for e in has_picks}
    n = len(xis)
    if n >= MIN_TEMPLATE:
        ref, cnt = reference_xi(list(xis.values()), pos, team)
        bp = [row(e, len(set(xi) & set(ref)), of=len(ref)) for e, xi in xis.items()]
        award("blueprint", bp, n, ref=[nm(i) for i in ref], ref_n=n)
        rare = {i for i, c in cnt.items() if c < GRAIN_SHARE * n}
        gr = []
        for e, xi in xis.items():
            mine = [i for i in xi if i in rare]
            v = sum(P(i) for i in mine)
            if mine and v > 0:
                gr.append(row(e, v, players=[[nm(i), P(i), cnt[i]] for i in sorted(mine, key=lambda i: -P(i))]))
        award("grain", gr, n, threshold=GRAIN_SHARE, base=n)
    else:
        for k in ("blueprint", "grain"):
            awards[k] = {"places": [], "qualified": 0, "covered": n, "status": "unavailable",
                         "why": f"Needs at least {MIN_TEMPLATE} starting XIs; {n} were available."}

    # 7. Hit Parade: points spent on hits, hit-takers only; whether the arrivals covered it where transfers are known.
    hp = []
    for e in has_hist:
        hit = inp[e]["hist"].get("event_transfers_cost") or 0
        if hit > 0:
            g = hit_gain.get(e)
            hp.append(row(e, hit, gain=g, covered_cost=None if g is None else g >= hit))
    award("hits", hp, len(has_hist))

    # 8. Team Sheet Shuffler: transfer records FPL lists for the gameweek. FPL's history counts 0 in Wildcard and Free
    # Hit weeks, so the records are used, and the chip is named.
    sh = []
    for e in has_tx:
        tx = inp[e]["transfers"]
        if tx:
            ins, _ = net_transfers(tx)
            sh.append(row(e, len(tx), chip=chip_of(inp[e]) if chip_of(inp[e]) in ("wildcard", "freehit") else None,
                          changed=len(ins)))
    award("shuffler", sh, len(has_tx))

    return {"gw": gw, "awards": {k: awards[k] for k in ORDER},
            "coverage": {"members": len(who), "size": size or len(who), "hist": len(has_hist), "picks": len(has_picks),
                         "transfers": len(has_tx)}}
