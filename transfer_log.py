"""Pre-deadline transfer log: history/transfers_gw{N}.json (see README).

FPL keeps no history of transfer counts within a week, so we sample them live and
can later test whether late selling predicts that a likely starter won't start.

Format (integers only, written compactly):
  {"gw": N, "deadline": "...Z",
   "players": [pid, ...],                 # append-only; order never changes
   "owned": {"pid": selected_by_percent * 10 at the first snapshot the player appeared in},
   "snaps": [{"t": "2026-10-30T12:00Z", "in": [...], "out": [...], "flags": {"pid": [status, chance]}}]}
"in"/"out" are transfers_in_event/transfers_out_event (cumulative since the previous
deadline), aligned to "players". A player who qualifies later is appended to "players",
so older snapshots can have shorter arrays: a missing index means unknown, not zero.
"flags" lists only tracked players with status != "a" or chance_of_playing_next_round < 100.
"""
import json, os, datetime as dt

MIN_OWNED = 0.5        # selected_by_percent
MIN_OUT = 2000         # transfers_out_event


def _parse(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def _due(last, now, deadline):
    """Is a new snapshot due? 6 h normally, 1 h inside 48 h, 25 min inside 3 h of the deadline."""
    left = deadline - now
    gap = dt.timedelta(minutes=25) if left <= dt.timedelta(hours=3) else \
        dt.timedelta(hours=1) if left <= dt.timedelta(hours=48) else dt.timedelta(hours=6)
    return now - last >= gap


def update(boot, next_ev, now, path):
    """Add a snapshot to the log at `path` if one is due. Returns True if the file was written.
    Never raises, and never overwrites a log that exists but cannot be read."""
    try:
        if not next_ev:
            return False
        deadline = _parse(next_ev["deadline_time"])
        if now >= deadline:
            return False
        log = None
        try:
            with open(path) as f:
                log = json.load(f)
            if not isinstance(log.get("players"), list) or not isinstance(log.get("snaps"), list):
                raise ValueError("no 'players'/'snaps'")
        except FileNotFoundError:
            log = {"gw": next_ev["id"], "deadline": next_ev["deadline_time"], "players": [], "snaps": [], "owned": {}}
        except Exception as ex:
            print(f"{path} unreadable, not updating it:", ex)
            return False
        if log["snaps"] and not _due(_parse(log["snaps"][-1]["t"]), now, deadline):
            return False

        els = {e["id"]: e for e in boot["elements"]}
        known = set(log["players"])
        for pid in sorted(els):
            e = els[pid]
            own = float(e["selected_by_percent"] or 0)
            if pid not in known and (own >= MIN_OWNED or (e["transfers_out_event"] or 0) >= MIN_OUT):
                log["players"].append(pid)
                log["owned"][str(pid)] = round(own * 10)
        snap = {"t": now.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
                "in": [int(els[p]["transfers_in_event"] or 0) if p in els else 0 for p in log["players"]],
                "out": [int(els[p]["transfers_out_event"] or 0) if p in els else 0 for p in log["players"]]}
        flags = {}
        for p in log["players"]:
            e = els.get(p)
            if e and (e["status"] != "a" or (e["chance_of_playing_next_round"] is not None and e["chance_of_playing_next_round"] < 100)):
                flags[str(p)] = [e["status"], e["chance_of_playing_next_round"]]
        snap["flags"] = flags
        log["snaps"].append(snap)

        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(log, f, separators=(",", ":"))
        os.replace(tmp, path)   # atomic, as for status.json
        return True
    except Exception as ex:
        print("transfer log not updated:", ex)
        return False
