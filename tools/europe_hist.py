#!/usr/bin/env python3
"""Past seasons' European match dates for English clubs (FL-115), for testing the European rotation cut.

    python3 tools/europe_hist.py          # downloads and writes europe_hist.json

Source: openfootball/champions-league (public domain, CC0), plain-text fixture lists per season and competition:
https://github.com/openfootball/champions-league. Free, no key. Each English club's match dates (every stage, as
played) are kept per season under its FPL short name; build.py's europe.json stays the live source for this season.

Missing or ambiguous, never guessed:
  - a competition file that isn't published (2025-26 Europa and Conference League, as of 13 Nov 2026) is listed in
    "missing", and its clubs simply have no dates that season; the bench then applies no cut to them;
  - an English club name not in NAMES, or a date line that can't be read, stops the script (fails loudly).
"""
import datetime as dt, json, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "europe_hist.json")
BASE = "https://raw.githubusercontent.com/openfootball/champions-league/master/{season}/{comp}.txt"
SEASONS = ["2024-25", "2025-26"]
COMPS = {"cl": "UCL", "el": "UEL", "conf": "UECL"}
NAMES = {"Arsenal FC": "ARS", "Aston Villa FC": "AVL", "Chelsea FC": "CHE", "Liverpool FC": "LIV", "Manchester City FC": "MCI",
         "Manchester United": "MUN", "Manchester United FC": "MUN", "Newcastle United FC": "NEW", "Tottenham Hotspur": "TOT",
         "Tottenham Hotspur FC": "TOT", "Nottingham Forest FC": "NFO", "Crystal Palace FC": "CRY", "Brighton & Hove Albion FC": "BHA",
         "West Ham United FC": "WHU", "Everton FC": "EVE", "Fulham FC": "FUL", "Bournemouth": "BOU", "AFC Bournemouth": "BOU"}
MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
DATE = re.compile(r"^\s{2}(Mon|Tue|Wed|Thu|Fri|Sat|Sun) ([A-Z][a-z]{2}) (\d{1,2})(?: (\d{4}))?\s*$")
ENG = re.compile(r"([A-Z][A-Za-z0-9 .&'-]*?) \(ENG\)")


def parse(text, season):
    """{short: [ISO dates]} for English clubs. The year comes from the season (Jul-Dec first year, Jan-Jun second)."""
    y0 = int(season[:4]); out, day = {}, None
    for line in text.splitlines():
        m = DATE.match(line)
        if m:
            mon = MONTHS[m.group(2)]
            year = int(m.group(4)) if m.group(4) else (y0 if mon >= 7 else y0 + 1)
            day = dt.date(year, mon, int(m.group(3)))
            continue
        for name in ENG.findall(line):
            name = name.strip()
            if name not in NAMES:
                sys.exit(f"europe_hist: unknown English club {name!r} in {season}; add it to NAMES")
            if day is None:
                sys.exit(f"europe_hist: a match before any date line in {season}: {line.strip()!r}")
            out.setdefault(NAMES[name], set()).add(day.isoformat())
    return {k: sorted(v) for k, v in sorted(out.items())}


def main():
    res = {"source": "openfootball/champions-league (CC0), https://github.com/openfootball/champions-league", "seasons": {}, "missing": []}
    for season in SEASONS:
        clubs = {}
        for comp, label in COMPS.items():
            try:
                with urllib.request.urlopen(BASE.format(season=season, comp=comp), timeout=30) as r:
                    text = r.read().decode("utf-8")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    res["missing"].append(f"{season} {label}")
                    continue
                raise
            for short, dates in parse(text, season).items():
                clubs.setdefault(short, {})[label] = dates
        res["seasons"][season] = clubs
    json.dump(res, open(OUT, "w"), indent=1)
    for s, c in res["seasons"].items():
        print(s, {k: sum(len(d) for d in v.values()) for k, v in c.items()})
    print("missing:", res["missing"] or "none")


if __name__ == "__main__":
    main()
