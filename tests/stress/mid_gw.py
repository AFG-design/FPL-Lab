#!/usr/bin/env python3
"""Live-only bug hunt: build.py feeds the in-progress gameweek's live data into the model. Players whose
match hasn't kicked off show 0 minutes for that week. Compare next-GW projections with and without it.
Needs raw/live{cur}_partial.json (saved mid-gameweek)."""
import json, os, sys, glob
from common import *
from fplmodel import prepare, project
boot = json.load(open("raw/bootstrap.json")); fixtures = json.load(open("raw/fixtures.json"))
cur = next(e["id"] for e in boot["events"] if e["is_current"]); nxt = cur + 1
fin = max(e["id"] for e in boot["events"] if e["finished"])
live = {g: json.load(open(f"raw/live{g}.json")) for g in range(1, fin + 1)}
part = json.load(open(f"raw/live{cur}_partial.json"))
priors = json.load(open("priors.json")); market = json.load(open("odds/odds.json"))
clean = project(prepare(boot, fixtures, live, priors, market), nxt, 6)["players"]
mid = project(prepare(boot, fixtures, {**live, cur: part}, priors, market), nxt, 6)["players"]
el = {e["id"]: e for e in boot["elements"]}
played = sum(1 for x in part["elements"] if x["stats"]["minutes"] > 0)
rows = sorted(((clean[p]["xp"].get(nxt, 0), mid[p]["xp"].get(nxt, 0), clean[p]["p_start"], mid[p]["p_start"], el[p]["web_name"]) for p in clean), reverse=True)
print(f"GW{cur} in progress ({played} players have minutes). GW{nxt} xP, clean vs as built mid-gameweek:")
for c, m, ps, pm, n in rows[:15]:
    print(f"  {n:<16} {c:5.2f} -> {m:5.2f}  ({m - c:+.2f})  start chance {ps:.2f} -> {pm:.2f}")
top = rows[:100]
print(f"top-100 by clean xP: mean change {sum(m - c for c, m, *_ in top) / 100:+.2f} pts; 6-GW sum change "
      f"{sum(sum(mid[p]['xp'].values()) - sum(clean[p]['xp'].values()) for p in clean if clean[p]['xp'].get(nxt,0) >= top[-1][0]) / 100:+.2f}")
mine = json.load(open("tests/stress/my_squad.json")) if os.path.exists("tests/stress/my_squad.json") else []
if mine:
    print("Your squad:")
    for p in mine: print(f"  {el[p]['web_name']:<16} {clean[p]['xp'][nxt]:5.2f} -> {mid[p]['xp'][nxt]:5.2f}")

# ---- suggested fix (for build.py): keep a gameweek's live rows only for players whose club's match(es) have finished
def drop_unplayed(live_g, fixtures, elements, g):
    done = defaultdict(bool); pending = set()
    for f in fixtures:
        if f["event"] == g:
            for t in (f["team_h"], f["team_a"]):
                if f.get("finished") or f.get("finished_provisional"): done[t] = True
                else: pending.add(t)
    keep = [x for x in live_g["elements"] if elements.get(x["id"], {}).get("team") not in pending]
    return {"elements": keep}
from collections import defaultdict
fixed = project(prepare(boot, fixtures, {**live, cur: drop_unplayed(part, fixtures, el, cur)}, priors, market), nxt, 6)["players"]
worst = max(abs(fixed[p]["xp"].get(nxt, 0) - clean[p]["xp"].get(nxt, 0)) for p in clean)
print(f"with the fix: largest GW{nxt} difference from the clean projection {worst:.2f} pts (teams that have played keep their new data)")
