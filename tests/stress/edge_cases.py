#!/usr/bin/env python3
"""2. Edge cases: synthetic and real situations, asserting the projections stay sane."""
import copy, json, math, datetime as dt
from collections import defaultdict
from common import *
from fplmodel import project, availability, return_date, prepare

C = cur_ctx(); NXT = cur_last() + 1   # first unplayed GW in the clean data
R = []
def check(name, ok, detail):
    R.append({"case": name, "ok": bool(ok), "detail": detail}); print(("PASS " if ok else "FAIL ") + name + ": " + detail)

def proj(ctx, flags=True, h=6):
    return project(ctx, NXT, h, {"use_flags": flags})

base = proj(C); P0 = base["players"]; el = C["elements"]
# E1 global sanity
bad = [(el[p]["web_name"], g, v) for p, r in P0.items() for g, v in r["xp"].items() if not math.isfinite(v) or v < 0 or v > 15]
check("E1 all xP finite, >= 0, <= 15", not bad, f"{len(bad)} bad values {bad[:5]}; max {max(v for r in P0.values() for v in r['xp'].values()):.2f}")

def with_fixtures(fx):
    b = dict(C["boot"]); return prepare(b, fx, {g: {"elements": [{"id": p, "stats": s, "explain": []} for p, gs in C["pstats"].items() for gg, s in gs.items() if gg == g]} for g in range(1, NXT)}, {"players": C["priors"]}, {"matches": C["market"]})
# pick a strong team and its GW NXT+1 fixture
g2 = NXT + 1
tid = max(C["teams"], key=lambda t: base["rating"][t]["att"])
top = max((p for p in P0 if el[p]["team"] == tid), key=lambda p: P0[p]["xp"].get(g2, 0))
fx = copy.deepcopy(C["fixtures"])
f0 = next(f for f in fx if f["event"] == g2 and tid in (f["team_h"], f["team_a"]))
opp_pool = [t for t in C["teams"] if t not in (f0["team_h"], f0["team_a"])]
dgw = dict(f0, id=99999, team_h=tid, team_a=opp_pool[0], team_h_score=None, team_a_score=None)
c2 = with_fixtures(fx + [dgw]); p2 = proj(c2)["players"]
c_ref = with_fixtures(fx); p_ref = proj(c_ref)["players"]
ratio = p2[top]["xp"][g2] / p_ref[top]["xp"][g2]
check("E2 double GW ~doubles xP", 1.6 <= ratio <= 2.2, f"{el[top]['web_name']} GW{g2} {p_ref[top]['xp'][g2]:.2f} -> {p2[top]['xp'][g2]:.2f} (x{ratio:.2f})")
c3 = with_fixtures([f for f in fx if f is not f0]); p3 = proj(c3)["players"]
check("E3 blank GW gives 0", p3[top]["xp"][g2] == 0, f"{el[top]['web_name']} GW{g2} {p3[top]['xp'][g2]}")
# rebuilt-ctx consistency (sanity of the harness itself)
check("E3b harness rebuild matches", abs(p_ref[top]["xp"][g2] - P0[top]["xp"][g2]) < 0.05, f"{p_ref[top]['xp'][g2]:.2f} vs {P0[top]['xp'][g2]:.2f}")

# E4 zero minutes all season
zero = [p for p in el if sum(s["minutes"] for s in C["pstats"].get(p, {}).values()) == 0 and el[p]["status"] == "a"]
mx = max(P0[p]["xp"][NXT] for p in zero)
check("E4 0-minute players project ~0", mx < 0.5, f"{len(zero)} available players with 0 minutes; max xP {mx:.2f}")

# E5 new signing: no minutes, no prior, at the strongest club (e.g. a big deadline-day buy)
c5 = copy.copy(C); c5["elements"] = dict(el); c5["priors"] = dict(C["priors"])
clone = dict(el[top], id=999999, web_name="NewSigning", chance_of_playing_next_round=None, status="a", news="", news_added=None, penalties_order=None)
c5["elements"][999999] = clone
r5 = proj(c5)["players"][999999]
check("E5 new signing with no data", r5["xp"][NXT] > 1.0, f"xP {r5['xp'][NXT]:.2f} (start chance {r5['p_start']}) - the model gives a new signing nothing until he has played")

# E6 suspensions and flags (availability table)
def av(e, k, ko=None): return availability(e, k, ko, return_date(e))
today = dt.date(2026, 10, 20)
e_ban2 = {"status": "s", "chance_of_playing_next_round": 0, "news": "Suspended until 3 Nov", "news_added": "2026-10-20T10:00:00Z"}
kos = [today + dt.timedelta(days=7 * k) for k in range(5)]
t = [av(e_ban2, k, kos[k]) for k in range(5)]
check("E6a dated ban uses the date", t == [0, 0, 1, 1, 1], f"{t}")
e_ban3 = {"status": "s", "chance_of_playing_next_round": 0, "news": "Suspended for three matches", "news_added": "2026-10-20T10:00:00Z"}
t = [av(e_ban3, k, kos[k]) for k in range(5)]
check("E6b undated 3-match ban", t[2] == 0, f"{t} - an undated ban is assumed over after 2 games")
for c in (75, 50, 25, 0):
    st = "d" if c else "i"
    e = {"status": st, "chance_of_playing_next_round": c, "news": "Knock", "news_added": "2026-10-20T10:00:00Z"}
    print(f"     flag {c:>3}% ({st}): k0-4 {[round(av(e, k), 2) for k in range(5)]}")
e_inone = {"status": "i", "chance_of_playing_next_round": None, "news": "Hamstring injury", "news_added": "2026-10-20T10:00:00Z"}
check("E6c injured with no chance value", av(e_inone, 0) == 0, f"k0 availability {av(e_inone, 0)} (FPL currently always sends 0 for status i)")
try:
    return_date({"news": "Expected back 30 Feb", "news_added": "2026-01-10T10:00:00Z"}); ok = True; d = "parsed"
except Exception as ex:
    ok = False; d = f"{type(ex).__name__}: {ex} - one malformed FPL note would crash build.py"
check("E6d impossible return date in news", ok, d)

# E7 keeper who lost his place: GKPs who started early and not in the last 2 club games
gk = []
for p, e in el.items():
    if e["element_type"] != 1: continue
    gs = C["pstats"].get(p, {})
    starts = [gs.get(g, {}).get("starts", 0) for g in range(1, NXT)]
    if sum(starts[:-2]) >= 3 and sum(starts[-2:]) == 0 and e["status"] == "a":
        gk.append((e["web_name"], starts, round(P0[p]["p_start"], 2), round(P0[p]["xp"][NXT], 2)))
check("E7 dropped keepers get low start chance", all(x[2] < 0.3 for x in gk), f"{gk}")

# E8 congestion week
c8 = copy.copy(C); c8["congestion"] = {(tid, NXT): 0.93}
r8 = proj(c8)["players"][top]["xp"][NXT]
check("E8 European week trims xP a little", 0.9 * P0[top]["xp"][NXT] <= r8 < P0[top]["xp"][NXT], f"{P0[top]['xp'][NXT]:.2f} -> {r8:.2f}")

# E9 fixtures with vs without their own betting odds (direct_w): size of the jump
p_no = project(C, NXT, 1, {"direct_w": 0.0})["players"]
diffs = sorted(((P0[p]["xp"][NXT] - p_no[p]["xp"][NXT]), el[p]["web_name"]) for p in P0 if P0[p]["xp"][NXT] > 2)
mad = sum(abs(d) for d, _ in diffs) / len(diffs)
has = sum(1 for m in C["market"] if m["gw"] == NXT); later = sum(1 for m in C["market"] if m["gw"] and m["gw"] > NXT)
check("E9 odds/no-odds discontinuity small", mad < 0.3, f"GW{NXT} fixtures with odds {has}, later GWs {later}; mean |change| for xP>2 players {mad:.2f}; extremes {diffs[0]} {diffs[-1]}")

# E10 mid-season PL transfer: xG credited to his new club's history (see leakage L2) and his minutes window
for name in ("Grealish", "Ndiaye"):
    p = next((i for i, e in el.items() if e["web_name"] == name), None)
    if p: print(f"     {name}: start chance {P0[p]['p_start']:.2f}, xP {P0[p]['xp'][NXT]:.2f}")
json.dump(R, open(out_path("edge.json"), "w"), indent=1)
print(f"{sum(r['ok'] for r in R)}/{len(R)} passed")
