"""Rivals page check: every state of My league and The field at seven widths, in dark and light, plus behaviour.

    python3 scripts/rivals_check.py                  # needs site/data.json and site/awards.json (a local build)
    python3 scripts/rivals_check.py --out shots/rivals --shots   # also save a screenshot of every state, width and theme

States (and a long-names copy of final) are made from the real site/data.json by editing a copy in the browser (Playwright route), so the league,
managers and awards are real; only the matchday state is changed:
  final     data.json as built (after a settled gameweek)
  live      the sample's gameweek in play: one rival with no picks (FPL table fallback, *, hit "–"), one with a −4 hit,
            one on a genuine 0
  pre       in play, no match started yet
  stale     live, then a failed "Refresh scores": the scores stay and the failure is said
  mismatch  in play but the live payload is for another gameweek: your live score isn't used
Each state is opened on Standings; final is also opened on Weekly honours, head-to-head and The field.

At each of 320, 390, 768, 1024, 1280, 1440 and 1920px wide, in both themes, it fails on: a JavaScript error, an error
card, the page wider than the window, or a control smaller than 24 x 24 px (WCAG 2.5.8). Behaviour checks (1280px):
league and pinned rival remembered after a reload, a saved league that's gone falls back with a note, keyboard tab
order through the tabs, the honours week selector loading an older settled week, and the scoring labels above.
Missing input fails loudly: no site/data.json or site/awards.json exits 2.
"""
import argparse, functools, http.server, json, socketserver, sys, threading
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
WIDTHS = [320, 390, 768, 1024, 1280, 1440, 1920]
LEAGUE = None   # the smallest league (as the page's own fallback picks), set in main()


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    httpd = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(SITE)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


def variant(d, kind):
    d = json.loads(json.dumps(d))
    C, L = d["crowd"], d.get("live")
    if kind in ("final", "long"):
        if kind == "long":   # long names: the longest FPL allows and then some, unbroken
            lg = next(l for l in C["leagues"] if l["id"] == LEAGUE)
            lg["rows"][1].update(player="Maximilian-Alexander Featherstonehaugh-Wolstenholme", team="Abcdefghijklmnopqrstuvwxyz0123")
            lg["name"] = "The Extremely Long Mini-League Name For Testing"
        return d
    C["in_play"] = True
    if L:
        L.update(gw=C["gw"], finished=False, in_play=kind != "pre")
        for i, f in enumerate(L["fixtures"]):
            f["started"] = kind != "pre" and i < 4
            f["done"] = kind != "pre" and i < 2
    if kind == "mismatch" and L:
        L["gw"] = C["gw"] - 1
    lg = next(l for l in C["leagues"] if l["id"] == LEAGUE)
    others = [r for r in lg["rows"] if not r["me"]]
    if kind != "pre":
        others[0].update(picks=None, live=None, gw_pts=41)        # no picks: FPL table fallback, hit not known
        others[1].update(hits=4)                                   # a hit, shown beside the score
        others[2].update(live=0)                                   # a genuine zero
    return d


def main():
    global LEAGUE
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="layout-shots/rivals")
    ap.add_argument("--shots", action="store_true")
    a = ap.parse_args()
    if not (SITE / "data.json").exists() or not (SITE / "awards.json").exists():
        print("rivals_check: site/data.json or site/awards.json missing; build first"); sys.exit(2)
    data = json.loads((SITE / "data.json").read_text())
    leagues = data["crowd"]["leagues"]
    LEAGUE = sorted([l for l in leagues if l["size"] <= 70] or leagues, key=lambda l: l["size"])[0]["id"]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    httpd, url = serve()
    fails = []

    def open_page(ctx, kind, ls=None, fail_refresh=False):
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(f"uncaught: {e}"))
        page.on("console", lambda m: errs.append(f"console.error: {m.text}") if m.type == "error" and not m.text.startswith("Failed to load resource") else None)
        body = json.dumps(variant(data, kind))
        state = {"n": 0}

        def handle(route):
            state["n"] += 1
            if fail_refresh and state["n"] > 1:
                return route.fulfill(status=503, body="down")
            route.fulfill(status=200, content_type="application/json", body=body)
        page.route("**/data.json*", handle)
        init = {"fpl.view": "rivals", **(ls or {})}
        page.add_init_script("".join(f"localStorage.setItem({k!r}, {json.dumps(json.dumps(v))});" for k, v in init.items()))
        page.goto(url + "#rivals")
        page.wait_for_selector(".view-rivals .rv-tabs", timeout=20000)
        page.wait_for_timeout(250)
        return page, errs

    def layout(page, errs, name, w):
        sw = page.evaluate("document.documentElement.scrollWidth")
        if sw > w:
            fails.append(f"{name}: page {sw}px wide in a {w}px window")
        if page.locator("text=This section couldn't be drawn").count():
            fails.append(f"{name}: error card")
        small = page.evaluate("""() => [...document.querySelectorAll('#app button, #app select, #app a, #app summary, #app input')]
            .filter(e => e.offsetParent && !e.closest('.tablebox th') && !e.closest('p') && !e.closest('.rv-lines li span') && !e.closest('.tablebox td .linkish') && !e.matches('.term'))
            .map(e => [e.getBoundingClientRect(), e.textContent.trim().slice(0, 30)]).filter(([r]) => r.width < 24 || r.height < 24).map(([r, t]) => `${t} ${Math.round(r.width)}x${Math.round(r.height)}`)""")
        if small:
            fails.append(f"{name}: controls under 24px: {small[:4]}")
        for e in errs:
            fails.append(f"{name}: {e}")
        # the standings fit their box: rank, manager, GW points, hit and official total readable without scrolling sideways
        t = page.evaluate("(() => { const b = document.querySelector('.rv-table'); return b ? [b.scrollWidth, b.clientWidth] : null; })()")
        if t and t[0] > t[1] + 1:
            fails.append(f"{name}: standings table needs sideways scrolling ({t[0]}px in {t[1]}px)")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for theme in ("dark", "light"):
            for w in WIDTHS:
                ctx = browser.new_context(viewport={"width": w, "height": 900}, service_workers="block", device_scale_factor=1)
                ctx.add_init_script(f"localStorage.setItem('fpl.theme', JSON.stringify({theme!r})); localStorage.setItem('fpl.theme', {theme!r});")
                for kind in ("final", "long", "live", "pre", "stale", "mismatch"):
                    page, errs = open_page(ctx, kind, {"fpl.league": LEAGUE}, fail_refresh=kind == "stale")
                    if kind == "stale":
                        page.click("[data-rvrefresh]")
                        page.wait_for_selector(".rv-stale", timeout=5000)
                    txt = page.inner_text("#app")   # the Standings state, before any tab is opened
                    screens = [("standings", None)]
                    if kind == "final":
                        screens += [("honours", '[data-ltab="honours"][role="tab"]'), ("h2h", ".rv-table [data-rvh2h]"), ("field", '[data-rtab="field"]')]
                    for scr, click in screens:
                        if click:
                            page.click(f"{click} >> nth=0")
                            page.wait_for_timeout(300)
                        if scr == "honours" and kind == "final":
                            page.wait_for_selector(".aw-grid")
                        if scr == "field":
                            page.evaluate("document.querySelectorAll('.rv-more').forEach(d => d.open = true)")
                        name = f"{kind}-{scr}-{w}-{theme}"
                        layout(page, errs, name, w)
                        if a.shots:
                            page.screenshot(path=str(out / f"{name}.png"), full_page=True)
                        if scr == "h2h":
                            page.click('[data-ltab="standings"] >> nth=0')
                            page.wait_for_timeout(150)
                        if scr == "honours":
                            page.click('[data-ltab="standings"][role="tab"]')
                    # scoring labels (all widths): what each state must say
                    if kind == "live":
                        for want in ("GW%d live" % data["crowd"]["gw"], "Checks every 5 min", "Refresh scores", "Updated"):
                            if want not in txt:
                                fails.append(f"{kind}-{w}-{theme}: missing '{want}'")
                        if not page.locator(".rv-table sup.rv-fb").count():
                            fails.append(f"{kind}-{w}-{theme}: fallback score not marked")
                        if not page.locator('.rv-table .rv-hit .down', has_text="−4").count():
                            fails.append(f"{kind}-{w}-{theme}: hit not shown")
                        if not page.locator('.rv-table .rv-hit [title^="Not known"]').count():
                            fails.append(f"{kind}-{w}-{theme}: unknown hit not shown as a dash")
                        if page.locator(".rv-moment").count():
                            fails.append(f"{kind}-{w}-{theme}: rivalry moment shown during play")
                        order = page.evaluate("[...document.querySelectorAll('.rv-standings, .rv-hero')].map(e => e.className)")
                        if not order or "rv-standings" not in order[0]:
                            fails.append(f"{kind}-{w}-{theme}: table isn't first during play")
                    if kind == "pre" and "Before kick-off" not in txt:
                        fails.append(f"{kind}-{w}-{theme}: pre-match label missing")
                    if kind == "stale" and "Couldn't check for new scores" not in txt:
                        fails.append(f"{kind}-{w}-{theme}: failed refresh not said")
                    if kind == "stale" and not page.locator(".rv-table tbody tr").count():
                        fails.append(f"{kind}-{w}-{theme}: scores cleared after a failed refresh")
                    if kind == "mismatch" and "in progress" not in txt:
                        fails.append(f"{kind}-{w}-{theme}: live payload for another GW not flagged")
                    if kind == "final" and "Final scores" not in txt:
                        fails.append(f"{kind}-{w}-{theme}: final label missing")
                    page.close()
                ctx.close()

        # behaviour (1280px, dark)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900}, service_workers="block")
        page, errs = open_page(ctx, "final")
        other = next(l for l in leagues if l["id"] != LEAGUE)
        page.select_option("#leagueSel", str(other["id"]))
        page.reload(); page.wait_for_selector(".rv-tabs")
        if page.input_value("#leagueSel") != str(other["id"]):
            fails.append("behaviour: chosen league not remembered after reload")
        page.select_option("#leagueSel", str(LEAGUE))
        rival = page.locator(".rv-table [data-rvh2h]").nth(3)
        rname = rival.inner_text()
        rival.click(); page.wait_for_selector("[data-rvpin]")
        page.click("[data-rvpin]")
        page.reload(); page.wait_for_selector(".rv-tabs")
        if "pinned rival" not in page.inner_text(".rv-moment").lower() or rname.split()[0] not in page.inner_text(".rv-proj"):
            fails.append("behaviour: pinned rival not leading after reload")
        page.click(".rv-proj [data-rvh2h]"); page.click('[data-rvpin="0"]')
        if page.locator(".rv-table .pill.warn", has_text="Rival").count():
            fails.append("behaviour: unpin left the rival marker")
        page.close()
        page, errs = open_page(ctx, "final", {"fpl.league": 999999999})
        if "isn't in this update" not in page.inner_text("#app"):
            fails.append("behaviour: missing saved league not said")
        # keyboard: arrow keys move between tabs and select them
        page.focus('[data-rtab="league"]'); page.keyboard.press("ArrowRight")
        if page.evaluate("document.activeElement.dataset.rtab") != "field" or not page.locator("#rvf-h").count():
            fails.append("behaviour: arrow key didn't move to The field tab")
        page.keyboard.press("ArrowLeft")
        page.click('[data-ltab="honours"][role="tab"]'); page.wait_for_selector(".aw-grid")
        page.click('[aria-label="Earlier gameweek"]')
        page.wait_for_function("document.querySelector('#hgwSel') && !document.querySelector('#app').innerText.includes('Loading GW')", timeout=10000)
        txt = page.inner_text("#app")
        if "Rebuilt on" not in txt or page.locator(".aw-card").count() != 8:
            fails.append("behaviour: earlier honours week didn't load with its backfill note")
        if page.locator(".medal").count() and not page.locator(".medal", has_text="gold").count():
            fails.append("behaviour: medal labels missing")
        for e in errs:
            fails.append(f"behaviour: {e}")
        browser.close()
    httpd.shutdown()
    if fails:
        print("\n".join("✗ " + f for f in fails[:80]))
        print(f"\n{len(fails)} problem(s)")
        sys.exit(1)
    print(f"✓ Rivals: 6 states × {len(WIDTHS)} widths × 2 themes, and behaviour checks" + (f"; screenshots in {out}" if a.shots else ""))


if __name__ == "__main__":
    main()
