#!/usr/bin/env python3
"""FL-229: past seasons' Understat shots and team pressing data, for the bench (FL-225's style matchups).

bench.py decides model changes on 2024/25 and 2025/26 pooled, and neither season has Understat data in the repo, so
nothing built on shot type, situation or last action can be tested without this. For each season it writes
understat/archive/<YYYY-YY>.json:

  {"season": "2024-25", "us_season": "2024", "v": 3, "built": ..., "complete": bool, "expected": 380,
   "matches": {id: {"date", "h", "a", "shots": [11-field rows as understat.shot_row], "la": true}},
   "teams":   {Understat short code: {"title", "us_id", "matches": [...]}}   # as understat.team_history
   "missing": [match ids not downloaded]}

Clubs are kept as Understat's short codes (understat.US_TO_FPL maps the four that differ); joining them to a season's
FPL teams is the consumer's job (FL-230), as it is for the live cache.

Missing / late / ambiguous:
- Understat down or the league feed unreadable: nothing is written and the script exits 1.
- Some matches fail to download: the file is still written with what was fetched (so the next run resumes, skipping
  matches already saved), "complete" is false, the ids are listed in "missing", and the script exits 1. Downloads
  are only retried on the next run; no partial season is ever marked complete.
- A finished season with other than 380 results in the feed: "expected" records the feed's count and the script
  prints a warning; it is not treated as complete unless every listed result was downloaded.
- A shot with no lastAction field is saved with "" (understat.shot_row); the script prints the share that carry one.

Usage: python3 tools/understat_backfill.py 2024 2025     (Understat season start years)
Only run from GitHub Actions (.github/workflows/understat-backfill.yml): Understat is not reachable from the Claude
sandbox. Live data and the site are unchanged by this script.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import understat  # noqa: E402

OUT = os.path.join(HERE, "understat", "archive")
SEASON_GAMES = 380


def season_name(start):
    """2024 -> "2024-25" (the vaastav archive names that bench.py and archive.py use)."""
    y = int(start)
    return f"{y}-{(y + 1) % 100:02d}"


def load_existing(path, start):
    """A saved file for the same Understat season to resume from, else an empty v3 shell."""
    try:
        d = json.load(open(path))
        if d.get("us_season") == str(start) and d.get("v") == understat.CACHE_V:
            return d
    except (OSError, ValueError):
        pass
    return {"season": season_name(start), "us_season": str(start), "v": understat.CACHE_V, "matches": {}}


def backfill(start, out_dir=OUT, fetch=None):
    """Download one season. Returns (path, complete). `fetch` is for tests (defaults to understat.fetch)."""
    fetch = fetch or understat.fetch
    league = fetch(f"https://understat.com/getLeagueData/EPL/{start}", f"https://understat.com/league/EPL/{start}")
    if not league:
        raise RuntimeError(f"Understat league feed for {start} unavailable; nothing written")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, season_name(start) + ".json")
    d = load_existing(path, start)
    done = [m for m in league["dates"] if m.get("isResult")]
    info = {m["id"]: m for m in done}
    todo = [mid for mid in info if not d["matches"].get(mid, {}).get("la")]
    old_fetch = understat.fetch
    understat.fetch = fetch
    try:
        failed = set(understat.download_matches(d, todo, info))
    finally:
        understat.fetch = old_fetch
    teams, unmapped, bad = understat.team_history(league)
    missing = sorted(mid for mid in info if mid in failed or mid not in d["matches"])
    d.update({"built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "expected": len(done), "teams": teams,
              "teams_unmapped": unmapped, "teams_bad_rows": bad, "missing": missing,
              "complete": not missing and not unmapped and not bad and len(teams) == 20})
    with open(path, "w") as f:
        json.dump(d, f, separators=(",", ":"))
    n, _, share = understat.last_action_stats(d)
    print(f"{d['season']}: {len(d['matches'])} of {len(done)} matches, {len(teams)} teams, "
          f"last action on {share if share is not None else 'n/a'} of shots, {len(missing)} missing")
    if len(done) != SEASON_GAMES:
        print(f"::warning::{d['season']}: the league feed lists {len(done)} results, not {SEASON_GAMES}")
    for t in unmapped:
        print(f"::warning::{d['season']}: Understat team {t!r} has no short code in the fixture list")
    if bad:
        print(f"::warning::{d['season']}: {bad} team-history rows were missing a field and left out")
    return path, d["complete"]


def main(args):
    if not args:
        print(__doc__); return 2
    ok = True
    for start in args:
        try:
            _, complete = backfill(start)
        except RuntimeError as e:
            print(f"::error::{e}"); ok = False; continue
        ok = ok and complete
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
