"""Adversarial hunt: players/archetypes the projection model systematically misreads.
Run: python3 tests/stress/adversarial.py   (writes tests/stress/out/adversarial.json)"""
import json, math, random
from collections import defaultdict
import numpy as np, pandas as pd
from common import *

random.seed(1); rng = np.random.default_rng(1)
A, TA = arch(); C = cur_ctx()
RA = run_ctx(A, range(4, 39), team_at=TA)
RC = run_ctx(C, range(3, 8))

def flat(R):
    return [(g, pid, pos, p, a) for g, rows in R.items() for pid, pos, p, a in rows]

def ms(res):
    res = np.asarray(res, float); n = len(res)
    if n < 2: return {"n": n, "bias": None, "se": None}
    return {"n": n, "bias": round(float(res.mean()), 3), "se": round(float(res.std(ddof=1) / math.sqrt(n)), 3)}

def cl(rows, ids):
    """mean residual (actual-pred) with player-clustered SE."""
    r = [(pid, a - p) for g, pid, pos, p, a in rows if pid in ids]
    if len(r) < 5: return {"n": len(r), "players": 0, "bias": None, "se": None, "se_cl": None}
    res = np.array([x[1] for x in r]); n = len(res); m = res.mean()
    d = defaultdict(float)
    for pid, x in r: d[pid] += x - m
    se_cl = math.sqrt(sum(v * v for v in d.values())) / n
    return {"n": n, "players": len(d), "bias": round(float(m), 3),
            "se": round(float(res.std(ddof=1) / math.sqrt(n)), 3), "se_cl": round(se_cl, 3)}

# ---------------- Task 1: per-player residuals
FA, FC = flat(RA), flat(RC)
def player_t(rows, minn):
    d = defaultdict(list)
    for g, pid, pos, p, a in rows: d[pid].append(a - p)
    out = {}
    for pid, r in d.items():
        if len(r) >= minn:
            r = np.array(r); se = r.std(ddof=1) / math.sqrt(len(r))
            out[pid] = (len(r), r.mean(), se, r.mean() / se if se > 0 else 0)
    return out
names = {pid: e["web_name"] for pid, e in A["elements"].items()}
PT = player_t(FA, 10)
elig = {k: v for k, v in PT.items() if v[0] >= 15}
def show(items): return [{"player": names[k], "id": k, "n": v[0], "bias": round(v[1], 2), "se": round(v[2], 2), "t": round(v[3], 2)} for k, v in items]
under = sorted([x for x in elig.items() if abs(x[1][3]) > 2 and x[1][3] > 0], key=lambda x: -x[1][3])[:15]
over = sorted([x for x in elig.items() if abs(x[1][3]) > 2 and x[1][3] < 0], key=lambda x: x[1][3])[:15]
obs_n = sum(1 for v in elig.values() if abs(v[3]) > 2)
obs_pos = sum(1 for v in elig.values() if v[3] > 2); obs_neg = obs_n - obs_pos
# permutation null: shuffle residuals across rows within (pos, pred-decile) strata, keep each player's row count
arr = pd.DataFrame(FA, columns=["g", "pid", "pos", "p", "a"]); arr["r"] = arr.a - arr.p
arr["bin"] = arr.groupby("pos").p.transform(lambda s: pd.qcut(s.rank(method="first"), 5, labels=False))
cnts = []; 
groups = [ix.values for _, ix in arr.groupby(["pos", "bin"]).groupby if False] if False else [g.index.values for _, g in arr.groupby(["pos", "bin"])]
pidv = arr.pid.values; rv = arr.r.values
for _ in range(500):
    sh = rv.copy()
    for ix in groups: sh[ix] = rng.permutation(rv[ix])
    df = pd.DataFrame({"pid": pidv, "r": sh}).groupby("pid").r.agg(["mean", "std", "count"])
    df = df[df["count"] >= 15]; t = df["mean"] / (df["std"] / np.sqrt(df["count"]))
    cnts.append(int((t.abs() > 2).sum()))
# sign-flip null
sf = []
for _ in range(500):
    sh = rv * rng.choice([-1, 1], size=len(rv))
    df = pd.DataFrame({"pid": pidv, "r": sh}).groupby("pid").r.agg(["mean", "std", "count"])
    df = df[df["count"] >= 15]; t = df["mean"] / (df["std"] / np.sqrt(df["count"]))
    sf.append(int((t.abs() > 2).sum()))
# split-half persistence of player residual
h1 = arr[arr.g <= 20].groupby("pid").r.agg(["mean", "count"]); h2 = arr[arr.g > 20].groupby("pid").r.agg(["mean", "count"])
j = h1.join(h2, lsuffix="1", rsuffix="2", how="inner"); j = j[(j.count1 >= 8) & (j.count2 >= 8)]
pcorr = float(np.corrcoef(j.mean1, j.mean2)[0, 1])
# repeat-flagged: those |t|>2 in H1 -- bias in H2?
t1 = {k: v for k, v in player_t([x for x in FA if x[0] <= 20], 8).items()}
flag1 = [k for k, v in t1.items() if abs(v[3]) > 2 and k in h2.index and h2.loc[k, "count"] >= 8]
flag_h2 = np.mean([np.sign(t1[k][3]) * h2.loc[k, "mean"] for k in flag1]) if flag1 else None
haal = [k for k, e in A["elements"].items() if e["web_name"] == "Haaland"]
T1 = {"n_players_ge15": len(elig), "n_abs_t_gt2": obs_n, "n_under": obs_pos, "n_over": obs_neg,
      "null_perm_mean": float(np.mean(cnts)), "null_perm_p95": float(np.percentile(cnts, 95)),
      "null_signflip_mean": float(np.mean(sf)), "null_signflip_p95": float(np.percentile(sf, 95)),
      "p_value_perm": float(np.mean([c >= obs_n for c in cnts])),
      "halves_corr_player_resid": round(pcorr, 3), "halves_n": int(len(j)),
      "flagged_H1_n": len(flag1), "flagged_H1_mean_signed_resid_in_H2": None if flag_h2 is None else round(float(flag_h2), 2),
      "most_under": show(under), "most_over": show(over),
      "haaland": show([(k, PT[k]) for k in haal if k in PT])}

# ---------------- Archetype definitions
raw = pd.read_csv("archive/2025-26/players_raw.csv").set_index("id")
bs = json.load(open("raw/bootstrap.json"))["elements"]; bc = pd.DataFrame(bs).set_index("id")
def rank1(df, cols):
    s = set()
    for c in cols: s |= set(df.index[df[c] == 1])
    return s
def group_defs(df, ctx, minmins, nfinal):
    pos = {pid: e["element_type"] for pid, e in ctx["elements"].items()}
    G = {}
    G["set_piece (corner/IFK/DFK order==1)"] = rank1(df, ["corners_and_indirect_freekicks_order", "direct_freekicks_order"])
    G["  corners/IFK taker only"] = rank1(df, ["corners_and_indirect_freekicks_order"])
    G["  direct FK taker only"] = rank1(df, ["direct_freekicks_order"])
    G["penalty takers (order==1)"] = rank1(df, ["penalties_order"])
    G["penalty takers, mid/fwd only"] = {p for p in G["penalty takers (order==1)"] if pos.get(p) in (3, 4)}
    d = df[(df.element_type == 2) & (df.minutes >= minmins)]
    G["box defenders (DEF xG/90 > median)"] = set(d.index[d.expected_goals_per_90 > d.expected_goals_per_90.median()])
    G["  DEF xG/90 <= median"] = set(d.index[d.expected_goals_per_90 <= d.expected_goals_per_90.median()])
    # rotation clubs
    mins = defaultdict(lambda: defaultdict(int)); nm = max(max(v) for v in ctx["pstats"].values())
    played = max((g for v in ctx["pstats"].values() for g, s in v.items() if s["minutes"] > 0), default=1)
    for pid, e in ctx["elements"].items():
        mins[e["team"]][pid] = sum(s["minutes"] for s in ctx["pstats"].get(pid, {}).values())
    rate = {}
    for t, d_ in mins.items():
        top = sorted(d_.items(), key=lambda x: -x[1])[:13]
        rate[t] = np.mean([sum(s["starts"] for s in ctx["pstats"][p].values()) / played for p, _ in top])
    low = sorted(rate, key=rate.get)[:5]
    G["rotation-heavy clubs (5 lowest regular start-rate)"] = {p for p, e in ctx["elements"].items() if e["team"] in low}
    G["  non-rotation clubs"] = {p for p, e in ctx["elements"].items() if e["team"] not in low}
    G["cheap enablers (now_cost < 4.5)"] = set(df.index[df.now_cost < 45]) & set(ctx["elements"])
    G["cheap MID/FWD < 6.0"] = {p for p in df.index[df.now_cost < 60] if pos.get(p) in (3, 4)}
    return G, {t: round(float(rate[t]), 3) for t in low}
GA, lowA = group_defs(raw, A, 900, 38)
GC, lowC = group_defs(bc, C, 250, 7)

def pred_filter(rows, lo, hi=99): return [r for r in rows if lo <= r[3] < hi]
results = {}
for name in GA:
    r = {"def_note": "end-of-season labels (archetype defined with hindsight)"}
    for tag, rows, G in (("2025/26", FA, GA), ("2026/27", FC, GC)):
        ids = G.get(name, set())
        r[tag] = {"all": cl(rows, ids), "pred>=4": cl(pred_filter(rows, 4), ids),
                  "players": len(ids & {x[1] for x in rows})}
    results[name] = r
# elite attackers & pred bins (pred-defined)
for tag, rows in (("2025/26", FA), ("2026/27", FC)):
    for nm, lo, hi in (("elite (pred>=6)", 6, 99), ("pred 4-6", 4, 6), ("pred 2-4", 2, 4), ("pred <2", -9, 2)):
        sub = pred_filter(rows, lo, hi)
        results.setdefault(nm, {"def_note": "ex-ante by prediction"})[tag] = {"all": ms([a - p for g, pid, pos, p, a in sub]),
            "pred>=4": ms([a - p for g, pid, pos, p, a in sub if p >= 4])}
# elite by position
for pn in ("GKP", "DEF", "MID", "FWD"):
    for tag, rows in (("2025/26", FA), ("2026/27", FC)):
        results.setdefault(f"pred>=4, pos {pn}", {"def_note": "ex-ante"})[tag] = {"all": ms([a - p for g, pid, pos, p, a in rows if pos == pn and p >= 4])}
# Haaland-type: pred>=6 and excluding top 1 player
# ---------------- Task 3: split-half persistence
def half(rows, ids, lo, hi, thr):
    return cl([r for r in rows if lo <= r[0] <= hi and r[3] >= thr], ids)
persist = {}
for name in GA:
    ids = GA[name]
    persist[name] = {"H1 (GW4-20) all": half(FA, ids, 4, 20, -9), "H2 (GW21-38) all": half(FA, ids, 21, 38, -9),
                     "H1 pred>=4": half(FA, ids, 4, 20, 4), "H2 pred>=4": half(FA, ids, 21, 38, 4)}
for nm, lo in (("elite (pred>=6)", 6),):
    sel = lambda rows, a, b: ms([x[4] - x[3] for x in rows if a <= x[0] <= b and x[3] >= lo])
    persist[nm] = {"H1 (GW4-20) all": sel(FA, 4, 20), "H2 (GW21-38) all": sel(FA, 21, 38)}
# carry-over: 2025/26 bias -> 2026/27
for name in GA:
    persist[name]["2026/27 (GW3-7) all"] = results[name]["2026/27"]["all"]
# ---------------- Task 4: decision impact
def decision(R, ids, pidpos):
    top5n = top5g = capn = weeks = 0; capgaps = []; allgaps = []; slot_res = []; swap = []
    for g, rows in R.items():
        if not rows: continue
        weeks += 1
        s = sorted(rows, key=lambda r: -r[2])
        t5 = s[:5]; gi = [r for r in t5 if r[0] in ids]
        top5n += len(gi); top5g += 1 if gi else 0
        slot_res += [r[3] - r[2] for r in gi]
        allgaps.append(s[0][3] - s[1][3])
        if s[0][0] in ids:
            capn += 1; capgaps.append(s[0][3] - s[1][3])
        # swap test: group member in top5 vs best non-group in ranks 6-10
        nong = [r for r in s[5:12] if r[0] not in ids]
        if gi and nong: swap.append(np.mean([r[3] for r in gi]) - np.mean([r[3] for r in nong[:3]]))
    f = lambda x: None if not len(x) else round(float(np.mean(x)), 2)
    return {"weeks": weeks, "top5_slots": top5n, "top5_slots_per_week": round(top5n / max(weeks, 1), 2),
            "weeks_with_member_in_top5": top5g, "captain_weeks": capn,
            "captain_gap_vs_2nd_actual (group captain weeks)": f(capgaps),
            "captain_gap_vs_2nd_actual (all weeks)": f(allgaps),
            "slot_bias_actual_minus_pred": f(slot_res), "slot_bias_se": round(float(np.std(slot_res, ddof=1) / math.sqrt(len(slot_res))), 2) if len(slot_res) > 2 else None,
            "top5_member_minus_ranks6-12_nongroup_actual": f(swap), "swap_weeks": len(swap)}
dec = {}
for name in GA:
    dec[name] = {"2025/26": decision(RA, GA[name], None), "2026/27": decision(RC, GC.get(name, set()), None)}
# per-player decision view of Haaland & others top-captains
cap_counts = defaultdict(lambda: [0, 0.0, 0.0]); 
for g, rows in RA.items():
    s = sorted(rows, key=lambda r: -r[2]); c = cap_counts[names[s[0][0]]]; c[0] += 1; c[1] += s[0][3] - s[0][2]; c[2] += s[0][3] - s[1][3]
caps = sorted(([k, v[0], round(v[1] / v[0], 2), round(v[2] / v[0], 2)] for k, v in cap_counts.items()), key=lambda x: -x[1])[:8]

out = {"task1": T1, "archetypes": results, "persistence": persist, "decision": dec,
       "captain_picks_2025_26 [player, weeks, mean(actual-pred), mean gap vs 2nd]": caps,
       "rotation_clubs_lowest_regular_start_rate": {"2025/26": lowA, "2026/27": lowC}}
json.dump(out, open(out_path("adversarial.json"), "w"), indent=1, default=float)
print(json.dumps(T1, indent=0, default=float)[:3500])
for n, r in results.items():
    print(f"{n:55s}", " | ".join(f"{t} all {r[t]['all'].get('bias')}±{r[t]['all'].get('se_cl', r[t]['all'].get('se'))} (n={r[t]['all']['n']}) p4 {r[t].get('pred>=4',{}).get('bias')}±{r[t].get('pred>=4',{}).get('se_cl', r[t].get('pred>=4',{}).get('se'))} (n={r[t].get('pred>=4',{}).get('n')})" for t in ("2025/26", "2026/27")))
print(); 
for n, r in persist.items(): print(n, {k: (v.get("bias"), v.get("se_cl", v.get("se"))) for k, v in r.items()})
print()
for n, r in dec.items(): print(n, r["2025/26"], r["2026/27"]["top5_slots"], r["2026/27"]["slot_bias_actual_minus_pred"])
print(caps, lowA, lowC)
