"""Team strength adjustments for absent players (experimental; see fplmodel abs_alpha_* params).

build_team_adj(ctx, k, horizon, team_at, mode="oracle") -> {(team, gw): {"att": a, "def": d}} for gw in k..k+horizon-1.
  att: share of the team's recent (xG + xA) belonging to players who play that week, relative to the
       average share that played in the window's own games (1.0 = normal line-up). Clipped to [0.5, 1.2].
  (centre=True divides each by that target week's league mean first; see the note in the code)
  def: goals-conceded multiplier = 1 / (same idea on GK + DEF minutes, GK weighted gk_w). Clipped to [0.8, 1.25].
mode "oracle" uses who really played (0 minutes = absent), i.e. perfect hindsight about absences.
Also returns, via explain=True, who was missing behind each factor.
"""
from collections import defaultdict

WINDOW = 6
ATT_CLIP = (0.5, 1.2)
DEF_CLIP = (0.8, 1.25)


def club_fn(ctx, team_at=None):
    el = ctx["elements"]
    if team_at is None:
        return lambda pid, g: el[pid]["team"]
    return lambda pid, g: team_at(pid, g + 1) or el[pid]["team"]


def _by_team_gw(ctx, club):
    """{(team, gw): [(pid, minutes, xg+xa, element_type)]} for players with a stats row."""
    out = defaultdict(list)
    el = ctx["elements"]
    for pid, gs in ctx["pstats"].items():
        if pid not in el:
            continue
        et = el[pid]["element_type"]
        for g, s in gs.items():
            out[(club(pid, g), g)].append((pid, s["minutes"], float(s["expected_goals"]) + float(s["expected_assists"]), et))
    return out


def build_team_adj(ctx, k, horizon, team_at=None, mode="oracle", gk_w=3.0, explain=False, centre=True, _cache={}):
    assert mode == "oracle"
    key = (id(ctx), team_at is None)  # rows are the same for any centre / gk_w
    if key not in _cache:
        club = club_fn(ctx, team_at)
        _cache[key] = _by_team_gw(ctx, club)
    rows = _cache[key]
    last = max(g for (_, g) in rows)
    adj, why = {}, {}
    teams = ctx["teams"]
    lo = max(1, k - WINDOW)
    raw = {}   # (team, gw) -> (att ratio, def ratio) before centring / clipping
    for tid in teams:
        # window games: weeks before k where the team has anyone playing
        wg = [g for g in range(lo, k) if any(m > 0 for _, m, _, _ in rows.get((tid, g), ()))]
        if not wg:
            continue
        att_w, def_w = defaultdict(float), defaultdict(float)
        for g in wg:
            for pid, m, xx, et in rows[(tid, g)]:
                att_w[pid] += xx
                if et == 1:
                    def_w[pid] += m * gk_w
                elif et == 2:
                    def_w[pid] += m
        ta, td = sum(att_w.values()), sum(def_w.values())
        if ta <= 0 or td <= 0:
            continue
        sa = {p: v / ta for p, v in att_w.items()}
        sd = {p: v / td for p, v in def_w.items()}

        def present(g, share):
            played = {pid for pid, m, _, _ in rows.get((tid, g), ()) if m > 0}
            return sum(v for p, v in share.items() if p in played), played

        base_a = sum(present(g, sa)[0] for g in wg) / len(wg)
        base_d = sum(present(g, sd)[0] for g in wg) / len(wg)
        if base_a <= 0 or base_d <= 0:
            continue
        for t in range(k, k + horizon):
            if t > last:
                continue
            pa, played = present(t, sa)
            pd_, _ = present(t, sd)
            if not played:
                continue   # no data for the week (blank / not yet played)
            raw[(tid, t)] = (pa / base_a, base_d / max(pd_, 1e-9))
            if explain:
                why[(tid, t)] = {"att": sorted(((v, p) for p, v in sa.items() if p not in played), reverse=True),
                                 "def": sorted(((v, p) for p, v in sd.items() if p not in played), reverse=True)}
    # the window is in-sample (everyone is "present" in the games they produced in), so the average team looks
    # ~9% short of attackers and ~10% short of defenders in later weeks; centre each target week on the league mean
    mean = {}
    for t in {t for _, t in raw}:
        v = [r for (tt, g), r in raw.items() if g == t]
        mean[t] = (sum(a for a, _ in v) / len(v), sum(d for _, d in v) / len(v)) if centre else (1.0, 1.0)
    for (tid, t), (a, d) in raw.items():
        adj[(tid, t)] = {"att": min(ATT_CLIP[1], max(ATT_CLIP[0], a / mean[t][0])),
                         "def": min(DEF_CLIP[1], max(DEF_CLIP[0], d / mean[t][1]))}
    return (adj, why) if explain else adj
