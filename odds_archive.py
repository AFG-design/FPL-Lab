#!/usr/bin/env python3
"""Betting-market odds for past seasons, so bench.py tests the archive seasons with odds like the live model.

  python3 odds_archive.py                  # 2024-25 and 2025-26
  python3 odds_archive.py 2023-24          # any season the vaastav archive and football-data.co.uk both have

For each season: football-data.co.uk's E0.csv (pre-match market averages, falling back to closing odds, exactly
as odds.py does live) is joined to the archive's fixtures (same clubs, kick-off within 3 days) and turned into
Poisson expected goals per side. Writes odds/archive/<season>.json in odds.json's shape, which archive.load_odds()
reads and bench.py passes to fplmodel.prepare().

Missing or ambiguous data fails loudly (exit 1, nothing written for that season):
  - football-data.co.uk unreachable, or the file has no E0 rows;
  - a club name with no mapping (add it to odds.NAMES);
  - a row with no archive fixture, a fixture matched twice, or fewer than MIN_COVERAGE of the season's fixtures
    matched (a postponed match with no odds is fine; a broken join is not).
"""
import json, os, sys, time

import archive
import odds

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "odds", "archive")
SEASONS = ("2024-25", "2025-26")
MIN_COVERAGE = 0.97   # share of the season's fixtures that must get odds


def season_odds(season):
    """Returns (payload, problems). problems is a list of strings; any problem means don't write the file."""
    y = int(season[:4])
    code = f"{y % 100:02d}{(y + 1) % 100:02d}"
    text = odds.fetch(f"{odds.BASE}/mmz4281/{code}/E0.csv")
    if not text:
        return None, [f"football-data.co.uk: could not download mmz4281/{code}/E0.csv"]
    rows = odds.rows_from(text, True)
    if not rows:
        return None, [f"football-data.co.uk: mmz4281/{code}/E0.csv has no E0 rows with odds"]

    teams = archive._rows(season, "teams.csv")
    short_to_id = {t["short_name"]: int(t["id"]) for t in teams}
    fixtures = [{"id": int(r["id"]), "event": int(float(r["event"])), "team_h": int(r["team_h"]),
                 "team_a": int(r["team_a"]), "kickoff_time": r["kickoff_time"]}
                for r in archive._rows(season, "fixtures.csv") if r["event"] and r["kickoff_time"]]
    matches, unmatched, no_fixture = odds.match_fixtures(rows, short_to_id, fixtures)

    problems = []
    if unmatched:
        problems.append(f"club names with no mapping in odds.NAMES: {sorted(unmatched)}")
    if no_fixture:
        problems.append(f"{len(no_fixture)} odds rows with no archive fixture, e.g. {no_fixture[:3]}")
    seen = {}
    for m in matches:
        seen[m["fixture"]] = seen.get(m["fixture"], 0) + 1
    dup = [f for f, n in seen.items() if n > 1]
    if dup:
        problems.append(f"fixtures matched more than once: {dup[:5]}")
    cover = len(seen) / len(fixtures) if fixtures else 0
    if cover < MIN_COVERAGE:
        problems.append(f"only {len(seen)} of {len(fixtures)} fixtures have odds ({cover:.1%} < {MIN_COVERAGE:.0%})")
    bad = [m for m in matches if not (0.1 <= m["lam_h"] <= 5 and 0.1 <= m["lam_a"] <= 5)]
    if bad:
        problems.append(f"{len(bad)} matches with expected goals outside 0.1-5, e.g. fixture {bad[0]['fixture']}")

    payload = {"built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "season": code, "source": "football-data.co.uk",
               "fixtures": len(fixtures), "matches": sorted(matches, key=lambda m: (m["gw"], m["fixture"])),
               "missing_fixtures": sorted({f["id"] for f in fixtures} - set(seen))}
    return payload, problems


def main(seasons):
    os.makedirs(OUT_DIR, exist_ok=True)
    failed = False
    for s in seasons:
        payload, problems = season_odds(s)
        if problems:
            failed = True
            print(f"{s}: NOT written")
            for p in problems:
                print(f"  - {p}")
            continue
        path = os.path.join(OUT_DIR, f"{s}.json")
        json.dump(payload, open(path, "w"), separators=(",", ":"))
        print(f"{s}: odds for {len(payload['matches'])} of {payload['fixtures']} fixtures"
              f" (missing {len(payload['missing_fixtures'])}) -> {os.path.relpath(path, HERE)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main(sys.argv[1:] or SEASONS)
