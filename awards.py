#!/usr/bin/env python3
"""Settle each mini-league's weekly honours once a gameweek is final, and keep them (history/awards.json).

Runs in the refresh after crowd.py (scripts/refresh.py). It does nothing until FPL marks the latest gameweek finished
and data_checked (bonus confirmed). Then, for every league crowd.py tracks, it fetches each tracked manager's history
(points, hits), transfer records (who came in and went out), and picks (XI, chip, FPL's confirmed automatic subs), plus
every player's points that gameweek, and works out the eight awards with league_awards.py.

Settled results are kept and never recalculated, so a later gameweek or a manager joining or leaving the league can't
rewrite them. A league-gameweek that is already in the file is skipped (--force recalculates).

Biggest Climber needs FPL's official league ranks before and after the gameweek. FPL's standings only carry the current
rank and the previous one, so they are used only while they belong to the settled gameweek: every tracked manager's
standings total must equal his history total for it and no later gameweek may have started. If they don't match yet,
that league waits for the next run; if the next gameweek has already begun, the week is saved with Climber unavailable.

--backfill also settles earlier gameweeks for the league's managers as they are now (marked "backfill"): their league
ranks can't be recovered, so Climber is unavailable there, and managers who left the league since are missing.

Missing / failed requests: a manager whose history, picks or transfers didn't download is left out of the awards that
need them; the result records how many managers each award covered. If FPL gives no data for the gameweek's players,
nothing is saved. An unreadable history/awards.json stops the run without touching it (it can't be rebuilt).

Usage: python3 awards.py [TEAM_ID] [--backfill] [--force]
"""
import json, os, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

import league_awards

API = "https://fantasy.premierleague.com/api"
HERE = os.path.dirname(os.path.abspath(__file__))
TEAM_ID = int(next((a for a in sys.argv[1:] if a.isdigit()), os.environ.get("FPL_TEAM_ID", 8122679)))
OUT = os.path.join(HERE, "history", "awards.json")
CROWD = os.path.join(HERE, "crowd", "latest.json")
POS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
FAILED = []
SMALL_LEAGUE = 70   # crowd.py: leagues up to this size are tracked in full


def get(path, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(API + path, headers={"User-Agent": "Mozilla/5.0 fpl-lab"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 + 3 * i)
        except Exception:
            time.sleep(2 + 3 * i)
    FAILED.append(path)
    return None


def pmap(fn, items, workers=8):
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(fn, items))


def load_store():
    try:
        with open(OUT) as f:
            st = json.load(f)
        if not (isinstance(st, dict) and isinstance(st.get("leagues"), dict)):
            raise ValueError("unexpected shape")
        return st
    except FileNotFoundError:
        return {"version": 1, "leagues": {}}
    except Exception as ex:
        sys.exit(f"awards: history/awards.json unreadable ({ex}); not touching it")


def official_ranks(lg, members, hist_of, G, cur_is_g):
    """{entry: (rank, last_rank)} when FPL's standings provably belong to gameweek G, else (None, why).
    A league that is fully tracked must also be comparable: everyone had a previous rank (nobody joined this week)."""
    if not cur_is_g:
        return None, "The next gameweek had started before this week's league ranks were saved."
    rows = {}
    pages = {1}
    if lg["size"] > SMALL_LEAGUE:            # big league: page 1 (top 10) and the page around your rank, as crowd.py
        pages.add(max(1, -(-(lg.get("my_rank") or 1) // 50)))
    elif lg["size"] > 50:
        pages.add(2)
    for pg in sorted(pages):
        d = get(f"/leagues-classic/{lg['id']}/standings/?page_standings={pg}")
        if not d:
            return None, "FPL's league standings didn't download."
        for r in d["standings"]["results"]:
            rows[r["entry"]] = r
    out = {}
    for m in members:
        r, h = rows.get(m["entry"]), hist_of(m["entry"], G)
        if not r or not h:
            continue
        if r["total"] != h["total_points"]:
            return False, "FPL's league standings haven't caught up with this gameweek yet."
        out[m["entry"]] = (r["rank"], r["last_rank"])
    if lg["size"] == len(members) and any(not v[1] for v in out.values()):
        return None, "A manager joined the league this gameweek, so the ranks before and after aren't comparable."
    return out, None


def main():
    backfill, force = "--backfill" in sys.argv, "--force" in sys.argv
    boot = get("/bootstrap-static/")
    if not boot:
        sys.exit("awards: bootstrap-static failed")
    events = boot["events"]
    settled = [e["id"] for e in events if e["finished"] and e.get("data_checked")]
    if not settled:
        print("awards: no settled gameweek yet"); return
    G = max(settled)
    cur = next((e["id"] for e in events if e["is_current"]), None)
    try:
        crowd = json.load(open(CROWD))
        leagues = crowd["leagues"]
    except Exception as ex:
        print(f"awards: no league sample ({ex}); nothing to settle"); return
    store = load_store()
    gws_for = lambda: list(range(1, G + 1)) if backfill else [G]
    todo = []   # (league, gw)
    for lg in leagues:
        have = store["leagues"].get(str(lg["id"]), {}).get("gws", {})
        for g in gws_for():
            if force or str(g) not in have:
                todo.append((lg, g))
    if not todo:
        print(f"awards: GW{G} already settled for every league"); return

    pos = {e["id"]: POS[e["element_type"]] for e in boot["elements"]}
    team = {e["id"]: e["team"] for e in boot["elements"]}
    name = {e["id"]: e["web_name"] for e in boot["elements"]}
    entries = sorted({m["entry"] for lg, _ in todo for m in lg["members"]})
    gws = sorted({g for _, g in todo})
    t0 = time.time()
    hist = dict(pmap(lambda e: (e, get(f"/entry/{e}/history/")), entries))
    trans = dict(pmap(lambda e: (e, get(f"/entry/{e}/transfers/")), entries))
    need_picks = sorted({(m["entry"], g) for lg, g in todo for m in lg["members"]})
    picks = dict(pmap(lambda eg: (eg, get(f"/entry/{eg[0]}/event/{eg[1]}/picks/")), need_picks, workers=10))
    live = {}
    for g in gws:
        d = get(f"/event/{g}/live/")
        if d and d.get("elements"):
            live[g] = {x["id"]: x["stats"]["total_points"] for x in d["elements"]}

    def hist_of(e, g):
        h = hist.get(e)
        return next((r for r in (h or {}).get("current", []) if r["event"] == g), None) if h else None

    saved = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    n_new = 0
    for lg, g in todo:
        if g not in live:
            print(f"awards: no player points for GW{g}; not settling it"); continue
        members = [{"entry": m["entry"], "player": m["player"]} for m in lg["members"]]
        inputs = {}
        for m in members:
            e = m["entry"]
            tx = trans.get(e)
            chips = (hist.get(e) or {}).get("chips", [])
            inputs[e] = {"hist": hist_of(e, g), "picks": picks.get((e, g)),
                         "transfers": [t for t in tx if t["event"] == g] if tx is not None else None,
                         "chip": next((c["name"] for c in chips if c["event"] == g), None)}
        # a request that failed (not a 404) for one of this league's managers: try the current week again next run rather
        # than keep it with a manager missing; a past week (backfill, or the next gameweek has begun) is kept as it is
        failed = [e for e in members if any(f"/entry/{e['entry']}/" in p for p in FAILED)]
        if failed and g == G and cur == G:
            print(f"awards: {lg['name']} GW{g}: {len(failed)} managers' data failed to download. Trying again next run."); continue
        ranks, why = None, None
        source = "settled" if g == G else "backfill"
        if g == G:
            ranks, why = official_ranks(lg, members, hist_of, G, cur == G)
            if ranks is False:
                print(f"awards: {lg['name']} GW{g}: {why} Trying again next run."); continue
        else:
            why = "Rebuilt later from the league's current managers: FPL doesn't keep earlier league ranks."
        res = league_awards.league_awards(members, g, inputs, {"pts": live[g], "pos": pos, "team": team, "name": name},
                                          ranks=ranks, size=lg["size"])
        if ranks is None:
            res["awards"]["climber"]["why"] = why
        res.update({"source": source, "saved": saved, "members": [[m["entry"], m["player"]] for m in members],
                    "league": lg["name"], "size": lg["size"]})
        L = store["leagues"].setdefault(str(lg["id"]), {"name": lg["name"], "gws": {}})
        L["name"] = lg["name"]
        L["gws"][str(g)] = res
        n_new += 1
    store["updated"] = saved
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        json.dump(store, f, separators=(",", ":"), sort_keys=True)
    os.replace(tmp, OUT)
    print(f"awards: settled {n_new} league-gameweeks up to GW{G} in {round(time.time() - t0)}s"
          + (f", {len(FAILED)} requests failed" if FAILED else ""))


if __name__ == "__main__":
    main()
