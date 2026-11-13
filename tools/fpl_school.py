#!/usr/bin/env python3
"""FPL School team review (FL-147): any team ID in, a squad rating and one suggested move out. Read-only.

  python3 tools/fpl_school.py              # a page on this computer: http://localhost:8765 (Ctrl+C to stop)
  python3 tools/fpl_school.py 123456       # the same review printed in the terminal
  python3 tools/fpl_school.py --data site/data.json 123456   # projections from a local build instead of the site

Why a local page and not a page on the site: FPL's API doesn't allow requests from other websites' pages (no CORS),
so the published site can't load an arbitrary team (that is why "Compare any team" goes through watch.json and a
rebuild). Run here, Python fetches the team from FPL directly. Nothing is saved: no files are written, nothing is
pushed, and the main app stays on your team (FL-016, the app for any team, stays on hold).

The review uses the same projections and the same scoring as the Squad rating on Home (site/js/components/rating.js):
  - rating 0-100 over the rating gameweeks (data.json rating.gws): best XI + captain each week from the team's 15, no
    transfers, against the top-10k average (rating.field: 50) and the best 15 for the team's own money (100), the
    best 15 worked out here with optimise.solve, as build.py does for your team;
  - one suggested move: the single transfer (same position, affordable, at most 3 from a club) that adds most to that
    best XI + captain over the same weeks, as the rating's "weakest links".
Missing / late / ambiguous (each said on the page, never filled in silently):
  - a team ID FPL doesn't know, or no team picked yet -> "no such team" / "no picks yet";
  - FPL or the site not answering -> says which, and nothing else is shown;
  - selling prices: FPL keeps them private, so the team's money is its bank plus its players' current prices (marked
    assumed: their real selling prices can be lower after price rises);
  - a player with no projection in data.json (not in the projected list) -> 0 xP, listed as "not projected";
  - the best-15 solve failing -> rating against the top-10k only, said;
  - no move that adds points -> "keep the squad".
"""
import html
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
API = "https://fantasy.premierleague.com/api"
SITE_DATA = os.environ.get("PAGES_DATA_URL", "https://afg-design.github.io/FPL-Lab/data.json")
MIN = {"GKP": 1, "DEF": 3, "MID": 2, "FWD": 1}
MAX = {"GKP": 1, "DEF": 5, "MID": 5, "FWD": 3}


class ReviewError(Exception):
    """A reason the review can't be shown (said on the page / in the terminal)."""


def fetch_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 fpl-lab"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def load_data(path=None):
    try:
        if path:
            with open(path) as f:
                return json.load(f)
        return fetch_json(SITE_DATA)
    except (OSError, ValueError, urllib.error.URLError) as ex:
        raise ReviewError(f"The projections ({path or SITE_DATA}) couldn't be loaded: {ex}")


def team_picks(team_id, get=fetch_json):
    """(entry, picks response) for the team's latest gameweek. Raises ReviewError with the reason."""
    try:
        entry = get(f"{API}/entry/{team_id}/")
    except urllib.error.HTTPError as ex:
        raise ReviewError(f"FPL has no team {team_id}." if ex.code == 404 else f"FPL didn't answer for team {team_id} ({ex.code}).")
    except (urllib.error.URLError, OSError, ValueError) as ex:
        raise ReviewError(f"FPL didn't answer ({ex}).")
    gw = entry.get("current_event")
    if not gw:
        raise ReviewError(f"Team {team_id} hasn't picked a team for a gameweek yet.")
    try:
        return entry, get(f"{API}/entry/{team_id}/event/{gw}/picks/")
    except (urllib.error.URLError, OSError, ValueError) as ex:
        raise ReviewError(f"FPL didn't give team {team_id}'s GW{gw} picks ({ex}).")


def best_xi_pts(ids, g, xp, pos):
    """Best XI + captain for gameweek g from these players (FPL's formation rules), as the site's bestXI."""
    order = sorted(ids, key=lambda i: -xp(i, g))
    xi, cnt = [], Counter()

    def add(i):
        p = pos[i]
        if i in xi or len(xi) >= 11 or cnt[p] >= MAX[p]:
            return
        cnt[p] += 1
        if len(xi) + 1 + sum(max(0, MIN[k] - cnt[k]) for k in MIN) > 11:
            cnt[p] -= 1
            return
        xi.append(i)
    for p in MIN:
        for i in order:
            if pos[i] == p and cnt[p] < MIN[p]:
                add(i)
    for i in order:
        add(i)
    return sum(xp(i, g) for i in xi) + (max(xp(i, g) for i in xi) if xi else 0)


def review(team_id, D, get=fetch_json, solve=True):
    """The review as a dict (see the module docstring for what each part is and what happens when input is missing)."""
    entry, pk = team_picks(team_id, get)
    P = {p["id"]: p for p in D["players"]}
    R = D.get("rating") or {}
    gws = R.get("gws") or []
    if not gws:
        raise ReviewError("The projections have no rating gameweeks (season over, or no plan this build).")
    ids = [x["element"] for x in pk["picks"]]
    missing = [i for i in ids if i not in P]
    # positions/clubs/prices for players outside data.json: from bootstrap-static
    boot = None
    if missing:
        try:
            boot = get(f"{API}/bootstrap-static/")
        except (urllib.error.URLError, OSError, ValueError) as ex:
            raise ReviewError(f"FPL didn't give the player list ({ex}).")
    pos_of = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
    info = {i: {"name": P[i]["name"], "pos": P[i]["pos"], "team": P[i]["team"], "price": P[i]["price"]} for i in ids if i in P}
    for e in (boot or {}).get("elements", []):
        if e["id"] in missing:
            info[e["id"]] = {"name": e["web_name"], "pos": pos_of[e["element_type"]], "team": e["team"], "price": e["now_cost"] / 10}
    pos = {i: info[i]["pos"] for i in ids}
    xp = lambda i, g: (P.get(i, {}).get("xp") or {}).get(str(g), 0.0)
    bank = (pk.get("entry_history") or {}).get("bank", 0) / 10
    budget = bank + sum(info[i]["price"] for i in ids)
    mine = sum(best_xi_pts(ids, g, xp, pos) for g in gws)
    field = sum(R["field"]) if R.get("field") else None
    best, best_note = None, None
    if solve:
        try:
            import optimise
            opt = {p["id"]: {"pos": p["pos"], "team": p["team"], "price": p["price"], "ok": p.get("ok", True) is not False,
                             "xp": {int(g): v for g, v in (p.get("xp") or {}).items()}} for p in D["players"]}
            wc = optimise.solve(opt, [], {}, budget, 5, gws, hit=0, ft_value=0, max_moves_week=15, freeze_after=1, time_limit=30)
            best = sum(wk["xp"] for wk in wc["weeks"]) if wc else None
            if best is None:
                best_note = "the best 15 for this money couldn't be worked out, so the rating is against the top-10k only"
        except Exception as ex:   # pulp missing or the solver failing: said, the review goes on
            best_note = f"the best 15 couldn't be worked out ({type(ex).__name__}), so the rating is against the top-10k only"
    if field is not None and best is not None and best > field:
        score = 50 + 50 * (mine - field) / (best - field)
    elif best:
        score = 100 * mine / best
    elif field:
        score = 50 * mine / field
    else:
        raise ReviewError("No yardstick: the projections have no top-10k field and the best 15 couldn't be worked out.")
    score = max(0, min(100, round(score)))
    # one suggested move: the transfer that adds most to best XI + captain over the rating weeks
    clubs = Counter(info[i]["team"] for i in ids)
    best_move = None
    for out in ids:
        o = info[out]
        money = bank + o["price"]
        cands = [p for p in D["players"] if p["pos"] == o["pos"] and p["id"] not in ids and p.get("ok", True) is not False
                 and p["price"] <= money + 1e-9 and clubs[p["team"]] - (o["team"] == p["team"]) < 3]
        cands.sort(key=lambda p: -sum((p.get("xp") or {}).get(str(g), 0) for g in gws))
        for p in cands[:12]:
            new = [p["id"] if i == out else i for i in ids]
            gain = sum(best_xi_pts(new, g, xp, {**pos, p["id"]: p["pos"]}) for g in gws) - mine
            if gain > 0.05 and (best_move is None or gain > best_move["gain"]):
                best_move = {"out": o["name"], "out_price": o["price"], "in": p["name"], "in_price": p["price"], "gain": round(gain, 1)}
    word = "Excellent" if score >= 85 else "Strong" if score >= 65 else "Above average" if score >= 50 else "Below average" if score >= 35 else "Needs work"
    return {"team_id": team_id, "team": entry.get("name"), "manager": f"{entry.get('player_first_name', '')} {entry.get('player_last_name', '')}".strip(),
            "gw": pk.get("entry_history", {}).get("event") or entry.get("current_event"), "gws": gws,
            "score": score, "word": word, "mine": round(mine, 1), "field": round(field, 1) if field is not None else None,
            "best": round(best, 1) if best is not None else None, "best_note": best_note,
            "budget": round(budget, 1), "bank": round(bank, 1), "move": best_move,
            "not_projected": [info[i]["name"] for i in ids if i not in P], "built": (D.get("meta") or {}).get("built")}


def as_text(r):
    lines = [f"{r['team']} ({r['manager']}), team {r['team_id']}, picks from GW{r['gw']}",
             f"Rating {r['score']}/100 ({r['word']}): projected {r['mine']} pts over GW{r['gws'][0]}-{r['gws'][-1]}, no transfers"]
    if r["field"] is not None:
        lines.append(f"  top-10k average {r['field']}")
    if r["best"] is not None:
        lines.append(f"  best 15 for £{r['budget']}m (assumed: current prices) {r['best']}")
    if r["best_note"]:
        lines.append(f"  note: {r['best_note']}")
    m = r["move"]
    lines.append(f"One move: {m['out']} (£{m['out_price']}m) -> {m['in']} (£{m['in_price']}m), +{m['gain']} projected pts"
                 if m else "One move: none adds points, keep the squad")
    if r["not_projected"]:
        lines.append(f"Not projected (0 xP): {', '.join(r['not_projected'])}")
    return "\n".join(lines)


PAGE = """<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>FPL School review</title><style>
:root{{--bg:#f6f7f5;--surface:#fff;--text:#14201a;--muted:#5b6b62;--line:#d9e0dc;--accent:#1f7a4d;--on-accent:#fff;--good:#1f7a4d;--bad:#b3261e}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0f1512;--surface:#18201c;--text:#e8efe9;--muted:#9fb0a6;--line:#2b3631;--accent:#4fc28a;--on-accent:#0f1512;--good:#4fc28a;--bad:#f08b84}}}}
body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.5 system-ui,sans-serif}}main{{max-width:640px;margin:0 auto;padding:16px}}
.panel{{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px;margin:12px 0}}h1{{font-size:22px;margin:8px 0}}
form{{display:flex;gap:8px;flex-wrap:wrap}}input{{font:inherit;padding:10px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--text);min-width:0;flex:1 1 160px}}
button{{font:inherit;padding:10px 16px;border:0;border-radius:8px;background:var(--accent);color:var(--on-accent);min-height:44px}}
.score{{font-size:48px;font-weight:700}}.muted{{color:var(--muted)}}.err{{color:var(--bad)}}.move b{{color:var(--good)}}
</style></head><body><main><h1>FPL School review</h1>
<form method="get" action="/"><input name="id" inputmode="numeric" pattern="[0-9]*" placeholder="FPL team ID" aria-label="FPL team ID" value="{tid}"><button type="submit">Review</button></form>
<p class="muted">Read-only: nothing is saved. Projections built {built}.</p>{body}</main></body></html>"""


def as_html(r=None, err=None, tid="", built="–"):
    e = html.escape
    if err:
        body = f'<div class="panel err">{e(err)}</div>'
    elif r:
        m = r["move"]
        notes = [f"Money: £{r['budget']}m (£{r['bank']}m in the bank), with players at their current prices: their real selling "
                 f"prices are private and can be lower (assumed)."]
        if r["best_note"]:
            notes.append(r["best_note"].capitalize() + ".")
        if r["not_projected"]:
            notes.append(f"Not in the projections, counted as 0: {', '.join(map(e, r['not_projected']))}.")
        body = (f'<div class="panel"><h2>{e(r["team"] or "")} <span class="muted">({e(r["manager"])})</span></h2>'
                f'<p class="muted">Their GW{r["gw"]} team, projected over GW{r["gws"][0]}–{r["gws"][-1]} with no transfers.</p>'
                f'<div class="score" aria-label="Rating {r["score"]} out of 100">{r["score"]}<span class="muted" style="font-size:18px">/100 · {e(r["word"])}</span></div>'
                f'<p>Projected {r["mine"]} pts'
                + (f' · top-10k average {r["field"]}' if r["field"] is not None else "")
                + (f' · best 15 for the same money {r["best"]}' if r["best"] is not None else "") + '</p></div>'
                + (f'<div class="panel move"><h2>One move</h2><p>{e(m["out"])} (£{m["out_price"]}m) → {e(m["in"])} (£{m["in_price"]}m): '
                   f'<b>+{m["gain"]}</b> projected pts over those weeks.</p></div>' if m else
                   '<div class="panel move"><h2>One move</h2><p>No single transfer adds points: keep the squad.</p></div>')
                + f'<div class="panel muted">{"<br>".join(notes)}</div>')
    else:
        body = '<div class="panel muted">Enter a team ID: it\'s the number in the address of their Points page on the FPL site.</div>'
    try:   # "13 Nov, 10:38 UTC"
        import datetime as dt
        built = dt.datetime.fromisoformat(built.replace("Z", "+00:00")).strftime("%-d %b, %H:%M UTC") if built else "–"
    except (ValueError, AttributeError):
        pass
    return PAGE.format(tid=e(str(tid)), built=e(built or "–"), body=body)


def serve(D, port=8765):
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            tid = (q.get("id") or [""])[0].strip()
            built = (D.get("meta") or {}).get("built")
            if not tid:
                page = as_html(built=built)
            elif not tid.isdigit():
                page = as_html(err="A team ID is a number.", tid=tid, built=built)
            else:
                try:
                    page = as_html(review(int(tid), D), tid=tid, built=built)
                except ReviewError as ex:
                    page = as_html(err=str(ex), tid=tid, built=built)
            b = page.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def log_message(self, *a):   # quiet: team IDs aren't logged anywhere
            pass
    print(f"FPL School review on http://localhost:{port} (Ctrl+C to stop)")
    HTTPServer(("127.0.0.1", port), H).serve_forever()


if __name__ == "__main__":
    args = sys.argv[1:]
    path = None
    if "--data" in args:
        i = args.index("--data")
        path = args[i + 1]
        del args[i:i + 2]
    try:
        D = load_data(path)
        if args:
            print(as_text(review(int(args[0]), D)))
        else:
            serve(D)
    except ReviewError as ex:
        sys.exit(str(ex))
