"""Late-selling inputs for the xMins B model: the per-round transfer history cache and the live next-GW inputs.

history/sell_history.json (committed by the Refresh workflow with the rest of history/):
  {"season": first deadline date of the season, "through": last round cached, "fetched": ISO time,
   "players": {"pid": [[round, transfers_in, transfers_out, selected], ...]},     # element-summary history rows
   "last_attempt": ISO time, "last_error": text or null}
It is refreshed ONCE per gameweek, after that gameweek has FINISHED (bootstrap event "finished"), with one
element-summary call per player (~670 calls, ~20 s with 8 threads). Not right after the deadline: a round's history
row (and its `selected`, the next window's owners-before) only exists once his match has been played. A failed or
incomplete refresh keeps the old cache, records last_error and waits RETRY_H hours before trying again.

live(...) decides whether B may run for the next gameweek and returns its inputs. B is ON only when all hold:
  - the cache exists, is this season's and reaches the gameweek just finished (next_gw - 1);
  - the live builder matches the training builder on the cache (xmins.selftest on the last two rounds);
  - the deadline hasn't passed and is at most SELL_WINDOW_H hours away (partial window, see below);
  - at least MIN_COVER of likely starters (started his club's last match) have a sell_share.
Otherwise the next gameweek uses A, and the reason is returned as "off: <reason>" with a kind:
  "wait"  normal parts of the week (window still open, gameweek in progress, deadline passed): no warning;
  "fault" missing / stale / unreadable cache, failed self-test, low coverage: validate.py warns on the Health page.

Partial window: transfers_in_event / transfers_out_event count the window so far. B was trained on complete
windows; a part-window sell_share is smaller than the final one, so B would under-react and slightly raise start
chances for players not (yet) sold. Nothing is rescaled (one logged gameweek, GW9 2026/27, isn't enough to test a
rescale): B is simply not used until SELL_WINDOW_H hours before the deadline. In the GW9 transfer log, the share of
the final net selling (players sold by 20k+) already done was 66% at 22 h, 81% at 12 h, 89% at 3.5 h before the
deadline. Backtests (backtest.py, bench.py) use complete windows, i.e. what the last pre-deadline build sees.
"""
import datetime as dt, json, math, os
from concurrent.futures import ThreadPoolExecutor

import xmins

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "history", "sell_history.json")
SELL_WINDOW_H = float(os.environ.get("SELL_WINDOW_H", 12))   # env override for local testing only
RETRY_H = 2
MIN_COVER = 0.9


def _now():
    return dt.datetime.now(dt.timezone.utc)


def _parse(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def season_key(boot):
    return min(e["deadline_time"] for e in boot["events"] if e.get("deadline_time"))[:10]


def load(path=PATH):
    """The cache dict, or None if missing. Unreadable -> raises (the caller reports it)."""
    if not os.path.exists(path):
        return None
    with open(path) as f:
        c = json.load(f)
    if not isinstance(c.get("players"), dict):
        raise ValueError("no 'players' table")
    return c


def rows_of(cache):
    """{pid: [(round, in, out, selected)]} from the cache."""
    return {int(p): [tuple(r) for r in rs] for p, rs in cache["players"].items()}


def _write(c, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(c, f, separators=(",", ":"))
    os.replace(tmp, path)


def refresh(boot, get, path=PATH, now=None):
    """Refresh the cache if due (see module docstring). get(path) fetches the FPL API. Returns a short note."""
    now = now or _now()
    cur = next((e for e in boot["events"] if e["is_current"]), None)
    if not cur or not cur["finished"]:
        return "not due (gameweek in progress)"
    try:
        old = load(path)
    except Exception as ex:
        return f"cache unreadable, not refreshing: {ex}"   # never overwrite a file we can't read
    season = season_key(boot)
    if old and old.get("season") == season and (old.get("through") or 0) >= cur["id"]:
        return "not due"
    if old and old.get("last_attempt") and now - _parse(old["last_attempt"]) < dt.timedelta(hours=RETRY_H) \
            and old.get("last_error"):
        return f"waiting to retry ({old['last_error']})"
    ids = [e["id"] for e in boot["elements"]]
    err = None
    try:
        with ThreadPoolExecutor(8) as ex:
            res = list(ex.map(lambda i: (i, get(f"/element-summary/{i}/")), ids))
        players = {}
        for pid, d in res:
            seen, rs = set(), []
            for h in d.get("history", []):
                if h["round"] in seen:   # doubles: one row per round (same window)
                    continue
                seen.add(h["round"])
                rs.append([h["round"], int(h["transfers_in"]), int(h["transfers_out"]), int(h["selected"])])
            players[str(pid)] = rs
        through = max((r[0] for rs in players.values() for r in rs), default=0)
        n_cur = sum(1 for rs in players.values() if any(r[0] == cur["id"] for r in rs))
        if through < cur["id"] or n_cur < 0.5 * len(ids):
            raise ValueError(f"history rows for GW{cur['id']} not published yet ({n_cur} players)")
    except Exception as ex:
        err = str(ex)[:200]
    if err:
        c = dict(old) if old and old.get("season") == season else {"season": season, "players": {}, "through": 0}
        c.update(last_attempt=now.isoformat(timespec="seconds"), last_error=err)
        _write(c, path)
        return f"refresh failed: {err}"
    _write({"season": season, "through": cur["id"], "fetched": now.isoformat(timespec="seconds"),
            "last_attempt": now.isoformat(timespec="seconds"), "last_error": None, "players": players}, path)
    return f"refreshed through GW{cur['id']} ({len(players)} players)"


def history_sell(boot, path=PATH):
    """Selling inputs for finished rounds (backtests and the build's re-runs of past weeks), complete windows.
    Returns (sell dict for fplmodel.prepare, note). No usable cache -> (None, reason): B is then off for every week."""
    try:
        c = load(path)
    except Exception as ex:
        return None, f"cache unreadable: {ex}"
    if not c or not c["players"]:
        return None, f"no selling history ({os.path.relpath(path, HERE)})"
    if c.get("season") != season_key(boot):
        return None, f"selling history is from another season ({c.get('season')})"
    rows = rows_of(c)
    vals = xmins.sell_from_rounds(rows)
    gws = sorted({r[0] for rs in rows.values() for r in rs if r[0] <= c["through"]})
    return {"values": vals, "gws": gws}, f"selling history GW1-{c['through']}"


def live(boot, pstats, fixtures, cache_note=None, path=PATH, now=None):
    """Selling inputs for the build: past rounds (complete) + the next gameweek's open window.
    Returns (sell dict for prepare, info). info = {"status": "on" | "off: <reason>", "kind": "on"|"wait"|"fault",
    "gw", "through", "coverage", "starters", "hours_left", "window_h", "own_fallback", "cache"}."""
    now = now or _now()
    events = boot["events"]
    cur = next((e for e in events if e["is_current"]), None)
    nxt = next((e for e in events if e["is_next"]), None)
    info = {"gw": nxt["id"] if nxt else None, "through": None, "coverage": None, "starters": None,
            "hours_left": None, "window_h": SELL_WINDOW_H, "own_fallback": None, "cache": cache_note}

    def off(kind, why, sell=None):
        info.update(status=f"off: {why}", kind=kind)
        return sell, info

    if not nxt:
        return off("wait", "no next gameweek")
    hist, note = history_sell(boot, path)
    if hist is None:
        return off("fault", note)
    c = load(path)
    info["through"] = c["through"]
    gw = nxt["id"]
    if c["through"] < gw - 1:
        if cur and not cur["finished"]:
            return off("wait", f"GW{cur['id']} in progress; selling history to GW{c['through']} (refreshed once it finishes)", hist)
        return off("fault", f"selling history stale (to GW{c['through']}, needs GW{gw - 1})"
                   + (f"; last refresh error: {c['last_error']}" if c.get("last_error") else ""), hist)
    rows = rows_of(c)
    bad = xmins.selftest(rows, sorted({r[0] for rs in rows.values() for r in rs})[-2:])
    if bad:
        return off("fault", f"live and training selling inputs differ for {bad} player-rounds", hist)
    managers = boot.get("total_players") or 0
    if managers <= 0:
        return off("fault", "bootstrap has no total_players", hist)
    window, fb = {}, 0
    for e in boot["elements"]:
        tin, tout = e.get("transfers_in_event"), e.get("transfers_out_event")
        if tin is None or tout is None:
            continue
        own_now = float(e.get("selected_by_percent") or 0) / 100 * managers
        if not any(r[0] < gw for r in rows.get(e["id"], ())):
            fb += 1   # no earlier row: owners-before from selected_by_percent (rounded to 0.1%)
        window[e["id"]] = (int(tin), int(tout), own_now)
    info["own_fallback"] = fb
    nxt_vals = xmins.sell_next(rows, gw, window, managers)
    vals = hist["values"]
    for pid, v in nxt_vals.items():
        vals.setdefault(pid, {})[gw] = v
    sell = {"values": vals, "gws": list(hist["gws"])}
    # coverage: likely starters = started his club's last finished match (live data)
    team = {e["id"]: e["team"] for e in boot["elements"]}
    last = {}
    for f in fixtures:
        if f.get("event") and f["event"] < gw and (f.get("finished") or f.get("finished_provisional")):
            for t in (f["team_h"], f["team_a"]):
                last[t] = max(last.get(t, 0), f["event"])
    starters = [pid for pid in team if last.get(team[pid]) and
                (pstats.get(pid, {}).get(last[team[pid]]) or {}).get("starts", 0) > 0]
    ok = [pid for pid in starters if not math.isnan(nxt_vals.get(pid, [math.nan])[0])]
    info["starters"] = len(starters)
    info["coverage"] = round(len(ok) / len(starters), 3) if starters else None
    dl = _parse(nxt["deadline_time"])
    info["hours_left"] = round((dl - now).total_seconds() / 3600, 1)
    if not starters or len(ok) < MIN_COVER * len(starters):
        return off("fault", f"selling inputs for only {len(ok)} of the {len(starters)} players who started their club's last match", sell)
    if now >= dl:
        return off("wait", "deadline passed; waiting for FPL to open the next gameweek", sell)
    if info["hours_left"] > SELL_WINDOW_H:
        return off("wait", f"transfer window open; used from {SELL_WINDOW_H:g} h before the deadline", sell)
    sell["gws"] = sorted(set(sell["gws"]) | {gw})
    info.update(status="on", kind="on")
    return sell, info


if __name__ == "__main__":
    # python3 sell_history.py --selftest : live builder (sell_next) vs training builder (sell_from_rounds) on every
    # round of this season's cache and of each archive season already downloaded; exits 1 on any difference.
    import sys
    import archive
    bad = 0
    try:
        c = load()
    except Exception as ex:
        c = None
        print("cache unreadable:", ex)
    if c and c["players"]:
        n = xmins.selftest(rows_of(c))
        print(f"cache GW1-{c['through']}: {n} mismatches")
        bad += n
    for s in ("2022-23", "2023-24", "2024-25", "2025-26"):
        if os.path.exists(os.path.join(HERE, "archive", s, "merged_gw.csv")):
            n = xmins.selftest(archive.load_transfers(s))
            print(f"archive {s}: {n} mismatches")
            bad += n
    sys.exit(1 if bad else 0)
