"""Set-piece taker change log: history/setpieces.json (FL-069).

FPL only gives the current penalty, corner and free-kick order, so the changes are logged here and committed with the
rest of history/ by the Refresh workflow. Before FL-069 the list lived only in the published data.json and each build
re-read it from the live site: one failed fetch published an empty list and the history was gone for good.

Format:
  {"now": {"team id": {"pen": [pid, ...], "cor": [...], "fk": [...]}},   # takers at the last change, top 3, in order
   "changes": [{"date": "YYYY-MM-DD", "season": "2026-27", "team": tid, "type": "pen"|"cor"|"fk",
                "old": pid|None, "new": pid|None}],                      # newest change first, at most KEEP kept
   "season": "2026-27", "updated": "...Z"}
The file is only rewritten when a first choice changes (or a team's row is new), so a quiet refresh commits nothing.

Missing, late or ambiguous input (status, shown on Data health and the Stats page):
  - "ok": the file loaded and was compared.
  - "seeded": no file yet (first run, or someone deleted it). The list is taken once from the deployed data.json (the
    old home of the list), compared, and the file written.
  - "seed_failed": no file and the deployed site couldn't be read either. Nothing is written, so the next build tries
    the seed again rather than starting a new, empty history; this build publishes no change list.
  - "unreadable": the file exists but isn't valid. It is never overwritten (the history can't be rebuilt); this build
    publishes the deployed site's list if it can read it, otherwise none, and compares nothing.
  - A team with no row in the log (new file entry) is added without a change: there is nothing to compare it with.
  - New season: FPL renumbers teams and players, so when the log's season differs from this one nothing is compared;
    the takers start afresh and older changes stay in the file (tagged with their season) but aren't published.
    Changes seeded from the deployed site carry no season and are tagged with the current one (they were this
    season's: the list was only ever kept within a season's deploys).
"""
import datetime as dt
import json
import os

KEEP = 300      # changes kept in the file (about three seasons); the site shows the newest PUBLISH
PUBLISH = 30
TYPES = ("pen", "cor", "fk")


def _valid(log):
    return isinstance(log, dict) and isinstance(log.get("now"), dict) and isinstance(log.get("changes"), list)


def _compare(old_now, sp_now, today, season):
    """Changes of first-choice taker, newest first, for teams that are in both tables."""
    out = []
    for tid, row in sp_now.items():
        old = old_now.get(tid)
        if not old:
            continue
        for key in TYPES:
            a, b = (old.get(key) or [None])[0], (row.get(key) or [None])[0]
            if a != b:
                out.append({"date": today, "season": season, "team": int(tid), "type": key, "old": a, "new": b})
    return out


def _write(path, log):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(log, f, separators=(",", ":"))
    os.replace(tmp, path)   # atomic: a crash mid-write can't leave a half-written log


def update(path, sp_now, now, season, fetch_prev):
    """Compare today's takers with the log, write it if anything changed, and return the block data.json publishes:
    {"now", "changes" (newest PUBLISH), "status"}. fetch_prev() returns the deployed data.json (or raises); it is only
    called when the log is missing or unreadable."""
    today = now.date().isoformat()
    try:
        with open(path) as f:
            log = json.load(f)
        if not _valid(log):
            raise ValueError("no 'now' table or 'changes' list")
        status = "ok"
    except FileNotFoundError:
        try:
            prev = (fetch_prev() or {}).get("setpieces") or {}
            log = {"now": prev.get("now") or {}, "season": season,
                   "changes": [dict(c, season=c.get("season") or season) for c in prev.get("changes") or []]}
            status = "seeded"
        except Exception as ex:
            print("set-piece log: no history/setpieces.json and no deployed list to seed it from:", type(ex).__name__)
            return {"now": sp_now, "changes": [], "status": "seed_failed"}
    except Exception as ex:
        print("history/setpieces.json unreadable, not updating it:", ex)
        try:
            shown = ((fetch_prev() or {}).get("setpieces") or {}).get("changes") or []
        except Exception:
            shown = []
        return {"now": sp_now, "changes": shown[:PUBLISH], "status": "unreadable"}

    rollover = log.get("season") not in (None, season)   # no season (pre-season-tag log): same season, compare
    old_now = {} if rollover else log["now"]
    new = _compare(old_now, sp_now, today, season)
    added = [t for t in sp_now if t not in old_now]
    if new or added or status == "seeded" or log.get("season") != season:
        log = {"now": {**old_now, **sp_now}, "season": season, "changes": (new + log["changes"])[:KEEP],
               "updated": now.isoformat(timespec="seconds")}
        _write(path, log)
    shown = [c for c in log["changes"] if c.get("season", season) == season]
    return {"now": sp_now, "changes": shown[:PUBLISH], "status": status}
