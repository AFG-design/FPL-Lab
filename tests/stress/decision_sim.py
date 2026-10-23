#!/usr/bin/env python3
"""7. Decision quality: replay 2025/26 from GW4. Each week: project with data before that GW, run the optimiser
(5 GWs planned, week 1 executed), score with real points (auto-subs, vice if the captain doesn't play).
Strategies share the same GW4 squad (a GW4 wildcard from the model) so only in-season decisions differ.
Simplifications: no chips; FPL ep_next not available in the archive; EO = ownership (no captaincy data)."""
import csv, json, sys, time, math, statistics as stt
from collections import defaultdict
from common import *
from fplmodel import project, availability
import optimise

STRATS = sys.argv[1].split(",") if len(sys.argv) > 1 else ["balanced", "roll", "safe", "chase", "form", "template"]
A, TA = arch(); G0, G1, H = 4, 38, 5
price = defaultdict(dict); sel = defaultdict(dict)
for r in csv.DictReader(open("archive/2025-26/merged_gw.csv", encoding="utf-8", errors="ignore")):
    p, g = int(r["element"]), int(r["GW"])
    price[p][g] = float(r["value"]) / 10; sel[p][g] = float(r["selected"] or 0)
def px(p, g):
    d = price.get(p, {});
    if g in d: return d[g]
    b = [x for x in d if x <= g]; return d[max(b)] if b else (d[min(d)] if d else 4.5)
MANAGERS = 11.5e6
def mins(p, g): return A["pstats"].get(p, {}).get(g, {}).get("minutes", 0)
def pts(p, g): return A["pts_gw"].get(p, {}).get(g, 0)

_cache = {}
def week_inputs(k):
    """Projection-based optimiser inputs for week k (data before k only)."""
    if k in _cache: return _cache[k]
    cx = dict(A); cx["elements"] = {pid: dict(e, team=TA(pid, k) or e["team"]) for pid, e in A["elements"].items()}
    res = project(cx, k, H, {"use_flags": False, "sim": 600})["players"]
    POSN = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
    pl = {}
    for pid, r in res.items():
        e = cx["elements"][pid]
        if pid not in price: continue
        pl[pid] = {"pos": POSN[e["element_type"]], "team": e["team"], "price": px(pid, k), "xp": r["xp"],
                   "ok": r["p_start"] + r["p_sub"] > 0.05 and k in price[pid] or any(g in price[pid] for g in range(k, k + 2)),
                   "p10": {g: d["p10"] for g, d in r["dist"].items()},
                   "nailed": int(round(100 * r["p_start"] * min(1.0, r["m_start"] / 85)))}
    own = {pid: sel[pid].get(k, sel[pid].get(k - 1, 0)) / MANAGERS for pid in pl}
    _cache[k] = (pl, own); return _cache[k]

def proxy(pl, k, kind, own):
    q = {}
    for pid, p in pl.items():
        if kind == "form":
            prev = [pts(pid, g) for g in range(max(1, k - 4), k)]; v = sum(prev) / len(prev)
        else:  # template: maximise ownership (scaled to points-like size)
            v = 10 * own.get(pid, 0)
        q[pid] = dict(p, xp={g: (v if p["xp"].get(g, 0) > 0 else 0.0) for g in p["xp"]})
    return q

FORM_MIN = {"GKP": (1, 1), "DEF": (3, 5), "MID": (2, 5), "FWD": (1, 3)}
def score_week(xi, bench, cap, vice, g, pl):
    """Real points with FPL auto-subs."""
    xi = list(xi)
    cnt = lambda L: {k: sum(1 for i in L if pl[i]["pos"] == k) for k in FORM_MIN}
    for i in list(xi):
        if mins(i, g) > 0: continue
        for b in bench:
            if b in xi or mins(b, g) == 0: continue
            if (pl[i]["pos"] == "GKP") != (pl[b]["pos"] == "GKP"): continue
            t = [x for x in xi if x != i] + [b]; c = cnt(t)
            if all(FORM_MIN[k][0] <= c[k] <= FORM_MIN[k][1] for k in c):
                xi[xi.index(i)] = b; break
    c = cap if mins(cap, g) > 0 else vice
    return sum(pts(i, g) for i in xi) + (pts(c, g) if mins(c, g) > 0 else 0), cap if mins(cap, g) > 0 else vice

def sell_price(buy, now):
    return now if now <= buy else round(buy + math.floor((now - buy) * 10 / 2) / 10, 1)

def run(strategy, start):
    squad, bank, buy = list(start["squad"]), start["bank"], dict(start["buy"])
    ft, tot, hits_tot, log = 1, 0, 0, []
    for k in range(G0, G1 + 1):
        pl, own = week_inputs(k)
        for i in squad:
            if i not in pl:  # left the league: keep him as a dead slot
                pl = dict(pl); pl[i] = {"pos": start["pos"][i], "team": -i, "price": px(i, k), "xp": {}, "ok": False, "p10": {}, "nailed": 0}
        gws = [g for g in range(k, min(39, k + H))]
        opt = pl if strategy not in ("form", "template") else proxy(pl, k, strategy, own)
        kw = {}
        if strategy == "roll": kw["week1_moves"] = 0
        if strategy == "safe": kw.update(eo=own, lam=0.02, hit_margin=2.0, nail_w=0.5)
        if strategy == "chase": kw.update(eo=own, lam=-0.03, haul_w=10.0)
        sell = {i: sell_price(buy[i], px(i, k)) for i in squad}
        t0 = time.time()
        r = optimise.solve(opt, squad, sell, bank, min(ft, 5), gws, time_limit=25, **kw)
        if r is None:
            r = optimise.solve(opt, squad, sell, bank, min(ft, 5), gws, week1_moves=0, time_limit=25)
        w = r["weeks"][0]
        n = len(w["in"]); hits = max(0, n - ft)
        for o in w["out"]: bank += sell[o]; squad.remove(o)
        for i in w["in"]: bank -= px(i, k); squad.append(i); buy[i] = px(i, k)
        bank = round(bank, 1)
        ft = 1 if n > ft else min(5, ft - n + 1)
        # strategy XI/captain from the optimiser; for the proxies, captain/lineup by the model's projections
        if strategy in ("form", "template"):
            xi_r = optimise.solve(pl, squad, {i: 0 for i in squad}, 0, 1, [k], week1_moves=0, time_limit=10)["weeks"][0]
            xi, bench, cap, vice = xi_r["xi"], xi_r["bench"], xi_r["captain"], xi_r["vice"]
            if strategy == "template":
                cap = max(xi, key=lambda i: own.get(i, 0)); vice = sorted(xi, key=lambda i: -own.get(i, 0))[1]
        else:
            xi, bench, cap, vice = w["xi"], w["bench"], w["captain"], w["vice"]
        wp, eff_cap = score_week(xi, bench, cap, vice, k, pl)
        tot += wp - 4 * hits; hits_tot += hits
        best_cap = max(xi, key=lambda i: pts(i, k))
        log.append({"gw": k, "pts": wp, "hits": hits, "moves": n, "cap": eff_cap, "cap_pts": pts(eff_cap, k), "best_cap_pts": pts(best_cap, k),
                    "ft": ft, "bank": bank, "secs": round(time.time() - t0, 1)})
        print(f"{strategy:<9} GW{k:2d} pts {wp:3d} moves {n} hits {hits} cap {A['elements'][eff_cap]['web_name']:<12} {pts(eff_cap,k):2d} total {tot}", flush=True)
    wk = [x["pts"] - 4 * x["hits"] for x in log]
    return {"total": tot, "hits": hits_tot, "moves": sum(x["moves"] for x in log), "cap_hit": sum(1 for x in log if x["cap_pts"] >= x["best_cap_pts"]) / len(log),
            "cap_pts": sum(x["cap_pts"] for x in log), "sd_week": round(stt.pstdev(wk), 2), "log": log}

# common start: a GW4 wildcard from the model's projections, £100m
pl4, _ = week_inputs(G0)
wc = optimise.solve(pl4, [], {}, 100.0, 5, list(range(G0, G0 + H)), hit=0, ft_value=0, max_moves_week=15, freeze_after=1, time_limit=60)
sq0 = sorted(set(wc["weeks"][0]["xi"]) | set(wc["weeks"][0]["bench"]))
start = {"squad": sq0, "bank": round(100.0 - sum(px(i, G0) for i in sq0), 1), "buy": {i: px(i, G0) for i in sq0}, "pos": {i: pl4[i]["pos"] for i in sq0}}
print("GW4 squad:", [A["elements"][i]["web_name"] for i in sq0], "bank", start["bank"])
results = {}
for s in STRATS:
    results[s] = run(s, start)
    print(f"== {s}: total {results[s]['total']} hits {results[s]['hits']} moves {results[s]['moves']} captain best-in-XI {results[s]['cap_hit']:.0%} weekly SD {results[s]['sd_week']}")
    json.dump({"start": [A["elements"][i]["web_name"] for i in sq0], "results": results}, open(out_path(f"decision_sim_{'_'.join(STRATS)}.json"), "w"), indent=1)
