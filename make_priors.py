#!/usr/bin/env python3
"""Download every player's previous-season totals and save per-90 priors to priors.json.
Run occasionally (new signings appear during the season)."""
import json, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

API = "https://fantasy.premierleague.com/api"
OUT = sys.argv[1] if len(sys.argv) > 1 else "priors.json"


def get(path):
    for i in range(4):
        try:
            req = urllib.request.Request(API + path, headers={"User-Agent": "Mozilla/5.0 fpl-lab"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:
            time.sleep(2 + 3 * i)
    return None


boot = get("/bootstrap-static/")
ids = [e["id"] for e in boot["elements"]]


def one(pid):
    d = get(f"/element-summary/{pid}/")
    if not d or not d.get("history_past"):
        return pid, None
    seasons = d["history_past"][-2:]
    # weight the most recent season 2:1 over the one before
    w = [1.0, 2.0][-len(seasons):]
    tot = {k: 0.0 for k in ("minutes", "xg", "xa", "bonus", "saves", "dc", "yc", "pts", "starts")}
    for wt, s in zip(w, seasons):
        tot["minutes"] += wt * s["minutes"]
        tot["xg"] += wt * float(s["expected_goals"])
        tot["xa"] += wt * float(s["expected_assists"])
        tot["bonus"] += wt * s["bonus"]
        tot["saves"] += wt * s["saves"]
        tot["dc"] += wt * s.get("defensive_contribution", 0)
        tot["yc"] += wt * s["yellow_cards"]
        tot["pts"] += wt * s["total_points"]
        tot["starts"] += wt * s.get("starts", 0)
    m = tot["minutes"]
    if m < 1:
        return pid, None
    last = seasons[-1]
    return pid, {
        "season": last["season_name"], "mins": round(m / sum(w)),
        "xg90": tot["xg"] / m * 90, "xa90": tot["xa"] / m * 90, "bonus90": tot["bonus"] / m * 90,
        "saves90": tot["saves"] / m * 90, "dc90": tot["dc"] / m * 90, "yc90": tot["yc"] / m * 90,
        "pts90": tot["pts"] / m * 90, "last_pts": last["total_points"], "last_mins": last["minutes"],
        "last_xgi": float(last["expected_goal_involvements"]),
    }


with ThreadPoolExecutor(6) as ex:
    res = dict(ex.map(one, ids))
priors = {str(k): {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in v.items()} for k, v in res.items() if v}
json.dump({"built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "players": priors}, open(OUT, "w"), separators=(",", ":"))
print(f"priors for {len(priors)} of {len(ids)} players -> {OUT}")
