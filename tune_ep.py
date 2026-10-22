import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fplmodel import prepare, project
R = sys.argv[1]
boot = json.load(open(f"{R}/bootstrap.json")); fixtures = json.load(open(f"{R}/fixtures.json"))
cur = max(e["id"] for e in boot["events"] if e["finished"])
live = {g: json.load(open(f"{R}/live{g}.json")) for g in range(1, cur + 1)}
ctx = prepare(boot, fixtures, live, json.load(open("priors.json")), json.load(open("odds/odds.json")))
rows = []
for k in range(3, cur + 1):
    res = project(ctx, k, horizon=1, params={"use_flags": False})["players"]
    for pid, r in res.items():
        a = ctx["pts_gw"].get(pid, {}).get(k)
        if a is None: continue
        if not any(ctx["pstats"].get(pid, {}).get(g, {}).get("minutes", 0) > 0 for g in range(k - 3, k)): continue
        # FPL-style form: average points per gameweek over the last ~30 days (about 4 GWs), counting blanks
        prev = [ctx["pts_gw"][pid].get(g, 0) for g in range(max(1, k - 4), k)]
        form = sum(prev) / len(prev)
        rows.append((k, r["xp"].get(k, 0.0), form, a))
def stats(pred, act):
    n = len(pred); mp, ma = sum(pred)/n, sum(act)/n
    cov = sum((p-mp)*(a-ma) for p, a in zip(pred, act))
    corr = cov / math.sqrt(sum((p-mp)**2 for p in pred) * sum((a-ma)**2 for a in act))
    rmse = math.sqrt(sum((p-a)**2 for p, a in zip(pred, act))/n)
    return corr, rmse
act = [r[3] for r in rows]
for w in [0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0]:
    c, e = stats([(1-w)*x + w*f for _, x, f, _ in rows], act)
    # per-GW robustness
    per = []
    for k in range(3, cur+1):
        sub = [r for r in rows if r[0] == k]
        per.append(stats([(1-w)*x + w*f for _, x, f, _ in sub], [r[3] for r in sub])[0])
    print(f"w_form={w:.2f} corr={c:.4f} rmse={e:.3f} perGW={' '.join(f'{p:.3f}' for p in per)}")
