import json, itertools, random
from fplmodel import prepare
from backtest import evaluate
raw = "raw"
boot = json.load(open(f"{raw}/bootstrap.json")); fixtures = json.load(open(f"{raw}/fixtures.json"))
cur = max(e["id"] for e in boot["events"] if e["finished"])
live = {g: json.load(open(f"{raw}/live{g}.json")) for g in range(1, cur + 1)}
ctx = prepare(boot, fixtures, live, json.load(open("priors.json")))
grid = {
    "recency": [0.7, 0.8], "w_pos": [300, 600], "w_last": [600, 1500],
    "home": [1.04, 1.08], "xg_weight": [0.7], "prior_games": [4], "bonus_scale": [0.8, 1.0],
    "assist_mult": [1.2, 1.4], "goal_mult": [0.85, 0.95], "cs_k": [0.8, 0.9],
}
keys = list(grid); combos = list(itertools.product(*grid.values()))
random.seed(1); combos = random.sample(combos, min(200, len(combos)))
res = []
for c in combos:
    p = dict(zip(keys, c)); r = evaluate(ctx, range(3, cur + 1), p)
    top = sum(x - a for _, a, x in r["top30"]) / len(r["top30"])
    res.append((r["rmse"], r["corr"], top, p))
res.sort(key=lambda x: x[0])
for r in res[:8]: print(f"rmse {r[0]:.4f} corr {r[1]:.4f} top30 bias {r[2]:+.2f}", r[3])
print("by corr"); [print(f"rmse {r[0]:.4f} corr {r[1]:.4f} top30 bias {r[2]:+.2f}", r[3]) for r in sorted(res, key=lambda x: -x[1])[:5]]
