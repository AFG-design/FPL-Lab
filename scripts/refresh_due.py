"""Should the 10-minute refresh schedule rebuild now? Prints "run=true" or "run=false" for the Refresh workflow.

The base schedule (hourly at 7 past), pushes and manual runs always rebuild; this decides only for the 10-minute
schedule and an external scheduler sending live_only=true (FL-111):
  - a match is live (kicked off in the last 2.5 hours, or kicks off in the next 10 minutes): every run, so every
    10 minutes;
  - within DEADLINE_WINDOW_H hours before the next deadline: the first run of each half hour, so every 30 minutes;
  - otherwise: the first run of each hour.
Missing / late / ambiguous: if FPL can't be reached, no match counts as live (as before) but the deadline is unknown,
so it rebuilds on the half hour (errs on fresher data near a deadline it can't see). No next deadline (season over):
hourly.
"""
import datetime as dt
import json
import sys
import urllib.request

DEADLINE_WINDOW_H = 6   # same window as validate.py's refresh-gap warning (GAP_WINDOW_H)
API = "https://fantasy.premierleague.com/api"


def _t(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def due(now, fixtures, events):
    """now: aware datetime; fixtures: FPL /fixtures/ list (None if unreachable); events: bootstrap events (None if
    unreachable). Returns (run, reason)."""
    if fixtures and any(f.get("kickoff_time") and dt.timedelta(minutes=-10) <= now - _t(f["kickoff_time"]) <= dt.timedelta(hours=2.5)
                        for f in fixtures):
        return True, "match live"
    if events is None:
        near = True
    else:
        nxt = next((e for e in events if e.get("is_next") and e.get("deadline_time")), None)
        near = nxt is not None and dt.timedelta(0) < _t(nxt["deadline_time"]) - now <= dt.timedelta(hours=DEADLINE_WINDOW_H)
    if near:
        return now.minute % 30 < 10, "deadline window" if events is not None else "deadline unknown"
    return now.minute < 10, "hourly"


def _get(path):
    try:
        req = urllib.request.Request(API + path, headers={"User-Agent": "Mozilla/5.0 fpl-lab"})
        return json.load(urllib.request.urlopen(req, timeout=20))
    except Exception:
        return None


if __name__ == "__main__":
    boot = _get("/bootstrap-static/")
    run, why = due(dt.datetime.now(dt.timezone.utc), _get("/fixtures/"), boot.get("events") if isinstance(boot, dict) else None)
    print(f"run={'true' if run else 'false'}")
    print(f"refresh_due: {why}, run={run}", file=sys.stderr)
