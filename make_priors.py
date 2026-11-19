#!/usr/bin/env python3
"""Download every player's previous-season totals and save per-90 priors to priors.json.
Run occasionally (new signings appear during the season).

Seasons (FL-113): only the two calendar seasons before the current one count (2025/26 and 2024/25 in 2026/27), weighted
2:1 for the more recent, the same rule archive.py uses for the backtests. A player's last two Premier League seasons
used to count however old they were (2015/16 for one player on 9 Nov 2026), and FPL's xG is 0 before 2022/23.
start_rate (FL-082): his share of his club's 38 league games started, over the same seasons and weights. It used to be
summed and dropped, so fplmodel fell back to a guess from minutes without saying so.
Missing / late / ambiguous:
  - a player with no Premier League minutes in either season gets no prior (the model's positional prior stands in);
  - a counted season with no "starts" field: no start_rate for that player (never estimated from minutes here);
    fplmodel then uses its minutes proxy, and validate.py warns how many priors lack it;
  - a season name that can't be read is left out, never guessed;
  - FPL xG doesn't exist before 2022/23 (XG_FIRST): such a season never counts, even if the window is changed;
  - defensive contributions (FL-176): FPL's history_past carries a defensive_contribution field for every season, but it
    is 0 for everyone before 2024/25 (DC_FIRST; checked 19 Nov 2026: 0 for all 900+ minute outfielders in 2021/22-2023/24,
    none at 0 in 2024/25, which FPL backfilled at 7.2 DEF / 8.5 MID per 90 against 7.8 / 8.5 in 2025/26). A season before
    DC_FIRST, or one with the field missing, counts as "no DefCon recorded", never as 0 DefCon: dc90 is DefCon over the
    minutes of recorded seasons only, and "dc_mins" (same per-season scale and weights as "mins") says how many minutes
    that is. dc_mins 0 = no recorded season: dc90 is 0 and fplmodel gives the DefCon prior no weight.
  - failed downloads: if more than MAX_FAILED of the players couldn't be fetched, or the new file would hold fewer than
    MIN_KEPT of the previous file's priors, nothing is written and the script exits 1, so the Priors workflow fails
    and the last good priors.json stays (a shrinking file used to be written without a word).
"""
import json, os, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

API = "https://fantasy.premierleague.com/api"
XG_FIRST = 2022     # first season (start year) with FPL expected goals
DC_FIRST = 2024     # first season (start year) whose defensive_contribution in history_past is real (FL-176)
MAX_FAILED = 0.02   # share of players whose summary may fail to download
MIN_KEPT = 0.85     # new prior count must be at least this share of the previous file's


def get(path):
    for i in range(4):
        try:
            req = urllib.request.Request(API + path, headers={"User-Agent": "Mozilla/5.0 fpl-lab"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:
            time.sleep(2 + 3 * i)
    return None


def start_year(name):
    """'2025/26' -> 2025; None if the name can't be read."""
    try:
        return int(str(name)[:4])
    except (TypeError, ValueError):
        return None


def dc_recorded(s):
    """FL-176: True when this history_past season's defensive_contribution is real (from DC_FIRST, field present)."""
    y = start_year(s.get("season_name"))
    return y is not None and y >= DC_FIRST and s.get("defensive_contribution") is not None


def window(current_start):
    """The seasons that count for a season starting in `current_start`: the two before it, oldest first."""
    return [y for y in (current_start - 2, current_start - 1) if y >= XG_FIRST]


def summarise(history_past, current_start):
    """Per-90 prior from FPL's history_past rows, or None. Weights 1:2 (older:newer), as before."""
    by_year = {start_year(s.get("season_name")): s for s in history_past or []}
    seasons = [(wt, by_year[y]) for wt, y in zip((1.0, 2.0), window(current_start)) if y in by_year and by_year[y]["minutes"] > 0]
    if not seasons:
        return None
    tot = {k: 0.0 for k in ("minutes", "xg", "xa", "bonus", "saves", "dc", "dc_min", "yc", "pts", "starts")}
    for wt, s in seasons:
        tot["minutes"] += wt * s["minutes"]
        tot["xg"] += wt * float(s["expected_goals"])
        tot["xa"] += wt * float(s["expected_assists"])
        tot["bonus"] += wt * s["bonus"]
        tot["saves"] += wt * s["saves"]
        if dc_recorded(s):   # FL-176: a season without real DefCon adds neither DefCon nor DefCon minutes
            tot["dc"] += wt * s["defensive_contribution"]
            tot["dc_min"] += wt * s["minutes"]
        tot["yc"] += wt * s["yellow_cards"]
        tot["pts"] += wt * s["total_points"]
        tot["starts"] += wt * s.get("starts", 0)
    m = tot["minutes"]
    w = sum(wt for wt, _ in seasons)
    last = seasons[-1][1]
    has_starts = all("starts" in s for _, s in seasons)
    return {
        **({"start_rate": min(1.0, tot["starts"] / (38 * w))} if has_starts else {}),
        "season": last["season_name"], "mins": round(m / w), "dc_mins": round(tot["dc_min"] / w),
        "xg90": tot["xg"] / m * 90, "xa90": tot["xa"] / m * 90, "bonus90": tot["bonus"] / m * 90,
        "saves90": tot["saves"] / m * 90, "dc90": tot["dc"] / tot["dc_min"] * 90 if tot["dc_min"] else 0.0, "yc90": tot["yc"] / m * 90,
        "pts90": tot["pts"] / m * 90, "last_pts": last["total_points"], "last_mins": last["minutes"],
        "last_xgi": float(last["expected_goal_involvements"]),
    }


def check_counts(new, previous, failed, total):
    """Raise when the download looks broken: too many players failed, or the file would shrink sharply."""
    if total and failed / total > MAX_FAILED:
        raise SystemExit(f"priors: {failed} of {total} player summaries failed to download; keeping the previous file")
    if previous and new < MIN_KEPT * previous:
        raise SystemExit(f"priors: {new} priors against {previous} in the previous file (below {MIN_KEPT:.0%}); "
                         f"keeping the previous file")


def main(out):
    boot = get("/bootstrap-static/")
    if not boot:
        raise SystemExit("priors: bootstrap-static failed to download; keeping the previous file")
    current = int(min(e["deadline_time"] for e in boot["events"])[:4])
    ids = [e["id"] for e in boot["elements"]]
    with ThreadPoolExecutor(6) as ex:
        raw = dict(zip(ids, ex.map(lambda pid: get(f"/element-summary/{pid}/"), ids)))
    failed = sum(1 for d in raw.values() if d is None)
    res = {pid: summarise(d.get("history_past"), current) for pid, d in raw.items() if d}
    priors = {str(k): {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in v.items()} for k, v in res.items() if v}
    try:
        with open(out) as f:
            previous = len(json.load(f).get("players", {}))
    except (OSError, ValueError, AttributeError):
        previous = 0   # first run or unreadable: nothing to compare against
    check_counts(len(priors), previous, failed, len(ids))
    tmp = out + ".tmp"
    json.dump({"built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "seasons": window(current), "players": priors},
              open(tmp, "w"), separators=(",", ":"))
    os.replace(tmp, out)
    print(f"priors for {len(priors)} of {len(ids)} players from seasons starting {window(current)} -> {out} "
          f"({failed} downloads failed)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "priors.json")
