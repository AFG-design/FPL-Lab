#!/usr/bin/env python3
"""Fetch FPL's backfilled 2024/25 defensive_contribution and minutes from element-summary history_past.

FL-212: FPL backfilled 2024/25 defensive_contribution in element-summary history_past (DC_FIRST = 2024,
see FL-176 in docs/model-log.md), so the live priors already use real 2024/25 DefCon. The public vaastav
archive's 2024-25 players_raw.csv has no defensive_contribution column, leaving the 2025/26 test season's
archive priors with dc_mins = 0. This tool writes a committed snapshot (archive_dc/2024-25.json) keyed by
FPL's stable player "code" so archive.py can attach real 2024/25 DefCon to 2025/26 test-season priors.

Hindsight note: only the 2024/25 season_name row is read from history_past. These are 2024/25 season totals,
known before 2025/26 GW1. No 2025/26 or later rows ever enter this file.

Missing / late / ambiguous:
  - players who left the Premier League before the fetch are absent from current bootstrap-static; archive.py
    leaves them with dc_mins = 0 (same as before FL-212), never guessed;
  - a player whose history_past has no 2024/25 row, 0 minutes, or defensive_contribution None is omitted;
  - if more than MAX_FAILED (2%) of player summaries fail to download, or the new count drops below MIN_KEPT
    (85%) of the existing file, nothing is written and the script exits 1 so the previous file stays intact.

Do not re-run: the file can only shrink as players leave the game, and a run that keeps 85-99% of players
passes the safety check and quietly cuts coverage. archive_dc/2024-25.json is a frozen snapshot.

Usage:
  python3 tools/dc_backfill.py                           # writes archive_dc/2024-25.json
  python3 tools/dc_backfill.py 2024-25 path/to/out.json
"""
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from make_priors import API, DC_FIRST, MAX_FAILED, MIN_KEPT, start_year  # noqa: E402

WORKERS = 4          # polite concurrency for FPL API element-summary
PAUSE_SEC = 0.05     # small per-request pause to avoid hammering the API


def get(path):
    """Fetch JSON from the official FPL API with polite backoff on failure."""
    for i in range(4):
        try:
            req = urllib.request.Request(API + path, headers={"User-Agent": "Mozilla/5.0 fpl-lab"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.load(r)
            if PAUSE_SEC:
                time.sleep(PAUSE_SEC)
            return data
        except Exception:
            time.sleep(2 + 3 * i)
    return None


def season_to_fpl_name(season):
    """'2024-25' -> '2024/25'. Validates start year >= DC_FIRST."""
    y = start_year(season)
    if y is None or y < DC_FIRST:
        raise ValueError(f"season {season!r} is before DC_FIRST ({DC_FIRST})")
    return f"{y}/{str(y + 1)[2:]}"


def extract_season_dc(history_past, target_season_name):
    """Return {'dc': int, 'minutes': int} for the exact target season_name, or None.

    Only the exact target_season_name row is inspected so no later season can leak in.
    """
    for s in history_past or []:
        if s.get("season_name") != target_season_name:
            continue
        mins = s.get("minutes") or 0
        dc = s.get("defensive_contribution")
        if mins > 0 and dc is not None:
            return {"dc": int(dc), "minutes": int(mins)}
    return None


def check_counts(new, previous, failed, total):
    """Same safety checks as make_priors.py: fail loudly and keep old file on broken downloads."""
    if total and failed / total > MAX_FAILED:
        raise SystemExit(
            f"dc_backfill: {failed} of {total} player summaries failed to download "
            f"(>{MAX_FAILED:.0%}); keeping the previous file"
        )
    if previous and new < MIN_KEPT * previous:
        raise SystemExit(
            f"dc_backfill: {new} players against {previous} in the previous file "
            f"(below {MIN_KEPT:.0%}); keeping the previous file"
        )


def build_payload(season, elements, summaries_by_id, fetched=None):
    """Assemble the archive_dc JSON payload from bootstrap elements and element-summary dicts."""
    target = season_to_fpl_name(season)
    players = {}
    failed = 0
    for e in elements:
        pid = e["id"]
        code = str(e["code"])
        d = summaries_by_id.get(pid)
        if d is None:
            failed += 1
            continue
        row = extract_season_dc(d.get("history_past"), target)
        if row is not None:
            players[code] = row
    ordered = {k: players[k] for k in sorted(players, key=lambda c: (int(c) if c.isdigit() else 0, c))}
    return {
        "season": season,
        "season_name": target,
        "source": "FPL API element-summary history_past",
        "fetched": fetched or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "player_count": len(ordered),
        "players_total": len(elements),
        "failed": failed,
        "players": ordered,
    }


def main(season="2024-25", out=None):
    target = season_to_fpl_name(season)
    out = out or os.path.join(ROOT, "archive_dc", f"{season}.json")
    boot = get("/bootstrap-static/")
    if not boot:
        raise SystemExit("dc_backfill: bootstrap-static failed to download; keeping the previous file")
    elements = [e for e in boot["elements"] if e.get("element_type") != 5]
    ids = [e["id"] for e in elements]
    with ThreadPoolExecutor(WORKERS) as ex:
        raw = dict(zip(ids, ex.map(lambda pid: get(f"/element-summary/{pid}/"), ids)))
    payload = build_payload(season, elements, raw)
    try:
        with open(out) as f:
            previous = len(json.load(f).get("players", {}))
    except (OSError, ValueError, AttributeError):
        previous = 0
    check_counts(payload["player_count"], previous, payload["failed"], payload["players_total"])
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    tmp = out + ".tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f, separators=(",", ":"))
    os.replace(tmp, out)
    skipped = sum(
        1
        for d in raw.values()
        if d
        for s in (d.get("history_past") or [])
        if s.get("season_name") == target and not ((s.get("minutes") or 0) > 0 and s.get("defensive_contribution") is not None)
    )
    print(
        f"dc_backfill: {payload['player_count']} players with {target} DefCon "
        f"(of {payload['players_total']} current players, {skipped} {target} rows skipped [0 minutes or missing DefCon], "
        f"{payload['failed']} failed) -> {out}"
    )


if __name__ == "__main__":
    s_arg = sys.argv[1] if len(sys.argv) > 1 else "2024-25"
    o_arg = sys.argv[2] if len(sys.argv) > 2 else None
    main(s_arg, o_arg)
