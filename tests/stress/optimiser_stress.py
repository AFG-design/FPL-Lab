#!/usr/bin/env python3
"""Optimiser stress test (tasks A-G). Writes tests/stress/out/optimiser.json.
Read-only on optimise.py / build.py / site/. Node is used for site/plan-solver.js and site/js/core/{model,plan}.js."""
import sys, os, re, json, time, copy, subprocess, itertools, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import pulp
import optimise
from opt_inputs import build, crowd_eo

HERE = os.path.dirname(os.path.abspath(__file__))
R = {}
JS_POOL = {"GKP": 10, "DEF": 26, "MID": 30, "FWD": 16}
PY_POOL = dict(optimise.POOL)

C, PL, SQUAD, SELL, BANK, GWS = build()
EO_FRAC, EO_PCT = crowd_eo()
EL = C["elements"]
NAME = lambda i: EL[i]["web_name"]
R["A_input"] = {"gws": GWS, "squad": [NAME(i) for i in SQUAD], "squad_value": round(sum(PL[i]["price"] for i in SQUAD), 1), "bank": BANK,
                "players": len(PL), "not_ok": sum(1 for p in PL.values() if not p["ok"])}
print("input", R["A_input"])

# ------------------------------------------------------------------ rule validator (independent of the solver)
def validate(res, players=PL, squad=SQUAD, sell=SELL, bank=BANK, ft0=1, locked=(), banned=(), max_moves=4, label=""):
    """Replay a returned plan against FPL rules. Returns list of issues (empty = legal)."""
    iss = []
    cur = list(squad); bought = set(); bk = bank; ft = ft0
    for wk in res["weeks"]:
        g = wk["gw"]
        for o in wk["out"]:
            if o not in cur: iss.append(f"GW{g}: sells {o} not in squad"); continue
            cur.remove(o)
            bk += sell[o] if (o in sell and o not in bought) else players[o]["price"]
        for i in wk["in"]:
            if i in cur: iss.append(f"GW{g}: buys {i} already owned")
            cur.append(i); bought.add(i); bk -= players[i]["price"]
            if not players[i]["ok"]: iss.append(f"GW{g}: buys non-ok {NAME(i)}")
        bk = round(bk, 1)
        n = len(wk["in"])
        if n != len(wk["out"]): iss.append(f"GW{g}: in/out mismatch")
        if len(cur) != 15 or len(set(cur)) != 15: iss.append(f"GW{g}: squad size {len(cur)}")
        pos = {}
        for i in cur: pos[players[i]["pos"]] = pos.get(players[i]["pos"], 0) + 1
        if pos != optimise.SHAPE: iss.append(f"GW{g}: shape {pos}")
        clubs = {}
        for i in cur: clubs[players[i]["team"]] = clubs.get(players[i]["team"], 0) + 1
        if any(v > 3 for v in clubs.values()): iss.append(f"GW{g}: >3 per club {clubs}")
        if bk < -1e-6: iss.append(f"GW{g}: bank {bk} < 0")
        if abs(bk - wk["bank"]) > 0.051: iss.append(f"GW{g}: solver bank {wk['bank']} vs replay {bk}")
        xi = wk["xi"]
        if len(xi) != 11 or not set(xi) <= set(cur): iss.append(f"GW{g}: XI not 11 squad players")
        xp_ = {}
        for i in xi: xp_[players[i]["pos"]] = xp_.get(players[i]["pos"], 0) + 1
        for p_ in optimise.XI_MIN:
            if not optimise.XI_MIN[p_] <= xp_.get(p_, 0) <= optimise.XI_MAX[p_]: iss.append(f"GW{g}: formation {xp_}")
        if wk["captain"] not in xi: iss.append(f"GW{g}: captain not in XI")
        if n > max_moves: iss.append(f"GW{g}: {n} moves > {max_moves}")
        if wk["ft"] != ft: iss.append(f"GW{g}: ft {wk['ft']} != rule {ft}")
        need = max(0, n - ft)
        if wk["hits"] != need: iss.append(f"GW{g}: hits {wk['hits']} != rule {need} (n={n}, ft={ft})")
        ft = min(5, max(0, ft - n) + 1)
        for b in banned:
            if b in cur: iss.append(f"GW{g}: banned {NAME(b)} in squad")
        for l in locked:
            if l not in cur: iss.append(f"GW{g}: locked {NAME(l)} missing")
    if "ft_left" in res and res["ft_left"] != ft: iss.append(f"ft_left {res['ft_left']} != rule {ft}")
    return iss

def run(label, **kw):
    """solve() wrapper: never lets an exception escape; records what came back and validates any plan."""
    a = dict(players=PL, squad=SQUAD, sell=SELL, bank=BANK, ft0=1, gws=GWS)
    a.update(kw)
    t = time.time(); rec = {"label": label}
    try:
        res = optimise.solve(a.pop("players"), a.pop("squad"), a.pop("sell"), a.pop("bank"), a.pop("ft0"), a.pop("gws"), **a)
        rec["returned"] = "None" if res is None else "plan"
        if res is not None:
            rec["xp_total"] = res["xp_total"]
    except BaseException as e:
        res = None; rec["returned"] = "EXCEPTION " + type(e).__name__; rec["error"] = str(e)[:200]
    rec["secs"] = round(time.time() - t, 2)
    return res, rec

# ------------------------------------------------------------------ B. hostile inputs
B = []
def case_B(label, res_rec, **vkw):
    res, rec = res_rec
    if res is not None:
        rec["issues"] = validate(res, **vkw)
        rec["verdict"] = "PLAN BREAKS RULES" if rec["issues"] else "legal plan returned"
    else:
        rec["verdict"] = "clean failure" if rec["returned"] == "None" else rec["returned"]
    B.append(rec); print("B", label, "->", rec["verdict"], rec.get("issues", "")[:3] if rec.get("issues") else "")

HAL, PAL = 411, 154
case_B("lock+ban same player (in squad)", run("lock+ban same player (in squad: Haaland)", locked=[HAL], banned=[HAL]), locked=[HAL], banned=[HAL])
cheap_out = min((i for i, p in PL.items() if p["ok"] and i not in SQUAD and p["pos"] == "MID"), key=lambda i: PL[i]["price"])
case_B("lock+ban same (outside squad)", run("lock+ban same player (outside squad)", locked=[cheap_out], banned=[cheap_out]), locked=[cheap_out], banned=[cheap_out])
# 4 locked from one club: Chelsea (team 6) already has 3 in the squad (Rogers? Palmer, Joao Pedro); lock a 4th
club6 = [i for i in SQUAD if PL[i]["team"] == 6]
fourth = max((i for i, p in PL.items() if p["team"] == 6 and i not in SQUAD and p["ok"]), key=lambda i: sum(PL[i]["xp"].values()))
locks4 = club6 + [fourth]
case_B("4 locked one club", run("4 locked players from one club (team 6)", locked=locks4), locked=locks4)
# 4 locked of one club, none in the squad
free_club = {}
for i, p in PL.items():
    if p["ok"] and i not in SQUAD: free_club.setdefault(p["team"], []).append(i)
tc = next(t for t, v in free_club.items() if t not in {PL[i]["team"] for i in SQUAD} and len(v) >= 4)
l4b = sorted(free_club[tc], key=lambda i: -sum(PL[i]["xp"].values()))[:4]
case_B("4 locked one club (none owned)", run("4 locked from one club, none owned", locked=l4b), locked=l4b)
# bank illegal
case_B("bank -15", run("bank = -15.0 (illegal start, can be repaired by selling)", bank=-15.0), bank=-15.0)
case_B("bank -60", run("bank = -60 (cannot be repaired)", bank=-60.0), bank=-60.0)
# locked premium squad above budget: top-priced legal 15 (2/5/5/3, <=3 per club)
prem, clubs_ = [], {}
for pos, n in optimise.SHAPE.items():
    for i in sorted((i for i, p in PL.items() if p["pos"] == pos and p["ok"]), key=lambda i: -PL[i]["price"]):
        if sum(1 for j in prem if j in PL and PL[j]["pos"] == pos) >= n: break
        if clubs_.get(PL[i]["team"], 0) >= 3: continue
        prem.append(i); clubs_[PL[i]["team"]] = clubs_.get(PL[i]["team"], 0) + 1
prem_val = round(sum(PL[i]["price"] for i in prem), 1)
rec = run(f"locked 15 most expensive players (value {prem_val}m, bank 0.5)", locked=prem)
case_B("locked premium squad", rec, locked=prem)
rec[0] and None
# locked a player who is not ok and not owned
notok = max((i for i, p in PL.items() if not p["ok"] and i not in SQUAD), key=lambda i: PL[i]["price"])
case_B("lock non-ok (not owned)", run(f"locked non-ok player not owned ({NAME(notok)}, status {EL[notok]['status']})", locked=[notok]), locked=[notok])
# locked non-ok player who IS owned: legitimate
SQ2 = list(SQUAD); PL2 = copy.deepcopy(PL); PL2[346]["ok"] = False
case_B("lock non-ok (owned)", run("locked non-ok player already owned (should be a legal hold)", players=PL2, locked=[346]), players=PL2, locked=[346])
# banned owned non-ok
case_B("ban owned player", run("banned an owned player (forced sale)", banned=[PAL]), banned=[PAL])
# extras
lockpool = min((i for i, p in PL.items() if p["ok"] and i not in SQUAD and p["pos"] == "MID" and sum(p["xp"].values()) < 1), key=lambda i: PL[i]["price"], default=None)
rec = run("locked cheap low-xP ok player outside the candidate pool", locked=[lockpool])
if rec[0] is not None:
    held = [any(lockpool in (w["xi"] + w["bench"]) for w in rec[0]["weeks"][k:k + 1]) for k in range(len(GWS))]
    rec[1]["locked_player_held_each_week"] = held
    rec[1]["note"] = "if any False the lock was silently ignored"
case_B("lock outside pool", rec, locked=[lockpool])
case_B("week1_moves=5", run("week1_moves=5 (> max_moves_week 4)", week1_moves=5))
case_B("ft0=7", run("ft0=7 (above FPL cap)", ft0=7))
case_B("ft0=-1", run("ft0=-1", ft0=-1))
case_B("squad id missing from players", run("squad contains id missing from players dict", squad=SQUAD[:14] + [99999], sell=SELL))
case_B("14-man squad", run("14-player squad (one slot empty)", squad=SQUAD[:14]), squad=SQUAD[:14])
case_B("duplicate squad id", run("duplicate id in squad list", squad=SQUAD[:14] + [SQUAD[0]]), squad=SQUAD[:14] + [SQUAD[0]])
case_B("empty gws", run("empty gws list", gws=[]))
case_B("time_limit=0", run("time_limit=0 (no time to find an incumbent)", time_limit=0))
case_B("max_moves_week=0 + week1_moves=1", run("max_moves_week=0 with week1_moves=1", max_moves_week=0, week1_moves=1))
R["B_hostile"] = B

# ------------------------------------------------------------------ C. free-transfer rules
def ft_rule(ft, n): return min(5, max(0, ft - n) + 1)
C_rows, C_bad = [], 0
for ft0 in (0, 1, 2, 5):
    for n1 in (0, 1, 2, 3, 4):
        res, rec = run(f"ft0={ft0} w1={n1}", ft0=ft0, week1_moves=n1)
        row = {"ft0": ft0, "week1_moves": n1, "returned": rec["returned"]}
        if res:
            ft = ft0; per = []
            for wk in res["weeks"]:
                n = len(wk["in"]); exp_h = max(0, n - ft)
                per.append({"gw": wk["gw"], "ft": wk["ft"], "n": n, "hits": wk["hits"], "rule_ft": ft, "rule_hits": exp_h})
                ft = ft_rule(ft, n)
            row["weeks"] = per
            row["ft_left"] = res["ft_left"]; row["rule_ft_left"] = ft
            row["issues"] = validate(res, ft0=ft0)
            row["mismatch"] = bool(row["issues"])
            C_bad += row["mismatch"]
        C_rows.append(row)
print("C grid mismatches:", C_bad, "of", len(C_rows))
R["C_ft_grid"] = {"runs": len(C_rows), "mismatches": C_bad, "rows": C_rows}
# the specific example: ft=2, 4 moves -> hits 2, next ft must be 1
res, rec = run("ft2 4moves", ft0=2, week1_moves=4)
R["C_example_ft2_4moves"] = {"weeks": [{k: w[k] for k in ("gw", "ft", "hits")} | {"n": len(w["in"])} for w in res["weeks"]], "issues": validate(res, ft0=2)} if res else None
# can hits inflate FTs? give FTs an inflated value and see whether the solver buys FTs with spare 'hits'
infl = []
for fv in (1.5, 3.9, 4.1, 6, 10):
    res, rec = run(f"ft_value={fv}", ft0=1, ft_value=fv)
    if res:
        issues = validate(res, ft0=1)
        infl.append({"ft_value": fv, "hits": [w["hits"] for w in res["weeks"]], "moves": [len(w["in"]) for w in res["weeks"]],
                     "ft": [w["ft"] for w in res["weeks"]], "ft_left": res["ft_left"], "rule_violations": issues})
R["C_ft_value_exploit"] = infl
# cap: starting from 5 with no moves
res, rec = run("ft5 no moves", ft0=5, week1_moves=0)
R["C_ft5_cap"] = [w["ft"] for w in res["weeks"]] + [res["ft_left"]] if res else None

# ------------------------------------------------------------------ D. selling prices / bank accounting
# build a sell map with profits like a real account: bought lower, sale price = buy + (now-buy)//2 (tenths)
def fpl_sell(now, buy): return now if now <= buy else buy + (now - buy) // 2
bought_at = {i: int(round(PL[i]["price"] * 10)) - (EL[i]["cost_change_start"] if EL[i]["cost_change_start"] > 0 else 0) for i in SQUAD}
SELL_P = {i: fpl_sell(int(round(PL[i]["price"] * 10)), bought_at[i]) / 10 for i in SQUAD}
D_out = {"profit_players": {NAME(i): {"now": PL[i]["price"], "bought": bought_at[i] / 10, "sell": SELL_P[i]} for i in SQUAD if SELL_P[i] < PL[i]["price"]}}
# 1: forced sale of profit players by banning them; solver bank vs independent replay
for lab, ban in (("ban Haaland (profit 0.2)", [411]), ("ban Palmer+Rogers+Groß", [154, 40, 124])):
    res, rec = run(lab, sell=SELL_P, banned=ban, ft0=3)
    if res:
        D_out[lab] = {"issues": validate(res, sell=SELL_P, ft0=3, banned=ban), "bank": [w["bank"] for w in res["weeks"]],
                      "moves": [[(NAME(o), NAME(i)) for o, i in zip(w["out"], w["in"])] for w in res["weeks"]]}
# 2: sell-in-plan: buy X in week 1, solver must sell X later at price. Force by banning the owned player at week>=? -> use
# lock of a bought player then ban is impossible, so instead replay explicit move chains with both accounting rules.
def bank_optimiser(moves, sell=SELL_P, bank=BANK, players=PL):
    """optimise.py: every 'out' sells at sp[i] = sell[i] if i in sell else price; every 'in' buys at price."""
    b = bank; res = []
    for g in GWS:
        for m in [m for m in moves if m["gw"] == g]:
            b += sell[m["out"]] if m["out"] in sell else players[m["out"]]["price"]
            b -= players[m["in"]]["price"]
        res.append(round(b, 1))
    return res
def bank_fpl(moves, sell=SELL_P, bank=BANK, players=PL):
    """FPL rule (and plan.js bankAt): originals sell at sell price unless re-bought in the plan; bought players sell at purchase=price."""
    b = bank; bought = set(); res = []
    for g in GWS:
        for m in [m for m in moves if m["gw"] == g]:
            b += sell[m["out"]] if (m["out"] in sell and m["out"] not in bought) else players[m["out"]]["price"]
            b -= players[m["in"]]["price"]; bought.add(m["in"])
        res.append(round(b, 1))
    return res
other_fwd = max((i for i, p in PL.items() if p["pos"] == "FWD" and p["ok"] and i not in SQUAD and p["team"] != 15), key=lambda i: PL[i]["price"])
chains = {
    "buy-in-plan then sell (A out, B in GW8; B out, C in GW9)": [{"gw": 8, "out": 411, "in": other_fwd}, {"gw": 9, "out": other_fwd, "in": 346 + 0 if False else next(i for i, p in PL.items() if p['pos'] == 'FWD' and p['ok'] and i not in SQUAD and i != other_fwd)}],
    "sell profit player (Haaland out, GW8)": [{"gw": 8, "out": 411, "in": other_fwd}],
    "sell-rebuy-sell original profit player (Haaland out GW8, back GW9, out GW10)": [
        {"gw": 8, "out": 411, "in": other_fwd}, {"gw": 9, "out": other_fwd, "in": 411}, {"gw": 10, "out": 411, "in": other_fwd}],
}
bank_cmp = {}
for k, mv in chains.items():
    bank_cmp[k] = {"optimise_py": bank_optimiser(mv), "fpl_rule": bank_fpl(mv), "moves": [[m["gw"], NAME(m["out"]), NAME(m["in"])] for m in mv]}
D_out["chains_python"] = bank_cmp
R["D_selling"] = D_out
R["_chains_for_node"] = {k: v["moves"] for k, v in bank_cmp.items()}
CHAIN_MOVES = chains

# ------------------------------------------------------------------ E. time limits
rec_all = []
_orig = pulp.LpProblem.solve
def _wrap(self, *a, **k):
    t = time.time(); st = _orig(self, *a, **k)
    rec_all.append({"lp_status": pulp.LpStatus[st], "sol_status": getattr(self, "sol_status", None), "secs": round(time.time() - t, 2)})
    return st
pulp.LpProblem.solve = _wrap
GW6 = list(range(GWS[0], GWS[0] + 6))
PL6 = build(horizon=6)[1]
E_rows = []
E_cfg = [("balanced", {}), ("chase", {"eo": EO_FRAC, "lam": -0.03, "haul_w": 10.0}), ("safe", {"eo": EO_FRAC, "lam": 0.02, "hit_margin": 2.0, "nail_w": 0.5})]
for mode, kw in E_cfg:
    for ft0 in (1, 3):
        ref = None; rows = []
        for tl in (40, 3, 1):
            rec_all.clear()
            res, rec = run(f"{mode} ft{ft0} tl{tl}", players=PL6, gws=GW6, ft0=ft0, time_limit=tl, **kw)
            row = {"mode": mode, "ft0": ft0, "time_limit": tl, "solver": dict(rec_all[-1]) if rec_all else None, "secs": rec["secs"],
                   "returned": rec["returned"]}
            if res:
                row["objective"] = res["objective"]; row["xp_total"] = res["xp_total"]
                row["result_has_status_field"] = any(k in res for k in ("status", "optimal", "gap", "proven"))
                row["issues"] = validate(res, players=PL6, ft0=ft0, max_moves=4)
            rows.append(row)
        full = rows[0].get("objective")
        for r in rows:
            if full is not None and "objective" in r:
                r["gap_vs_full"] = round(full - r["objective"], 3)
        E_rows += rows
        print("E", mode, ft0, [(r["time_limit"], r["solver"] and r["solver"]["lp_status"], r["solver"] and r["solver"]["sol_status"], r.get("objective"), r["secs"]) for r in rows])
R["E_time_limit"] = E_rows
pulp.LpProblem.solve = _orig

# ------------------------------------------------------------------ F. Python vs browser solver
def case_opts(kind):
    if kind == "balanced": return {}, {}
    if kind == "chase":
        return {"eo": EO_FRAC, "lam": -0.03, "haul_w": 10.0}, {"eo": EO_FRAC, "lam": -0.03, "haulW": 10.0}
    if kind == "safe":
        return {"eo": EO_FRAC, "lam": 0.02, "hit_margin": 2.0, "nail_w": 0.5}, {"eo": EO_FRAC, "lam": 0.02, "hitMargin": 2.0, "nailW": 0.5}
F_cases = []
for kind in ("balanced", "chase", "safe"):
    for ft0 in (1, 2, 5):
        py, js = case_opts(kind)
        F_cases.append({"name": f"{kind}_ft{ft0}", "kind": kind, "ft0": ft0, "py": py, "js": js, "locked": [], "banned": []})
py, js = case_opts("balanced")
F_cases.append({"name": "balanced_lock154_ban411", "kind": "balanced", "ft0": 2, "py": py, "js": js, "locked": [154], "banned": [411]})
F_cases.append({"name": "balanced_lockpool", "kind": "balanced", "ft0": 2, "py": py, "js": js, "locked": [lockpool], "banned": []})
F_cases.append({"name": "balanced_lock4club", "kind": "balanced", "ft0": 2, "py": py, "js": js, "locked": locks4, "banned": []})

node_cases = []
for c in F_cases:
    node_cases.append({"name": c["name"], "squad": SQUAD, "sell": {str(k): v for k, v in SELL.items()}, "bank": BANK, "ft0": c["ft0"], "gws": GWS,
                       "opts": dict(c["js"], locked=c["locked"], banned=c["banned"])})
# JS-only features: maxHits, decay etc. exercised on one case
node_cases.append({"name": "js_maxHits0_ft1", "squad": SQUAD, "sell": {str(k): v for k, v in SELL.items()}, "bank": BANK, "ft0": 1, "gws": GWS, "opts": {"maxHits": 0}})
# hostile cases through the browser solver
for lab, o, bank_, sq_ in (("js_lock_ban_same", {"locked": [HAL], "banned": [HAL]}, BANK, SQUAD), ("js_4club", {"locked": locks4}, BANK, SQUAD),
                           ("js_bank_-60", {}, -60.0, SQUAD), ("js_lock_notok", {"locked": [notok]}, BANK, SQUAD), ("js_prem", {"locked": prem}, BANK, SQUAD),
                           ("js_14man", {}, BANK, SQUAD[:14])):
    node_cases.append({"name": lab, "squad": sq_, "sell": {str(k): v for k, v in SELL.items()}, "bank": bank_, "ft0": 1, "gws": GWS, "opts": o})
json.dump({"players": PL, "cases": node_cases}, open(out_path("_js_solver_in.json"), "w"))
t = time.time()
pr = subprocess.run(["node", os.path.join(HERE, "js_parity.mjs"), "solver", out_path("_js_solver_in.json"), out_path("_js_solver_out.json")], capture_output=True, text=True)
print("node solver", round(time.time() - t, 1), "s", pr.stderr[-500:])
JSR = json.load(open(out_path("_js_solver_out.json")))

def objective(players, weeks, ft_end, gws, eo=None, lam=0.0, haul_w=0.0, nail_w=0.0, hit_margin=0.0, decay=0.9, bench_w=0.1, ft_value=1.5, eo_weeks=2):
    """The shared MILP objective (optimise.py form), evaluated on any plan {weeks:[{xi,sq,captain,hits}]}."""
    tot = 0.0
    for w, wk in enumerate(weeks):
        g = gws[w]; d = decay ** w; cap = wk["captain"]; xi = set(wk["xi"]); sq = set(wk["sq"])
        for i in sq:
            x = players[i]["xp"].get(g, 0.0)
            tot += d * x * ((i in xi) + (i == cap) + bench_w * ((i in sq) - (i in xi)))
            if i in xi and haul_w: tot += d * haul_w * players[i].get("p10", {}).get(g, 0.0) * (1 + (i == cap))
            if i in xi and nail_w: tot -= d * nail_w * (1 - min(100, players[i].get("nailed", 100)) / 100) * x
            if eo is not None and lam and w < eo_weeks and x > 0:
                v = optimise.variance(players[i]["pos"], x); e = eo.get(i, 0.0)
                k = lambda z: max(0.0, z) if lam < 0 else z
                tot -= lam * d * v * ((i in xi) * k(1 - 2 * e) + (i == cap) * k(3 - 2 * e))
        tot -= d * (4 + hit_margin) * wk["hits"]
    return tot + ft_value * ft_end

def plain(players, weeks, gws):
    return sum(sum(players[i]["xp"].get(gws[w], 0) for i in wk["xi"]) + players[wk["captain"]]["xp"].get(gws[w], 0) - 4 * wk["hits"] for w, wk in enumerate(weeks))

def js_to_weeks(j):
    return j["weeks"], j["ft_end"]

def mv(res_weeks):
    return sorted((w["gw"], o, i) for w in res_weeks for o, i in zip(sorted(w["out"], key=lambda x: PL[x]["pos"]), sorted(w["in"], key=lambda x: PL[x]["pos"])))
def mvset(res_weeks):  # position-matched, order-independent
    out = set()
    for w in res_weeks:
        outs = list(w["out"])
        for i in w["in"]:
            k = next((k for k, o in enumerate(outs) if PL[o]["pos"] == PL[i]["pos"]), None)
            if k is not None: out.add((w["gw"], outs.pop(k), i))
    return out

F_rows = []
for c in F_cases:
    row = {"case": c["name"]}
    for tag, pool in (("py_default_pool", PY_POOL), ("py_js_pool", JS_POOL)):
        optimise.POOL.clear(); optimise.POOL.update(pool)
        t = time.time()
        res = optimise.solve(PL, SQUAD, SELL, BANK, c["ft0"], GWS, locked=c["locked"], banned=c["banned"], time_limit=60, **c["py"])
        row[tag] = None
        if res:
            ws = [{"xi": w["xi"], "sq": w["xi"] + w["bench"], "captain": w["captain"], "hits": w["hits"], "in": w["in"], "out": w["out"], "gw": w["gw"]} for w in res["weeks"]]
            pk = dict(c["py"])
            row[tag] = {"secs": round(time.time() - t, 2), "obj_reeval": round(objective(PL, ws, res["ft_left"], GWS, **pk), 3), "obj_reported": res["objective"],
                        "plain_xp": round(plain(PL, ws, GWS), 2), "moves": sorted(mvset(ws)), "captains": [w["captain"] for w in ws],
                        "xi": [sorted(w["xi"]) for w in ws], "hits": [w["hits"] for w in ws], "ft_end": res["ft_left"],
                        "issues": validate(res, ft0=c["ft0"], locked=c["locked"], banned=c["banned"])}
    optimise.POOL.clear(); optimise.POOL.update(PY_POOL)
    j = JSR[c["name"]]
    if j.get("weeks"):
        ws = [dict(w, **{}) for w in j["weeks"]]
        pk = dict(c["py"])
        iss = validate({"weeks": [{"gw": w["gw"], "in": w["in"], "out": w["out"], "xi": w["xi"], "captain": w["captain"], "ft": w["ft"], "hits": w["hits"], "bank": w["bank"]} for w in ws], "ft_left": j["ft_end"]},
                       ft0=c["ft0"], locked=c["locked"], banned=c["banned"])
        row["js"] = {"status": j["status"], "secs": j["secs"], "obj_reeval": round(objective(PL, ws, j["ft_end"], GWS, **pk), 3), "obj_highs": round(j["objective"], 3),
                     "plain_xp": round(plain(PL, ws, GWS), 2), "moves": sorted(mvset(ws)), "captains": [w["captain"] for w in ws],
                     "xi": [sorted(w["xi"]) for w in ws], "hits": [w["hits"] for w in ws], "ft_end": j["ft_end"], "issues": iss, "pool": j["pool"]}
    else:
        row["js"] = {"error": j.get("error"), "status": j.get("status")}
    F_rows.append(row)
    a, b, jj = row["py_default_pool"], row["py_js_pool"], row["js"]
    print("F", c["name"], "py", a and a["obj_reeval"], "py(jspool)", b and b["obj_reeval"], "js", jj.get("obj_reeval"),
          "| same moves(jspool/js)", b and jj.get("moves") is not None and [list(x) for x in b["moves"]] == [list(x) for x in jj["moves"]])
R["F_py_vs_js"] = F_rows
R["F_js_hostile"] = {k: {kk: v for kk, v in JSR[k].items() if kk in ("status", "error", "accepted", "secs")} | ({"plan_issues": None} if False else {}) for k in JSR if k.startswith("js_")}
for k in JSR:
    if k.startswith("js_") and JSR[k].get("weeks"):
        cfg = next(n for n in node_cases if n["name"] == k)
        R["F_js_hostile"][k]["plan_issues"] = validate({"weeks": [{kk: w[kk] for kk in ("gw", "in", "out", "xi", "captain", "ft", "hits", "bank")} for w in JSR[k]["weeks"]], "ft_left": JSR[k]["ft_end"]},
                                                      squad=cfg["squad"], bank=cfg["bank"], ft0=1, locked=cfg["opts"].get("locked", []), banned=cfg["opts"].get("banned", []))

# ------------------------------------------------------------------ G. front-end parity (real model.js / plan.js in Node)
def moves_of(weeks):
    out = []
    for w in weeks:
        outs = list(w["out"])
        for i in w["in"]:
            k = next((k for k, o in enumerate(outs) if PL[o]["pos"] == PL[i]["pos"]), None)
            if k is not None: out.append({"gw": w["gw"], "out": outs.pop(k), "in": i})
    return out

crowd_js = {"near": {"n": 500, "eo": {str(k): v for k, v in EO_PCT.items()}}}
plans_by_mode = {}
for mode, (kw, lam) in {"balanced": ({}, 0.0), "safe": (dict(E_cfg[2][1]), 0.02), "chase": (dict(E_cfg[1][1]), -0.03)}.items():
    plans = {}
    for ft0 in (1, 2, 3, 5):
        for key, n in (("best", None), ("roll", 0), ("one", 1), ("two", 2)):
            res = optimise.solve(PL, SQUAD, SELL, BANK, ft0, GWS, week1_moves=n, **kw)
            if res: plans[f"ft{ft0}_{key}"] = res
    plans_by_mode[mode] = plans
# captain-swap census squads: every weekly squad of every plan + random legal-ish squads
import random
rng = random.Random(7)
def rand_squad():
    while True:
        sq = []
        for pos, n in optimise.SHAPE.items():
            top = sorted((i for i, p in PL.items() if p["pos"] == pos and p["ok"]), key=lambda i: -sum(PL[i]["xp"].values()))[:[8, 22, 22, 12][list(optimise.SHAPE).index(pos)]]
            sq += rng.sample(top, n)
        cl = {}
        for i in sq: cl[PL[i]["team"]] = cl.get(PL[i]["team"], 0) + 1
        if max(cl.values()) <= 3 and sum(PL[i]["price"] for i in sq) <= 101.5: return sq
rand_sqs = [rand_squad() for _ in range(300)]

scen = []
for mode, plans in plans_by_mode.items():
    sc = {"name": f"{mode}", "mode": mode, "players": PL, "squad": SQUAD, "sell": SELL, "bank": BANK, "ft0": 1, "gws": GWS,
          "crowd": crowd_js if mode != "balanced" else None, "plans": [], "probes": []}
    sc["plans"] = [{"name": k, "moves": moves_of(r["weeks"])} for k, r in plans.items()]
    scen.append(sc)
# ft0 differs per plan: make one scenario per (mode, ft0)
scen2 = []
for sc in scen:
    for ft0 in (1, 2, 3, 5):
        s2 = dict(sc, name=f"{sc['mode']}_ft{ft0}", ft0=ft0, plans=[p for p in sc["plans"] if p["name"].startswith(f"ft{ft0}_")])
        s2["probes"] = []
        scen2.append(s2)
# probes (balanced): the optimiser's weekly squads and random squads
probe_sc = {"name": "probes_balanced", "mode": "balanced", "players": PL, "squad": SQUAD, "sell": SELL, "bank": BANK, "ft0": 1, "gws": GWS, "crowd": None, "plans": [], "probes": []}
for sq in rand_sqs:
    for g in GWS: probe_sc["probes"].append({"squad": sq, "gw": g})
plan_sqs = []
for plans in (plans_by_mode["balanced"],):
    for k, r in plans.items():
        sqd = list(SQUAD)
        for w in r["weeks"]:
            sqd = w["xi"] + w["bench"]
            plan_sqs.append((k, w["gw"], sqd, w["captain"]))
for _, g, sqd, _c in plan_sqs: probe_sc["probes"].append({"squad": sqd, "gw": g})
# explicit bank probes
probe_sc["bankProbes"] = [{"name": k, "moves": v} for k, v in chains.items()]
scen2.append(probe_sc)
json.dump({"scenarios": scen2}, open(out_path("_js_front_in.json"), "w"))
pr = subprocess.run(["node", os.path.join(HERE, "js_parity.mjs"), "front", out_path("_js_front_in.json"), out_path("_js_front_out.json")], capture_output=True, text=True)
print("node front", pr.stderr[-800:])
FR = json.load(open(out_path("_js_front_out.json")))

G = {"consts": FR["probes_balanced"]["__consts"]}
rows = []; agg = {"weeks": 0, "xi_diff_pts": 0, "xi_set_diff": 0, "cap_diff": 0, "cap_diff_swap": 0, "ft_diff": 0, "hit_diff": 0, "bank_diff": 0, "pts_diff": 0, "max_pts_gap": 0.0}
per_mode = {}
for sc in scen2:
    if not sc["plans"]: continue
    mode = sc["mode"]; kw = {"balanced": {}, "safe": E_cfg[2][1], "chase": E_cfg[1][1]}[mode]
    fr = FR[sc["name"]]
    pm = per_mode.setdefault(mode, {"weeks": 0, "cap_diff": 0, "xi_set_diff": 0, "pts_diff": 0, "ft_diff": 0, "hits_diff": 0, "bank_diff": 0, "tot_gap": [], "examples": []})
    for p in sc["plans"]:
        py = plans_by_mode[mode][p["name"]]; js = fr[p["name"]]
        ft0 = sc["ft0"]
        for wp, wj in zip(py["weeks"], js["weeks"]):
            pm["weeks"] += 1
            if wp["captain"] != wj["cap"]:
                pm["cap_diff"] += 1
                if len(pm["examples"]) < 6:
                    pm["examples"].append({"plan": p["name"], "gw": wp["gw"], "optimiser_cap": NAME(wp["captain"]), "optimiser_pos": PL[wp["captain"]]["pos"], "page_cap": NAME(wj["cap"]), "page_swapped": wj["swapped"] and NAME(wj["swapped"]),
                                           "xp_opt": PL[wp["captain"]]["xp"][str(wp["gw"])] if str(wp["gw"]) in PL[wp["captain"]]["xp"] else PL[wp["captain"]]["xp"].get(wp["gw"]),
                                           "xp_page": PL[wj["cap"]]["xp"].get(wp["gw"]) if wp["gw"] in PL[wj["cap"]]["xp"] else PL[wj["cap"]]["xp"].get(str(wp["gw"]))})
            if set(wp["xi"]) != set(wj["xi"]): pm["xi_set_diff"] += 1
            if abs(wp["xp"] - wj["pts"]) > 0.015: pm["pts_diff"] += 1
            if wp["ft"] != wj["ft"]: pm["ft_diff"] += 1
            if wp["hits"] != wj["hits"]: pm["hits_diff"] += 1
            if abs(wp["bank"] - wj["bank"]) > 0.051: pm["bank_diff"] += 1
        pm["tot_gap"].append(round(py["xp_total"] - js["tot"], 2))
for m, pm in per_mode.items():
    pm["tot_gap_max"] = max(pm["tot_gap"], key=abs); pm["tot_gap_mean"] = round(sum(pm["tot_gap"]) / len(pm["tot_gap"]), 3); del pm["tot_gap"]
G["per_mode_plan_replay"] = per_mode

# captain-swap census (balanced; page rule vs "highest adjCap in XI")
probes = FR["probes_balanced"]["__probes"]
n_rand = len(rand_sqs) * len(GWS)
def census(ps):
    sw = [p for p in ps if p["swapped"]]
    loss = [PL[p["swapped"]]["xp"].get(p["gw"], PL[p["swapped"]]["xp"].get(str(p["gw"]), 0)) - PL[p["cap"]]["xp"].get(p["gw"], PL[p["cap"]]["xp"].get(str(p["gw"]), 0)) for p in sw]
    return {"squad_weeks": len(ps), "swaps": len(sw), "pct": round(100 * len(sw) / max(1, len(ps)), 1),
            "xp_given_up_mean": round(sum(loss) / len(loss), 3) if loss else 0, "xp_given_up_max": round(max(loss), 3) if loss else 0,
            "captain_differs_from_optimiser_rule": sum(1 for p in ps if p["cap"] != p["optCap"])}
G["capPick_census_random_squads"] = census(probes[:n_rand])
G["capPick_census_plan_squads"] = census(probes[n_rand:n_rand + len(plan_sqs)])
G["capPick_census_plan_squads"]["optimiser_chose_GKP_or_DEF_captain"] = sum(1 for _, _, _, c in plan_sqs if PL[c]["pos"] in ("GKP", "DEF"))
# how often is the GKP/DEF the best xP in the XI at all, using the user's own squad per week
own = []
for g in GWS:
    t = [p for p in probes[n_rand:] if p["gw"] == g]
G["bank_probes"] = FR["probes_balanced"]["__bank"]
G["python_bank_models"] = {k: {"optimise_py": v["optimise_py"], "fpl_rule": v["fpl_rule"]} for k, v in bank_cmp.items()}
# bank probes under the page's sell map: the page's D.squad.sell is SELL (current price), so rerun with profit sell map
sc_bank = {"name": "bank_profit", "mode": "balanced", "players": PL, "squad": SQUAD, "sell": SELL_P, "bank": BANK, "ft0": 1, "gws": GWS, "crowd": None, "plans": [],
           "bankProbes": [{"name": k, "moves": v} for k, v in chains.items()]}
json.dump({"scenarios": [sc_bank]}, open(out_path("_js_front_in2.json"), "w"))
subprocess.run(["node", os.path.join(HERE, "js_parity.mjs"), "front", out_path("_js_front_in2.json"), out_path("_js_front_out2.json")], check=True)
FR2 = json.load(open(out_path("_js_front_out2.json")))["bank_profit"]["__bank"]
G["bank_compare_profit_sell_map"] = [{"chain": b["name"], "plan_js_bankAt": b["bank"], "optimise_py_rule": bank_cmp[b["name"]]["optimise_py"], "fpl_rule": bank_cmp[b["name"]]["fpl_rule"]} for b in FR2]

# ftTable vs rule on move counts 0..6 and ft0 0..5 (real JS)
ft_sc = {"name": "ft", "mode": "balanced", "players": PL, "squad": SQUAD, "sell": SELL, "bank": BANK, "ft0": 0, "gws": GWS, "crowd": None, "plans": []}
ft_checks = []
all_squad_new = [i for i in PL if i not in SQUAD and PL[i]["ok"]]
ftmis = []
for ft0 in (0, 1, 2, 3, 5):
    sc_ = dict(ft_sc, name=f"ft{ft0}", ft0=ft0)
    plans_ = []
    for n in range(0, 7):
        # n moves in GW8 then n moves in GW9 (ids irrelevant to ftTable): swap first n squad players for distinct same-position outsiders
        mvs = []
        used = set(SQUAD)
        for k in range(n):
            o = SQUAD[k]; i = next(x for x in all_squad_new if PL[x]["pos"] == PL[o]["pos"] and x not in used); used.add(i)
            mvs.append({"gw": GWS[0], "out": o, "in": i})
        for k in range(min(n, 2)):
            o = mvs[k]["in"]; i = next(x for x in all_squad_new if PL[x]["pos"] == PL[o]["pos"] and x not in used); used.add(i)
            mvs.append({"gw": GWS[1], "out": o, "in": i})
        plans_.append({"name": f"n{n}", "moves": mvs})
    sc_["plans"] = plans_; ft_checks.append(sc_)
json.dump({"scenarios": ft_checks}, open(out_path("_js_front_in3.json"), "w"))
subprocess.run(["node", os.path.join(HERE, "js_parity.mjs"), "front", out_path("_js_front_in3.json"), out_path("_js_front_out3.json")], check=True)
FR3 = json.load(open(out_path("_js_front_out3.json")))
for ft0 in (0, 1, 2, 3, 5):
    for n in range(0, 7):
        wk = FR3[f"ft{ft0}"][f"n{n}"]["weeks"]
        ft = ft0; n2 = min(n, 2)
        for w, cnt in zip(wk, (n, n2, 0, 0, 0)):
            if (w["ft"], w["hits"], w["next"]) != (ft, max(0, cnt - ft), ft_rule(ft, cnt)):
                ftmis.append({"ft0": ft0, "n_gw8": n, "gw": w["gw"], "js": [w["ft"], w["hits"], w["next"]], "rule": [ft, max(0, cnt - ft), ft_rule(ft, cnt)]})
            ft = ft_rule(ft, cnt)
G["ftTable_vs_rule"] = {"cases": 5 * 7 * 5, "mismatches": ftmis[:10], "n_mismatch": len(ftmis)}
R["G_frontend"] = G

# constants / defaults comparison (static text parse)
src_b = open(os.path.join(ROOT, "build.py")).read(); src_m = open(os.path.join(ROOT, "site/js/core/model.js")).read()
from fplmodel import DEFAULTS
R["G_constants"] = {
    "build.py_MODES_lam": re.findall(r'"(balanced|safe|chase)": \{"lam": ([-\d.]+)', src_b),
    "build.py_STRATEGY": re.search(r"STRATEGY = (\{.*\})", src_b).group(1),
    "model.js_LAM": re.search(r"const LAM = (\{.*?\});", src_m).group(1),
    "model.js_STRAT": re.search(r"const STRAT = (\{.*?\});", src_m).group(1),
    "build.py_slope_literal": re.search(r"slope = ([\d.]+)", src_b).group(1),
    "fplmodel_cal_slope": DEFAULTS["cal_slope"], "fplmodel_cal_int": DEFAULTS["cal_int"],
    "optimise_defaults": {"decay": 0.9, "bench_w": 0.1, "ft_value": 1.5, "hit": 4, "max_moves_week": 4, "eo_weeks": 2, "POOL": PY_POOL},
    "plan-solver_defaults": {"decay": 0.9, "benchW": 0.1, "ftValue": 1.5, "hit": 4, "maxMovesWeek": 4, "eoWeeks": 2, "POOL": JS_POOL},
}
# xp_detail uses slope but omits the intercept: size of the gap on the user's squad
det = project(C, GWS[0], 5, {"use_flags": True})["players"]
gaps = []
for i in SQUAD:
    d = det[i]["detail"].get(GWS[0])
    if d: gaps.append(round(det[i]["xp"][GWS[0]] - 0.86 * sum(d.values()), 2))
R["G_constants"]["xp_minus_slope_x_detail_sum_GW8_squad"] = gaps

json.dump(R, open(out_path("optimiser.json"), "w"), indent=1, default=str)
print("wrote", out_path("optimiser.json"))
