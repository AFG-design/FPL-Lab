#!/usr/bin/env python3
"""Fetch the FPL API files the backtests read into raw/ (gitignored): bootstrap.json, fixtures.json and
live{g}.json for every gameweek up to the current one.

Usage (from the repo root):  python3 tools/fetch_raw.py [OUT_DIR]     (default raw/)

Missing or late data: any request that still fails after 4 tries raises, so the caller (retune.yml) stops
rather than tuning on a partial season. A live{g}.json already on disk for a gameweek that was finished and
data_checked when it was saved is kept (FPL doesn't change those); everything else is fetched again.
"""
import json, os, sys, time, urllib.request

API = "https://fantasy.premierleague.com/api"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get(path, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(API + path, headers={"User-Agent": "Mozilla/5.0 fpl-lab"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(3 * (i + 1))


def save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    os.replace(tmp, path)


def main(out):
    os.makedirs(out, exist_ok=True)
    old_checked = set()
    try:   # gameweeks that were already final the last time we fetched
        old_checked = {e["id"] for e in json.load(open(os.path.join(out, "bootstrap.json")))["events"]
                       if e["finished"] and e["data_checked"]}
    except Exception:
        pass
    boot = get("/bootstrap-static/")
    fixtures = get("/fixtures/")
    cur = max((e["id"] for e in boot["events"] if e["is_current"] or e["finished"]), default=0)
    fetched = 0
    for g in range(1, cur + 1):
        p = os.path.join(out, f"live{g}.json")
        if g in old_checked and os.path.exists(p):
            continue
        save(p, get(f"/event/{g}/live/"))
        fetched += 1
    save(os.path.join(out, "fixtures.json"), fixtures)
    save(os.path.join(out, "bootstrap.json"), boot)   # last: it marks which live files are final
    print(f"raw data in {out}: GW1-{cur}, fetched {fetched} live file(s)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "raw"))
