#!/usr/bin/env python3
"""FL-115: do regular starters at clubs in Europe start fewer league games around a European match?

    python3 tools/europe_check.py        # needs archive/ (archive.py), raw/ (a local build) and europe_hist.json

The window is the live model's (build.py): a league fixture from 2 days before to 3 days after a European match, not
the same day. A "regular" started at least REG of his club's league games that season (so both groups use the same
definition and nobody is picked by how he did in one group). The ratio is his start rate inside the window over his
rate outside it, pooled over regulars; the live model's cut (0.93) implies 0.93. 95% interval: bootstrap over club
fixtures (a fixture's players move together). Seasons: 2024-25 and 2025-26 from the archive with europe_hist.json
(2025-26 has the Champions League only: its Europa and Conference League files aren't published, so those clubs are
left out rather than counted as "no Europe"); this season from raw/ and europe.json, as the live build reads it.
"""
import csv, datetime as dt, json, os, random
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
REG = 0.6
B = 2000


def in_window(kd, dates):
    return any(-2 <= (kd - d).days <= 3 and (kd - d).days != 0 for d in dates)


def season_rows(season):
    """[(club short, fixture id, kickoff date, pid, started)] from the archive."""
    teams = {r["name"]: r["short_name"] for r in csv.DictReader(open(os.path.join(ROOT, "archive", season, "teams.csv")))}
    out = []
    for r in csv.DictReader(open(os.path.join(ROOT, "archive", season, "merged_gw.csv"), encoding="utf-8", errors="ignore")):
        if not r.get("kickoff_time"):
            continue
        out.append((teams.get(r["team"]), int(r["fixture"]), dt.date.fromisoformat(r["kickoff_time"][:10]), int(r["element"]), int(float(r.get("starts") or 0))))
    return out


def current_rows():
    """This season: every player at a club (his club now, from bootstrap) for each of its finished fixtures, started or
    not (the live file's per-gameweek "starts"), so a regular left out counts as not starting. A double gameweek with
    one start out of two can't be split between the games, so that player-week is left out. Mid-season transfers are
    counted at their current club only for the games they have rows for."""
    raw = os.path.join(ROOT, "raw")
    boot = json.load(open(os.path.join(raw, "bootstrap.json")))
    short = {t["id"]: t["short_name"] for t in boot["teams"]}
    cur = max(e["id"] for e in boot["events"] if e["finished"])
    fx = [f for f in json.load(open(os.path.join(raw, "fixtures.json"))) if f.get("event") and f["event"] <= cur and f.get("kickoff_time")]
    by_team = defaultdict(list)
    for e in boot["elements"]:
        by_team[e["team"]].append(e["id"])
    out = []
    for g in range(1, cur + 1):
        live = {e["id"]: e for e in json.load(open(os.path.join(raw, f"live{g}.json")))["elements"]}
        for t, pids in by_team.items():
            games = [f for f in fx if f["event"] == g and t in (f["team_h"], f["team_a"])]
            for pid in pids:
                st = int((live.get(pid) or {}).get("stats", {}).get("starts") or 0)
                if 0 < st < len(games):
                    continue
                for f in games:
                    out.append((short[t], f["id"], dt.date.fromisoformat(f["kickoff_time"][:10]), pid, 1 if st else 0))
    return out


def measure(rows, euro):
    """euro: {short: [dates]}. Returns (ratio, lo, hi, n_in, n_out) over regulars at clubs with European dates."""
    rows = [r for r in rows if r[0] in euro]
    starts, games, club = defaultdict(int), defaultdict(int), {}
    for c, f, kd, pid, st in rows:
        starts[pid] += st; games[pid] += 1; club[pid] = c
    club_games = defaultdict(set)
    for c, f, kd, pid, st in rows:
        club_games[c].add(f)
    regular = {pid for pid in starts if starts[pid] >= REG * len(club_games[club[pid]])}
    by_fx = defaultdict(lambda: [0, 0, False])   # fixture-club -> [starts, players, in window]
    for c, f, kd, pid, st in rows:
        if pid in regular:
            k = (c, f); by_fx[k][0] += st; by_fx[k][1] += 1; by_fx[k][2] = in_window(kd, euro[c])
    keys = list(by_fx)
    def ratio(ks):
        a = [by_fx[k] for k in ks]
        si, ni = sum(x[0] for x in a if x[2]), sum(x[1] for x in a if x[2])
        so, no = sum(x[0] for x in a if not x[2]), sum(x[1] for x in a if not x[2])
        return (si / ni) / (so / no) if ni and no and so else float("nan")
    r = ratio(keys)
    rnd = random.Random(7)
    bs = sorted(ratio([rnd.choice(keys) for _ in keys]) for _ in range(B))
    n_in = sum(by_fx[k][1] for k in keys if by_fx[k][2]); n_out = sum(by_fx[k][1] for k in keys if not by_fx[k][2])
    return r, bs[int(0.025 * B)], bs[int(0.975 * B)], n_in, n_out, len(regular)


def main():
    hist = json.load(open(os.path.join(ROOT, "europe_hist.json")))
    print(f"start rate of regulars (>= {REG:.0%} of league starts) in the cut's window / outside it; the live cut implies 0.93")
    for season in ("2024-25", "2025-26"):
        euro = {c: [dt.date.fromisoformat(d) for comp in v.values() for d in comp] for c, v in hist["seasons"][season].items()}
        r, lo, hi, ni, no, nr = measure(season_rows(season), euro)
        print(f"  {season}: {r:.3f}  95% CI [{lo:.3f}, {hi:.3f}]  player-games in window {ni}, outside {no}, regulars {nr}")
    live = json.load(open(os.path.join(ROOT, "europe.json")))["competitions"]
    euro = defaultdict(list)
    for comp, c in live.items():
        if c.get("confirmed") is False:
            continue
        for s in c["teams"]:
            euro[s] += [dt.date.fromisoformat(d) for d in c["dates"]]
    r, lo, hi, ni, no, nr = measure(current_rows(), dict(euro))
    print(f"  this season (to date, europe.json): {r:.3f}  95% CI [{lo:.3f}, {hi:.3f}]  in window {ni}, outside {no}, regulars {nr}")


if __name__ == "__main__":
    main()
