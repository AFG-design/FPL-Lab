#!/usr/bin/env python3
"""Sample what other managers own, once per gameweek (picks only become public
after the deadline).

- Top 10k: every 5th manager in the overall top 10,000 (2,000 teams)
- Your rank band: the 500 managers ranked around you
- Mini-leagues: all members of small private leagues; top 10 and your neighbours in big ones

Writes crowd/latest.json. Exits early if that file already covers the current gameweek.
Usage: python3 crowd.py [TEAM_ID] [--force]
"""
import json, os, sys, time, math, urllib.request, urllib.error
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

API = "https://fantasy.premierleague.com/api"
TEAM_ID = int(next((a for a in sys.argv[1:] if a.isdigit()), os.environ.get("FPL_TEAM_ID", 8122679)))
FORCE = "--force" in sys.argv
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crowd", "latest.json")
SMALL_LEAGUE = 70


def get(path, tries=5):
    for i in range(tries):
        try:
            req = urllib.request.Request(API + path, headers={"User-Agent": "Mozilla/5.0 fpl-lab"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 + 4 * i)
        except Exception:
            time.sleep(2 + 4 * i)
    return None


def pmap(fn, items, workers=8):
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(fn, items))


boot = get("/bootstrap-static/")
cur = next((e for e in boot["events"] if e["is_current"]), None)
if not cur:
    print("season not started"); sys.exit(0)
G = cur["id"]
if not FORCE and os.path.exists(OUT):
    try:
        old = json.load(open(OUT))
        if old.get("gw") == G and old.get("complete"):
            print(f"crowd data for GW{G} already built"); sys.exit(0)
    except Exception:
        pass

t0 = time.time()
entry = get(f"/entry/{TEAM_ID}/")
my_rank = entry.get("summary_overall_rank") or 100000


def standings(league, page):
    d = get(f"/leagues-classic/{league}/standings/?page_standings={page}")
    return (d or {}).get("standings", {}).get("results", [])


# ---- samples
top_rows = [r for rows in pmap(lambda p: standings(314, p), range(1, 201)) for r in rows]
top_rows = [r for r in top_rows if r["rank"] <= 10000]
top_sample = [r["entry"] for i, r in enumerate(sorted(top_rows, key=lambda r: r["rank"])) if i % 5 == 0]
mp = max(1, math.ceil(my_rank / 50))
near_rows = [r for rows in pmap(lambda p: standings(314, p), range(max(1, mp - 5), mp + 5)) for r in rows]
near_sample = [r["entry"] for r in near_rows if r["entry"] != TEAM_ID]

# ---- mini-leagues
leagues = []
for lg in entry["leagues"]["classic"]:
    if lg["league_type"] == "s" or lg.get("rank_count", 0) < 2:
        continue  # system leagues (Overall, country, club...) are skipped
    size = lg.get("rank_count") or 0
    rows = []
    if size <= SMALL_LEAGUE:
        rows = standings(lg["id"], 1) + (standings(lg["id"], 2) if size > 50 else [])
    else:
        top = standings(lg["id"], 1)[:10]
        r = lg.get("entry_rank") or 1
        pg = max(1, math.ceil(r / 50))
        around = [x for x in standings(lg["id"], pg) if abs(x["rank"] - r) <= 5]
        seen = set()
        rows = [x for x in top + around if not (x["entry"] in seen or seen.add(x["entry"]))]
    leagues.append({"id": lg["id"], "name": lg["name"], "size": size, "my_rank": lg.get("entry_rank"),
                    "members": [{"entry": x["entry"], "player": x["player_name"], "team": x["entry_name"]} for x in rows]})
rival_ids = {m["entry"] for lg in leagues for m in lg["members"] if m["entry"] != TEAM_ID}

# ---- picks
everyone = sorted(set(top_sample) | set(near_sample) | rival_ids)


def picks(eid):
    d = get(f"/entry/{eid}/event/{G}/picks/")
    if not d:
        return eid, None
    return eid, {"p": [[x["element"], x["multiplier"]] for x in d["picks"]], "chip": d.get("active_chip"),
                 "hits": d["entry_history"]["event_transfers_cost"], "tx": d["entry_history"]["event_transfers"],
                 "pts": d["entry_history"]["points"], "total": d["entry_history"]["total_points"],
                 "bank": d["entry_history"]["bank"], "value": d["entry_history"]["value"]}


all_picks = dict(pmap(picks, everyone, workers=10))


def aggregate(ids):
    got = [all_picks[i] for i in ids if all_picks.get(i)]
    n = len(got)
    own, cap, eo, chips = defaultdict(int), defaultdict(int), defaultdict(float), defaultdict(int)
    for t in got:
        for el, m in t["p"]:
            own[el] += 1
            eo[el] += min(m, 2)  # a Triple Captain is a one-off; count it as a normal captain
            if m >= 2:
                cap[el] += 1
        if t["chip"]:
            chips[t["chip"]] += 1
    pct = lambda d: {str(k): round(100 * v / n, 1) for k, v in d.items()} if n else {}
    return {"n": n, "own": pct(own), "cap": pct(cap), "eo": pct(eo), "chips": pct(chips),
            "hits": round(sum(t["hits"] for t in got) / n, 2) if n else 0,
            "avg_pts": round(sum(t["pts"] for t in got) / n, 1) if n else 0}


near_ranks = [r["rank"] for r in near_rows]
out = {
    "gw": G, "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "complete": True,
    "top10k": aggregate(top_sample),
    "near": dict(aggregate(near_sample), rank_from=min(near_ranks) if near_ranks else None,
                 rank_to=max(near_ranks) if near_ranks else None),
    "leagues": leagues,
    "rivals": {str(i): all_picks[i] for i in rival_ids if all_picks.get(i)},
    "secs": round(time.time() - t0),
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(out, open(OUT, "w"), separators=(",", ":"))
print(f"GW{G}: top10k n={out['top10k']['n']}, near n={out['near']['n']}, leagues {len(leagues)}, "
      f"rivals {len(out['rivals'])}, {out['secs']}s")
