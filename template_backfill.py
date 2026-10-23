#!/usr/bin/env python3
"""One-off: rebuild the top-10k template for past gameweeks, before weekly sampling began.

Takes 500 managers who are in the overall top 10,000 now (every 20th) and reads their team in every finished
gameweek. Caveat: they are top-10k *now*, so their past picks are the ones that worked; real weekly samples
(crowd.py) replace these weeks' figures from the first sampled gameweek on. Writes crowd/history.json:
{"gws": {gw: {"n", "own", "eo", "cap", "source"}}} with percentages for players at 0.5%+.
Usage: python3 template_backfill.py
"""
import json, os, time, urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

API = "https://fantasy.premierleague.com/api"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crowd", "history.json")


def get(path, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(API + path, headers={"User-Agent": "Mozilla/5.0 fpl-lab"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:
            time.sleep(2 + 3 * i)
    return None


boot = get("/bootstrap-static/")
done = [e["id"] for e in boot["events"] if e["finished"]]
ids = []
for page in range(1, 201, 4):          # 50 managers a page, top 10,000 = pages 1-200; every 4th page...
    d = get(f"/leagues-classic/314/standings/?page_standings={page}")
    ids += [r["entry"] for r in (d or {}).get("standings", {}).get("results", [])][::5]   # ...every 5th manager
ids = ids[:500]
print(len(ids), "managers")
hist = json.load(open(OUT)) if os.path.exists(OUT) else {"gws": {}}
for g in done:
    if hist["gws"].get(str(g), {}).get("source") == "sample":
        continue                        # a real weekly sample beats the backfill
    with ThreadPoolExecutor(8) as ex:
        picks = [p for p in ex.map(lambda e: get(f"/entry/{e}/event/{g}/picks/"), ids) if p]
    own, cap, eo = defaultdict(int), defaultdict(int), defaultdict(float)
    for p in picks:
        for x in p["picks"]:
            own[x["element"]] += 1
            eo[x["element"]] += min(x["multiplier"], 2)
            cap[x["element"]] += x["is_captain"]
    n = len(picks)
    pct = lambda d: {str(k): round(100 * v / n, 1) for k, v in d.items() if 100 * v / n >= 0.5}
    hist["gws"][str(g)] = {"n": n, "own": pct(own), "eo": pct(eo), "cap": pct(cap), "source": "backfill"}
    print(f"GW{g}: {n} teams")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(hist, open(OUT, "w"), separators=(",", ":"))
