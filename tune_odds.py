import json
from fplmodel import prepare
from backtest import evaluate
raw = "raw"
boot = json.load(open(f"{raw}/bootstrap.json")); fixtures = json.load(open(f"{raw}/fixtures.json"))
cur = max(e["id"] for e in boot["events"] if e["finished"])
live = {g: json.load(open(f"{raw}/live{g}.json")) for g in range(1, cur + 1)}
ctx = prepare(boot, fixtures, live, json.load(open("priors.json")), json.load(open("odds/odds.json")))
gws = range(3, cur + 1)
for mw in (0.0, 0.3, 0.5, 0.7, 1.0):
    for dw in (0.0, 0.5, 0.8, 1.0):
        r = evaluate(ctx, gws, {"mkt_w": mw, "direct_w": dw})
        top = sum(x - a for _, a, x in r["top30"]) / len(r["top30"])
        print(f"mkt_w {mw:.1f} direct_w {dw:.1f}: corr {r['corr']:.4f} rmse {r['rmse']:.4f} bias {r['bias']:+.3f} top30 {top:+.2f}")
