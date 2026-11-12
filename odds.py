#!/usr/bin/env python3
"""Betting-market expected goals per match.

Played matches come from football-data.co.uk (free, no key). Upcoming matches come from The Odds API (FL-092): one bulk
call for match result (h2h) and over/under (totals) odds at each pre-deadline checkpoint (72, 24 and 3 h, as
odds_players.py), for every EPL fixture the API lists, which usually covers the next two or three gameweeks.
football-data's fixtures.csv only fills an upcoming fixture the Odds API snapshot doesn't have (no key, credits low,
or a fixture it doesn't list yet), and each row says which source it came from.
Either way the market's match-result and over/under 2.5 goals odds are converted into expected goals for each side,
by finding the Poisson rates that reproduce those probabilities.
Writes odds/odds.json: [{date, h, a (FPL team ids), lam_h, lam_a, p_h, p_d, p_a, p_over, played, src}],
odds/upcoming.json (latest Odds API snapshot and fetch state) and history/fixture_odds_gw{N}.json (every checkpoint).

Credits (free key, 500 a month shared with odds_players.py): the bulk odds endpoint costs markets x regions per call
whatever the number of fixtures, so 2 markets x 1 region = 2 credits a snapshot, 3 snapshots = 6 per gameweek.
odds_players.py spends about 20 per checkpoint (10 fixtures x 2 markets), 60 per gameweek. Together 66 a gameweek;
the busiest month (6 gameweeks, e.g. December) is about 396, and both scripts stop at MIN_CREDITS (40) left.
"""
import csv, io, json, math, os, statistics, sys, time, urllib.error, urllib.request, datetime as dt

import odds_players

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "odds", "odds.json")
UPCOMING = os.path.join(HERE, "odds", "upcoming.json")
HIST = os.path.join(HERE, "history")
API_MARKETS = "h2h,totals"
API_REGION = os.environ.get("ODDS_FIXTURE_REGION", "uk")   # one region only: each extra region doubles the cost
API_COST = 2                                                # credits per snapshot: 2 markets x 1 region
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
                    "p_h": r["p_h"], "p_d": r["p_d"], "p_a": r["p_a"], "p_over": r["p_over"], "played": r["played"],
                    "src": "football-data"})
    return out, unmatched, no_fixture


def carry_played(matches, previous, season, past_ok):
    """Never lose played matches: add back any from the previous odds file that the new rows don't have.

    The market team ratings (70% of the blend) are built from every played match so far and need at least 20, so
    when this season's results file fails to download but the fixtures file loads, writing the new rows alone would
    switch the blend off without a word. Played odds never change once a match is over, so the previous file's
    played rows are carried over by fixture id. A results file that loads but comes back shorter is treated the same.
    Returns (matches, status): status goes into odds.json for validate.py and the Health page.
    Missing / late / ambiguous: no previous file, an unreadable one or one from another season -> nothing is carried
    and status says how many played rows there are, so validate.py can still warn that the results file failed.
    """
    have = {m["fixture"] for m in matches if m["played"]}
    prev = previous if isinstance(previous, dict) and previous.get("season") == season else {}
    kept = [m for m in prev.get("matches", []) if isinstance(m, dict) and m.get("played") and m.get("fixture") not in have]
    status = {"past_ok": bool(past_ok), "kept_played": len(kept)}
    if not past_ok or kept:
        # when the trouble started: carried forward from the previous file while it lasts
        status["past_failed_since"] = (prev.get("status") or {}).get("past_failed_since") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return kept + matches, status


def one_row_per_fixture(matches, fixtures):
    """One odds row per FPL fixture (FL-112).

    football-data.co.uk's fixtures.csv keeps listing a match for a while after it is played, so the same fixture came
    back twice: once from this season's results file (played) and once from the fixtures file (upcoming). Both rows
    then counted in the market team ratings, and Health reported upcoming odds for a gameweek that was over.
    Rules: an upcoming row is dropped once FPL marks its fixture finished; if a fixture id still appears more than
    once, the played row wins over an upcoming one, and the later row wins between two of the same kind (new rows
    come after carried ones, so fresh odds win).
    Missing / late / ambiguous: a fixture FPL doesn't list or whose `finished` is missing counts as not finished, so its
    upcoming row stays until FPL confirms the result. A finished match whose only row was the upcoming one (results
    file failed and nothing to carry) loses its odds rather than having pre-match odds passed off as played; the count
    goes into status["dropped_finished"] so validate.py and Health can see it.
    A row with no fixture id is kept as it is. fplmodel.prepare applies the same rule to whatever file it is given,
    so an odds file written before this fix (or one odds.py couldn't rewrite) never double-counts a match.
    Returns (matches, dropped_finished, dropped_duplicate).
    """
    finished = {f["id"] for f in fixtures if f.get("finished")}
    kept = [m for m in matches if m.get("played") or m.get("fixture") not in finished]
    dropped_finished = len(matches) - len(kept)
    best = {}
    for i, m in enumerate(kept):
        if m.get("fixture") is None:
            continue   # no id to match on: kept as it is, never merged with another row
        cur = best.get(m.get("fixture"))
        if cur is None or bool(m.get("played")) >= bool(kept[cur].get("played")):
            best[m.get("fixture")] = i
    out = [m for i, m in enumerate(kept) if m.get("fixture") is None or best.get(m.get("fixture")) == i]
    return out, dropped_finished, len(kept) - len(out)


def api_probs(event):
    """One Odds API event -> (p_h, p_d, p_a, p_over, books): the median over bookmakers of each one's probabilities
    with its own margin removed. Over/under uses only the 2.5 line, and only bookmakers that priced both sides.
    Missing / ambiguous: a bookmaker without all three result prices is left out; no bookmaker with all three ->
    None (the fixture gets no API row); no 2.5 line anywhere -> p_over None, and fit_lambdas fits the result odds alone.
    """
    home, away = event["home_team"], event["away_team"]
    res, over = [], []
    for bk in event.get("bookmakers", []):
        for m in bk.get("markets", []):
            if m.get("key") == "h2h":
                pr = {o.get("name"): o.get("price") for o in m.get("outcomes", [])}
                trio = [pr.get(home), pr.get("Draw"), pr.get(away)]
                if all(isinstance(x, (int, float)) and x > 1 for x in trio):
                    res.append(implied(trio))
            elif m.get("key") == "totals":
                pr = {o.get("name"): o.get("price") for o in m.get("outcomes", [])
                      if abs(float(o.get("point") or 0) - 2.5) < 1e-6}
                pair = [pr.get("Over"), pr.get("Under")]
                if all(isinstance(x, (int, float)) and x > 1 for x in pair):
                    over.append(implied(pair)[0])
    if not res:
        return None
    med = [statistics.median(r[i] for r in res) for i in range(3)]
    tot = sum(med)
    return (round(med[0] / tot, 4), round(med[1] / tot, 4), round(med[2] / tot, 4),
            round(statistics.median(over), 4) if over else None, len(res))


def api_rows(events, boot, fixtures):
    """Odds API events -> odds.json rows for unfinished FPL fixtures (same home/away clubs, kick-off within 36 h).
    Returns (rows, unmatched team names, events with no fixture). Never guesses a club or a fixture."""
    tkey = {odds_players.team_key(t["name"]): t["id"] for t in boot["teams"]}
    by = {}
    for f in fixtures:
        if f.get("kickoff_time") and not f.get("finished"):
            by.setdefault((f["team_h"], f["team_a"]), []).append(f)
    rows, unmatched, no_fixture = [], set(), []
    for e in events:
        h, a = tkey.get(odds_players.team_key(e.get("home_team"))), tkey.get(odds_players.team_key(e.get("away_team")))
        if not h or not a:
            unmatched.update(n for n, t in ((e.get("home_team"), h), (e.get("away_team"), a)) if not t)
            continue
        et = dt.datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00"))
        near = [f for f in by.get((h, a), [])
                if abs((dt.datetime.fromisoformat(f["kickoff_time"].replace("Z", "+00:00")) - et).total_seconds()) < 36 * 3600]
        if len(near) != 1:
            no_fixture.append(f'{e["commence_time"][:10]} {e.get("home_team")} v {e.get("away_team")}')
            continue
        pr = api_probs(e)
        if not pr:
            continue
        f = near[0]
        lh, la = fit_lambdas(pr[0], pr[2], pr[3])
        rows.append({"fixture": f["id"], "gw": f["event"], "date": f["kickoff_time"][:10], "h": h, "a": a,
                     "lam_h": lh, "lam_a": la, "p_h": pr[0], "p_d": pr[1], "p_a": pr[2], "p_over": pr[3],
                     "played": False, "src": "odds_api", "books": pr[4]})
    return rows, sorted(unmatched), no_fixture


def known_credits_left():
    """Lowest credits-left figure either Odds API script last saw this month (None if neither has one)."""
    month = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")
    seen = []
    for path in (UPCOMING, odds_players.OUT):
        try:
            with open(path) as f:
                st = json.load(f)
        except (OSError, ValueError):
            continue
        if isinstance(st.get("credits_left"), (int, float)) and str(st.get("built", ""))[:7] == month:
            seen.append(st["credits_left"])
    return min(seen) if seen else None


def fetch_upcoming(boot, fixtures, now=None, key=None, get=None):
    """Save an Odds API snapshot when a pre-deadline checkpoint is due; return the latest snapshot's rows.

    Missing / late / ambiguous:
      - no ODDS_API_KEY: nothing fetched; the last saved snapshot (if any) is still used and the state says why
      - no checkpoint due, the deadline passed, or this checkpoint already saved: no call, last snapshot used
      - credits at or below MIN_CREDITS + the cost (from the last figure either script saw): no call, state says so
      - HTTP error: the error is saved in odds/upcoming.json (last_error, for validate.py / Health); last snapshot used
      - a fixture in the snapshot that has since finished or kicked off is dropped from the live rows (odds.json
        keeps its football-data played row once that loads); the history file keeps it as fetched
    Returns (rows, state)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    key = os.environ.get("ODDS_API_KEY") if key is None else key
    get = get or odds_players.get
    state = odds_players.load_json(UPCOMING)
    nxt = next((e for e in boot["events"] if e.get("is_next")), None)
    if nxt:
        gw = nxt["id"]
        deadline = dt.datetime.fromisoformat(nxt["deadline_time"].replace("Z", "+00:00"))
        label = odds_players.checkpoint_label(deadline, now)
        hpath = os.path.join(HIST, f"fixture_odds_gw{gw}.json")
        hist = odds_players.load_json(hpath)
        left = known_credits_left()
        skip = None
        if not key:
            skip = "no ODDS_API_KEY"
        elif now >= deadline or label in hist.get("snapshots", {}):
            skip = "checkpoint already saved or deadline passed"
        elif not (os.environ.get("ODDS_FORCE") or odds_players.due(state, gw, deadline, now)):
            skip = "no checkpoint due"
        elif left is not None and left < odds_players.MIN_CREDITS + API_COST:
            skip = f"only {left} credits left this month"
        state["skipped"] = skip
        if not skip:
            try:
                events, left, used = get(f"/sports/{odds_players.SPORT}/odds", apiKey=key, regions=API_REGION,
                                         markets=API_MARKETS, oddsFormat="decimal")
            except (urllib.error.URLError, OSError, ValueError) as ex:
                state["last_error"] = {"at": now.isoformat(timespec="seconds"), "message": f"{type(ex).__name__}: {ex}"[:300]}
                print(f"::warning::fixture odds request failed: {ex}")
            else:
                rows, unmatched, no_fixture = api_rows(events, boot, fixtures)
                stamp = now.isoformat(timespec="seconds")
                snap = {"built": stamp, "credits_used": int(float(used or 0)), "region": API_REGION,
                        "rows": rows, "unmatched_teams": unmatched, "no_fixture": no_fixture}
                if rows:   # an empty reply is a failed fetch, not a checkpoint: a later run may retry
                    hist.setdefault("snapshots", {})[label] = snap
                    hist.update(gw=gw, deadline=nxt["deadline_time"])
                    odds_players.write_json(hpath, hist)
                    state.setdefault("fetched", {})[str(gw)] = stamp
                    state.update(latest=snap, gw=gw, label=label)
                    state.pop("last_error", None)
                else:
                    state["last_error"] = {"at": stamp, "message": f"no fixture odds matched ({len(events)} events)"}
                state.update(built=stamp, credits_left=left, credits_used=snap["credits_used"])
                print(f"fixture odds GW{gw} ({label} h checkpoint): {len(rows)} fixtures, {snap['credits_used']} credits used, "
                      f"{left} left; unmatched teams {unmatched}, no fixture {len(no_fixture)}")
        else:
            print(f"fixture odds: {skip}; using the last snapshot")
    odds_players.write_json(UPCOMING, state)
    live = {f["id"] for f in fixtures if not f.get("finished")
            and f.get("kickoff_time") and dt.datetime.fromisoformat(f["kickoff_time"].replace("Z", "+00:00")) > now}
    at = (state.get("latest") or {}).get("built")
    rows = [dict(r, at=at) for r in (state.get("latest") or {}).get("rows", []) if r["fixture"] in live]
    return rows, state


def merge_upcoming(matches, api):
    """Odds API rows replace football-data upcoming rows for the same fixture; played rows are never touched."""
    have = {r["fixture"] for r in api}
    return [m for m in matches if m.get("played") or m.get("fixture") not in have] + api


def main():
    boot = fpl("/bootstrap-static/")
    fixtures = fpl("/fixtures/")
    season_start = int(min(e["deadline_time"] for e in boot["events"])[:4])
    code = f"{season_start % 100:02d}{(season_start + 1) % 100:02d}"
    past = fetch(f"{BASE}/mmz4281/{code}/E0.csv")
    upcoming = fetch(f"{BASE}/fixtures.csv")
    if not past and not upcoming:
        # keep the previous football-data rows (its "built" time stays, so validate.py still sees how old they are),
        # but still refresh the Odds API upcoming rows and keep one row per fixture (FL-112)
        try:
            with open(OUT) as f:
                previous = json.load(f)
            api, ust = fetch_upcoming(boot, fixtures)
            ms, df, dd = one_row_per_fixture(merge_upcoming(previous.get("matches", []), api), fixtures)
            previous["matches"] = ms
            previous.setdefault("status", {}).update(dropped_finished=df, dropped_duplicate=dd, upcoming_api=len(api),
                                                     upcoming_api_built=(ust.get("latest") or {}).get("built"))
            json.dump(previous, open(OUT, "w"), separators=(",", ":"))
        except (OSError, ValueError, AttributeError):
            pass   # no readable previous file: validate.py already warns that match odds didn't load
        print("football-data.co.uk unavailable; keeping previous odds"); sys.exit(0)
    rows = (rows_from(past, True) if past else []) + (rows_from(upcoming, False) if upcoming else [])

    short_to_id = {t["short_name"]: t["id"] for t in boot["teams"]}
    out, unmatched, _ = match_fixtures(rows, short_to_id, fixtures)
    try:
        with open(OUT) as f:
            previous = json.load(f)
    except (OSError, ValueError):
        previous = None   # first run, or an unreadable file: nothing to carry over (carry_played reports it)
    out, status = carry_played(out, previous, code, bool(past))
    api, ust = fetch_upcoming(boot, fixtures)
    out = merge_upcoming(out, api)
    status["upcoming_api"] = len(api)
    status["upcoming_api_built"] = (ust.get("latest") or {}).get("built")
    out, status["dropped_finished"], status["dropped_duplicate"] = one_row_per_fixture(out, fixtures)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "season": code, "matches": out,
               "unmatched_names": sorted(unmatched), "status": status}, open(OUT, "w"), separators=(",", ":"))
    print(f"odds for {len(out)} matches ({sum(1 for m in out if not m['played'])} upcoming); unmatched names: {sorted(unmatched)}")
    if not status["past_ok"] or status["kept_played"]:
        print(f"::warning::odds: this season's results file {'did not load' if not status['past_ok'] else 'came back short'}; "
              f"{status['kept_played']} played matches carried over from the previous file")


if __name__ == "__main__":
    main()
