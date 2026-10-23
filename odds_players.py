#!/usr/bin/env python3
"""Player betting odds (anytime goalscorer, assists) from The Odds API, for the next gameweek.

Needs the ODDS_API_KEY environment variable (a GitHub Actions secret). Without it the script
does nothing. The refresh workflow runs every 10-30 minutes, but this only calls the API at a
few checkpoints before each deadline (CHECKPOINTS), so a free key (500 credits a month) lasts:
about 10 fixtures x 2 markets = ~20 credits per refresh, 3 refreshes per gameweek.

Writes odds/players.json (latest) and history/player_odds_gw{N}.json (the last snapshot before
that deadline, for backtests). Only derived numbers are saved, never raw bookmaker prices:
  p_score  : median implied chance of scoring if he plays (bookmaker margin still included;
             the model removes it by matching each team's total to its expected goals)
  p_assist : median chance of 1+ assist (margin removed from the over/under pair when both sides exist)
  books    : how many bookmakers priced him
"""
import json, os, statistics, sys, time, unicodedata, urllib.request, urllib.error, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "odds", "players.json")
HIST = os.path.join(HERE, "history")
API = "https://api.the-odds-api.com/v4"
SPORT = "soccer_epl"
MARKETS = "player_goal_scorer_anytime,player_assists"
REGIONS = os.environ.get("ODDS_REGIONS", "us")
CHECKPOINTS = [72, 24, 3]   # hours before the deadline at which to refresh
MIN_CREDITS = 40            # never spend the last few credits of the month

# The Odds API team names that differ from FPL's full names after normalising
ALIASES = {"brighton and hove albion": "brighton", "tottenham hotspur": "spurs", "manchester city": "man city",
           "manchester united": "man utd", "newcastle united": "newcastle", "nottingham forest": "nott'm forest",
           "wolverhampton wanderers": "wolves", "west ham united": "west ham", "leeds united": "leeds",
           "ipswich town": "ipswich", "hull city": "hull", "coventry city": "coventry", "leicester city": "leicester",
           "afc bournemouth": "bournemouth", "sheffield united": "sheffield utd", "luton town": "luton"}


TRANSLIT = str.maketrans({"ø": "o", "Ø": "O", "ß": "ss", "ı": "i", "æ": "ae", "Æ": "AE", "đ": "d", "Đ": "D",
                          "ł": "l", "Ł": "L", "þ": "th", "ð": "d", "œ": "oe"})
PARTICLES = {"da", "de", "do", "dos", "das", "di", "van", "von", "der", "den", "le", "la", "el", "al", "bin", "ben"}


def norm(s):
    s = unicodedata.normalize("NFKD", (s or "").translate(TRANSLIT)).encode("ascii", "ignore").decode().lower()
    return " ".join(s.replace("-", " ").replace(".", " ").replace("'", "").split())


def get(path, **params):
    from urllib.parse import urlencode
    url = f"{API}{path}?{urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "fpl-lab"})
    with urllib.request.urlopen(req, timeout=30) as r:
        left = r.headers.get("x-requests-remaining")
        used = r.headers.get("x-requests-last")
        return json.load(r), (int(float(left)) if left else None), used


def fpl(path):
    req = urllib.request.Request("https://fantasy.premierleague.com/api" + path, headers={"User-Agent": "Mozilla/5.0 fpl-lab"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def team_key(name):
    n = norm(name)
    return norm(ALIASES.get(n, n))


def match_player(desc, squad):
    """Bookmaker player name -> FPL element id among the two clubs' players, or None."""
    d = norm(desc)
    toks = d.split()
    if not toks:
        return None
    # 1. exact full name or exact FPL display name
    for key in ("full", "web"):
        hit = [e["id"] for e in squad if (norm(f"{e['first_name']} {e['second_name']}") if key == "full" else norm(e["web_name"])) == d]
        if len(hit) == 1:
            return hit[0]
    # 2. most name words in common. He must share a surname word (or display name) with the bookmaker's name,
    #    and either that is the bookmaker's last word or another word matches his first name. Handles full
    #    legal names ("Marcelino Ignacio Nunez Espinoza" -> Núñez, "Ogochukwu Onyeka Frank" -> Onyeka) and
    #    shared first names ("Gabriel Martinelli" -> Martinelli, not Gabriel Magalhães).
    best, score = [], 0
    for e in squad:
        sec = norm(e["second_name"]).split()
        sur = (set(sec) | set(norm(e["web_name"]).split()) | {"".join(sec)}) - PARTICLES
        first = set(norm(e["first_name"]).split()) - PARTICLES
        common = set(toks) & sur
        if not common:
            continue
        if not (toks[-1] in sur or (set(toks) - common) & first):
            continue
        s = len(set(toks) & (sur | first))
        if s > score:
            best, score = [e["id"]], s
        elif s == score:
            best.append(e["id"])
    return best[0] if len(best) == 1 else None


def implied(price):
    return 1.0 / price if price and price > 1 else None


def due(state, gw, deadline, now):
    """True when a checkpoint has passed since the last fetch for this gameweek."""
    if now >= deadline:
        return False
    last = state.get("fetched", {}).get(str(gw))
    last = dt.datetime.fromisoformat(last) if last else None
    for h in CHECKPOINTS:
        cp = deadline - dt.timedelta(hours=h)
        if now >= cp and (last is None or last < cp):
            return True
    return False


def main():
    key = os.environ.get("ODDS_API_KEY")
    if not key:
        print("ODDS_API_KEY not set; skipping player odds")
        return
    try:
        state = json.load(open(OUT))
    except Exception:
        state = {}
    boot, fixtures = fpl("/bootstrap-static/"), fpl("/fixtures/")
    nxt = next((e for e in boot["events"] if e["is_next"]), None)
    if not nxt:
        print("no next gameweek"); return
    gw = nxt["id"]
    deadline = dt.datetime.fromisoformat(nxt["deadline_time"].replace("Z", "+00:00"))
    now = dt.datetime.now(dt.timezone.utc)
    if not (os.environ.get("ODDS_FORCE") or due(state, gw, deadline, now)):
        print(f"player odds: no checkpoint due for GW{gw} (deadline {deadline:%a %d %b %H:%M} UTC)")
        return

    teams = {t["id"]: t for t in boot["teams"]}
    tkey = {team_key(t["name"]): t["id"] for t in boot["teams"]}
    gw_fx = [f for f in fixtures if f["event"] == gw and f["kickoff_time"]]
    squads = {}
    for e in boot["elements"]:
        squads.setdefault(e["team"], []).append(e)

    events, left, _ = get(f"/sports/{SPORT}/events", apiKey=key)   # listing events costs no credits
    out_fx, unmatched, unmatched_teams, spent = {}, [], set(), 0
    for f in gw_fx:
        ko = dt.datetime.fromisoformat(f["kickoff_time"].replace("Z", "+00:00"))
        ev = None
        for e in events:
            h, a = tkey.get(team_key(e["home_team"])), tkey.get(team_key(e["away_team"]))
            for nm, tid in ((e["home_team"], h), (e["away_team"], a)):
                if tid is None:
                    unmatched_teams.add(nm)
            et = dt.datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00"))
            if (h, a) == (f["team_h"], f["team_a"]) and abs((et - ko).total_seconds()) < 36 * 3600:
                ev = e
                break
        if not ev:
            continue
        if left is not None and left < MIN_CREDITS:
            print(f"only {left} credits left this month; stopping"); break
        try:
            data, left, used = get(f"/sports/{SPORT}/events/{ev['id']}/odds", apiKey=key, regions=REGIONS,
                                   markets=MARKETS, oddsFormat="decimal")
        except urllib.error.HTTPError as ex:
            print(f"odds request failed for fixture {f['id']}: HTTP {ex.code}"); continue
        spent += int(float(used or 0))
        squad = squads.get(f["team_h"], []) + squads.get(f["team_a"], [])
        score, assist_o, assist_u = {}, {}, {}
        for bk in data.get("bookmakers", []):
            for m in bk.get("markets", []):
                for o in m.get("outcomes", []):
                    desc = o.get("description") or ""
                    if norm(desc) in ("", "no scorer", "no goalscorer", "no goal"):
                        continue
                    if m["key"] == "player_goal_scorer_anytime" and o.get("name") in ("Yes", None):
                        score.setdefault(desc, []).append(o["price"])
                    elif m["key"] == "player_assists" and abs(float(o.get("point") or 0.5) - 0.5) < 1e-6:
                        (assist_o if o.get("name") == "Over" else assist_u).setdefault((desc, bk["key"]), o["price"])
        players = {}
        for desc in set(score) | {d for d, _ in assist_o}:
            pid = match_player(desc, squad)
            if pid is None:
                unmatched.append(f"{desc} ({teams[f['team_h']]['short_name']}-{teams[f['team_a']]['short_name']})")
                continue
            row = players.setdefault(str(pid), {})
            ps = [implied(p) for p in score.get(desc, []) if implied(p)]
            if ps:
                row["p_score"] = round(statistics.median(ps), 4)
                row["books"] = len(ps)
            pa = []
            for (d, bk), po in assist_o.items():
                if d != desc:
                    continue
                pu = assist_u.get((d, bk))
                io, iu = implied(po), implied(pu)
                if io and iu:
                    pa.append(io / (io + iu))
                elif io:
                    pa.append(io)
            if pa:
                row["p_assist"] = round(statistics.median(pa), 4)
        out_fx[str(f["id"])] = {"h": f["team_h"], "a": f["team_a"], "kickoff": f["kickoff_time"],
                                "books": len(data.get("bookmakers", [])), "players": players}

    stamp = now.isoformat(timespec="seconds")
    state.setdefault("fetched", {})[str(gw)] = stamp
    state.pop("last_error", None)
    state.update({"built": stamp, "gw": gw, "deadline": nxt["deadline_time"], "regions": REGIONS,
                  "credits_left": left, "credits_used": spent, "fixtures": out_fx,
                  "unmatched_players": sorted(set(unmatched)), "unmatched_teams": sorted(unmatched_teams)})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(state, open(OUT, "w"), separators=(",", ":"))
    os.makedirs(HIST, exist_ok=True)
    json.dump({k: state[k] for k in ("built", "gw", "deadline", "regions", "fixtures")},
              open(os.path.join(HIST, f"player_odds_gw{gw}.json"), "w"), separators=(",", ":"))
    n = sum(len(x["players"]) for x in out_fx.values())
    print(f"player odds GW{gw}: {len(out_fx)}/{len(gw_fx)} fixtures, {n} players, {len(set(unmatched))} unmatched names, "
          f"{spent} credits used, {left} left")
    if unmatched_teams:
        print("unmatched team names:", sorted(unmatched_teams))


def record_error(msg):
    """Save the failure in odds/players.json (committed by the workflow) so it can be read without the run log."""
    try:
        state = json.load(open(OUT))
    except Exception:
        state = {}
    state["last_error"] = {"at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "message": msg[:500]}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(state, open(OUT, "w"), separators=(",", ":"))
    print("player odds failed:", msg)


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as ex:
        body = ""
        try:
            body = ex.read().decode("utf-8", "ignore")[:300]
        except Exception:
            pass
        record_error(f"HTTP {ex.code} from {ex.url.split('?')[0]}: {body}")
    except Exception as ex:
        import traceback
        record_error(f"{type(ex).__name__}: {ex} | {traceback.format_exc().splitlines()[-3]}")
