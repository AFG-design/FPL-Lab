#!/usr/bin/env python3
"""Betting-market expected goals per match, from football-data.co.uk (free, no key).

For every Premier League match with odds (played this season, plus upcoming fixtures once the
weekly file lists them) we convert the market's match-result and over/under 2.5 goals odds into
expected goals for each side, by finding the Poisson rates that reproduce those probabilities.
Writes odds/odds.json: [{date, h, a (FPL team ids), lam_h, lam_a, p_h, p_d, p_a, p_over, played}].
"""
import csv, io, json, math, os, sys, time, urllib.request, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "odds", "odds.json")
BASE = "https://football-data.co.uk"
# football-data team names -> FPL short names
NAMES = {"Arsenal": "ARS", "Aston Villa": "AVL", "Bournemouth": "BOU", "Brentford": "BRE", "Brighton": "BHA",
         "Burnley": "BUR", "Chelsea": "CHE", "Coventry": "COV", "Crystal Palace": "CRY", "Everton": "EVE",
         "Fulham": "FUL", "Hull": "HUL", "Ipswich": "IPS", "Leeds": "LEE", "Leicester": "LEI", "Liverpool": "LIV",
         "Man City": "MCI", "Man United": "MUN", "Newcastle": "NEW", "Nott'm Forest": "NFO", "Southampton": "SOU",
         "Sunderland": "SUN", "Tottenham": "TOT", "West Ham": "WHU", "Wolves": "WOL", "Middlesbrough": "MID",
         "Sheffield United": "SHU", "Norwich": "NOR", "Watford": "WAT", "West Brom": "WBA", "Luton": "LUT"}


def fetch(url):
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 fpl-lab"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8-sig", errors="ignore")
        except Exception:
            time.sleep(2 + 3 * i)
    return None


def fpl(path):
    req = urllib.request.Request("https://fantasy.premierleague.com/api" + path, headers={"User-Agent": "Mozilla/5.0 fpl-lab"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def pois(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def outcome_probs(lh, la, kmax=10):
    ph = [pois(k, lh) for k in range(kmax + 1)]
    pa = [pois(k, la) for k in range(kmax + 1)]
    w = d = over = 0.0
    for i in range(kmax + 1):
        for j in range(kmax + 1):
            p = ph[i] * pa[j]
            if i > j:
                w += p
            elif i == j:
                d += p
            if i + j >= 3:
                over += p
    return w, d, 1 - w - d, over


def implied(odds):
    """Bookmaker odds -> probabilities with the margin removed (proportionally)."""
    inv = [1 / o for o in odds]
    s = sum(inv)
    return [x / s for x in inv]


def fit_lambdas(p_h, p_a, p_over):
    """Poisson rates (home, away) that best reproduce the market's home/away win and over-2.5 chances."""
    best, bl = None, (1.4, 1.1)
    def err(lh, la):
        w, d, l, o = outcome_probs(lh, la)
        return (w - p_h) ** 2 + (l - p_a) ** 2 + (0.6 * (o - p_over)) ** 2 if p_over is not None else (w - p_h) ** 2 + (l - p_a) ** 2
    lh, la, step = 1.4, 1.1, 0.4
    cur = err(lh, la)
    while step > 0.002:
        moved = False
        for dh, da in ((step, 0), (-step, 0), (0, step), (0, -step), (step, step), (-step, -step), (step, -step), (-step, step)):
            nh, na = lh + dh, la + da
            if nh < 0.05 or na < 0.05:
                continue
            e = err(nh, na)
            if e < cur:
                lh, la, cur, moved = nh, na, e, True
        if not moved:
            step /= 2
    return round(lh, 3), round(la, 3)


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def rows_from(text, played):
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        if r.get("Div") != "E0":
            continue
        # prefer pre-match market averages (what was known before kick-off); fall back to closing
        h, d, a = num(r.get("AvgH")), num(r.get("AvgD")), num(r.get("AvgA"))
        if not all((h, d, a)):
            h, d, a = num(r.get("AvgCH")), num(r.get("AvgCD")), num(r.get("AvgCA"))
        if not all((h, d, a)):
            continue
        o, u = num(r.get("Avg>2.5")) or num(r.get("AvgC>2.5")), num(r.get("Avg<2.5")) or num(r.get("AvgC<2.5"))
        p_h, p_d, p_a = implied([h, d, a])
        p_over = implied([o, u])[0] if o and u else None
        try:
            date = dt.datetime.strptime(r["Date"], "%d/%m/%Y").date().isoformat()
        except ValueError:
            date = dt.datetime.strptime(r["Date"], "%d/%m/%y").date().isoformat()
        out.append({"date": date, "home": r["HomeTeam"], "away": r["AwayTeam"], "p_h": round(p_h, 4), "p_d": round(p_d, 4),
                    "p_a": round(p_a, 4), "p_over": round(p_over, 4) if p_over else None, "played": played,
                    "fthg": num(r.get("FTHG")), "ftag": num(r.get("FTAG"))})
    return out


def match_fixtures(rows, short_to_id, fixtures, names=NAMES):
    """Join football-data rows to FPL fixtures (same home/away clubs, kick-off within 3 days) and fit lambdas.

    Returns (matches, unmatched team names, rows with no fixture). Rows whose club names aren't in `names`
    or whose fixture can't be found are left out and reported, never guessed.
    """
    fx_by = {}
    for f in fixtures:
        if f["kickoff_time"]:
            fx_by.setdefault((f["team_h"], f["team_a"]), []).append(f)
    out, unmatched, no_fixture = [], set(), []
    for r in rows:
        h, a = short_to_id.get(names.get(r["home"], "")), short_to_id.get(names.get(r["away"], ""))
        if not h or not a:
            unmatched.update(x for x, t in ((r["home"], h), (r["away"], a)) if not t)
            continue
        cands = fx_by.get((h, a), [])
        rd = dt.date.fromisoformat(r["date"])
        f = min(cands, key=lambda f: abs((dt.date.fromisoformat(f["kickoff_time"][:10]) - rd).days), default=None)
        if not f or abs((dt.date.fromisoformat(f["kickoff_time"][:10]) - rd).days) > 3:
            no_fixture.append(f'{r["date"]} {r["home"]} v {r["away"]}')
            continue
        lh, la = fit_lambdas(r["p_h"], r["p_a"], r["p_over"])
        out.append({"fixture": f["id"], "gw": f["event"], "date": r["date"], "h": h, "a": a, "lam_h": lh, "lam_a": la,
                    "p_h": r["p_h"], "p_d": r["p_d"], "p_a": r["p_a"], "p_over": r["p_over"], "played": r["played"]})
    return out, unmatched, no_fixture


def main():
    boot = fpl("/bootstrap-static/")
    fixtures = fpl("/fixtures/")
    season_start = int(min(e["deadline_time"] for e in boot["events"])[:4])
    code = f"{season_start % 100:02d}{(season_start + 1) % 100:02d}"
    past = fetch(f"{BASE}/mmz4281/{code}/E0.csv")
    upcoming = fetch(f"{BASE}/fixtures.csv")
    if not past and not upcoming:
        print("football-data.co.uk unavailable; keeping previous odds"); sys.exit(0)
    rows = (rows_from(past, True) if past else []) + (rows_from(upcoming, False) if upcoming else [])

    short_to_id = {t["short_name"]: t["id"] for t in boot["teams"]}
    out, unmatched, _ = match_fixtures(rows, short_to_id, fixtures)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "season": code, "matches": out,
               "unmatched_names": sorted(unmatched)}, open(OUT, "w"), separators=(",", ":"))
    print(f"odds for {len(out)} matches ({sum(1 for m in out if not m['played'])} upcoming); unmatched names: {sorted(unmatched)}")


if __name__ == "__main__":
    main()
