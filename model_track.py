"""The model's track record per gameweek, for the Model page (FL-145). Built only from what was saved before each
deadline (history/), never from today's model, so each number is what the app really said then.

  start_brier: next-GW start chance as the forecast used it (history/deadline_gwN.json "mins", saved from GW10) against
               whether each player started (live data). Players whose club played once that GW (a double's start chance
               is per match). Brier = mean (chance - started)^2; lower is better.
  misses:      next-GW xP (history/proj_gwN.json, saved from GW8) against real points: the count of player-weeks off
               by BIG or more points, and the mean miss, over players projected above 0 or who played.
  downloads:   links to every saved pre-deadline file, so the projections can be checked independently.
  versions:    the model changes adopted between one deadline and the next (docs/model-log.md headings with a date and
               an Adopt decision), so each GW's numbers can be read against the model that made them. A change logged
               on a deadline's own day is counted for the next GW (the log has dates, not times: marked "assumed").
Missing / late: a GW without the file -> no row for that part (the page says from which GW each part starts); a GW
not finished -> not scored. Nothing is estimated.
"""
import datetime as dt
import json
import os
import re

BIG = 6          # points off, either way, for a "big miss"
RAW = "https://raw.githubusercontent.com/AFG-design/FPL-Lab/main/history/"
MONTHS = {m: i for i, m in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}


def _load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def start_brier(hist, finished, live, fixtures, teams_of):
    """[{gw, n, brier, chance, started}] for finished GWs with a deadline snapshot. teams_of: {player id: club}."""
    nfx = {}
    for f in fixtures:
        if f.get("event"):
            for t in (f["team_h"], f["team_a"]):
                nfx[(t, f["event"])] = nfx.get((t, f["event"]), 0) + 1
    out = []
    for g in finished:
        snap = _load(os.path.join(hist, f"deadline_gw{g}.json"))
        if not snap or g not in live:
            continue
        stats = {x["id"]: x["stats"] for x in live[g]["elements"]}
        rows = []
        for pid, m in (snap.get("mins") or {}).items():
            pid = int(pid)
            if not m or m[0] is None or nfx.get((teams_of.get(pid), g)) != 1 or pid not in stats:
                continue
            rows.append((min(1.0, m[0]), 1.0 if stats[pid]["starts"] > 0 else 0.0))
        if rows:
            n = len(rows)
            out.append({"gw": g, "n": n, "brier": round(sum((c - s) ** 2 for c, s in rows) / n, 4),
                        "chance": round(sum(c for c, _ in rows) / n, 3), "started": round(sum(s for _, s in rows) / n, 3)})
    return out


def misses(hist, finished, live, big=BIG):
    """[{gw, n, big, mae}] for finished GWs with a projection snapshot."""
    out = []
    for g in finished:
        snap = _load(os.path.join(hist, f"proj_gw{g}.json"))
        if not snap or g not in live:
            continue
        real = {x["id"]: (x["stats"]["total_points"], x["stats"]["minutes"]) for x in live[g]["elements"]}
        proj = {int(k): v[0] for k, v in snap.get("players", {}).items()}
        ids = {i for i, x in proj.items() if x > 0} | {i for i, (p, m) in real.items() if m > 0}
        rows = [(proj.get(i, 0.0), real.get(i, (0, 0))[0]) for i in ids]
        if rows:
            out.append({"gw": g, "n": len(rows), "big": sum(1 for x, a in rows if abs(a - x) >= big),
                        "mae": round(sum(abs(a - x) for x, a in rows) / len(rows), 3)})
    return out


def downloads(hist):
    """[{gw, proj, deadline}] raw GitHub links to each saved file (None when that file wasn't saved for the GW)."""
    gws = set()
    for f in os.listdir(hist):
        m = re.fullmatch(r"(proj|deadline)_gw(\d+)\.json", f)
        if m:
            gws.add(int(m.group(2)))
    return [{"gw": g, "proj": RAW + f"proj_gw{g}.json" if os.path.exists(os.path.join(hist, f"proj_gw{g}.json")) else None,
             "deadline": RAW + f"deadline_gw{g}.json" if os.path.exists(os.path.join(hist, f"deadline_gw{g}.json")) else None}
            for g in sorted(gws)]


NOT_LIVE = ("don't adopt", "not adopted", "rejected", "no change", "test only", "shadow", "neutral", "no live change",
            "nothing adopted", "neither adopted", "research")


def adopted(log_text):
    """[(date, label)] for dated model-log headings that changed what the live app does: an adopt decision (Adopt,
    Adopt as Marginal, "adopted:"), or an FL- fix whose heading doesn't say it changed nothing live (NOT_LIVE)."""
    out = []
    for m in re.finditer(r"^## (\d{1,2}) (\w{3}) (\d{4}) — (.+)$", log_text, re.M):
        title = m.group(4)
        low = title.lower()
        if any(w in low for w in NOT_LIVE):
            continue
        if not ("(adopt" in low or "adopted:" in low or "; adopt" in low or re.match(r"fl-\d+", low)):
            continue
        try:
            d = dt.date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))
        except (KeyError, ValueError):
            continue
        out.append((d, re.sub(r"\s*\(.*\)\s*$", "", title)))
    return sorted(out)


def versions(log_text, deadlines):
    """[{gw, deadline, changes, assumed}]: changes adopted after the previous deadline's day and up to (not including)
    this deadline's day; a change logged on a deadline's day goes to the next GW, marked assumed.
    deadlines: [(gw, ISO deadline)] in order."""
    ch = adopted(log_text)
    out, prev = [], None
    for g, iso in deadlines:
        day = dt.date.fromisoformat(iso[:10])
        rows = [(d, t) for d, t in ch if (prev is None or d >= prev) and d < day]
        out.append({"gw": g, "deadline": iso, "changes": [t for _, t in rows],
                    "assumed": any(prev is not None and d == prev for d, _ in rows)})
        prev = day
    return out
