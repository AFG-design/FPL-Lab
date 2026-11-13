"""Late-selling inputs for the selling-informed xMins model (xmins.predict_sell; param "xmins_sell").

Managers sell a player before the deadline when they hear he won't start (press conferences, leaks, a knock
in training). The net selling in the window before a deadline, as a share of his owners, is the signal.

Sell table: {pid: {gw: (balance, own_before)}}
  balance     net transfers (in - out) in the window that closes at GW gw's deadline (FPL's transfers_balance
              for that round in element-summary history)
  own_before  managers who owned him when that window opened (at the previous deadline)

Sources (every one of them free FPL data):
  archive (training, bench.py) - vaastav merged_gw.csv, which is FPL's element-summary history: the round-gw row's
      transfers_balance, and own_before = selected - transfers_balance (`selected` is his ownership in gw, i.e. at
      gw's deadline; the archive check: selected(gw) - balance(gw) is within -1% / +3% of selected(gw-1) for 80%
      of 50k+ owned players, the gap being new teams and chips).
  past rounds, live season - the same element-summary history rows, cached in history/sell_hist.json by refresh()
      (one /element-summary/{id}/ call per player, made once per transfer window, plus once more if the first
      fetch was within 2 hours of the deadline). FPL adds the round row for every player as soon as the deadline
      passes (checked 31 Oct 2026: all 669 players had a GW9 row hours after the GW9 deadline).
  next GW, before its deadline - bootstrap-static transfers_in_event - transfers_out_event (running count since the
      last deadline, no extra call) and own_before = `selected` of his latest cached element-summary row (his
      ownership at the last deadline). A 30-minute build sees the window up to its run time: the last snapshot
      before the GW9 deadline (36 minutes before it) had 96% of the round's final transfers (median, 101 players
      with 20k+ out), so live selling reads about 4% low compared with training.

features(): sell_share = -balance / max(own_before, 1000), clipped to [-1, 1] (positive = net selling; the 1000-owner
floor, 0.01% of managers, stops a few hundred owners turning noise into +-100%); sell_spike = sell_share minus the
median of his own sell_share over his previous (up to) 6 rounds with data; log_own = log10(1 + own_before).
Missing data: no entry for the round (fetch failed, no element-summary row yet, new signing with no earlier row)
-> all three NaN, which XGBoost treats as missing, as in training; no earlier rounds -> sell_spike NaN. Nothing is
filled with a number. Callers count the NaNs (build.py -> data.json shadow block -> validate.py warning).
"""
import csv, datetime as dt, json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_OWN = 1000
SPIKE_GWS = 6
NAN = float("nan")


def from_archive(season):
    """Sell table for a past season from archive/<season>/merged_gw.csv (download it with archive.load_season)."""
    path = os.path.join(HERE, "archive", season, "merged_gw.csv")
    out = {}
    with open(path, encoding="utf-8", errors="ignore") as f:
        for r in csv.DictReader(f):
            try:
                pid, g, bal, sel = int(r["element"]), int(r["GW"]), int(float(r["transfers_balance"])), int(float(r["selected"]))
            except (KeyError, TypeError, ValueError):
                continue   # a row without transfer counts: that round stays missing (NaN), never 0
            out.setdefault(pid, {})[g] = (bal, sel - bal)   # doubles: both rows carry the same counts
    return out


def from_rounds(rounds):
    """Sell table for past rounds from cached element-summary rows {pid: [[round, balance, selected], ...]}."""
    return {int(pid): {g: (bal, sel - bal) for g, bal, sel in rows} for pid, rows in rounds.items()}


def add_live_window(sell, boot, rounds, gw):
    """Add the open window (GW gw, deadline not passed) to the sell table from bootstrap-static, in place.
    own_before = `selected` of his latest cached row before gw; no cached row -> no entry (NaN features).
    Returns the number of players with a fixture-independent live entry."""
    n = 0
    for e in boot["elements"]:
        rows = [r for r in rounds.get(str(e["id"]), ()) if r[0] < gw]
        tin, tout = e.get("transfers_in_event"), e.get("transfers_out_event")
        if not rows or tin is None or tout is None:
            continue
        sell.setdefault(e["id"], {})[gw] = (int(tin) - int(tout), max(rows, key=lambda r: r[0])[2])
        n += 1
    return n


def _share(entry):
    bal, own = entry
    return max(-1.0, min(1.0, -bal / max(own, MIN_OWN)))


def features(sell, pid, gw):
    """(sell_share, sell_spike, log_own) for player pid before GW gw's deadline; NaN where the data is missing."""
    rows = sell.get(pid) or {}
    cur = rows.get(gw)
    if cur is None:
        return NAN, NAN, NAN
    s = _share(cur)
    prev = [_share(rows[g]) for g in sorted(g for g in rows if g < gw)[-SPIKE_GWS:]]
    if prev:
        prev.sort()
        m = len(prev) // 2
        med = prev[m] if len(prev) % 2 else (prev[m - 1] + prev[m]) / 2
        spike = s - med
    else:
        spike = NAN
    return s, spike, math.log10(1 + max(0, cur[1]))


def refresh(boot, next_ev, path, get, now=None, workers=8):
    """Keep history/sell_hist.json ([round, transfers_balance, selected] for every round before the next GW) up to
    date. Fetches every player's element-summary when the cache is for an earlier window, or was fetched within 2 h
    of the last deadline (rows may still have been filling in) and that is now past. Never raises: on failure it
    returns the cache as it was (possibly None). Returns (cache dict or None, number of calls made)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        cache = json.load(open(path))
    except FileNotFoundError:
        cache = None
    except Exception as ex:
        print(f"{path} unreadable, refetching:", ex)
        cache = None
    if not next_ev:
        return cache, 0
    gw = next_ev["id"]
    prev_dl = max((dt.datetime.fromisoformat(e["deadline_time"].replace("Z", "+00:00")) for e in boot["events"]
                   if e["id"] < gw and e.get("deadline_time")), default=None)
    fresh = cache and cache.get("gw") == gw
    if fresh and prev_dl:
        fetched = dt.datetime.fromisoformat(cache["fetched"])
        if fetched < prev_dl + dt.timedelta(hours=2) <= now:
            fresh = False
    if fresh:
        return cache, 0
    try:
        from concurrent.futures import ThreadPoolExecutor
        ids = [e["id"] for e in boot["elements"]]

        def one(pid):
            try:
                hist = get(f"/element-summary/{pid}/")["history"]
            except Exception:
                return pid, None   # this player's rounds stay missing (NaN features), counted below
            by = {}
            for r in hist:
                if r["round"] < gw and r.get("transfers_balance") is not None and r.get("selected") is not None:
                    by[r["round"]] = [r["round"], int(r["transfers_balance"]), int(r["selected"])]
            return pid, [by[g] for g in sorted(by)]   # every round so far: backtests of this season read it too

        with ThreadPoolExecutor(workers) as ex:
            got = list(ex.map(one, ids))
        rounds = {str(p): rows for p, rows in got if rows is not None}
        failed = sum(1 for _, rows in got if rows is None)
        cache = {"gw": gw, "fetched": now.isoformat(timespec="seconds"), "failed": failed, "rounds": rounds}
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(cache, f, separators=(",", ":"))
        os.replace(tmp, path)
        return cache, len(ids)
    except Exception as ex:
        print("sell history not refreshed:", ex)
        return cache, 0
