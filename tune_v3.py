import json
from fplmodel import prepare, understat_sp
from backtest import evaluate
raw = "raw"
boot = json.load(open(f"{raw}/bootstrap.json")); fixtures = json.load(open(f"{raw}/fixtures.json"))
cur = max(e["id"] for e in boot["events"] if e["finished"])
live = {g: json.load(open(f"{raw}/live{g}.json")) for g in range(1, cur + 1)}
sp = understat_sp(boot, fixtures, json.load(open("understat/shots.json")), json.load(open("understat/fpl_players.json"))["players"])
ctx = prepare(boot, fixtures, live, json.load(open("priors.json")), json.load(open("odds/odds.json")), sp)
gws = range(3, cur + 1)
def show(label, p):
    r = evaluate(ctx, gws, p); top = sum(x - a for _, a, x in r["top30"]) / len(r["top30"])
    print(f"{label:28s} corr {r['corr']:.4f} rmse {r['rmse']:.4f} top30 {top:+.2f}")
show("current", {})
for a in (0.25, 0.5, 0.75, 1.0): show(f"opp_adj {a}", {"opp_adj": a})
for b in (0.5, 1.0, 1.5): show(f"sp_match {b}", {"sp_match": b})
for a in (0.5, 1.0):
    for b in (0.5, 1.0): show(f"opp_adj {a} + sp {b}", {"opp_adj": a, "sp_match": b})
