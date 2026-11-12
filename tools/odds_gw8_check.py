# Research only: the 26 Oct 2026 GW8 player-odds check (see docs/odds-log.md), kept for the FL-021 re-test. Not part of the app.
import json, math, sys, statistics as st
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from odds_players import load_json, snapshots
import bench
from fplmodel import project, POS
ctx = bench.current_ctx()
res = project(ctx, 8, 1, {"use_flags": False})
P = res["players"]; up = res["upcoming"]; el = ctx["elements"]; sc = ctx["scoring"]
live = json.load(open("history/proj_gw8.json"))["players"]          # pre-deadline: [FPL Lab xP, FPL ep]
# Explicit checkpoint: never silently substitute an early snapshot for deadline odds.
snaps = snapshots(load_json(ROOT / "history/player_odds_gw8.json"))
odds = snaps["legacy" if "legacy" in snaps else "3"]["fixtures"]
act = {e["id"]: e["stats"]["total_points"] for e in json.load(open("raw/live8.json"))["elements"]}
mins8 = {e["id"]: e["stats"]["minutes"] for e in json.load(open("raw/live8.json"))["elements"]}
SLOPE = 0.86
# odds-implied goals/assists per player (team-normalised), keyed by pid
og, oa = {}, {}
for f in odds.values():
    for tid in (f["h"], f["a"]):
        tf = up[tid].get(8, [])
        if not tf: continue
        mu = tf[0][2]
        pl = [(int(p), v) for p, v in f["players"].items() if int(p) in P and el[int(p)]["team"] == tid and "p_score" in v]
        # appearance: model chance, gated by the live pre-deadline projection (0 = flagged out at the deadline)
        pa = {p: min(1.0, P[p]["p_start"] + P[p]["p_sub"]) * (1.0 if live.get(str(p), [0])[0] > 0 else 0.0) for p, _ in pl}
        lam = {p: -math.log(1 - v["p_score"]) for p, v in pl}
        tot = sum(lam[p] * pa[p] for p, _ in pl)
        # Legacy p_assist was mixed raw/fair; this research rescaling treats it as margin-bearing.
        lama = {p: -math.log(1 - v.get("p_assist_raw", v.get("p_assist"))) for p, v in pl if v.get("p_assist_raw", v.get("p_assist"))}
        tota = sum(lama[p] * pa[p] for p in lama)
        for p, _ in pl:
            if tot: og[p] = mu * 0.97 / tot * lam[p] * pa[p]
            if tota and p in lama: oa[p] = mu * 0.75 / tota * lama[p] * pa[p]
def blended(p, w):
    base = live[str(p)][0]
    if p not in og or p not in P: return base
    pos = POS[el[p]["element_type"]]; d = P[p]["detail"][8]
    gm = d.get("goals", 0) / sc["goals_scored"][pos]; am = d.get("assists", 0) / sc["assists"]
    return max(0.0, base + SLOPE * w * ((og[p] - gm) * sc["goals_scored"][pos] + (oa.get(p, am) - am) * sc["assists"]))
pool = [p for p in P if str(p) in live and p in act and any(ctx["pstats"].get(p, {}).get(g, {}).get("minutes", 0) > 0 for g in (5, 6, 7))]
def corr(a, b):
    ma, mb = st.mean(a), st.mean(b)
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
def ranks(v):
    o = sorted(range(len(v)), key=lambda i: v[i]); r = [0] * len(v)
    for k, i in enumerate(o): r[i] = k
    return r
def score(pred, label):
    pr = [pred(p) for p in pool]; ac = [act[p] for p in pool]
    order = sorted(pool, key=lambda p: -pred(p))
    cap = order[0]
    print(f"{label:16} MAE {st.mean(abs(a-b) for a,b in zip(pr,ac)):.3f} corr {corr(pr,ac):.3f} rank {corr(ranks(pr),ranks(ac)):.3f} bias {st.mean(pr)-st.mean(ac):+.2f} | top5 {st.mean(act[p] for p in order[:5]):.1f} top10 {st.mean(act[p] for p in order[:10]):.1f} | cap {el[cap]['web_name']} {act[cap]}")
print(f"pool: {len(pool)} players who played in GW5-7; {sum(1 for p in pool if p in og)} priced by bookmakers")
for w in (0, 0.25, 0.5, 0.75, 1.0): score(lambda p, w=w: blended(p, w), f"FPL Lab +odds {int(w*100)}%" if w else "FPL Lab (live)")
score(lambda p: live[str(p)][1], "FPL ep_next")
# priced attackers only (where the odds act)
att = [p for p in pool if p in og and POS[el[p]["element_type"]] in ("MID", "FWD")]
pool_all = pool; pool = att
print(f"-- priced MID/FWD only ({len(att)}) --")
for w in (0, 0.5, 1.0): score(lambda p, w=w: blended(p, w), f"FPL Lab +odds {int(w*100)}%" if w else "FPL Lab (live)")
pool = pool_all
mine = ["Raya","Konsa","Calafiori","Hall","Palmer","Rogers","Groß","Gibbs-White","Haaland","Calvert-Lewin","João Pedro","Dubravka","van Ewijk","De Cuyper","Slater"]
name = {p: el[p]["web_name"] for p in el}
print("-- your squad: live xP / +50% odds / FPL ep / actual (mins) --")
for p in sorted([p for p in el if name[p] in mine and str(p) in live], key=lambda p: -live[str(p)][0]):
    print(f"  {name[p]:14} {live[str(p)][0]:5.2f} {blended(p,0.5):5.2f} {live[str(p)][1]:5.1f}  {act.get(p)} ({mins8.get(p)})")
