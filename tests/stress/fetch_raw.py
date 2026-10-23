#!/usr/bin/env python3
"""Write raw/ (bootstrap, fixtures, live{g}) for bench.py from the public FPL API. raw/ is gitignored."""
import json, os, sys, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
API = "https://fantasy.premierleague.com/api"
def get(p):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(API + p, headers={"User-Agent": "Mozilla/5.0 fpl-lab"}), timeout=30) as r:
                return json.load(r)
        except Exception:
            if i == 3: raise
            time.sleep(3)
raw = os.path.join(ROOT, "raw"); os.makedirs(raw, exist_ok=True)
boot = get("/bootstrap-static/"); json.dump(boot, open(f"{raw}/bootstrap.json", "w"))
json.dump(get("/fixtures/"), open(f"{raw}/fixtures.json", "w"))
cur = max(e["id"] for e in boot["events"] if e["finished"])
for g in range(1, cur + 1):
    json.dump(get(f"/event/{g}/live/"), open(f"{raw}/live{g}.json", "w"))
print("raw/ written, finished GWs 1 -", cur, "| next:", next((e["id"] for e in boot["events"] if e["is_next"]), None))
