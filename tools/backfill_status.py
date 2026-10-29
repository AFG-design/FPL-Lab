#!/usr/bin/env python3
"""One-off: fill gaps in history/status.json (each player's FPL status at every deadline) for gameweeks
before the log started.

Two sources, both saved at the time (no hindsight):
  1. history/proj_gw{g}.json snapshots whose rows hold [xP, ep_next, status, chance] (written before deadline g);
  2. history/news.json, every change to a player's status and chance, timed by FPL's news_added. A status holds
     from its timestamp until the next entry, so the entry in force at deadline g is his status then. Before a
     player's first entry nothing is known, so nothing is filled.
Gameweeks already in the log are never changed. Run from the repo root: python3 tools/backfill_status.py
Needs the FPL API for the deadlines (or pass a saved bootstrap-static JSON as the first argument).
"""
import json, os, sys, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(HERE, "history")
OUT_STATUS = ("i", "s", "n", "u")


def bootstrap():
    if len(sys.argv) > 1:
        return json.load(open(sys.argv[1]))
    req = urllib.request.Request("https://fantasy.premierleague.com/api/bootstrap-static/", headers={"User-Agent": "Mozilla/5.0 fpl-lab"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def iso(t):
    return t.replace("Z", "+00:00")[:19]


def main():
    boot = bootstrap()
    deadlines = {e["id"]: e["deadline_time"] for e in boot["events"] if e.get("deadline_time")}
    path = os.path.join(HIST, "status.json")
    log = json.load(open(path))
    have = set(log["gws"])
    first = min(int(g) for g in have) if have else max(deadlines) + 1
    news = json.load(open(os.path.join(HIST, "news.json")))
    added = {}
    for g in sorted(deadlines):
        if str(g) in have or g >= first:
            continue
        rows, src = {}, None
        snap = os.path.join(HIST, f"proj_gw{g}.json")
        if os.path.exists(snap):
            s = json.load(open(snap))
            if s["players"] and all(len(v) >= 4 for v in s["players"].values()):
                rows = {pid: [v[2], v[3]] for pid, v in s["players"].items() if v[2] != "a"}
                src = "proj_gw snapshot"
        if src is None:
            dl = iso(deadlines[g])
            for pid, hist in news.items():
                cur = None
                for t, st, ch, _txt in hist:
                    if iso(t) < dl:
                        cur = (st, ch)
                    else:
                        break
                if cur and cur[0] != "a":
                    rows[pid] = [cur[0], cur[1]]
            src = "news.json"
        log["gws"][str(g)] = rows
        added[g] = (src, len(rows), sum(1 for st, ch in rows.values() if st in OUT_STATUS or (ch is not None and ch <= 25)))
    if not added:
        print("nothing to backfill"); return
    log["gws"] = dict(sorted(log["gws"].items(), key=lambda kv: int(kv[0])))
    log["backfilled"] = dict(log.get("backfilled", {}), **{str(g): v[0] for g, v in added.items()})
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(log, f, separators=(",", ":"))
    os.replace(tmp, path)
    for g, (src, n, nout) in sorted(added.items()):
        print(f"GW{g}: {n} flagged players ({nout} out) from {src}")


if __name__ == "__main__":
    main()
